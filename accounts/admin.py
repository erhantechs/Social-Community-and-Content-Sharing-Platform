from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Count
from django.utils.html import format_html

from .models import (
    Block, Follow, Interest, Mute, Profile, SocialAccount, TwoFactorSecret,
)

User = get_user_model()


# ---------- Profile inline on User ---------------------------------------

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fieldsets = (
        ("Basic", {"fields": ("display_name", "bio", "location", "website")}),
        ("Media", {"fields": ("avatar", "avatar_preview", "cover", "cover_preview")}),
        ("Interests", {"fields": ("interests",)}),
        ("Status", {"fields": (
            "email_verified", "onboarded", "two_factor_enabled",
            "created_at", "updated_at",
        )}),
    )
    readonly_fields = ("avatar_preview", "cover_preview", "created_at", "updated_at")
    filter_horizontal = ("interests",)

    @admin.display(description="Avatar")
    def avatar_preview(self, obj):
        if obj and obj.avatar:
            return format_html(
                '<img src="{}" style="width:64px;height:64px;border-radius:50%;object-fit:cover;">',
                obj.avatar.url,
            )
        return "—"

    @admin.display(description="Cover")
    def cover_preview(self, obj):
        if obj and obj.cover:
            return format_html(
                '<img src="{}" style="width:240px;height:80px;border-radius:6px;object-fit:cover;">',
                obj.cover.url,
            )
        return "—"


# ---------- Custom User admin --------------------------------------------

# Re-register User to embed the Profile inline + extra columns + actions.
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = [ProfileInline]
    list_display = (
        "username", "email", "avatar_thumb", "first_name", "last_name",
        "is_staff", "is_active", "email_verified", "two_factor", "date_joined",
    )
    list_filter = (
        "is_staff", "is_superuser", "is_active",
        "profile__email_verified", "profile__two_factor_enabled",
        "date_joined",
    )
    actions = (
        "activate_users", "deactivate_users",
        "force_email_verified", "reset_two_factor",
    )

    @admin.display(description="Avatar")
    def avatar_thumb(self, obj):
        if hasattr(obj, "profile") and obj.profile.avatar:
            return format_html(
                '<img src="{}" style="width:32px;height:32px;border-radius:50%;object-fit:cover;">',
                obj.profile.avatar.url,
            )
        return "—"

    @admin.display(boolean=True, description="Email verified")
    def email_verified(self, obj):
        return bool(getattr(obj, "profile", None) and obj.profile.email_verified)

    @admin.display(boolean=True, description="2FA")
    def two_factor(self, obj):
        return bool(getattr(obj, "profile", None) and obj.profile.two_factor_enabled)

    @admin.action(description="Activate selected users")
    def activate_users(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f"Activated {n} user(s).", messages.SUCCESS)

    @admin.action(description="Deactivate selected users")
    def deactivate_users(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {n} user(s).", messages.SUCCESS)

    @admin.action(description="Mark selected users' emails as verified")
    def force_email_verified(self, request, queryset):
        n = Profile.objects.filter(user__in=queryset).update(email_verified=True)
        self.message_user(request, f"Verified {n} email(s).", messages.SUCCESS)

    @admin.action(description="Reset 2FA on selected users")
    def reset_two_factor(self, request, queryset):
        TwoFactorSecret.objects.filter(user__in=queryset).delete()
        n = Profile.objects.filter(user__in=queryset).update(two_factor_enabled=False)
        self.message_user(
            request, f"Reset 2FA for {n} user(s).", messages.WARNING,
        )


# ---------- Profile (separate page for power-users) ----------------------

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user", "avatar_thumb", "display_name", "location",
        "email_verified", "two_factor_enabled", "post_count",
        "follower_count", "created_at",
    )
    list_filter = ("email_verified", "two_factor_enabled", "onboarded", "created_at")
    search_fields = ("user__username", "display_name", "location", "bio")
    autocomplete_fields = ("user", "interests")
    readonly_fields = ("avatar_preview", "cover_preview", "created_at", "updated_at")
    filter_horizontal = ("interests",)
    list_select_related = ("user",)
    list_per_page = 50

    fieldsets = (
        ("User", {"fields": ("user",)}),
        ("Profile", {"fields": ("display_name", "bio", "location", "website")}),
        ("Media", {"fields": (("avatar", "avatar_preview"), ("cover", "cover_preview"))}),
        ("Interests", {"fields": ("interests",)}),
        ("Status", {"fields": (
            "email_verified", "onboarded", "two_factor_enabled",
            ("created_at", "updated_at"),
        )}),
    )

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .annotate(
                _post_count=Count("user__posts", distinct=True),
                _follower_count=Count("user__followers", distinct=True),
            )
        )

    @admin.display(description="Avatar")
    def avatar_thumb(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="width:32px;height:32px;border-radius:50%;object-fit:cover;">',
                obj.avatar.url,
            )
        return "—"

    @admin.display(description="Avatar preview")
    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="width:96px;height:96px;border-radius:50%;object-fit:cover;">',
                obj.avatar.url,
            )
        return "—"

    @admin.display(description="Cover preview")
    def cover_preview(self, obj):
        if obj.cover:
            return format_html(
                '<img src="{}" style="width:300px;height:90px;border-radius:6px;object-fit:cover;">',
                obj.cover.url,
            )
        return "—"

    @admin.display(description="Posts", ordering="_post_count")
    def post_count(self, obj):
        return obj._post_count

    @admin.display(description="Followers", ordering="_follower_count")
    def follower_count(self, obj):
        return obj._follower_count


