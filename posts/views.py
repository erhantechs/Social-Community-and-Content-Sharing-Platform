"""Post views: feed, explore, detail, create/update/delete, comments, likes, stories."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import DeleteView, UpdateView

from accounts.models import Block, Follow, Interest, Mute
from notifications.models import Notification

from .forms import CommentForm, DraftForm, PollCreateForm, PostForm, QuickPostForm, RepostForm, StoryForm
from .models import (
    Bookmark, Comment, CommentLike, Hashtag, HashtagFollow, Like,
    Poll, PollOption, PollVote, Post, PostDraft, Story,
)
from .templatetags.post_extras import extract_hashtags, extract_mentions

User = get_user_model()


def _attach_hashtags(post, body):
    """Extract `#tags` from body and attach matching Hashtag rows to `post`.

    Creates new Hashtag rows on the fly. Replaces (not extends) the post's
    current hashtag set so editing a post stays consistent.
    """
    if not body:
        post.hashtags.clear()
        return
    tag_slugs = extract_hashtags(body)
    if not tag_slugs:
        post.hashtags.clear()
        return
    tags = []
    for slug in tag_slugs:
        tag, _ = Hashtag.objects.get_or_create(
            slug=slug.lower()[:80],
            defaults={"name": slug.lower()[:80]},
        )
        tags.append(tag)
    post.hashtags.set(tags)


def _notify_mentions(actor, body, post=None):
    """Send a 'mention' notification to every @username found in `body`.

    Skips the actor themselves, ignores usernames that don't exist, and never
    notifies someone who has blocked (or been blocked by) the actor.
    """
    if not body:
        return
    usernames = extract_mentions(body)
    if not usernames:
        return
    blocked_either_way = list(
        Block.objects.filter(blocker=actor).values_list("blocked_id", flat=True)
    ) + list(
        Block.objects.filter(blocked=actor).values_list("blocker_id", flat=True)
    )
    targets = (
        User.objects.filter(username__in=usernames)
        .exclude(pk=actor.pk)
        .exclude(pk__in=blocked_either_way)
    )
    for u in targets:
        Notification.objects.create(
            recipient=u, actor=actor, verb=Notification.MENTION, post=post,
        )


# ---------- helpers ----------

def annotate_posts(qs, user):
    """Attach like/comment counts and 'liked-by-current-user' flag in one query.

    Uses Subquery counts (not joined Count) so multiple M2M annotations don't
    inflate each other's totals via cartesian joins — a known Django pitfall.
    """
    from django.db.models import IntegerField, Subquery
    like_count_sub = (
        Like.objects.filter(post=OuterRef("pk"))
        .order_by()
        .values("post")
        .annotate(c=Count("*"))
        .values("c")
    )
    comment_count_sub = (
        Comment.objects.filter(post=OuterRef("pk"))
        .order_by()
        .values("post")
        .annotate(c=Count("*"))
        .values("c")
    )
    qs = qs.select_related("author", "author__profile").prefetch_related(
        "extra_images", "interests"
    ).annotate(
        like_count=Coalesce(Subquery(like_count_sub, output_field=IntegerField()), 0),
        comment_count=Coalesce(Subquery(comment_count_sub, output_field=IntegerField()), 0),
    )
    if user.is_authenticated:
        liked = Like.objects.filter(user=user, post=OuterRef("pk"))
        bookmarked = Bookmark.objects.filter(user=user, post=OuterRef("pk"))
        qs = qs.annotate(
            is_liked=Exists(liked),
            is_bookmarked=Exists(bookmarked),
        )
    return qs


# Backwards-compatible alias for older call sites.
def _annotate_posts(qs, request):
    return annotate_posts(qs, request.user)


def _suggestions_for(user, limit=3, pool_size=15):
    """People to follow — random sample from the most popular candidates.

    We pick the top `pool_size` users by follower count and then randomly
    sample `limit` from that pool. This way the sidebar suggests popular
    accounts but rotates them, so visitors don't see the same three every
    time the (60s-TTL) cache misses.
    """
    import random as _random
    qs = (
        User.objects.select_related("profile")
        .annotate(follower_count=Count("followers"))
    )
    if user.is_authenticated:
        already = Follow.objects.filter(follower=user).values_list("following_id", flat=True)
        qs = qs.exclude(id__in=already).exclude(id=user.id)
    pool = list(qs.order_by("-follower_count")[:pool_size])
    if len(pool) <= limit:
        return pool
    return _random.sample(pool, limit)


SIDEBAR_CACHE_TTL = 60  # seconds — short, since "Suggestions" should refresh as you follow people.


def _sidebar_context(request):
    """Right-sidebar data: stories, suggestions, interest recommendations.

    Per-user cached for 60 seconds — long enough to spare DB hits when a user
    clicks around quickly, short enough that follows/unfollows feel responsive.
    """
    user_id = request.user.id if request.user.is_authenticated else "anon"
    cache_key = f"sidebar:v2:{user_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    trending = list(
        Hashtag.objects
        .annotate(c=Count("posts"))
        .filter(c__gt=0)
        .order_by("-c", "-created_at")[:5]
    )
    data = {
        "stories": list(
            Story.active()
            .select_related("author", "author__profile")
            .order_by("-created_at")[:2]
        ),
        "suggestions": list(_suggestions_for(request.user, limit=3)),
        "recommendations": list(Interest.objects.all()[:8]),
        "trending_hashtags": trending,
    }
    cache.set(cache_key, data, SIDEBAR_CACHE_TTL)
    return data


def invalidate_sidebar_cache(user_id):
    """Drop a user's cached sidebar — call after follow/unfollow toggles."""
    cache.delete(f"sidebar:v2:{user_id}")


