"""Tiny cache-backed rate limiter.

Used on the login view: 10 failed attempts per IP in 5 minutes triggers a
temporary block. Successful logins are not counted.
"""
from django.core.cache import cache
from django.http import HttpResponse

LOGIN_LIMIT = 10
LOGIN_WINDOW = 5 * 60   # seconds


def _client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def is_login_blocked(request):
    key = f"login-fails:{_client_ip(request)}"
    return (cache.get(key) or 0) >= LOGIN_LIMIT


def record_login_failure(request):
    key = f"login-fails:{_client_ip(request)}"
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, LOGIN_WINDOW)


def reset_login_failures(request):
    cache.delete(f"login-fails:{_client_ip(request)}")


def too_many_attempts_response():
    return HttpResponse(
        "Too many login attempts. Please try again in a few minutes.",
        status=429,
    )
