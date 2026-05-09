"""Direct messaging — supports both 1-to-1 DMs and N-person group chats.

Historical note: this model started as a strict 1-to-1 conversation. To add
group chats, we kept user_a / user_b for backwards compat (still used by DMs)
and added a `participants` M2M alongside `is_group` / `name` / `created_by`.
For DMs, both user_a/user_b AND participants are populated. For group chats,
user_a/user_b are NULL and `participants` carries the membership.
"""
from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """A direct conversation. 1-to-1 by default; set `is_group=True` for groups."""

    user_a = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="conversations_as_a",
        null=True, blank=True,
    )
    user_b = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="conversations_as_b",
        null=True, blank=True,
    )
    is_group = models.BooleanField(default=False)
    name = models.CharField(max_length=80, blank=True)
    cover = models.ImageField(upload_to="messaging/covers/", blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_conversations",
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="conversations",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        if self.is_group:
            return f"Group: {self.name or f'#{self.pk}'}"
        return f"Conversation {self.user_a_id}↔{self.user_b_id}"

    @classmethod
    def between(cls, u1, u2):
        """Return the canonical 1-to-1 Conversation for two users (creating if missing).

        Result is normalized so (u1, u2) and (u2, u1) yield the same row.
        Also ensures both users are in the `participants` M2M.
        """
        if u1.id == u2.id:
            raise ValueError("Cannot have a conversation with yourself.")
        a, b = (u1, u2) if u1.id < u2.id else (u2, u1)
        conv, created = cls.objects.get_or_create(
            user_a=a, user_b=b, is_group=False,
        )
        # Sync the M2M for new convs (and for legacy convs that pre-date M2M).
        if created or conv.participants.count() < 2:
            conv.participants.set([a, b])
        return conv

    @classmethod
    def create_group(cls, *, creator, name, members):
        """Create a group conversation. `members` is an iterable of User instances
        (creator will be added automatically if not present)."""
        members = list({m for m in members if m and m.id != creator.id}) + [creator]
        conv = cls.objects.create(
            is_group=True,
            name=(name or "").strip()[:80],
            created_by=creator,
        )
        conv.participants.set(members)
        return conv

    def other(self, user):
        """For a 1-to-1, the partner. For a group, raises ValueError."""
        if self.is_group:
            raise ValueError("Group conversations have no single 'other' user.")
        return self.user_b if user.id == self.user_a_id else self.user_a

    def is_participant(self, user):
        if not user or not user.is_authenticated:
            return False
        if not self.is_group:
            return user.id in (self.user_a_id, self.user_b_id)
        return self.participants.filter(pk=user.id).exists()

    @property
    def display_name(self):
        if self.is_group:
            return self.name or f"Group #{self.pk}"
        return ""


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
