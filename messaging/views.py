from django.contrib import messages as flash
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from notifications.models import Notification

from .models import Conversation, Message

User = get_user_model()


@login_required
def inbox(request):
    """List of every conversation the current user has."""
    convs = (
        Conversation.objects
        .filter(Q(user_a=request.user) | Q(user_b=request.user))
        .select_related("user_a__profile", "user_b__profile")
        .prefetch_related("messages")
    )
    rows = []
    for c in convs:
        partner = c.other(request.user)
        last = c.messages.order_by("-created_at").first()
        unread = c.messages.filter(is_read=False).exclude(sender=request.user).count()
        rows.append({"conv": c, "partner": partner, "last": last, "unread": unread})
    return render(request, "messaging/inbox.html", {"rows": rows})


@login_required
def open_conversation(request, username):
    """Open (or create) a conversation with `username` and show its thread."""
    other = get_object_or_404(User.objects.select_related("profile"), username=username)
    if other == request.user:
        raise Http404
    from accounts.models import Block
    if Block.is_blocked_either_way(request.user, other):
        flash.error(request, "You cannot message this user.")
        return redirect("messaging:inbox")
    conv = Conversation.between(request.user, other)
    return redirect("messaging:thread", pk=conv.pk)


@login_required
def thread(request, pk):
    conv = get_object_or_404(
        Conversation.objects.select_related(
            "user_a__profile", "user_b__profile"
        ),
        pk=pk,
    )
    if request.user.id not in (conv.user_a_id, conv.user_b_id):
        raise Http404

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        if body:
            Message.objects.create(conversation=conv, sender=request.user, body=body)
            partner = conv.other(request.user)
            Notification.objects.create(
                recipient=partner, actor=request.user, verb=Notification.MESSAGE,
            )
            return redirect("messaging:thread", pk=conv.pk)
        flash.error(request, "Message cannot be empty.")

    # Mark all incoming as read.
    conv.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    return render(request, "messaging/thread.html", {
        "conv": conv,
        "partner": conv.other(request.user),
        "messages_list": conv.messages.select_related("sender__profile"),
    })
