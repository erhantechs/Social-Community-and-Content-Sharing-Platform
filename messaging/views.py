"""Messaging views — DMs and group chats."""
from django.contrib import messages as flash
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Block, Follow
from notifications.models import Notification

from .models import Conversation, Message

User = get_user_model()


@login_required
def inbox(request):
    """List of every conversation (DM + group) the current user is in.

    Supports an optional `?q=` search that matches against conversation/group
    name, partner display-name, partner username, or last-message body.
    """
    convs = (
        Conversation.objects
        .filter(participants=request.user)
        .select_related("user_a__profile", "user_b__profile")
        .prefetch_related("participants__profile", "messages")
        .distinct()
    )
    rows = []
    for c in convs:
        last = c.messages.order_by("-created_at").first()
        unread = c.messages.filter(is_read=False).exclude(sender=request.user).count()
        if c.is_group:
            preview_users = list(c.participants.exclude(pk=request.user.pk)[:3])
            rows.append({
                "conv": c, "partner": None, "is_group": True,
                "name": c.display_name, "preview_users": preview_users,
                "last": last, "unread": unread,
            })
        else:
            partner = c.other(request.user)
            rows.append({
                "conv": c, "partner": partner, "is_group": False,
                "name": (partner.profile.name or partner.username) if partner else "—",
                "preview_users": [],
                "last": last, "unread": unread,
            })
    rows.sort(
        key=lambda r: r["last"].created_at if r["last"] else r["conv"].created_at,
        reverse=True,
    )

    # Apply search filter (case-insensitive over name + last-message body + handle).
    query = (request.GET.get("q") or "").strip()
    if query:
        q = query.lower()
        def _match(row):
            if q in row["name"].lower():
                return True
            partner = row.get("partner")
            if partner and q in partner.username.lower():
                return True
            last = row.get("last")
            if last and q in (last.body or "").lower():
                return True
            return False
        rows = [r for r in rows if _match(r)]

    return render(request, "messaging/inbox.html", {
        "rows": rows,
        "query": query,
        "total_unread": sum(r["unread"] for r in rows),
    })


@login_required
def open_conversation(request, username):
    """Open (or create) a 1-to-1 conversation with `username`."""
    other = get_object_or_404(User.objects.select_related("profile"), username=username)
    if other == request.user:
        raise Http404
    if Block.is_blocked_either_way(request.user, other):
        flash.error(request, "You cannot message this user.")
        return redirect("messaging:inbox")
    conv = Conversation.between(request.user, other)
    return redirect("messaging:thread", pk=conv.pk)


@login_required
def thread(request, pk):
    conv = get_object_or_404(
        Conversation.objects
        .select_related("user_a__profile", "user_b__profile")
        .prefetch_related("participants__profile"),
        pk=pk,
    )
    if not conv.is_participant(request.user):
        raise Http404

    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        if body:
            Message.objects.create(conversation=conv, sender=request.user, body=body)
            recipients = list(conv.participants.exclude(pk=request.user.pk))
            for r in recipients:
                Notification.objects.create(
                    recipient=r, actor=request.user, verb=Notification.MESSAGE,
                )
            return redirect("messaging:thread", pk=conv.pk)
        flash.error(request, "Message cannot be empty.")

    conv.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    raw_messages = list(conv.messages.select_related("sender__profile"))
    # Annotate each message with is_mine + is_continuation (Slack-style grouping).
    annotated = []
    prev_sender_id = None
    for m in raw_messages:
        annotated.append({
            "message": m,
            "is_mine": m.sender_id == request.user.id,
            "is_continuation": (
                conv.is_group and prev_sender_id is not None
                and prev_sender_id == m.sender_id
            ),
        })
        prev_sender_id = m.sender_id

    ctx = {
        "conv": conv,
        "messages_list": annotated,
    }
    if conv.is_group:
        ctx["is_group"] = True
        ctx["group_members"] = list(conv.participants.select_related("profile"))
    else:
        ctx["is_group"] = False
        ctx["partner"] = conv.other(request.user)

    return render(request, "messaging/thread.html", ctx)


@login_required
def group_create(request):
    """Create a new group chat from the user's followers/following list."""
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        member_ids = request.POST.getlist("members")
        if not name:
            flash.error(request, "Please name the group.")
            return redirect("messaging:group_create")
        if len(member_ids) < 1:
            flash.error(request, "Pick at least one person.")
            return redirect("messaging:group_create")
        members = list(
            User.objects.filter(pk__in=member_ids).exclude(pk=request.user.pk)
        )
        # Drop anyone the creator has blocked or who has blocked them.
        members = [m for m in members if not Block.is_blocked_either_way(request.user, m)]
        if not members:
            flash.error(request, "No valid people to add.")
            return redirect("messaging:group_create")
        conv = Conversation.create_group(creator=request.user, name=name, members=members)
        flash.success(request, f"Group “{conv.name}” created.")
        return redirect("messaging:thread", pk=conv.pk)

    # GET: pick from people I follow
    candidates = (
        User.objects.filter(followers__follower=request.user)
        .select_related("profile")
        .order_by("username")
    )
    return render(request, "messaging/group_create.html", {"candidates": candidates})


@login_required
def group_leave(request, pk):
    conv = get_object_or_404(Conversation, pk=pk, is_group=True)
    if not conv.is_participant(request.user):
        return HttpResponseForbidden("Not a member.")
    conv.participants.remove(request.user)
    flash.success(request, f"You left {conv.display_name}.")
    # Drop conv entirely if creator leaves and nobody else is left.
    if conv.participants.count() == 0:
        conv.delete()
    return redirect("messaging:inbox")
