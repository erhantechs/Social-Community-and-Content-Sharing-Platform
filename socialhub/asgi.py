"""ASGI entry point — handles HTTP and WebSocket traffic.

Channels' `ProtocolTypeRouter` routes by URL scheme. HTTP traffic is
delegated straight to Django; WebSocket traffic is auth'd via the session
cookie middleware and then dispatched to the WebSocket URL routes in
`messaging/routing.py`.
"""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "socialhub.settings")
django.setup()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

from messaging.routing import websocket_urlpatterns  # noqa: E402

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
