"""Content models: Post, PostImage, Comment, Like, Story."""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Post(models.Model):
    """A user's post — text plus optional cover image plus extra gallery images."""

    PUBLIC = "public"
    FRIENDS = "friends"
    PRIVATE = "private"
    VISIBILITY_CHOICES = [
        (PUBLIC, "Public"),
        (FRIENDS, "Friends only"),
        (PRIVATE, "Private"),
    ]

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    body = models.TextField(max_length=2000)
    image = models.ImageField(upload_to="posts/%Y/%m/", blank=True, null=True)
    location = models.CharField(max_length=120, blank=True)
    visibility = models.CharField(
        max_length=10, choices=VISIBILITY_CHOICES, default=PUBLIC
    )
    interests = models.ManyToManyField(
        "accounts.Interest", blank=True, related_name="posts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["author", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.author.username}: {self.body[:40]}"

    def get_absolute_url(self):
        return reverse("posts:detail", kwargs={"pk": self.pk})

    @property
    def likes_count(self):
        return self.likes.count()

    @property
    def comments_count(self):
        return self.comments.count()

    def is_liked_by(self, user):
        if not user.is_authenticated:
            return False
        return self.likes.filter(user=user).exists()


class PostImage(models.Model):
    """Additional gallery images on a post (e.g. the 3-image collage in the design)."""

    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="extra_images"
    )
    image = models.ImageField(upload_to="posts/%Y/%m/")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Image #{self.order} for post {self.post_id}"


class Comment(models.Model):
    """A comment on a post — supports one level of reply via `parent`."""

    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="replies",
        null=True, blank=True,
    )
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author.username} on post #{self.post_id}"

    @property
    def is_reply(self):
        return self.parent_id is not None

    @property
    def likes_count(self):
        return self.comment_likes.count()

    def is_liked_by(self, user):
        if not user.is_authenticated:
            return False
        return self.comment_likes.filter(user=user).exists()


class CommentLike(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comment_likes",
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="comment_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "comment"],
                name="unique_comment_like",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} likes comment #{self.comment_id}"


class Like(models.Model):
    """A like on a post — one row per (user, post)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="likes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"], name="unique_like_per_user_per_post"
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} likes post #{self.post_id}"


class Bookmark(models.Model):
    """Saved-for-later marker. One row per (user, post)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="bookmarks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="unique_bookmark"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} bookmarks post #{self.post_id}"


def _story_default_expiry():
    return timezone.now() + timedelta(hours=24)


class Story(models.Model):
    """24-hour ephemeral story (image + optional caption)."""

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="stories",
    )
    image = models.ImageField(upload_to="stories/%Y/%m/")
    caption = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_story_default_expiry)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Stories"

    def __str__(self):
        return f"Story by {self.author.username}"

    @property
    def is_active(self):
        return self.expires_at > timezone.now()

    @classmethod
    def active(cls):
        return cls.objects.filter(expires_at__gt=timezone.now())
