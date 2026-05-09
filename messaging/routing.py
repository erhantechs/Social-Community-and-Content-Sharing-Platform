"""WebSocket URL routes for the messaging app."""
from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/messages/<int:conv_id>/", consumers.ConversationConsumer.as_asgi()),
]
