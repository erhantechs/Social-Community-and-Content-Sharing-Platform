"""User-related domain models: Profile, Follow, Interest."""
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Interest(models.Model):
    """Topic / category users can follow (Music, Cooking, Hiking, UI/UX, etc.)."""

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    icon = models.CharField(
        max_length=10, blank=True,
        help_text="Single emoji or short text used in the recommendations card."
    )
    color = models.CharField(
        max_length=20, default="#e9ecef",
        help_text="Tailwind/CSS background color for the recommendation chip."
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Profile(models.Model):
    """One-to-one extension of the built-in User."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=80, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    cover = models.ImageField(upload_to="covers/", blank=True, null=True)
    location = models.CharField(max_length=120, blank=True)
    website = models.URLField(blank=True)
    interests = models.ManyToManyField(
        Interest, blank=True, related_name="followers_profiles"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile<{self.user.username}>"

    def get_absolute_url(self):
        return reverse("accounts:profile", kwargs={"username": self.user.username})

    @property
    def name(self):
        return self.display_name or self.user.get_full_name() or self.user.username

    @property
    def handle(self):
        return f"@{self.user.username}"

    @property
    def avatar_url(self):
        if self.avatar:
            try:
                return self.avatar.url
            except ValueError:
                pass
        return ""

    @property
    def followers_count(self):
        return self.user.followers.count()

    @property
    def following_count(self):
        return self.user.following.count()

    @property
    def posts_count(self):
        return self.user.posts.count()


class Follow(models.Model):
    """Directed follow relationship: follower → following."""

    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="following",
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="followers",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["follower", "following"],
                name="unique_follow",
            ),
            models.CheckConstraint(
                check=~models.Q(follower=models.F("following")),
                name="prevent_self_follow",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.follower} → {self.following}"


class Block(models.Model):
    """`blocker` has blocked `blocked` — neither can interact with the other.

    Blocking implicitly removes any existing follow between the two users
    (handled in the view layer) and prevents new follows, comments, mentions,
    and direct messages.
    """

    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocking",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_block"),
            models.CheckConstraint(
                check=~models.Q(blocker=models.F("blocked")),
                name="prevent_self_block",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.blocker} blocks {self.blocked}"

    @classmethod
    def is_blocked_either_way(cls, u1, u2):
        """Either-direction block test — useful for hiding content."""
        if not getattr(u1, "is_authenticated", False) or not getattr(u2, "is_authenticated", False):
            return False
        return cls.objects.filter(
            models.Q(blocker=u1, blocked=u2) | models.Q(blocker=u2, blocked=u1)
        ).exists()
