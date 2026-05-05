"""Project-level URL routing."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", views.healthz, name="healthz"),
    path("", RedirectView.as_view(pattern_name="posts:feed", permanent=False)),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("posts/", include("posts.urls", namespace="posts")),
    path("notifications/", include("notifications.urls", namespace="notifications")),
    path("messages/", include("messaging.urls", namespace="messaging")),
    path("api/", include("api.urls", namespace="api")),
]

# Custom error handlers
handler404 = "socialhub.views.handler404"
handler500 = "socialhub.views.handler500"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
