def unread_notifications(request):
    if not request.user.is_authenticated:
        return {"unread_notification_count": 0, "unread_message_count": 0}
    # Unread DM count (lazy import to avoid app-load order issues).
    try:
        from messaging.models import Message
        unread_messages = (
            Message.objects.filter(
                conversation__user_a=request.user, is_read=False,
            ).exclude(sender=request.user).count()
            +
            Message.objects.filter(
                conversation__user_b=request.user, is_read=False,
            ).exclude(sender=request.user).count()
        )
    except Exception:
        unread_messages = 0
    return {
        "unread_notification_count": request.user.notifications.filter(is_read=False).count(),
        "unread_message_count": unread_messages,
    }
