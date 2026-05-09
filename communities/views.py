"""Community views: list, detail, create, manage, join/leave, events."""
from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CommunityEventForm, CommunityForm
from .models import Community, CommunityEvent, CommunityMember, EventRSVP


def community_list(request):
    """All public communities + the current user's joined communities.

    Each card surfaces a small avatar stack of up to 4 active members so the
    grid feels populated at a glance. We fetch members in a separate query
    (one per page of communities) rather than via Prefetch + Python slicing,
    to keep the SQL clean.
    """
    qs = Community.objects.annotate(
        members_count=Count("memberships", filter=Q(memberships__status=CommunityMember.ACTIVE))
    ).filter(privacy=Community.PUBLIC)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
    qs = qs.order_by("-members_count", "-created_at")

    my_communities = []
    if request.user.is_authenticated:
        my_communities = list(
            Community.objects
            .filter(memberships__user=request.user, memberships__status=CommunityMember.ACTIVE)
            .annotate(members_count=Count("memberships", filter=Q(memberships__status=CommunityMember.ACTIVE)))
            .order_by("name")[:20]
        )

    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get("page"))

    # Attach up to 4 preview members to each community on the current page.
    page_ids = [c.id for c in page.object_list]
    if page_ids:
        all_active = (
            CommunityMember.objects
            .filter(community_id__in=page_ids, status=CommunityMember.ACTIVE)
            .select_related("user__profile")
            .order_by("community_id", "-role", "joined_at")
        )
        by_community = {}
        for m in all_active:
            by_community.setdefault(m.community_id, []).append(m)
        for c in page.object_list:
            c.preview_members = by_community.get(c.id, [])[:4]

    return render(request, "communities/list.html", {
        "communities": page,
        "page_obj": page,
        "my_communities": my_communities,
        "query": q,
    })


def community_detail(request, slug):
    community = get_object_or_404(Community, slug=slug)
    role = community.role_of(request.user)
    is_member = role is not None
    is_admin = role in (CommunityMember.OWNER, CommunityMember.ADMIN)
    has_pending = community.has_pending_request(request.user)

    from django.db.models import F as _F
    posts_qs = community.posts.select_related("author", "author__profile") \
        .prefetch_related("hashtags", "extra_images") \
        .order_by(_F("pinned_at").desc(nulls_last=True), "-created_at")
    if community.privacy == Community.PRIVATE and not is_member:
        posts_qs = posts_qs.none()

    paginator = Paginator(posts_qs, 10)
    page = paginator.get_page(request.GET.get("page"))

    members = community.memberships.filter(status=CommunityMember.ACTIVE) \
        .select_related("user__profile") \
        .order_by("-role", "joined_at")[:8]

    from django.utils import timezone as _tz
    upcoming_events = community.events.filter(starts_at__gte=_tz.now()).order_by("starts_at")[:3]

    return render(request, "communities/detail.html", {
        "community": community,
        "posts": page,
        "page_obj": page,
        "is_member": is_member,
        "is_admin": is_admin,
        "role": role,
        "has_pending": has_pending,
        "members_preview": members,
        "upcoming_events": upcoming_events,
    })


@login_required
def community_create(request):
    if request.method == "POST":
        form = CommunityForm(request.POST, request.FILES)
        if form.is_valid():
            community = form.save(commit=False)
            community.owner = request.user
            community.save()
            CommunityMember.objects.create(
                community=community,
                user=request.user,
                role=CommunityMember.OWNER,
                status=CommunityMember.ACTIVE,
            )
            flash.success(request, f"{community.name} created.")
            return redirect("communities:detail", slug=community.slug)
    else:
        form = CommunityForm()
    return render(request, "communities/form.html", {
        "form": form,
        "title": "New community",
    })


@login_required
@require_POST
def community_join(request, slug):
    community = get_object_or_404(Community, slug=slug)
    existing = CommunityMember.objects.filter(community=community, user=request.user).first()
    if existing:
        if existing.status == CommunityMember.BANNED:
            flash.error(request, "You are banned from this community.")
            return redirect("communities:detail", slug=slug)
        if existing.status == CommunityMember.PENDING:
            flash.info(request, "Your request is pending approval.")
            return redirect("communities:detail", slug=slug)
        flash.info(request, "You're already a member.")
        return redirect("communities:detail", slug=slug)

    status = CommunityMember.PENDING if community.privacy == Community.PRIVATE else CommunityMember.ACTIVE
    CommunityMember.objects.create(
        community=community,
        user=request.user,
        role=CommunityMember.MEMBER,
        status=status,
    )
    if status == CommunityMember.PENDING:
        flash.success(request, f"Membership request sent to {community.name}.")
    else:
        flash.success(request, f"Welcome to {community.name}!")
    return redirect("communities:detail", slug=slug)