# ---------- feed / explore ----------

@login_required
def feed_view(request):
    """Home/feed page: posts from people the user follows, plus their own,
    plus public posts that carry a hashtag the user is following."""
    following_ids = list(
        Follow.objects.filter(follower=request.user).values_list("following_id", flat=True)
    )
    followed_tag_ids = list(
        HashtagFollow.objects.filter(user=request.user).values_list("hashtag_id", flat=True)
    )
    base_q = Q(author__in=following_ids) | Q(author=request.user)
    if followed_tag_ids:
        base_q |= Q(hashtags__in=followed_tag_ids, visibility=Post.PUBLIC)
    posts_qs = Post.objects.filter(base_q).distinct()

    # Belt-and-braces: blocking removes follows, but exclude here too in case
    # a Block was added without going through the toggle_block view.
    # Also hide muted users from the feed (mute is silent — they're not told).
    hidden_ids = Block.hidden_user_ids_for(request.user) + Mute.muted_user_ids_for(request.user)
    if hidden_ids:
        posts_qs = posts_qs.exclude(author_id__in=hidden_ids)

    # Filter tab: Recents (default) | Friends | Popular
    tab = request.GET.get("tab", "recents")
    if tab == "popular":
        posts_qs = posts_qs.order_by("-id")
        posts_qs = _annotate_posts(posts_qs, request).order_by(
            "-like_count", "-created_at"
        )
    elif tab == "friends":
        # Friends tab is strictly people you follow — no hashtag spillover.
        posts_qs = Post.objects.filter(author__in=following_ids)
        if hidden_ids:
            posts_qs = posts_qs.exclude(author_id__in=hidden_ids)
        posts_qs = _annotate_posts(posts_qs, request).order_by("-created_at")
    else:
        posts_qs = _annotate_posts(posts_qs, request).order_by("-created_at")

    paginator = Paginator(posts_qs, 10)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "posts": page,
        "page_obj": page,
        "active_tab": tab,
        "quick_form": QuickPostForm(),
        "is_explore": False,
        **_sidebar_context(request),
    }
    return render(request, "posts/feed.html", context)


