from django.contrib import admin, messages
from django.db.models import Count
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Bookmark, Comment, CommentLike, Hashtag, HashtagFollow, Like,
    Poll, PollOption, PollVote, Post, PostDraft, PostImage, Story,
)


# ---------- Inlines -------------------------------------------------------

class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1
    readonly_fields = ("preview",)
    fields = ("image", "preview", "order")

    @admin.display(description="Preview")
    def preview(self, obj):
        if obj and obj.image:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:4px;">',
                obj.image.url,
            )
        return "—"


class PollOptionInline(admin.TabularInline):
    model = PollOption
    extra = 1
    fields = ("text", "order", "vote_count")
    readonly_fields = ("vote_count",)


# ---------- Post ----------------------------------------------------------

class HasImageFilter(admin.SimpleListFilter):
    title = "image"
    parameter_name = "has_image"

    def lookups(self, request, model_admin):
        return (("yes", "With image"), ("no", "Text-only"))

    def queryset(self, request, qs):
        if self.value() == "yes":
            return qs.exclude(image="").exclude(image__isnull=True)
        if self.value() == "no":
            return qs.filter(image="") | qs.filter(image__isnull=True)
        return qs


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id", "image_thumb", "author", "short_body", "visibility",
        "community", "like_count", "comment_count", "created_at",
    )
    list_filter = ("visibility", HasImageFilter, "community", "created_at")
    list_editable = ("visibility",)
    search_fields = ("body", "author__username", "location")
    autocomplete_fields = ("author", "interests", "hashtags", "community", "quoted_post")
    inlines = [PostImageInline]
    readonly_fields = ("image_preview", "created_at", "updated_at")
    list_select_related = ("author", "community")
    list_per_page = 50
    date_hierarchy = "created_at"
    actions = ("make_public", "make_private", "make_friends_only")

    fieldsets = (
        (None, {"fields": ("author", "body", "visibility", "community")}),
        ("Media", {"fields": (("image", "image_preview"), "location")}),
        ("Tagging", {"fields": ("interests", "hashtags")}),
        ("Repost", {"fields": ("quoted_post",), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _likes=Count("likes", distinct=True),
            _comments=Count("comments", distinct=True),
        )

    @admin.display(description="Body")
    def short_body(self, obj):
        return (obj.body[:60] + "…") if len(obj.body) > 60 else obj.body

    @admin.display(description="Image")
    def image_thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:48px;height:36px;object-fit:cover;border-radius:4px;">',
                obj.image.url,
            )
        return "—"

    @admin.display(description="Image preview")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:240px;max-width:480px;border-radius:8px;">',
                obj.image.url,
            )
        return "—"

    @admin.display(description="❤️", ordering="_likes")
    def like_count(self, obj):
        return obj._likes

    @admin.display(description="💬", ordering="_comments")
    def comment_count(self, obj):
        return obj._comments

    @admin.action(description="Set selected to PUBLIC")
    def make_public(self, request, queryset):
        n = queryset.update(visibility=Post.PUBLIC)
        self.message_user(request, f"{n} post(s) set to public.", messages.SUCCESS)

    @admin.action(description="Set selected to PRIVATE")
    def make_private(self, request, queryset):
        n = queryset.update(visibility=Post.PRIVATE)
        self.message_user(request, f"{n} post(s) set to private.", messages.SUCCESS)

    @admin.action(description="Set selected to FRIENDS-ONLY")
    def make_friends_only(self, request, queryset):
        n = queryset.update(visibility=Post.FRIENDS)
        self.message_user(request, f"{n} post(s) set to friends-only.", messages.SUCCESS)


# ---------- Comment -------------------------------------------------------

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "post", "short_body", "edited", "created_at")
    list_filter = ("edited", "created_at")
    search_fields = ("author__username", "body")
    autocomplete_fields = ("author", "post", "parent")
    list_select_related = ("author", "post")
    date_hierarchy = "created_at"
    list_per_page = 50

    @admin.display(description="Body")
    def short_body(self, obj):
        return (obj.body[:60] + "…") if len(obj.body) > 60 else obj.body


# ---------- Reactions -----------------------------------------------------

@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "emoji", "created_at")
    list_filter = ("emoji", "created_at")
    search_fields = ("user__username",)
    autocomplete_fields = ("user", "post")
    list_select_related = ("user", "post")
    date_hierarchy = "created_at"
    list_per_page = 50


@admin.register(CommentLike)
class CommentLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "comment", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "comment__body")
    autocomplete_fields = ("user", "comment")
    list_select_related = ("user",)
    date_hierarchy = "created_at"


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "post__body")
    autocomplete_fields = ("user", "post")
    list_select_related = ("user", "post")
    date_hierarchy = "created_at"


# ---------- Story ---------------------------------------------------------

