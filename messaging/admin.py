from django.contrib import admin, messages
from django.db.models import Count, Max
from django.utils.html import format_html

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("sender", "body", "is_read", "created_at")
    fields = ("sender", "body", "is_read", "created_at")
    can_delete = False
    show_change_link = True
    ordering = ("-created_at",)

    def get_queryset(self, request):
        # Show only the most recent 25 to keep the page snappy.
        return super().get_queryset(request).order_by("-created_at")[:25]

    def has_add_permission(self, request, obj=None):
        return False


class ConversationKindFilter(admin.SimpleListFilter):
    title = "kind"
    parameter_name = "kind"

    def lookups(self, request, model_admin):
        return (("dm", "Direct message"), ("group", "Group chat"))

    def queryset(self, request, qs):
        if self.value() == "dm":
            return qs.filter(is_group=False)
        if self.value() == "group":
            return qs.filter(is_group=True)
        return qs


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id", "kind", "label", "participant_count", "message_count",
        "last_activity",
    )
    list_filter = (ConversationKindFilter, "created_at", "updated_at")
    search_fields = (
        "name", "user_a__username", "user_b__username",
        "participants__username",
    )
    autocomplete_fields = ("user_a", "user_b", "participants", "created_by")
    readonly_fields = ("created_at", "updated_at")
    inlines = [MessageInline]
    date_hierarchy = "updated_at"
    list_per_page = 50

    fieldsets = (
        ("Type", {"fields": ("is_group", "name", "cover")}),
        ("Participants (1-to-1)", {"fields": ("user_a", "user_b")}),
        ("Participants (group)", {"fields": ("participants", "created_by")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _msgs=Count("messages", distinct=True),
            _last=Max("messages__created_at"),
            _participants=Count("participants", distinct=True),
        )

    @admin.display(description="Kind")
    def kind(self, obj):
        return "Group" if obj.is_group else "DM"

    @admin.display(description="Label")
    def label(self, obj):
        if obj.is_group:
            return obj.name or f"Group #{obj.pk}"
        return f"{obj.user_a} ↔ {obj.user_b}" if obj.user_a and obj.user_b else "—"

    @admin.display(description="Participants", ordering="_participants")
    def participant_count(self, obj):
        return obj._participants

    @admin.display(description="Messages", ordering="_msgs")
    def message_count(self, obj):
        return obj._msgs

    @admin.display(description="Last activity", ordering="_last")
    def last_activity(self, obj):
        return obj._last or obj.created_at


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id", "conversation", "sender", "short_body", "is_read", "created_at",
    )
    list_filter = ("is_read", "created_at")
    search_fields = ("body", "sender__username")
    autocomplete_fields = ("conversation", "sender")
    list_select_related = ("conversation", "sender")
    date_hierarchy = "created_at"
    list_per_page = 100
    actions = ("mark_read", "mark_unread")

    @admin.display(description="Body")
    def short_body(self, obj):
        return (obj.body[:80] + "…") if len(obj.body) > 80 else obj.body

    @admin.action(description="Mark selected as read")
    def mark_read(self, request, queryset):
        n = queryset.update(is_read=True)
        self.message_user(request, f"Marked {n} message(s) as read.", messages.SUCCESS)

    @admin.action(description="Mark selected as unread")
    def mark_unread(self, request, queryset):
        n = queryset.update(is_read=False)
        self.message_user(request, f"Marked {n} message(s) as unread.", messages.SUCCESS)