@login_required
@require_POST
def community_leave(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if community.owner_id == request.user.id:
        flash.error(request, "Owners cannot leave their own community. Transfer ownership or delete it instead.")
        return redirect("communities:detail", slug=slug)
    deleted, _ = CommunityMember.objects.filter(community=community, user=request.user).delete()
    if deleted:
        flash.success(request, f"You left {community.name}.")
    return redirect("communities:detail", slug=slug)


@login_required
def community_manage(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if not community.is_admin(request.user):
        return HttpResponseForbidden("Only admins can manage this community.")

    if request.method == "POST":
        form = CommunityForm(request.POST, request.FILES, instance=community)
        if form.is_valid():
            form.save()
            flash.success(request, "Community updated.")
            return redirect("communities:detail", slug=community.slug)
    else:
        form = CommunityForm(instance=community)

    members = community.memberships.select_related("user__profile").order_by("-role", "joined_at")
    return render(request, "communities/manage.html", {
        "community": community,
        "form": form,
        "members": members,
    })


@login_required
@require_POST
def member_action(request, slug, user_id):
    """Promote/demote/remove a member. Owner-only operations are gated."""
    community = get_object_or_404(Community, slug=slug)
    if not community.is_admin(request.user):
        return HttpResponseForbidden("Forbidden.")

    membership = get_object_or_404(CommunityMember, community=community, user_id=user_id)
    action = request.POST.get("action")
    is_owner_acting = community.owner_id == request.user.id

    if action == "approve":
        membership.status = CommunityMember.ACTIVE
        membership.save(update_fields=["status"])
        flash.success(request, f"{membership.user.username} approved.")
    elif action == "ban":
        if membership.role == CommunityMember.OWNER:
            return HttpResponseForbidden("Cannot ban the owner.")
        membership.status = CommunityMember.BANNED
        membership.save(update_fields=["status"])
        flash.success(request, f"{membership.user.username} banned.")
    elif action == "remove":
        if membership.role == CommunityMember.OWNER:
            return HttpResponseForbidden("Cannot remove the owner.")
        membership.delete()
        flash.success(request, "Member removed.")
    elif action == "promote" and is_owner_acting:
        if membership.role == CommunityMember.MEMBER:
            membership.role = CommunityMember.ADMIN
            membership.save(update_fields=["role"])
            flash.success(request, f"{membership.user.username} promoted to admin.")
    elif action == "demote" and is_owner_acting:
        if membership.role == CommunityMember.ADMIN:
            membership.role = CommunityMember.MEMBER
            membership.save(update_fields=["role"])
            flash.success(request, f"{membership.user.username} demoted.")

    return redirect("communities:manage", slug=slug)


# ----- Events --------------------------------------------------------------

def event_list(request, slug):
    """All events for a community, split into upcoming + past."""
    community = get_object_or_404(Community, slug=slug)
    if community.privacy == Community.PRIVATE and not community.is_member(request.user):
        return HttpResponseForbidden("This community is private.")

    now = timezone.now()
    upcoming = community.events.filter(starts_at__gte=now).order_by("starts_at")
    past = community.events.filter(starts_at__lt=now).order_by("-starts_at")[:20]

    return render(request, "communities/events_list.html", {
        "community": community,
        "upcoming_events": upcoming,
        "past_events": past,
        "is_admin": community.is_admin(request.user),
    })


@login_required
def event_create(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if not community.is_admin(request.user):
        return HttpResponseForbidden("Only admins can create events.")
    if request.method == "POST":
        form = CommunityEventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.community = community
            event.created_by = request.user
            event.save()
            flash.success(request, f"Event \"{event.title}\" created.")
            return redirect("communities:event_detail", slug=slug, event_id=event.pk)
    else:
        form = CommunityEventForm()
    return render(request, "communities/event_form.html", {
        "community": community,
        "form": form,
        "title": "New event",
    })


def event_detail(request, slug, event_id):
    community = get_object_or_404(Community, slug=slug)
    if community.privacy == Community.PRIVATE and not community.is_member(request.user):
        return HttpResponseForbidden("This community is private.")
    event = get_object_or_404(CommunityEvent, pk=event_id, community=community)
    rsvps = event.rsvps.filter(status=EventRSVP.GOING).select_related("user__profile")[:12]
    my_status = event.rsvp_status_for(request.user)
    return render(request, "communities/event_detail.html", {
        "community": community,
        "event": event,
        "rsvps": rsvps,
        "my_status": my_status,
        "is_admin": community.is_admin(request.user),
    })


@login_required
@require_POST
def event_rsvp(request, slug, event_id):
    community = get_object_or_404(Community, slug=slug)
    event = get_object_or_404(CommunityEvent, pk=event_id, community=community)
    if community.privacy == Community.PRIVATE and not community.is_member(request.user):
        return HttpResponseForbidden("Join the community to RSVP.")

    status = request.POST.get("status", EventRSVP.GOING)
    valid = {s for s, _ in EventRSVP.STATUS_CHOICES}
    if status not in valid:
        status = EventRSVP.GOING

    rsvp, created = EventRSVP.objects.get_or_create(
        event=event, user=request.user, defaults={"status": status},
    )
    if not created:
        if rsvp.status == status:
            rsvp.delete()
            new_status = None
        else:
            rsvp.status = status
            rsvp.save(update_fields=["status", "updated_at"])
            new_status = status
    else:
        new_status = status

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "status": new_status,
            "going_count": event.rsvp_count,
        })
    return redirect("communities:event_detail", slug=slug, event_id=event_id)


@login_required
@require_POST
def event_delete(request, slug, event_id):
    community = get_object_or_404(Community, slug=slug)
    if not community.is_admin(request.user):
        return HttpResponseForbidden("Only admins can delete events.")
    event = get_object_or_404(CommunityEvent, pk=event_id, community=community)
    title = event.title
    event.delete()
    flash.success(request, f"Event \"{title}\" deleted.")
    return redirect("communities:event_list", slug=slug)
