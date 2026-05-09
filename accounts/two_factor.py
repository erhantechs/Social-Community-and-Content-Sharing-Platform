"""2FA / TOTP helpers.

Wraps `pyotp` so views don't import the lib directly. Also handles the
QR-code data URI used on the setup page.
"""
import base64
import io
import secrets
from datetime import timedelta

import pyotp
import qrcode
from django.utils import timezone


ISSUER = "SocialHub"


def generate_secret() -> str:
    """A new random base32 secret for a user enabling 2FA."""
    return pyotp.random_base32()


def verify_token(secret: str, token: str, valid_window: int = 1) -> bool:
    """Validate a 6-digit code. `valid_window` allows ±30s of clock drift."""
    if not secret or not token:
        return False
    token = (token or "").strip().replace(" ", "")
    if not token.isdigit() or len(token) != 6:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=valid_window)


def provisioning_uri(secret: str, username: str) -> str:
    """otpauth:// URI suitable for embedding in a QR code."""
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=ISSUER)


def qr_data_uri(uri: str) -> str:
    """Render the otpauth URI as a base64 PNG data URI."""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def generate_backup_codes(n: int = 8, length: int = 10) -> list[str]:
    """Generate `n` one-time backup codes (alphanumeric, uppercase)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1 to avoid confusion
    return [
        "".join(secrets.choice(alphabet) for _ in range(length))
        for _ in range(n)
    ]


# ----- Pre-2FA login session token ------------------------------------------

PENDING_KEY = "tfa_pending_user_id"
PENDING_TS_KEY = "tfa_pending_ts"
PENDING_TTL = timedelta(minutes=5)


def stash_pending_login(session, user_id: int) -> None:
    session[PENDING_KEY] = user_id
    session[PENDING_TS_KEY] = timezone.now().isoformat()


def pop_pending_login(session) -> int | None:
    user_id = session.pop(PENDING_KEY, None)
    ts_str = session.pop(PENDING_TS_KEY, None)
    if not user_id or not ts_str:
        return None
    try:
        ts = timezone.datetime.fromisoformat(ts_str)
    except Exception:
        return None
    if timezone.now() - ts > PENDING_TTL:
        return None
    return int(user_id)


def peek_pending_login(session) -> int | None:
    """Read without consuming, used to render the verify page."""
    user_id = session.get(PENDING_KEY)
    ts_str = session.get(PENDING_TS_KEY)
    if not user_id or not ts_str:
        return None
    try:
        ts = timezone.datetime.fromisoformat(ts_str)
    except Exception:
        return None
    if timezone.now() - ts > PENDING_TTL:
        return None
    return int(user_id)


def clear_pending_login(session) -> None:
    session.pop(PENDING_KEY, None)
    session.pop(PENDING_TS_KEY, None)