def explore_view(request):
    """Public explore page — all recent public posts."""
    posts_qs = Post.objects.filter(visibility=Post.PUBLIC)

    # Hide posts from anyone the current user has blocked (or muted, or who has blocked them).
    hidden_ids = Block.hidden_user_ids_for(request.user) + Mute.muted_user_ids_for(request.user)
    if hidden_ids:
        posts_qs = posts_qs.exclude(author_id__in=hidden_ids)

    interest_slug = request.GET.get("interest")
    if interest_slug:
        posts_qs = posts_qs.filter(interests__slug=interest_slug)

    posts_qs = _annotate_posts(posts_qs, request).order_by("-created_at")

    paginator = Paginator(posts_qs, 12)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "posts": page,
        "page_obj": page,
        "active_tab": "explore",
        "quick_form": QuickPostForm() if request.user.is_authenticated else None,
        "is_explore": True,
        "current_interest": interest_slug,
        **_sidebar_context(request),
    }
    return render(request, "posts/explore.html", context)


# ---------- post CRUD ----------

@login_required
def post_create(request):
    """Full post-create form (separate page).

    Two side-paths:
      ?draft=<id>      pre-fill from an existing draft (ownership-checked).
      ?community=<sl>  pre-select a community the user is a member of.
    On a successful publish, any draft passed via the hidden `draft_id`
    field is deleted (the draft becomes a Post).
    """
    draft = None
    draft_id = request.POST.get("draft_id") or request.GET.get("draft")
    if draft_id:
        draft = PostDraft.objects.filter(pk=draft_id, author=request.user).first()

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, user=request.user)
        poll_form = PollCreateForm(request.POST)
        if form.is_valid() and poll_form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m()
            _attach_hashtags(post, post.body)
            poll_form.attach_to(post)
            _notify_mentions(request.user, post.body, post=post)
            if draft:
                draft.delete()
            messages.success(request, "Post published.")
            return redirect("posts:detail", pk=post.pk)
    else:
        initial = {}
        if draft:
            initial = {
                "body": draft.body,
                "location": draft.location,
                "visibility": draft.visibility,
                "community": draft.community,
            }
        community_slug = request.GET.get("community")
        if community_slug and not draft:
            from communities.models import Community
            community = Community.objects.filter(slug=community_slug).first()
            if community and community.is_member(request.user):
                initial["community"] = community
        form = PostForm(initial=initial, user=request.user)
        poll_form = PollCreateForm()
    return render(request, "posts/post_form.html", {
        "form": form,
        "poll_form": poll_form,
        "title": "New post",
        "draft": draft,
    })


# ---------- drafts ----------

@login_required
def draft_list(request):
    """List the current user's saved drafts."""
    drafts = PostDraft.objects.filter(author=request.user)
    return render(request, "posts/drafts.html", {"drafts": drafts})


@login_required
def draft_save(request):
    """Save a new draft (or update an existing one). Renders/redirects to the
    draft list. Used by the explicit "Save as draft" button on the post form."""
    if request.method != "POST":
        return redirect("posts:draft_list")
    draft_id = request.POST.get("draft_id") or None
    instance = None
    if draft_id:
        instance = PostDraft.objects.filter(pk=draft_id, author=request.user).first()
    form = DraftForm(request.POST, request.FILES, instance=instance, user=request.user)
    if form.is_valid():
        draft = form.save(commit=False)
        draft.author = request.user
        draft.save()
        messages.success(request, "Draft saved.")
        return redirect("posts:draft_list")
    # If invalid (very unlikely — drafts are permissive) fall back to feed.
    messages.error(request, "Couldn't save draft.")
    return redirect(request.META.get("HTTP_REFERER") or "posts:feed")


@login_required
@require_POST
def draft_delete(request, pk):
    draft = get_object_or_404(PostDraft, pk=pk, author=request.user)
    draft.delete()
    messages.success(request, "Draft deleted.")
    return redirect("posts:draft_list")


