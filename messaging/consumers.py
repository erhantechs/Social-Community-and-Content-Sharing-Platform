"""WebSocket consumer for live direct-message conversations.

Each conversation is a Channels group named `dm_<conv_id>`. When a user
sends a message:
    1. The consumer validates the user is a participant.
    2. Persists the message to the DB.
    3. Broadcasts the rendered message to all participants of the group.

Typing indicator is also broadcast (not persisted) for a polished feel.
"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Conversation, Message


class ConversationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.conv_id = int(self.scope["url_route"]["kwargs"]["conv_id"])

        # Reject anonymous or non-participant connections cleanly.
        if not self.user.is_authenticated:
            await self.close(code=4401)
            return
        is_member = await self._is_participant(self.conv_id, self.user.id)
        if not is_member:
            await self.close(code=4403)
            return

        self.group_name = f"dm_{self.conv_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        if action == "send":
            body = (content.get("body") or "").strip()
            if not body:
                return
            msg = await self._save_message(self.conv_id, self.user.id, body[:2000])
            payload = {
                "type": "chat.message",
                "id": msg.id,
                "sender_id": self.user.id,
                "sender_username": self.user.username,
                "body": msg.body,
                "created_at": msg.created_at.isoformat(),
            }
            await self.channel_layer.group_send(self.group_name, payload)

        elif action == "typing":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.typing",
                    "sender_id": self.user.id,
                    "sender_username": self.user.username,
                },
            )

        elif action == "read":
            # Mark all incoming messages as read (one DB call).
            await self._mark_read(self.conv_id, self.user.id)
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "chat.read", "sender_id": self.user.id},
            )

    # ---- Group event handlers ---------------------------------------------

    async def chat_message(self, event):
        # Don't echo a sender's own message back as "new" — they already added
        # it optimistically in the UI.
        if event["sender_id"] == self.user.id:
            event = {**event, "self_echo": True}
        await self.send_json(event)

    async def chat_typing(self, event):
        if event["sender_id"] == self.user.id:
            return
        await self.send_json(event)

    async def chat_read(self, event):
        await self.send_json(event)

    # ---- DB helpers (sync ORM, called from async via decorator) ----------

    @database_sync_to_async
    def _is_participant(self, conv_id, user_id):
        from django.db.models import Q
        # Accept both legacy DMs (user_a/user_b) and the new M2M `participants`.
        return Conversation.objects.filter(
            Q(user_a_id=user_id) | Q(user_b_id=user_id) | Q(participants__id=user_id),
            id=conv_id,
        ).exists()

    @database_sync_to_async
    def _save_message(self, conv_id, sender_id, body):
        return Message.objects.create(
            conversation_id=conv_id, sender_id=sender_id, body=body,
        )

    @database_sync_to_async
    def _mark_read(self, conv_id, user_id):
        Message.objects.filter(conversation_id=conv_id, is_read=False).exclude(
            sender_id=user_id,
        ).update(is_read=True)
