from django.contrib import admin, messages

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id", "verb", "actor", "recipient", "post", "is_read", "created_at",
    )
    list_filter = ("verb", "is_read", "created_at")
    search_fields = ("recipient__username", "actor__username")
    autocomplete_fields = ("recipient", "actor", "post")
    list_select_related = ("recipient", "actor", "post")
    date_hierarchy = "created_at"
    list_per_page = 100
    actions = ("mark_read", "mark_unread", "delete_old")

    @admin.action(description="Mark selected as read")
    def mark_read(self, request, queryset):
        n = queryset.update(is_read=True)
        self.message_user(request, f"Marked {n} as read.", messages.SUCCESS)

    @admin.action(description="Mark selected as unread")
    def mark_unread(self, request, queryset):
        n = queryset.update(is_read=False)
        self.message_user(request, f"Marked {n} as unread.", messages.SUCCESS)

    @admin.action(description="Delete notifications older than 30 days")
    def delete_old(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=30)
        n, _ = queryset.filter(created_at__lt=cutoff).delete()
        self.message_user(request, f"Deleted {n} old notification(s).", messages.SUCCESS)
