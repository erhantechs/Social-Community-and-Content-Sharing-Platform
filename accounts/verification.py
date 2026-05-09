"""Email verification — token-based, one-shot links.

Uses Django's built-in `PasswordResetTokenGenerator` machinery (with a
distinct hash purpose) so we never store tokens in the DB. The token is
derived from the user's pk + verified flag + last_login, so it auto-expires
once the user is verified.
"""
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Distinct salt so verification tokens can't be reused as password-reset tokens."""

    key_salt = "accounts.email_verification.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        # Hash flips when email_verified does → consumed tokens stop working.
        verified = getattr(user.profile, "email_verified", False) if hasattr(user, "profile") else False
        return f"{user.pk}{user.email}{verified}{timestamp}"


verification_token = EmailVerificationTokenGenerator()


def send_verification_email(request, user):
    """Send a one-time verification link to the user's email address."""
    if not user.email:
        return False
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = verification_token.make_token(user)
    path = reverse("accounts:verify_email", kwargs={"uidb64": uidb64, "token": token})
    verify_url = request.build_absolute_uri(path)

    subject = "Verify your SocialHub email"
    body = render_to_string("accounts/email_verification.txt", {
        "user": user,
        "verify_url": verify_url,
    })
    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=True,
    )
    return True


def consume_token(uidb64, token):
    """Return the User if `(uidb64, token)` is a valid, fresh verification
    pair, else None. Caller is responsible for setting `email_verified=True`.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
    if not verification_token.check_token(user, token):
        return None
    return user