# ---------- pinned posts ----------

@login_required
@require_POST
def toggle_pin(request, pk):
    """Pin or unpin a post.

    Permission: post author OR (if the post is in a community) a community
    admin/owner. Same `pinned_at` field serves both profile and community
    contexts — pinned posts surface first wherever they're listed.
    """
    post = get_object_or_404(Post, pk=pk)
    is_author = post.author_id == request.user.id
    is_community_admin = bool(
        post.community_id and post.community.is_admin(request.user)
    )
    if not (is_author or is_community_admin):
        return HttpResponseForbidden("You can't pin this post.")

    from django.utils import timezone as _tz
    if post.pinned_at:
        post.pinned_at = None
        pinned = False
    else:
        post.pinned_at = _tz.now()
        pinned = True
    post.save(update_fields=["pinned_at"])

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "pinned": pinned})
    messages.success(request, "Pinned." if pinned else "Unpinned.")
    return redirect(request.META.get("HTTP_REFERER") or post.get_absolute_url())


# ---------- hashtag follow ----------

@login_required
@require_POST
def toggle_hashtag_follow(request, slug):
    tag = get_object_or_404(Hashtag, slug=slug.lower())
    follow, created = HashtagFollow.objects.get_or_create(user=request.user, hashtag=tag)
    if not created:
        follow.delete()
        following = False
    else:
        following = True
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "following": following})
    messages.success(
        request,
        f"You're now following #{tag.name}." if following else f"Unfollowed #{tag.name}.",
    )
    return redirect("posts:tag", slug=tag.slug)


@login_required
@require_POST
def quick_post_create(request):
    """Compact composer at the bottom of the feed."""
    form = QuickPostForm(request.POST, request.FILES)
    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        _attach_hashtags(post, post.body)
        _notify_mentions(request.user, post.body, post=post)
        messages.success(request, "Post shared.")
    else:
        for errs in form.errors.values():
            for err in errs:
                messages.error(request, err)
    return redirect(request.META.get("HTTP_REFERER") or "posts:feed")


def post_detail(request, pk):
    qs = Post.objects.select_related("author", "author__profile").prefetch_related(
        "extra_images", "interests",
        "comments__author__profile",
    )
    post = get_object_or_404(qs, pk=pk)

    # Visibility check
    if post.visibility == Post.PRIVATE and post.author != request.user:
        raise Http404
    if post.visibility == Post.FRIENDS and request.user.is_authenticated:
        is_friend = Follow.objects.filter(
            follower=request.user, following=post.author
        ).exists()
        if not is_friend and post.author != request.user:
            raise Http404
    elif post.visibility == Post.FRIENDS and not request.user.is_authenticated:
        raise Http404

    comment_form = CommentForm()
    is_liked = post.is_liked_by(request.user)

    # Hide comments (and their replies) from blocked users in either direction.
    hidden_ids = Block.hidden_user_ids_for(request.user)
    top_level_comments = (
        post.comments
        .filter(parent__isnull=True)
        .exclude(author_id__in=hidden_ids)
        .select_related("author", "author__profile")
        .prefetch_related("replies__author__profile", "comment_likes", "replies__comment_likes")
    )

    context = {
        "post": post,
        "comments": top_level_comments,
        "comment_form": comment_form,
        "is_liked": is_liked,
        "likes_count": post.likes.count(),
        **_sidebar_context(request),
    }
    return render(request, "posts/post_detail.html", context)


class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = "posts/post_form.html"

    def test_func(self):
        return self.get_object().author == self.request.user

    def handle_no_permission(self):
        return HttpResponseForbidden("You can't edit a post you don't own.")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Edit post"
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        _attach_hashtags(self.object, self.object.body)
        messages.success(self.request, "Post updated.")
        return response


