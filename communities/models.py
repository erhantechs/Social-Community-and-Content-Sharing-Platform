"""Community (group / forum) models."""
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Community(models.Model):
    """A user-created topical community.

    Public communities are visible to everyone and anyone can join.
    Private communities are listed but joining requires owner/admin approval
    (approval flow is simplified to a request/accept toggle in v1).
    """

    PUBLIC = "public"
    PRIVATE = "private"
    PRIVACY_CHOICES = [
        (PUBLIC, "Public"),
        (PRIVATE, "Private"),
    ]

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to="communities/avatars/", blank=True, null=True)
    cover = models.ImageField(upload_to="communities/covers/", blank=True, null=True)
    privacy = models.CharField(max_length=10, choices=PRIVACY_CHOICES, default=PUBLIC)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_communities",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["privacy", "-created_at"]),
        ]
        verbose_name_plural = "communities"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:90] or "community"
            slug = base
            n = 2
            while Community.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"[:90]
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("communities:detail", kwargs={"slug": self.slug})

    @property
    def member_count(self):
        return self.memberships.filter(status=CommunityMember.ACTIVE).count()

    def role_of(self, user):
        if not user or not user.is_authenticated:
            return None
        m = self.memberships.filter(user=user, status=CommunityMember.ACTIVE).only("role").first()
        return m.role if m else None

    def is_member(self, user):
        return self.role_of(user) is not None

    def is_admin(self, user):
        role = self.role_of(user)
        return role in (CommunityMember.OWNER, CommunityMember.ADMIN)

    def has_pending_request(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.memberships.filter(user=user, status=CommunityMember.PENDING).exists()


class CommunityMember(models.Model):
    """Membership row tying a user to a community with a role + status."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    ROLE_CHOICES = [
        (OWNER, "Owner"),
        (ADMIN, "Admin"),
        (MEMBER, "Member"),
    ]

    ACTIVE = "active"
    PENDING = "pending"
    BANNED = "banned"
    STATUS_CHOICES = [
        (ACTIVE, "Active"),
        (PENDING, "Pending"),
        (BANNED, "Banned"),
    ]

    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_memberships",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["community", "user"], name="unique_community_member"
            ),
        ]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user.username} in {self.community.name} ({self.role})"


class CommunityEvent(models.Model):
    """An event hosted by a community — meetup, AMA, workshop, etc."""

    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="events",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_events",
    )
    title = models.CharField(max_length=140)
    description = models.TextField(max_length=2000, blank=True)
    location = models.CharField(max_length=200, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    cover = models.ImageField(upload_to="events/%Y/%m/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [
            models.Index(fields=["community", "starts_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.community.name})"

    def get_absolute_url(self):
        return reverse(
            "communities:event_detail",
            kwargs={"slug": self.community.slug, "event_id": self.pk},
        )

    @property
    def is_upcoming(self):
        from django.utils import timezone
        return self.starts_at >= timezone.now()

    @property
    def is_past(self):
        from django.utils import timezone
        end = self.ends_at or self.starts_at
        return end < timezone.now()

    @property
    def rsvp_count(self):
        return self.rsvps.filter(status=EventRSVP.GOING).count()

    def rsvp_status_for(self, user):
        if not user or not user.is_authenticated:
            return None
        rsvp = self.rsvps.filter(user=user).only("status").first()
        return rsvp.status if rsvp else None


class EventRSVP(models.Model):
    """A user's response to a community event."""

    GOING = "going"
    INTERESTED = "interested"
    NOT_GOING = "not_going"
    STATUS_CHOICES = [
        (GOING, "Going"),
        (INTERESTED, "Interested"),
        (NOT_GOING, "Not going"),
    ]

    event = models.ForeignKey(
        CommunityEvent, on_delete=models.CASCADE, related_name="rsvps",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_rsvps",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=GOING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["event", "user"], name="unique_event_rsvp"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} → {self.event.title} ({self.status})"
