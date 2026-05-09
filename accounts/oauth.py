"""Lightweight OAuth2 social login for Google + GitHub.

Configure via env vars:
    GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET
    GITHUB_OAUTH_CLIENT_ID, GITHUB_OAUTH_CLIENT_SECRET

Set the callback URL in the provider's console to:
    https://yourdomain/accounts/oauth/<provider>/callback/

If credentials are missing the corresponding "Continue with X" buttons
won't appear and the routes return 404. This keeps the deploy safe in dev.
"""
import secrets as _secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import SocialAccount

User = get_user_model()

# ----- Provider config ----------------------------------------------------

PROVIDERS = {
    "google": {
        "client_id_setting": "GOOGLE_OAUTH_CLIENT_ID",
        "client_secret_setting": "GOOGLE_OAUTH_CLIENT_SECRET",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope": "openid email profile",
    },
    "github": {
        "client_id_setting": "GITHUB_OAUTH_CLIENT_ID",
        "client_secret_setting": "GITHUB_OAUTH_CLIENT_SECRET",
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scope": "read:user user:email",
    },
}


def is_configured(provider: str) -> bool:
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return False
    cid = getattr(settings, cfg["client_id_setting"], "")
    csec = getattr(settings, cfg["client_secret_setting"], "")
    return bool(cid and csec)


def _client_id(provider):
    return getattr(settings, PROVIDERS[provider]["client_id_setting"], "")


def _client_secret(provider):
    return getattr(settings, PROVIDERS[provider]["client_secret_setting"], "")


def _redirect_uri(request, provider):
    return request.build_absolute_uri(
        reverse("accounts:oauth_callback", kwargs={"provider": provider})
    )


# ----- Views --------------------------------------------------------------

def oauth_start(request, provider):
    """Send the user to the provider's authorization page."""
    cfg = PROVIDERS.get(provider)
    if not cfg or not is_configured(provider):
        raise Http404("Provider not configured.")
    state = _secrets.token_urlsafe(24)
    request.session[f"oauth_state_{provider}"] = state
    request.session[f"oauth_next_{provider}"] = (
        request.GET.get("next") or reverse("posts:feed")
    )
    params = {
        "client_id": _client_id(provider),
        "redirect_uri": _redirect_uri(request, provider),
        "response_type": "code",
        "scope": cfg["scope"],
        "state": state,
    }
    return HttpResponseRedirect(f"{cfg['auth_url']}?{urlencode(params)}")


def oauth_callback(request, provider):
    """Handle the redirect from the provider after the user authorizes."""
    cfg = PROVIDERS.get(provider)
    if not cfg or not is_configured(provider):
        raise Http404("Provider not configured.")

    error = request.GET.get("error")
    if error:
        messages.error(request, f"Sign-in cancelled: {error}")
        return redirect("accounts:login")

    code = request.GET.get("code")
    state = request.GET.get("state")
    expected = request.session.pop(f"oauth_state_{provider}", None)
    if not code or not state or state != expected:
        messages.error(request, "Invalid OAuth state — please try again.")
        return redirect("accounts:login")

    # Exchange code for an access token.
    headers = {"Accept": "application/json"}
    token_resp = requests.post(
        cfg["token_url"],
        data={
            "code": code,
            "client_id": _client_id(provider),
            "client_secret": _client_secret(provider),
            "redirect_uri": _redirect_uri(request, provider),
            "grant_type": "authorization_code",
        },
        headers=headers,
        timeout=10,
    )
    if not token_resp.ok:
        messages.error(request, "Could not complete sign-in. Try again.")
        return redirect("accounts:login")
    payload = token_resp.json()
    access_token = payload.get("access_token")
    if not access_token:
        messages.error(request, "Provider didn't return an access token.")
        return redirect("accounts:login")

    # Fetch the user profile.
    user_resp = requests.get(
        cfg["userinfo_url"],
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        timeout=10,
    )
    if not user_resp.ok:
        messages.error(request, "Couldn't fetch your profile from the provider.")
        return redirect("accounts:login")
    info = user_resp.json()

    # Normalize across providers.
    if provider == "google":
        provider_uid = str(info.get("sub") or "")
        email = info.get("email") or ""
        username_seed = (info.get("email") or "").split("@", 1)[0] or info.get("name", "")
    else:  # github
        provider_uid = str(info.get("id") or "")
        email = info.get("email") or ""
        username_seed = info.get("login") or info.get("name") or ""
        # GitHub: email may be private — fall back to /user/emails
        if not email:
            try:
                emails_resp = requests.get(
                    "https://api.github.com/user/emails",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                if emails_resp.ok:
                    primary = next(
                        (e for e in emails_resp.json() if e.get("primary")), None,
                    )
                    if primary:
                        email = primary.get("email", "")
            except requests.RequestException:
                pass

    if not provider_uid:
        messages.error(request, "Provider didn't return a stable user ID.")
        return redirect("accounts:login")

    # Linking flow: existing logged-in user → link to their account.
    if request.user.is_authenticated:
        existing = SocialAccount.objects.filter(
            provider=provider, provider_uid=provider_uid,
        ).first()
        if existing and existing.user_id != request.user.id:
            messages.error(request, "That account is already linked to another user.")
            return redirect("accounts:settings")
        SocialAccount.objects.update_or_create(
            provider=provider, provider_uid=provider_uid,
            defaults={"user": request.user, "email": email, "extra_data": info},
        )
        messages.success(request, f"{cfg['client_id_setting'].split('_')[0].title()} linked.")
        return redirect("accounts:settings")

    # Sign-in flow: find or create.
    sa = SocialAccount.objects.filter(
        provider=provider, provider_uid=provider_uid,
    ).select_related("user").first()
    if sa:
        user = sa.user
        sa.email = email or sa.email
        sa.extra_data = info
        sa.save(update_fields=["email", "extra_data"])
    else:
        # Try to match an existing user by email (only auto-link for verified
        # providers — Google emails are verified, GitHub primary emails are too).
        user = User.objects.filter(email=email).first() if email else None
        if user is None:
            user = _create_user_from_oauth(username_seed, email, info)
        SocialAccount.objects.create(
            user=user, provider=provider, provider_uid=provider_uid,
            email=email, extra_data=info,
        )

    # OAuth-verified emails count as verified locally.
    if email and not user.profile.email_verified:
        user.profile.email_verified = True
        user.profile.save(update_fields=["email_verified"])

    # If 2FA is enabled, route through the verify flow just like password login.
    if user.profile.two_factor_enabled:
        from .two_factor import stash_pending_login
        stash_pending_login(request.session, user.pk)
        request.session["tfa_next_url"] = (
            request.session.pop(f"oauth_next_{provider}", "")
            or reverse("posts:feed")
        )
        return redirect("accounts:two_factor_verify")

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    next_url = request.session.pop(f"oauth_next_{provider}", "")
    return HttpResponseRedirect(next_url or reverse("posts:feed"))


def _create_user_from_oauth(username_seed, email, info):
    """Mint a new local user from OAuth claims."""
    base = "".join(c for c in (username_seed or "user").lower() if c.isalnum() or c in "_-")[:24] or "user"
    username = base
    n = 2
    while User.objects.filter(username=username).exists():
        username = f"{base}{n}"[:30]
        n += 1
    user = User.objects.create_user(
        username=username, email=email or "",
        first_name=info.get("given_name") or info.get("name", "").split(" ", 1)[0][:30] or "",
        last_name=info.get("family_name") or "".join(info.get("name", "").split(" ")[1:])[:30] or "",
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    # Profile is auto-created by the signal; nothing else to do here.
    return user