class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Post
    template_name = "posts/post_confirm_delete.html"
    success_url = reverse_lazy("posts:feed")

    def test_func(self):
        return self.get_object().author == self.request.user

    def handle_no_permission(self):
        return HttpResponseForbidden("You can't delete a post you don't own.")

    def form_valid(self, form):
        messages.success(self.request, "Post deleted.")
        return super().form_valid(form)


# ---------- like ----------

@login_required
@require_POST
def toggle_like(request, pk):
    """Toggle a reaction on a post.

    Accepts an optional `emoji` POST/GET param. When the same emoji is sent
    twice, the reaction is removed; sending a different emoji updates the
    existing reaction in place. No emoji => default heart.
    """
    post = get_object_or_404(Post, pk=pk)
    valid_emojis = {e for e, _ in Like.EMOJI_CHOICES}
    requested = (request.POST.get("emoji") or request.GET.get("emoji") or Like.HEART).lower()
    if requested not in valid_emojis:
        requested = Like.HEART

    existing = Like.objects.filter(user=request.user, post=post).first()
    notify = False
    if existing is None:
        Like.objects.create(user=request.user, post=post, emoji=requested)
        liked = True
        active_emoji = requested
        notify = post.author != request.user
    elif existing.emoji == requested:
        existing.delete()
        liked = False
        active_emoji = None
    else:
        existing.emoji = requested
        existing.save(update_fields=["emoji"])
        liked = True
        active_emoji = requested

    if notify:
        Notification.objects.create(
            recipient=post.author,
            actor=request.user,
            verb=Notification.LIKE,
            post=post,
        )

    # Aggregate breakdown for the new picker UI.
    breakdown = dict(
        Like.objects.filter(post=post).values_list("emoji").annotate(c=Count("emoji"))
        .values_list("emoji", "c")
    )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "liked": liked,
            "emoji": active_emoji,
            "likes_count": post.likes.count(),
            "breakdown": breakdown,
        })
    return redirect(request.META.get("HTTP_REFERER") or post.get_absolute_url())


# ---------- reposts ----------

@login_required
def post_repost(request, pk):
    """Quote or pure-repost an existing post.

    GET:  show a small form with the original post embedded.
    POST: create a new Post pointing at `quoted_post = original`.
    """
    original = get_object_or_404(
        Post.objects.select_related("author", "author__profile"),
        pk=pk,
    )

    # Don't let people repost private/friends-only posts they shouldn't see.
    if original.visibility == Post.PRIVATE and original.author != request.user:
        raise Http404
    if original.visibility == Post.FRIENDS and original.author != request.user:
        is_friend = Follow.objects.filter(
            follower=request.user, following=original.author
        ).exists()
        if not is_friend:
            raise Http404

    # Block check — can't repost from someone you've blocked or vice versa.
    if Block.is_blocked_either_way(request.user, original.author):
        raise Http404

    # Don't repost a repost — collapse to the underlying post.
    target = original.quoted_post if original.is_repost else original

    if request.method == "POST":
        form = RepostForm(request.POST)
        if form.is_valid():
            new_post = form.save(commit=False)
            new_post.author = request.user
            new_post.quoted_post = target
            new_post.save()
            _notify_mentions(request.user, new_post.body, post=new_post)

            # Notify the original author (unless self-repost).
            if target.author != request.user:
                Notification.objects.create(
                    recipient=target.author,
                    actor=request.user,
                    verb=Notification.COMMENT,   # closest verb in current model
                    post=target,
                )

            messages.success(request, "Reposted.")
            return redirect("posts:detail", pk=new_post.pk)
    else:
        form = RepostForm()

    return render(request, "posts/post_repost.html", {
        "form": form,
        "original": target,
    })


# ---------- bookmarks ----------

@login_required
@require_POST
def toggle_bookmark(request, pk):
    post = get_object_or_404(Post, pk=pk)
    bm, created = Bookmark.objects.get_or_create(user=request.user, post=post)
    if not created:
        bm.delete()
        bookmarked = False
    else:
        bookmarked = True
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "bookmarked": bookmarked})
    return redirect(request.META.get("HTTP_REFERER") or post.get_absolute_url())


