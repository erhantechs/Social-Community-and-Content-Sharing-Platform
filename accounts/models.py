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
    email_verified = models.BooleanField(default=False)
    onboarded = models.BooleanField(default=False)
    two_factor_enabled = models.BooleanField(default=False)
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


class Mute(models.Model):
    """Soft hide: `muter` doesn't see `muted`'s posts in their feed/explore,
    but the muted user is unaware and can still comment, mention, follow.

    Different from Block: Block is two-way and prevents interaction; Mute
    is one-way and silent. Useful when you want to skip someone without the
    social cost of blocking.
    """

    muter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="muting",
    )
    muted = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="muted_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["muter", "muted"], name="unique_mute"),
            models.CheckConstraint(
                check=~models.Q(muter=models.F("muted")),
                name="prevent_self_mute",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.muter} muted {self.muted}"

    @classmethod
    def muted_user_ids_for(cls, user):
        if not getattr(user, "is_authenticated", False):
            return []
        return list(cls.objects.filter(muter=user).values_list("muted_id", flat=True))


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

    @classmethod
    def hidden_user_ids_for(cls, user):
        """Return the set of user IDs `user` should never see content from.

        Includes anyone `user` has blocked, plus anyone who has blocked `user`.
        Returns an empty list for anonymous users so callers can safely
        `.exclude(author_id__in=...)` without a special case.
        """
        if not getattr(user, "is_authenticated", False):
            return []
        return list(
            cls.objects.filter(blocker=user).values_list("blocked_id", flat=True)
        ) + list(
            cls.objects.filter(blocked=user).values_list("blocker_id", flat=True)
        )


# ----- 2FA / TOTP --------------------------------------------------------

class TwoFactorSecret(models.Model):
    """Per-user TOTP secret + backup codes.

    The secret is stored only for users who have enabled 2FA. We keep this in
    a separate table (rather than on Profile) so the row's lifecycle is tied
    to "2FA configured" — disabling 2FA deletes the row and the secret.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="two_factor_secret",
    )
    secret = models.CharField(max_length=64)
    # Backup codes — newline-separated, each consumed when used.
    backup_codes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"2FA<{self.user.username}>"

    def get_backup_codes(self):
        return [c for c in (self.backup_codes or "").splitlines() if c.strip()]

    def consume_backup_code(self, code):
        codes = self.get_backup_codes()
        code = (code or "").strip().upper()
        if code not in codes:
            return False
        codes.remove(code)
        self.backup_codes = "\n".join(codes)
        self.save(update_fields=["backup_codes"])
        return True


# ----- Social (OAuth) accounts -----------------------------------------

class SocialAccount(models.Model):
    """Links an external OAuth identity to a local user.

    A user may have multiple linked accounts (e.g. Google AND GitHub), but
    each provider+provider_uid pair is unique globally.
    """

    GOOGLE = "google"
    GITHUB = "github"
    PROVIDER_CHOICES = [
        (GOOGLE, "Google"),
        (GITHUB, "GitHub"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_accounts",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_uid = models.CharField(max_length=191)
    email = models.EmailField(blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_uid"],
                name="unique_social_identity",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "provider"]),
        ]

    def __str__(self):
        return f"{self.user.username} via {self.provider}"
