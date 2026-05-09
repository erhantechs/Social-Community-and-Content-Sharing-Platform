"""Account views: signup, login, logout, profile, edit, follow/unfollow, search."""
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from posts.models import Post
from posts.views import annotate_posts

from .forms import LoginForm, ProfileForm, SignUpForm, UserForm
from .models import Block, Follow, Mute

User = get_user_model()


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("posts:feed")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            from .verification import send_verification_email
            sent = send_verification_email(request, user)
            if sent:
                messages.info(
                    request,
                    "Welcome aboard! Check your inbox to verify your email address.",
                )
            else:
                messages.success(request, f"Welcome aboard, {user.username}!")
            return redirect("posts:feed")
    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def resend_verification_email(request):
    """Re-send the verification link if the user hasn't clicked it yet."""
    if request.user.profile.email_verified:
        messages.info(request, "Your email is already verified.")
    else:
        from .verification import send_verification_email
        if send_verification_email(request, request.user):
            messages.success(request, "Verification email sent — check your inbox.")
        else:
            messages.error(request, "Couldn't send the verification email. Please try again later.")
    return redirect("accounts:profile", username=request.user.username)


def verify_email(request, uidb64, token):
    """Click-through endpoint for the verification link in the email."""
    from .verification import consume_token
    user = consume_token(uidb64, token)
    if user is None:
        messages.error(request, "This verification link is invalid or has expired.")
        return redirect("accounts:login")
    profile = user.profile
    if not profile.email_verified:
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])
    messages.success(request, "Email verified — thanks!")
    return redirect("posts:feed")


class CustomLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        from .oauth import is_configured as _oauth_configured
        ctx = super().get_context_data(**kwargs)
        ctx["oauth_google_enabled"] = _oauth_configured("google")
        ctx["oauth_github_enabled"] = _oauth_configured("github")
        return ctx

    def dispatch(self, request, *args, **kwargs):
        from .throttle import is_login_blocked, too_many_attempts_response
        if request.method == "POST" and is_login_blocked(request):
            return too_many_attempts_response()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        from .throttle import reset_login_failures
        reset_login_failures(self.request)
        user = form.get_user()
        # If 2FA is enabled, do NOT log in yet — stash the user_id and bounce
        # to the verification page.
        if getattr(user, "profile", None) and user.profile.two_factor_enabled:
            from .two_factor import stash_pending_login
            stash_pending_login(self.request.session, user.pk)
            self.request.session["tfa_next_url"] = self.get_success_url()
            from django.http import HttpResponseRedirect
            from django.urls import reverse
            return HttpResponseRedirect(reverse("accounts:two_factor_verify"))
        return super().form_valid(form)

    def form_invalid(self, form):
        from .throttle import record_login_failure
        record_login_failure(self.request)
        return super().form_invalid(form)


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You've been logged out.")
    return redirect("accounts:login")