@login_required
def saved_posts(request):
    """Posts the current user has bookmarked."""
    posts_qs = annotate_posts(
        Post.objects.filter(bookmarks__user=request.user),
        request.user,
    ).order_by("-bookmarks__created_at")

    paginator = Paginator(posts_qs, 12)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "posts/saved.html", {
        "posts": page, "page_obj": page,
        **_sidebar_context(request),
    })


# ---------- comments ----------

@login_required
@require_POST
def comment_create(request, pk):
    post = get_object_or_404(Post, pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        # Optional reply target — must belong to this same post.
        parent_id = request.POST.get("parent_id")
        if parent_id:
            parent = Comment.objects.filter(pk=parent_id, post=post).first()
            if parent:
                # Flatten replies to a reply onto the original comment so the
                # tree never gets deeper than one level.
                comment.parent = parent.parent or parent
        comment.save()
        if post.author != request.user:
            Notification.objects.create(
                recipient=post.author,
                actor=request.user,
                verb=Notification.COMMENT,
                post=post,
            )
        # Notify the author of the comment we're replying to (if different).
        if comment.parent and comment.parent.author not in (request.user, post.author):
            Notification.objects.create(
                recipient=comment.parent.author,
                actor=request.user,
                verb=Notification.COMMENT,
                post=post,
            )
        _notify_mentions(request.user, comment.body, post=post)
        messages.success(request, "Comment added.")
    else:
        for errs in form.errors.values():
            for err in errs:
                messages.error(request, err)
    return redirect("posts:detail", pk=post.pk)


@login_required
@require_POST
def toggle_comment_like(request, pk):
    """AJAX-friendly toggle for comment likes."""
    comment = get_object_or_404(Comment, pk=pk)
    like, created = CommentLike.objects.get_or_create(user=request.user, comment=comment)
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True, "liked": liked,
            "likes_count": comment.comment_likes.count(),
        })
    return redirect(request.META.get("HTTP_REFERER")
                    or comment.post.get_absolute_url())


@login_required
@require_POST
def comment_edit(request, pk):
    """Edit your own comment. Body is replaced, `edited` flag is set."""
    comment = get_object_or_404(Comment, pk=pk)
    if comment.author != request.user:
        return HttpResponseForbidden("You can only edit your own comments.")
    new_body = (request.POST.get("body") or "").strip()
    if not new_body:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Empty"}, status=400)
        messages.error(request, "Comment can't be empty.")
        return redirect("posts:detail", pk=comment.post.pk)
    comment.body = new_body[:1000]
    comment.edited = True
    comment.save(update_fields=["body", "edited", "updated_at"])
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        from .templatetags.post_extras import linkify_post
        return JsonResponse({"ok": True, "body_html": linkify_post(comment.body), "edited": True})
    messages.success(request, "Comment updated.")
    return redirect("posts:detail", pk=comment.post.pk)


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if comment.author != request.user and comment.post.author != request.user:
        return HttpResponseForbidden("You can only delete your own comments.")
    post_pk = comment.post.pk
    comment.delete()
    messages.success(request, "Comment deleted.")
    return redirect("posts:detail", pk=post_pk)


# ---------- stories ----------

@login_required
def story_create(request):
    if request.method == "POST":
        form = StoryForm(request.POST, request.FILES)
        if form.is_valid():
            story = form.save(commit=False)
            story.author = request.user
            story.save()
            # Drop everyone's cached sidebar so the new story appears immediately
            # for followers viewing the feed.
            cache.delete_pattern = getattr(cache, "delete_pattern", None)
            invalidate_sidebar_cache(request.user.id)
            messages.success(request, "Story posted.")
            return redirect("posts:feed")
    else:
        form = StoryForm()
    return render(request, "posts/story_form.html", {"form": form})


