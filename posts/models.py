"""Content models: Post, PostImage, Comment, Like, Story, Hashtag, Poll."""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


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
    hashtags = models.ManyToManyField(
        "Hashtag", blank=True, related_name="posts"
    )
    community = models.ForeignKey(
        "communities.Community",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="posts",
    )
    # When set, this post quotes (or pure-reposts) another. If `body` is empty
    # and `quoted_post` is set, treat it as a "boost" / retweet — display as
    # "X reposted Y". Otherwise show the body above the quoted card.
    quoted_post = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="quotes",
    )
    pinned_at = models.DateTimeField(null=True, blank=True)
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

    def reaction_of(self, user):
        """Emoji code the user reacted with, or None."""
        if not user.is_authenticated:
            return None
        like = self.likes.filter(user=user).only("emoji").first()
        return like.emoji if like else None

    def reaction_breakdown(self, top=3):
        """Top emoji reactions on this post as [(emoji, char, count), ...]."""
        from django.db.models import Count as _C
        rows = (
            self.likes.values("emoji")
            .annotate(c=_C("emoji"))
            .order_by("-c")[:top]
        )
        char_map = dict(Like.EMOJI_CHOICES)
        return [(r["emoji"], char_map.get(r["emoji"], "❤️"), r["c"]) for r in rows]

    @property
    def is_repost(self):
        """A pure repost = quoted another post and has no body of its own."""
        return self.quoted_post_id is not None and not (self.body or "").strip()

    @property
    def is_quote(self):
        """A quote = quoted another post AND added some body text."""
        return self.quoted_post_id is not None and bool((self.body or "").strip())


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
    updated_at = models.DateTimeField(auto_now=True)
    edited = models.BooleanField(default=False)

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
    """A reaction on a post — one row per (user, post). The `emoji` field captures
    which reaction the user picked (heart by default, but also laugh, fire, sad, wow).
    Renamed conceptually to "reaction" but the model stays `Like` for backwards-compat.
    """

    HEART = "heart"
    LAUGH = "laugh"
    FIRE = "fire"
    SAD = "sad"
    WOW = "wow"
    CLAP = "clap"
    EMOJI_CHOICES = [
        (HEART, "❤️"),
        (LAUGH, "😂"),
        (FIRE, "🔥"),
        (SAD, "😢"),
        (WOW, "😮"),
        (CLAP, "👏"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="likes"
    )
    emoji = models.CharField(
        max_length=10, choices=EMOJI_CHOICES, default=HEART,
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
        return f"{self.user.username} reacted {self.emoji} to post #{self.post_id}"

    @property
    def emoji_char(self):
        return dict(self.EMOJI_CHOICES).get(self.emoji, "❤️")


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


# ----- Hashtags -------------------------------------------------------------

class Hashtag(models.Model):
    """A tracked hashtag. Created on demand whenever a post body contains `#word`."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"#{self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:80] or self.name.lower()
        if not self.name:
            self.name = self.slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("posts:tag", kwargs={"slug": self.slug})

    @property
    def post_count(self):
        return self.posts.count()


# ----- Polls ----------------------------------------------------------------

class Poll(models.Model):
    """A poll attached to a single post. One-to-one — a post has at most one poll."""

    post = models.OneToOneField(
        Post, on_delete=models.CASCADE, related_name="poll",
    )
    question = models.CharField(max_length=200, blank=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    multiple_choice = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Poll on post #{self.post_id}"

    @property
    def is_closed(self):
        return bool(self.closes_at and self.closes_at <= timezone.now())

    @property
    def total_votes(self):
        return PollVote.objects.filter(option__poll=self).count()

    def voted_by(self, user):
        if not user.is_authenticated:
            return False
        return PollVote.objects.filter(option__poll=self, user=user).exists()

    def votes_for(self, user):
        if not user.is_authenticated:
            return []
        return list(
            PollVote.objects.filter(option__poll=self, user=user)
            .values_list("option_id", flat=True)
        )


class PollOption(models.Model):
    """One choice in a poll."""

    poll = models.ForeignKey(
        Poll, on_delete=models.CASCADE, related_name="options"
    )
    text = models.CharField(max_length=120)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.text} (poll #{self.poll_id})"

    @property
    def vote_count(self):
        return self.votes.count()

    def percentage_of(self, total):
        if not total:
            return 0
        return round(self.votes.count() * 100 / total)


class PollVote(models.Model):
    """One vote cast by a user on a poll option."""

    option = models.ForeignKey(
        PollOption, on_delete=models.CASCADE, related_name="votes"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="poll_votes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["option", "user"], name="unique_poll_vote_per_user_per_option"
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} → option #{self.option_id}"


# ----- Drafts ---------------------------------------------------------------

class PostDraft(models.Model):
    """A saved-but-unpublished post. Same shape as Post, minus engagement.

    Drafts are owned by the author and never visible to anyone else. Publishing
    a draft creates a Post and deletes the draft row.
    """

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_drafts",
    )
    body = models.TextField(max_length=2000, blank=True)
    image = models.ImageField(upload_to="drafts/%Y/%m/", blank=True, null=True)
    location = models.CharField(max_length=120, blank=True)
    visibility = models.CharField(
        max_length=10, choices=Post.VISIBILITY_CHOICES, default=Post.PUBLIC,
    )
    community = models.ForeignKey(
        "communities.Community",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="post_drafts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        snippet = (self.body or "").strip().splitlines()[0][:40] if self.body else "(empty)"
        return f"Draft by {self.author.username}: {snippet}"


# ----- Hashtag follows ------------------------------------------------------

class HashtagFollow(models.Model):
    """A user follows a hashtag — its posts then surface in their feed."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hashtag_follows",
    )
    hashtag = models.ForeignKey(
        Hashtag, on_delete=models.CASCADE, related_name="followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "hashtag"], name="unique_hashtag_follow",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} follows #{self.hashtag.name}"