def profile_view(request, username):
    user_obj = get_object_or_404(
        User.objects.select_related("profile").prefetch_related("profile__interests"),
        username=username,
    )

    # If either side has blocked the other, hide the profile from interaction.
    is_blocked = Block.is_blocked_either_way(request.user, user_obj)
    blocked_by_me = (
        request.user.is_authenticated
        and Block.objects.filter(blocker=request.user, blocked=user_obj).exists()
    )
    muted_by_me = (
        request.user.is_authenticated
        and Mute.objects.filter(muter=request.user, muted=user_obj).exists()
    )

    # Profile tabs: Posts (default) / Media / Likes / Reposts / Replies.
    tab = request.GET.get("tab", "posts")
    base_qs = Post.objects.filter(author=user_obj)
    if tab == "media":
        base_qs = base_qs.exclude(image="")
    elif tab == "reposts":
        base_qs = base_qs.exclude(quoted_post__isnull=True)
    elif tab == "likes":
        from posts.models import Like
        liked_ids = Like.objects.filter(user=user_obj).values_list("post_id", flat=True)
        base_qs = Post.objects.filter(pk__in=liked_ids)
    elif tab == "replies":
        from posts.models import Comment
        commented = (
            Comment.objects.filter(author=user_obj)
            .values_list("post_id", flat=True).distinct()
        )
        base_qs = Post.objects.filter(pk__in=commented)
    # else: "posts" — keep default

    # Hide private posts from non-owner; hide friends-only from non-followers.
    # Pinned posts (pinned_at not null) surface first, then chronological.
    from django.db.models import F as _F
    posts_qs = annotate_posts(base_qs, request.user).order_by(
        _F("pinned_at").desc(nulls_last=True), "-created_at",
    )

    if request.user != user_obj:
        if request.user.is_authenticated:
            is_friend = Follow.objects.filter(
                follower=request.user, following=user_obj
            ).exists()
            allowed = [Post.PUBLIC] + ([Post.FRIENDS] if is_friend else [])
        else:
            allowed = [Post.PUBLIC]
        posts_qs = posts_qs.filter(visibility__in=allowed)

    paginator = Paginator(posts_qs, 10)
    page = paginator.get_page(request.GET.get("page"))

    is_following = False
    if request.user.is_authenticated and request.user != user_obj:
        is_following = Follow.objects.filter(
            follower=request.user, following=user_obj
        ).exists()

    context = {
        "profile_user": user_obj,
        "profile": user_obj.profile,
        "posts": page,
        "page_obj": page,
        "is_following": is_following,
        "is_self": request.user == user_obj,
        "is_blocked": is_blocked,
        "blocked_by_me": blocked_by_me,
        "muted_by_me": muted_by_me,
        "active_tab": tab,
        "followers_count": user_obj.followers.count(),
        "following_count": user_obj.following.count(),
    }
    return render(request, "accounts/profile.html", context)


@login_required
@require_POST
def dismiss_onboarding(request):
    """Mark the current user's onboarding modal as seen."""
    profile = request.user.profile
    if not profile.onboarded:
        profile.onboarded = True
        profile.save(update_fields=["onboarded"])
    return JsonResponse({"ok": True})


@login_required
def settings_view(request):
    """Account settings hub — links into edit-profile, blocked, muted, etc."""
    from .oauth import is_configured as _oauth_configured
    blocked_count = Block.objects.filter(blocker=request.user).count()
    muted_count = Mute.objects.filter(muter=request.user).count()
    linked_providers = list(
        request.user.social_accounts.values_list("provider", flat=True)
    )
    return render(request, "accounts/settings.html", {
        "blocked_count": blocked_count,
        "muted_count": muted_count,
        "linked_providers": linked_providers,
        "oauth_google_enabled": _oauth_configured("google"),
        "oauth_github_enabled": _oauth_configured("github"),
    })


@login_required
def edit_profile_view(request):
    profile = request.user.profile
    if request.method == "POST":
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile", username=request.user.username)
        messages.error(request, "Please fix the errors below.")
    else:
        user_form = UserForm(instance=request.user)
        profile_form = ProfileForm(instance=profile)
    return render(
        request,
        "accounts/edit_profile.html",
        {"user_form": user_form, "profile_form": profile_form},
    )


@login_required
@require_POST
def toggle_follow(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return JsonResponse(
            {"ok": False, "error": "You can't follow yourself."}, status=400
        )
    if Block.is_blocked_either_way(request.user, target):
        return JsonResponse(
            {"ok": False, "error": "Cannot follow a blocked user."}, status=400
        )

    follow, created = Follow.objects.get_or_create(
        follower=request.user, following=target
    )
    if not created:
        follow.delete()
        following = False
    else:
        following = True
        # Trigger notification
        from notifications.models import Notification
        Notification.objects.create(
            recipient=target,
            actor=request.user,
            verb=Notification.FOLLOW,
        )

    # Both users' suggestions/feed snapshots are now stale.
    from posts.views import invalidate_sidebar_cache
    invalidate_sidebar_cache(request.user.id)
    invalidate_sidebar_cache(target.id)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "ok": True,
                "following": following,
                "followers_count": target.followers.count(),
            }
        )
    return redirect("accounts:profile", username=target.username)


