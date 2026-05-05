from django.conf import settings
from django.db import models


class Notification(models.Model):
    LIKE = "like"
    COMMENT = "comment"
    FOLLOW = "follow"
    MENTION = "mention"
    MESSAGE = "message"
    VERB_CHOICES = [
        (LIKE, "liked your post"),
        (COMMENT, "commented on your post"),
        (FOLLOW, "started following you"),
        (MENTION, "mentioned you"),
        (MESSAGE, "sent you a message"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="actions",
    )
    verb = models.CharField(max_length=20, choices=VERB_CHOICES)
    post = models.ForeignKey(
        "posts.Post",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.actor} {self.get_verb_display()} → {self.recipient}"

    def message(self):
        return self.get_verb_display()
