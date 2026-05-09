"""2FA setup, verify-on-login, disable views."""
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import TwoFactorSecret
from .two_factor import (
    clear_pending_login,
    generate_backup_codes,
    generate_secret,
    peek_pending_login,
    pop_pending_login,
    provisioning_uri,
    qr_data_uri,
    verify_token,
)

User = get_user_model()


@login_required
@require_http_methods(["GET", "POST"])
def two_factor_setup(request):
    """Begin enrolling in 2FA — show QR + verify the first code."""
    user = request.user
    if user.profile.two_factor_enabled:
        messages.info(request, "Two-factor authentication is already enabled.")
        return redirect("accounts:two_factor_status")

    # Reuse the in-progress secret across the GET → POST cycle so the QR
    # code matches the one the user already scanned.
    secret = request.session.get("tfa_setup_secret")
    if not secret:
        secret = generate_secret()
        request.session["tfa_setup_secret"] = secret

    if request.method == "POST":
        token = request.POST.get("token", "")
        if verify_token(secret, token):
            backup_codes = generate_backup_codes()
            tfs, _ = TwoFactorSecret.objects.update_or_create(
                user=user,
                defaults={
                    "secret": secret,
                    "backup_codes": "\n".join(backup_codes),
                },
            )
            user.profile.two_factor_enabled = True
            user.profile.save(update_fields=["two_factor_enabled"])
            request.session.pop("tfa_setup_secret", None)
            request.session["tfa_just_enrolled_codes"] = backup_codes
            messages.success(request, "Two-factor authentication enabled.")
            return redirect("accounts:two_factor_backup_codes")
        messages.error(request, "Code didn't match. Try again with a fresh one.")

    uri = provisioning_uri(secret, user.username)
    return render(request, "accounts/two_factor_setup.html", {
        "secret": secret,
        "qr_data_uri": qr_data_uri(uri),
        "manual_entry": secret,
    })


@login_required
def two_factor_backup_codes(request):
    """One-shot view of the freshly-issued backup codes (only after enrolling).

    Codes are not shown again after this — users must save them now.
    """
    codes = request.session.pop("tfa_just_enrolled_codes", None)
    if not codes:
        return redirect("accounts:two_factor_status")
    return render(request, "accounts/two_factor_backup_codes.html", {"codes": codes})


@login_required
def two_factor_status(request):
    """Settings page for 2FA — shows enabled/disabled + actions."""
    user = request.user
    enabled = user.profile.two_factor_enabled
    secret_obj = TwoFactorSecret.objects.filter(user=user).first()
    return render(request, "accounts/two_factor_status.html", {
        "enabled": enabled,
        "remaining_backup_codes": (
            len(secret_obj.get_backup_codes()) if secret_obj else 0
        ),
    })


@login_required
@require_http_methods(["GET", "POST"])
def two_factor_disable(request):
    """Disable 2FA — confirms by asking for a current TOTP code or backup code.

    Done via a confirmation form to prevent accidental disabling.
    """
    user = request.user
    if not user.profile.two_factor_enabled:
        return redirect("accounts:two_factor_status")

    if request.method == "POST":
        code = request.POST.get("code", "")
        secret_obj = TwoFactorSecret.objects.filter(user=user).first()
        ok = False
        if secret_obj:
            if verify_token(secret_obj.secret, code):
                ok = True
            elif secret_obj.consume_backup_code(code):
                ok = True
        if ok:
            TwoFactorSecret.objects.filter(user=user).delete()
            user.profile.two_factor_enabled = False
            user.profile.save(update_fields=["two_factor_enabled"])
            messages.success(request, "Two-factor authentication disabled.")
            return redirect("accounts:two_factor_status")
        messages.error(request, "Invalid code.")

    return render(request, "accounts/two_factor_disable.html")


@login_required
def two_factor_regenerate_codes(request):
    """Issue a fresh batch of backup codes (invalidates old ones)."""
    user = request.user
    if not user.profile.two_factor_enabled:
        return redirect("accounts:two_factor_status")
    if request.method == "POST":
        codes = generate_backup_codes()
        TwoFactorSecret.objects.filter(user=user).update(
            backup_codes="\n".join(codes),
        )
        request.session["tfa_just_enrolled_codes"] = codes
        messages.success(request, "New backup codes generated.")
        return redirect("accounts:two_factor_backup_codes")
    return render(request, "accounts/two_factor_regenerate.html")


@require_http_methods(["GET", "POST"])
def two_factor_verify(request):
    """The post-login challenge: user is half-authenticated and must provide a TOTP code."""
    user_id = peek_pending_login(request.session)
    if not user_id:
        return redirect("accounts:login")

    user = User.objects.filter(pk=user_id).first()
    if not user:
        clear_pending_login(request.session)
        return redirect("accounts:login")

    if request.method == "POST":
        code = request.POST.get("code", "")
        secret_obj = TwoFactorSecret.objects.filter(user=user).first()
        ok = False
        if secret_obj:
            if verify_token(secret_obj.secret, code):
                ok = True
            elif secret_obj.consume_backup_code(code):
                ok = True
        if ok:
            pop_pending_login(request.session)
            secret_obj.last_used_at = timezone.now()
            secret_obj.save(update_fields=["last_used_at"])
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            next_url = request.session.pop("tfa_next_url", "")
            return HttpResponseRedirect(next_url or reverse("posts:feed"))
        messages.error(request, "Invalid code.")

    return render(request, "accounts/two_factor_verify.html", {"username": user.username})
