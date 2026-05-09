from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils.html import format_html

from .models import Community, CommunityEvent, CommunityMember, EventRSVP


class CommunityMemberInline(admin.TabularInline):
    model = CommunityMember
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("user", "role", "status", "joined_at")
    readonly_fields = ("joined_at",)


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = (
        "avatar_thumb", "name", "slug", "privacy", "owner",
        "member_count_col", "post_count", "created_at",
    )
    list_filter = ("privacy", "created_at")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("owner",)
    inlines = [CommunityMemberInline]
    readonly_fields = ("avatar_preview", "cover_preview", "created_at")
    list_select_related = ("owner",)
    list_per_page = 50
    date_hierarchy = "created_at"
    actions = ("make_public", "make_private")

    fieldsets = (
        ("Basic", {"fields": ("name", "slug", "description", "privacy", "owner")}),
        ("Media", {"fields": (("avatar", "avatar_preview"), ("cover", "cover_preview"))}),
        ("Timestamps", {"fields": ("created_at",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _members=Count(
                "memberships",
                filter=Q(memberships__status=CommunityMember.ACTIVE),
                distinct=True,
            ),
            _posts=Count("posts", distinct=True),
        )

    @admin.display(description="Avatar")
    def avatar_thumb(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="width:36px;height:36px;border-radius:8px;object-fit:cover;">',
                obj.avatar.url,
            )
        return "—"

    @admin.display(description="Avatar preview")
    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="width:120px;height:120px;border-radius:12px;object-fit:cover;">',
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

    @admin.display(description="Members", ordering="_members")
    def member_count_col(self, obj):
        return obj._members

    @admin.display(description="Posts", ordering="_posts")
    def post_count(self, obj):
        return obj._posts

    @admin.action(description="Set selected to PUBLIC")
    def make_public(self, request, queryset):
        n = queryset.update(privacy=Community.PUBLIC)
        self.message_user(request, f"{n} set to public.", messages.SUCCESS)

    @admin.action(description="Set selected to PRIVATE")
    def make_private(self, request, queryset):
        n = queryset.update(privacy=Community.PRIVATE)
        self.message_user(request, f"{n} set to private.", messages.SUCCESS)


@admin.register(CommunityMember)
class CommunityMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "community", "role", "status", "joined_at")
    list_filter = ("role", "status", "joined_at")
    search_fields = ("user__username", "community__name")
    autocomplete_fields = ("user", "community")
    list_select_related = ("user", "community")
    date_hierarchy = "joined_at"
    list_per_page = 100
    actions = ("approve", "ban", "unban", "promote_to_admin", "demote_to_member")

    @admin.action(description="Approve pending memberships")
    def approve(self, request, queryset):
        n = queryset.filter(status=CommunityMember.PENDING).update(status=CommunityMember.ACTIVE)
        self.message_user(request, f"Approved {n} member(s).", messages.SUCCESS)

    @admin.action(description="Ban selected members")
    def ban(self, request, queryset):
        n = queryset.exclude(role=CommunityMember.OWNER).update(status=CommunityMember.BANNED)
        self.message_user(request, f"Banned {n} member(s).", messages.WARNING)

    @admin.action(description="Unban selected (set to active)")
    def unban(self, request, queryset):
        n = queryset.filter(status=CommunityMember.BANNED).update(status=CommunityMember.ACTIVE)
        self.message_user(request, f"Unbanned {n} member(s).", messages.SUCCESS)

    @admin.action(description="Promote selected to admin")
    def promote_to_admin(self, request, queryset):
        n = queryset.filter(role=CommunityMember.MEMBER).update(role=CommunityMember.ADMIN)
        self.message_user(request, f"Promoted {n} to admin.", messages.SUCCESS)

    @admin.action(description="Demote admins back to members")
    def demote_to_member(self, request, queryset):
        n = queryset.filter(role=CommunityMember.ADMIN).update(role=CommunityMember.MEMBER)
        self.message_user(request, f"Demoted {n} member(s).", messages.SUCCESS)


class EventRSVPInline(admin.TabularInline):
    model = EventRSVP
    extra = 0
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
    fields = ("user", "status", "created_at")


@admin.register(CommunityEvent)
class CommunityEventAdmin(admin.ModelAdmin):
    list_display = ("title", "community", "starts_at", "ends_at", "rsvp_count_col", "created_by")
    list_filter = ("community", "starts_at")
    search_fields = ("title", "description", "community__name")
    autocomplete_fields = ("community", "created_by")
    list_select_related = ("community", "created_by")
    date_hierarchy = "starts_at"
    inlines = [EventRSVPInline]
    readonly_fields = ("created_at",)
    list_per_page = 50

    @admin.display(description="Going")
    def rsvp_count_col(self, obj):
        return obj.rsvp_count


@admin.register(EventRSVP)
class EventRSVPAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "user", "status", "updated_at")
    list_filter = ("status", "updated_at")
    search_fields = ("user__username", "event__title")
    autocomplete_fields = ("event", "user")
    list_select_related = ("event", "user")
    date_hierarchy = "updated_at"