# ---------- hashtags ----------

def tag_view(request, slug):
    """Posts tagged with a specific hashtag."""
    tag = get_object_or_404(Hashtag, slug=slug.lower())
    hidden_ids = Block.hidden_user_ids_for(request.user) + Mute.muted_user_ids_for(request.user)
    posts_qs = (
        Post.objects.filter(hashtags=tag, visibility=Post.PUBLIC)
        .exclude(author_id__in=hidden_ids)
    )
    posts_qs = annotate_posts(posts_qs, request.user).order_by("-created_at")
    paginator = Paginator(posts_qs, 12)
    page = paginator.get_page(request.GET.get("page"))
    is_followed = (
        request.user.is_authenticated
        and HashtagFollow.objects.filter(user=request.user, hashtag=tag).exists()
    )
    follower_count = tag.followers.count()
    return render(request, "posts/tag.html", {
        "tag": tag,
        "posts": page, "page_obj": page,
        "is_followed": is_followed,
        "follower_count": follower_count,
        **_sidebar_context(request),
    })


# ---------- polls ----------

@login_required
@require_POST
def poll_vote(request, pk):
    """Cast (or change) a vote on a poll. `pk` is the Poll id; the option(s)
    come in the POST body as `option_id` (single) or `option_ids` (multiple).
    """
    poll = get_object_or_404(Poll.objects.select_related("post"), pk=pk)
    if poll.is_closed:
        return JsonResponse({"ok": False, "error": "Poll is closed."}, status=400)

    raw_ids = request.POST.getlist("option_ids") or [request.POST.get("option_id")]
    raw_ids = [i for i in raw_ids if i]
    if not raw_ids:
        return JsonResponse({"ok": False, "error": "No option selected."}, status=400)
    if not poll.multiple_choice and len(raw_ids) > 1:
        raw_ids = raw_ids[:1]

    valid_ids = list(poll.options.filter(pk__in=raw_ids).values_list("pk", flat=True))
    if not valid_ids:
        return JsonResponse({"ok": False, "error": "Invalid option(s)."}, status=400)

    PollVote.objects.filter(option__poll=poll, user=request.user).delete()
    for opt_id in valid_ids:
        PollVote.objects.create(option_id=opt_id, user=request.user)

    breakdown = []
    total = poll.total_votes
    for opt in poll.options.all():
        vc = opt.vote_count
        breakdown.append({
            "id": opt.id,
            "text": opt.text,
            "votes": vc,
            "percent": round(vc * 100 / total) if total else 0,
        })

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "total": total,
            "voted_for": valid_ids,
            "options": breakdown,
            "is_closed": poll.is_closed,
        })
    return redirect(poll.post.get_absolute_url())


# ---------- search ----------

def search_posts(request):
    q = (request.GET.get("q") or "").strip()
    hidden_ids = Block.hidden_user_ids_for(request.user)
    posts = Post.objects.none()
    if q:
        # `#tag` searches are anchored on body — prefix preserved so
        # users can paste a hashtag link verbatim.
        if q.startswith("#"):
            tag = q.lstrip("#").strip()
            posts = (
                Post.objects.filter(visibility=Post.PUBLIC)
                .filter(Q(body__icontains=f"#{tag}") | Q(interests__name__iexact=tag))
                .distinct()
            )
        else:
            posts = (
                Post.objects.filter(visibility=Post.PUBLIC)
                .filter(
                    Q(body__icontains=q)
                    | Q(location__icontains=q)
                    | Q(author__username__icontains=q)
                    | Q(interests__name__icontains=q)
                )
                .distinct()
            )
        if hidden_ids:
            posts = posts.exclude(author_id__in=hidden_ids)
        posts = annotate_posts(posts, request.user).order_by("-created_at")

    paginator = Paginator(posts, 10)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "posts/search_results.html",
        {"query": q, "posts": page, "page_obj": page},
    )