# ---------- Follow / Block / Mute -----------------------------------------

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "following", "created_at")
    list_filter = ("created_at",)
    search_fields = ("follower__username", "following__username")
    autocomplete_fields = ("follower", "following")
    list_select_related = ("follower", "following")
    date_hierarchy = "created_at"
    list_per_page = 50


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")
    list_filter = ("created_at",)
    search_fields = ("blocker__username", "blocked__username")
    autocomplete_fields = ("blocker", "blocked")
    list_select_related = ("blocker", "blocked")
    date_hierarchy = "created_at"


@admin.register(Mute)
class MuteAdmin(admin.ModelAdmin):
    list_display = ("muter", "muted", "created_at")
    list_filter = ("created_at",)
    search_fields = ("muter__username", "muted__username")
    autocomplete_fields = ("muter", "muted")
    list_select_related = ("muter", "muted")
    date_hierarchy = "created_at"


class InterestPopularityFilter(admin.SimpleListFilter):
    title = "popularity"
    parameter_name = "popularity"

    def lookups(self, request, model_admin):
        return (
            ("dead", "Dead (0 followers)"),
            ("low", "Low (1–10)"),
            ("trending", "Trending (10+)"),
        )

    def queryset(self, request, qs):
        value = self.value()
        if value == "dead":
            return qs.filter(_followers=0)
        if value == "low":
            return qs.filter(_followers__gte=1, _followers__lte=10)
        if value == "trending":
            return qs.filter(_followers__gt=10)
        return qs


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "color", "follower_count")
    list_filter = (InterestPopularityFilter,)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _followers=Count("followers_profiles", distinct=True),
        )

    @admin.display(description="Followers", ordering="_followers")
    def follower_count(self, obj):
        return obj._followers


# ---------- 2FA + Social Accounts -----------------------------------------

@admin.register(TwoFactorSecret)
class TwoFactorSecretAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "last_used_at", "backup_codes_left")
    search_fields = ("user__username",)
    autocomplete_fields = ("user",)
    readonly_fields = ("secret", "backup_codes", "created_at", "last_used_at")
    list_select_related = ("user",)
    actions = ("revoke_2fa",)

    @admin.display(description="Backup codes left")
    def backup_codes_left(self, obj):
        return len(obj.get_backup_codes())

    @admin.action(description="Revoke 2FA (delete secret + clear flag)")
    def revoke_2fa(self, request, queryset):
        user_ids = list(queryset.values_list("user_id", flat=True))
        n = queryset.delete()[0]
        Profile.objects.filter(user_id__in=user_ids).update(two_factor_enabled=False)
        self.message_user(request, f"Revoked 2FA for {n} user(s).", messages.WARNING)


class SocialEmailPresenceFilter(admin.SimpleListFilter):
    title = "social email"
    parameter_name = "social_email"

    def lookups(self, request, model_admin):
        return (("yes", "Has email"), ("no", "Missing email"))

    def queryset(self, request, qs):
        if self.value() == "yes":
            return qs.exclude(email="")
        if self.value() == "no":
            return qs.filter(email="")
        return qs


class LinkedEmailVerifiedFilter(admin.SimpleListFilter):
    title = "linked email verified"
    parameter_name = "linked_verified"

    def lookups(self, request, model_admin):
        return (("yes", "Verified"), ("no", "Unverified"))

    def queryset(self, request, qs):
        if self.value() == "yes":
            return qs.filter(user__profile__email_verified=True)
        if self.value() == "no":
            return qs.filter(user__profile__email_verified=False)
        return qs


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "email", "created_at")
    list_filter = (
        "provider",
        SocialEmailPresenceFilter,
        LinkedEmailVerifiedFilter,
        "created_at",
    )
    search_fields = ("user__username", "email", "provider_uid")
    autocomplete_fields = ("user",)
    readonly_fields = ("provider_uid", "extra_data", "created_at")
    list_select_related = ("user", "user__profile")