@login_required
def mention_autocomplete(request):
    """JSON endpoint for the @-mention dropdown.

    Returns up to 8 users matching `q` by username or display name. Excludes
    the current user, excludes anyone they've blocked or who blocked them.
    """
    q = (request.GET.get("q") or "").strip().lstrip("@")
    if len(q) < 1:
        return JsonResponse({"results": []})

    hidden = list(Block.objects.filter(blocker=request.user).values_list("blocked_id", flat=True)) + \
             list(Block.objects.filter(blocked=request.user).values_list("blocker_id", flat=True))

    users = (
        User.objects
        .filter(Q(username__istartswith=q) | Q(profile__display_name__icontains=q))
        .exclude(pk=request.user.pk)
        .exclude(pk__in=hidden)
        .select_related("profile")
        .order_by("username")[:8]
    )
    results = [{
        "username": u.username,
        "name": u.profile.name if hasattr(u, "profile") else u.username,
        "avatar_url": (u.profile.avatar.url if hasattr(u, "profile") and u.profile.avatar else ""),
    } for u in users]
    return JsonResponse({"results": results})


def search_users(request):
    """Search users by username, first name, last name, or display name."""
    q = (request.GET.get("q") or "").strip()
    users = User.objects.none()
    if q:
        users = (
            User.objects.select_related("profile")
            .filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(profile__display_name__icontains=q)
            )
            .annotate(post_count=Count("posts"))[:50]
        )
    return render(request, "accounts/search_users.html", {"query": q, "users": users})


@login_required
@require_POST
def toggle_block(request, username):
    """Block / unblock a user. Blocking also removes any existing follow either way."""
    target = get_object_or_404(User, username=username)
    if target == request.user:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "You can't block yourself."}, status=400)
        messages.error(request, "You can't block yourself.")
        return redirect("accounts:profile", username=target.username)

    block, created = Block.objects.get_or_create(blocker=request.user, blocked=target)
    if not created:
        block.delete()
        is_blocked = False
        messages.info(request, f"You no longer block {target.username}.")
    else:
        # Cascade: remove any follows between the two users.
        Follow.objects.filter(
            Q(follower=request.user, following=target)
            | Q(follower=target, following=request.user)
        ).delete()
        is_blocked = True
        messages.success(request, f"{target.username} is now blocked.")

    # Sidebar suggestions are now stale.
    from posts.views import invalidate_sidebar_cache
    invalidate_sidebar_cache(request.user.id)
    invalidate_sidebar_cache(target.id)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "blocked": is_blocked})
    return redirect("accounts:profile", username=target.username)


@login_required
@require_POST
def toggle_mute(request, username):
    """Mute / unmute a user. One-way, silent — the muted user isn't told."""
    target = get_object_or_404(User, username=username)
    if target == request.user:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Can't mute yourself."}, status=400)
        messages.error(request, "You can't mute yourself.")
        return redirect("accounts:profile", username=target.username)
    mute, created = Mute.objects.get_or_create(muter=request.user, muted=target)
    if not created:
        mute.delete()
        muted = False
        messages.info(request, f"You unmuted {target.username}.")
    else:
        muted = True
        messages.success(request, f"{target.username} is now muted.")
    from posts.views import invalidate_sidebar_cache
    invalidate_sidebar_cache(request.user.id)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "muted": muted})
    return redirect("accounts:profile", username=target.username)


@login_required
def muted_list(request):
    mutes = (
        Mute.objects.filter(muter=request.user)
        .select_related("muted", "muted__profile")
    )
    return render(request, "accounts/muted_list.html", {"mutes": mutes})


@login_required
def blocked_list(request):
    """The currently logged-in user's list of blocked accounts."""
    blocks = (
        Block.objects.filter(blocker=request.user)
        .select_related("blocked", "blocked__profile")
    )
    return render(request, "accounts/blocked_list.html", {"blocks": blocks})


@login_required
def followers_list(request, username):
    user_obj = get_object_or_404(User, username=username)
    follows = (
        Follow.objects.filter(following=user_obj)
        .select_related("follower", "follower__profile")
    )
    return render(
        request,
        "accounts/follow_list.html",
        {
            "profile_user": user_obj,
            "follows": follows,
            "list_type": "Followers",
            "use_field": "follower",
        },
    )


@login_required
def following_list(request, username):
    user_obj = get_object_or_404(User, username=username)
    follows = (
        Follow.objects.filter(follower=user_obj)
        .select_related("following", "following__profile")
    )
    return render(
        request,
        "accounts/follow_list.html",
        {
            "profile_user": user_obj,
            "follows": follows,
            "list_type": "Following",
            "use_field": "following",
        },
    )
