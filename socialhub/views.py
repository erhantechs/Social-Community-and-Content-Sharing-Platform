"""Project-level error handlers and infrastructure endpoints."""
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache


def handler404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def handler500(request):
    return render(request, "errors/500.html", status=500)


@never_cache
def healthz(request):
    """Liveness + readiness probe for Render / Kubernetes / uptime monitors.

    Returns 200 with {"status": "ok"} when the database and cache are reachable,
    503 with details when either is not. Designed to be cheap (single SELECT 1).
    """
    checks = {"database": "ok", "cache": "ok"}
    healthy = True

    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception as e:
        checks["database"] = f"error: {e.__class__.__name__}"
        healthy = False

    try:
        cache.set("healthz:ping", "1", 5)
        if cache.get("healthz:ping") != "1":
            checks["cache"] = "miss"
            # Cache miss isn't fatal — local-mem cache works fine, but we surface it.
    except Exception as e:
        checks["cache"] = f"error: {e.__class__.__name__}"
        healthy = False

    return JsonResponse(
        {"status": "ok" if healthy else "unhealthy", **checks},
        status=200 if healthy else 503,
    )


def robots_txt(request):
    """Tell crawlers what's public, what's not, and where the sitemap is."""
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    body = (
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /accounts/\n"
        "Disallow: /messages/\n"
        "Disallow: /notifications/\n"
        "Disallow: /api/\n"
        "Allow: /\n"
        f"\nSitemap: {sitemap_url}\n"
    )
    return HttpResponse(body, content_type="text/plain")