class StoryActiveFilter(admin.SimpleListFilter):
    title = "status"
    parameter_name = "story_status"

    def lookups(self, request, model_admin):
        return (("active", "Active"), ("expired", "Expired"))

    def queryset(self, request, qs):
        now = timezone.now()
        if self.value() == "active":
            return qs.filter(expires_at__gt=now)
        if self.value() == "expired":
            return qs.filter(expires_at__lte=now)
        return qs


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = (
        "id", "image_thumb", "author", "caption",
        "is_active", "created_at", "expires_at",
    )
    list_filter = (StoryActiveFilter, "created_at")
    search_fields = ("author__username", "caption")
    autocomplete_fields = ("author",)
    readonly_fields = ("image_preview", "created_at")
    list_select_related = ("author",)
    date_hierarchy = "created_at"
    actions = ("force_expire", "extend_24h")

    @admin.display(description="Image")
    def image_thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:32px;height:48px;object-fit:cover;border-radius:4px;">',
                obj.image.url,
            )
        return "—"

    @admin.display(description="Image preview")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:300px;border-radius:8px;">',
                obj.image.url,
            )
        return "—"

    @admin.display(boolean=True, description="Active")
    def is_active(self, obj):
        return obj.is_active

    @admin.action(description="Force expire selected stories")
    def force_expire(self, request, queryset):
        n = queryset.update(expires_at=timezone.now())
        self.message_user(request, f"Expired {n} story(ies).", messages.SUCCESS)

    @admin.action(description="Extend selected by 24h")
    def extend_24h(self, request, queryset):
        from datetime import timedelta
        count = 0
        for s in queryset:
            s.expires_at = (s.expires_at if s.expires_at > timezone.now() else timezone.now()) + timedelta(hours=24)
            s.save(update_fields=["expires_at"])
            count += 1
        self.message_user(request, f"Extended {count} story(ies) by 24h.", messages.SUCCESS)


# ---------- Hashtag -------------------------------------------------------

class HashtagPopularityFilter(admin.SimpleListFilter):
    title = "popularity"
    parameter_name = "popularity"

    def lookups(self, request, model_admin):
        return (
            ("orphan", "Orphan (0 posts)"),
            ("low", "Low (1–10)"),
            ("trending", "Trending (10+)"),
        )

    def queryset(self, request, qs):
        value = self.value()
        if value == "orphan":
            return qs.filter(_posts=0)
        if value == "low":
            return qs.filter(_posts__gte=1, _posts__lte=10)
        if value == "trending":
            return qs.filter(_posts__gt=10)
        return qs


@admin.register(Hashtag)
class HashtagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "post_count", "created_at")
    list_filter = (HashtagPopularityFilter, "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    actions = ("delete_orphans",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_posts=Count("posts"))

    @admin.display(description="Posts", ordering="_posts")
    def post_count(self, obj):
        return obj._posts

    @admin.action(description="Delete tags with no posts")
    def delete_orphans(self, request, queryset):
        n, _ = queryset.filter(posts__isnull=True).delete()
        self.message_user(request, f"Deleted {n} orphan tag(s).", messages.SUCCESS)


# ---------- Polls ---------------------------------------------------------

@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = (
        "id", "post", "question", "multiple_choice",
        "total_votes", "is_closed", "closes_at", "created_at",
    )
    list_filter = ("multiple_choice", "closes_at", "created_at")
    search_fields = ("question", "post__body")
    autocomplete_fields = ("post",)
    inlines = [PollOptionInline]
    list_select_related = ("post",)
    date_hierarchy = "created_at"
    actions = ("close_polls",)

    @admin.display(boolean=True, description="Closed")
    def is_closed(self, obj):
        return obj.is_closed

    @admin.action(description="Close selected polls now")
    def close_polls(self, request, queryset):
        n = queryset.update(closes_at=timezone.now())
        self.message_user(request, f"Closed {n} poll(s).", messages.SUCCESS)


@admin.register(PollOption)
class PollOptionAdmin(admin.ModelAdmin):
    list_display = ("id", "poll", "text", "order", "vote_count")
    search_fields = ("text", "poll__question")
    autocomplete_fields = ("poll",)


@admin.register(PollVote)
class PollVoteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "option", "created_at")
    search_fields = ("user__username", "option__text")
    autocomplete_fields = ("user", "option")
    list_select_related = ("user", "option")
    date_hierarchy = "created_at"


@admin.register(PostDraft)
class PostDraftAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "short_body", "visibility", "community", "updated_at")
    list_filter = ("visibility", "community", "updated_at")
    search_fields = ("author__username", "body")
    autocomplete_fields = ("author", "community")
    list_select_related = ("author", "community")
    date_hierarchy = "updated_at"
    list_per_page = 50

    @admin.display(description="Body")
    def short_body(self, obj):
        body = obj.body or ""
        return (body[:60] + "…") if len(body) > 60 else (body or "—")


@admin.register(HashtagFollow)
class HashtagFollowAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "hashtag", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "hashtag__name")
    autocomplete_fields = ("user", "hashtag")
    list_select_related = ("user", "hashtag")
    date_hierarchy = "created_at"
