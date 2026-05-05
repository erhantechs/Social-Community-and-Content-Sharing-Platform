from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST


@login_required
def notification_list(request):
    notes = (
        request.user.notifications.select_related("actor", "actor__profile", "post")
    )
    # Mark all as read on view
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, "notifications/list.html", {"notifications": notes})


@login_required
@require_POST
def mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "unread": 0})
    return redirect("notifications:list")


@login_required
def notification_dropdown(request):
    """Lightweight JSON feed of the latest 5 notifications for the topbar."""
    notes = (
        request.user.notifications
        .select_related("actor", "actor__profile", "post")[:5]
    )
    items = []
    for n in notes:
        items.append({
            "id": n.id,
            "actor": {
                "username": n.actor.username,
                "name": n.actor.profile.name if hasattr(n.actor, "profile") else n.actor.username,
                "avatar_url": (n.actor.profile.avatar.url
                               if hasattr(n.actor, "profile") and n.actor.profile.avatar
                               else ""),
                "profile_url": reverse("accounts:profile",
                                       kwargs={"username": n.actor.username}),
            },
            "verb": n.get_verb_display(),
            "post_url": (reverse("posts:detail", kwargs={"pk": n.post_id})
                         if n.post_id else None),
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        })
    unread = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({"items": items, "unread": unread})
