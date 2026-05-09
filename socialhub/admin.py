"""Project-level admin tweaks: branded site headers and a dashboard summary
shown on the admin index. We don't subclass AdminSite (that would require
re-registering every model); instead we just monkey-patch the default site's
strings and wrap each_context to inject stats into the index template.
"""
from django.contrib import admin


# --------- Branding -------------------------------------------------------
admin.site.site_header = "SocialHub Admin"
admin.site.site_title = "SocialHub Admin"
admin.site.index_title = "Operations Dashboard"


# --------- Dashboard hook -------------------------------------------------
_original_each_context = admin.site.each_context


def _stat(label, value, app_model, icon, group):
    app, model = app_model.split(".")
    return {
        "label": label,
        "value": value,
        "url": f"{app}/{model}/",
        "icon": icon,
        "group": group,
    }


def each_context_with_stats(request):
    ctx = _original_each_context(request)
    if request.path.rstrip("/").endswith("/admin"):
        try:
            from django.contrib.auth import get_user_model
            from posts.models import Post, Story, Like, Comment, Hashtag, Poll
            from messaging.models import Conversation, Message
            from communities.models import Community
            from notifications.models import Notification

            User = get_user_model()
            ctx["dashboard_stats"] = [
                _stat("Users",         User.objects.count(),         "auth.user",                 "👤",  "Audience"),
                _stat("Communities",   Community.objects.count(),    "communities.community",     "🌐",  "Audience"),

                _stat("Posts",         Post.objects.count(),         "posts.post",                "📝",  "Content"),
                _stat("Comments",      Comment.objects.count(),      "posts.comment",             "💬",  "Content"),
                _stat("Reactions",     Like.objects.count(),         "posts.like",                "❤️",  "Content"),
                _stat("Stories",       Story.objects.count(),        "posts.story",               "📸",  "Content"),
                _stat("Active stories", Story.active().count(),      "posts.story",               "⏱️",  "Content"),
                _stat("Polls",         Poll.objects.count(),         "posts.poll",                "📊",  "Content"),
                _stat("Hashtags",      Hashtag.objects.count(),      "posts.hashtag",             "#",   "Content"),

                _stat("Conversations", Conversation.objects.count(), "messaging.conversation",    "💭",  "Messaging"),
                _stat("Messages",      Message.objects.count(),      "messaging.message",         "✉️",  "Messaging"),

                _stat("Notifications", Notification.objects.count(), "notifications.notification","🔔",  "Operations"),
            ]
        except Exception:
            ctx["dashboard_stats"] = []
    return ctx


admin.site.each_context = each_context_with_stats
