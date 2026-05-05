"""1-to-1 direct messaging."""
from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """A direct conversation between exactly two users.

    Stored unordered: a (user_a, user_b) pair always normalizes to
    (lower-pk, higher-pk) so we never end up with two rows for the same
    conversation.
    """

    user_a = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="conversations_as_a",
    )
    user_b = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="conversations_as_b",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user_a", "user_b"], name="unique_conv_pair"),
            models.CheckConstraint(
                check=models.Q(user_a__lt=models.F("user_b")),
                name="conv_user_a_lt_user_b",
            ),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation {self.user_a_id}↔{self.user_b_id}"

    @classmethod
    def between(cls, u1, u2):
        """Return the canonical Conversation for two users (creating if missing)."""
        if u1.id == u2.id:
            raise ValueError("Cannot have a conversation with yourself.")
        a, b = (u1, u2) if u1.id < u2.id else (u2, u1)
        conv, _ = cls.objects.get_or_create(user_a=a, user_b=b)
        return conv

    def other(self, user):
        return self.user_b if user.id == self.user_a_id else self.user_a


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "-created_at"]),
        ]

    def __str__(self):
        return f"Msg #{self.pk} from {self.sender_id}"
