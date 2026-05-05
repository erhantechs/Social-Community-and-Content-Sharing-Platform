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

from accounts.models import Follow, Interest
from notifications.models import Notification

from .forms import CommentForm, PostForm, QuickPostForm, StoryForm
from .models import Bookmark, Comment, CommentLike, Like, Post, Story
from .templatetags.post_extras import extract_mentions

User = get_user_model()


def _notify_mentions(actor, body, post=None):
    """Send a 'mention' notification to every @username found in `body`.

    Skips the actor themselves, and silently ignores usernames that don't exist.
    """
    if not body:
        return
    usernames = extract_mentions(body)
    if not usernames:
        return
    for u in User.objects.filter(username__in=usernames).exclude(pk=actor.pk):
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


def _suggestions_for(user, limit=3):
    """People to follow — users not already followed, excluding self."""
    if not user.is_authenticated:
        return (
            User.objects.select_related("profile")
            .annotate(follower_count=Count("followers"))
            .order_by("-follower_count")[:limit]
        )
    already = Follow.objects.filter(follower=user).values_list("following_id", flat=True)
    return (
        User.objects.select_related("profile")
        .exclude(id__in=already)
        .exclude(id=user.id)
        .annotate(follower_count=Count("followers"))
        .order_by("-follower_count")[:limit]
    )


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

    data = {
        "stories": list(
            Story.active()
            .select_related("author", "author__profile")
            .order_by("-created_at")[:2]
        ),
        "suggestions": list(_suggestions_for(request.user, limit=3)),
        "recommendations": list(Interest.objects.all()[:8]),
    }
    cache.set(cache_key, data, SIDEBAR_CACHE_TTL)
    return data


def invalidate_sidebar_cache(user_id):
    """Drop a user's cached sidebar — call after follow/unfollow toggles."""
    cache.delete(f"sidebar:v2:{user_id}")


# ---------- feed / explore ----------

@login_required
def feed_view(request):
    """Home/feed page: posts from people the user follows, plus their own."""
    following_ids = Follow.objects.filter(follower=request.user).values_list(
        "following_id", flat=True
    )
    posts_qs = Post.objects.filter(
        Q(author__in=following_ids) | Q(author=request.user)
    )

    # Filter tab: Recents (default) | Friends | Popular
    tab = request.GET.get("tab", "recents")
    if tab == "popular":
        posts_qs = posts_qs.order_by("-id")
        posts_qs = _annotate_posts(posts_qs, request).order_by(
            "-like_count", "-created_at"
        )
    elif tab == "friends":
        posts_qs = posts_qs.filter(author__in=following_ids)
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
    """Full post-create form (separate page)."""
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m()
            _notify_mentions(request.user, post.body, post=post)
            messages.success(request, "Post published.")
            return redirect("posts:detail", pk=post.pk)
    else:
        form = PostForm()
    return render(request, "posts/post_form.html", {"form": form, "title": "New post"})


@login_required
@require_POST
def quick_post_create(request):
    """Compact composer at the bottom of the feed."""
    form = QuickPostForm(request.POST, request.FILES)
    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
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

    top_level_comments = (
        post.comments
        .filter(parent__isnull=True)
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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = "Edit post"
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Post updated.")
        return super().form_valid(form)


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
    post = get_object_or_404(Post, pk=pk)
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
        if post.author != request.user:
            Notification.objects.create(
                recipient=post.author,
                actor=request.user,
                verb=Notification.LIKE,
                post=post,
            )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "liked": liked,
            "likes_count": post.likes.count(),
        })
    return redirect(request.META.get("HTTP_REFERER") or post.get_absolute_url())


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


# ---------- search ----------

def search_posts(request):
    q = (request.GET.get("q") or "").strip()
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
        posts = annotate_posts(posts, request.user).order_by("-created_at")

    paginator = Paginator(posts, 10)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "posts/search_results.html",
        {"query": q, "posts": page, "page_obj": page},
    )
