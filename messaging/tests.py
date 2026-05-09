from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .models import Conversation, Message

User = get_user_model()


class WebSocketConsumerTests(TransactionTestCase):
    """Smoke test: connect, send, receive across two participants."""

    async def test_two_participants_can_chat_live(self):
        from asgiref.sync import sync_to_async
        from channels.testing import WebsocketCommunicator

        from socialhub.asgi import application

        alice = await sync_to_async(User.objects.create_user)(
            username="alice_ws", password="ComplexPass!234",
        )
        bob = await sync_to_async(User.objects.create_user)(
            username="bob_ws", password="ComplexPass!234",
        )
        conv = await sync_to_async(Conversation.between)(alice, bob)

        # Alice connects.
        a = WebsocketCommunicator(application, f"/ws/messages/{conv.id}/")
        a.scope["user"] = alice
        a.scope["url_route"] = {"kwargs": {"conv_id": conv.id}}
        connected_a, _ = await a.connect()
        assert connected_a

        # Bob connects.
        b = WebsocketCommunicator(application, f"/ws/messages/{conv.id}/")
        b.scope["user"] = bob
        b.scope["url_route"] = {"kwargs": {"conv_id": conv.id}}
        connected_b, _ = await b.connect()
        assert connected_b

        # Alice sends; Bob should receive a chat.message event.
        await a.send_json_to({"action": "send", "body": "hello bob"})
        evt = await b.receive_json_from(timeout=2)
        assert evt["type"] == "chat.message"
        assert evt["body"] == "hello bob"
        assert evt["sender_username"] == "alice_ws"

        await a.disconnect()
        await b.disconnect()


class ConversationModelTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="x")
        self.bob = User.objects.create_user(username="bob", password="x")

    def test_between_normalizes_pair(self):
        c1 = Conversation.between(self.alice, self.bob)
        c2 = Conversation.between(self.bob, self.alice)
        self.assertEqual(c1.id, c2.id)

    def test_cannot_self_chat(self):
        with self.assertRaises(ValueError):
            Conversation.between(self.alice, self.alice)


class MessagingViewTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.client.login(username="alice", password="ComplexPass!234")

    def test_open_creates_conversation(self):
        resp = self.client.get(reverse("messaging:open_with", args=["bob"]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_send_message(self):
        conv = Conversation.between(self.alice, self.bob)
        resp = self.client.post(reverse("messaging:thread", args=[conv.pk]),
                                {"body": "Hi Bob"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Message.objects.first().body, "Hi Bob")

    def test_third_party_cannot_view_thread(self):
        carol = User.objects.create_user(username="carol", password="ComplexPass!234")
        conv = Conversation.between(self.alice, self.bob)
        self.client.login(username="carol", password="ComplexPass!234")
        resp = self.client.get(reverse("messaging:thread", args=[conv.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_inbox_lists_conversations(self):
        Conversation.between(self.alice, self.bob)
        resp = self.client.get(reverse("messaging:inbox"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "bob")

    def test_opening_thread_marks_incoming_read(self):
        conv = Conversation.between(self.alice, self.bob)
        Message.objects.create(conversation=conv, sender=self.bob, body="hi")
        self.client.get(reverse("messaging:thread", args=[conv.pk]))
        self.assertTrue(Message.objects.first().is_read)
