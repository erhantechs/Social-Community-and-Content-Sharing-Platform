"""DRF API views — posts CRUD, comment CRUD, like toggle, follow toggle."""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Follow
from posts.models import Comment, Like, Post
from posts.views import annotate_posts

from .permissions import IsAuthorOrReadOnly
from .serializers import (
    CommentSerializer,
    PostSerializer,
    ProfilePublicSerializer,
)

User = get_user_model()


class FollowToggleResponseSerializer(drf_serializers.Serializer):
    following = drf_serializers.BooleanField()
    followers_count = drf_serializers.IntegerField()


class LikeToggleResponseSerializer(drf_serializers.Serializer):
    liked = drf_serializers.BooleanField()
    likes_count = drf_serializers.IntegerField()


class PostViewSet(viewsets.ModelViewSet):
    """`/api/posts/` — list public posts, create your own, edit/delete yours."""

    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_queryset(self):
        # Public posts to everyone; visibility-restricted ones to the right viewers.
        qs = Post.objects.all()
        user = self.request.user
        if user.is_authenticated:
            following_ids = Follow.objects.filter(follower=user).values_list(
                "following_id", flat=True
            )
            qs = qs.filter(
                # public OR friends-only-of-followed OR your own
                models_q_filter(user, following_ids)
            )
        else:
            qs = qs.filter(visibility=Post.PUBLIC)

        return annotate_posts(qs, user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @extend_schema(
        request=None,
        responses={200: LikeToggleResponseSerializer},
        description="Toggle like on a post. Returns the new state.",
    )
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def like(self, request, pk=None):
        post = self.get_object()
        like, created = Like.objects.get_or_create(user=request.user, post=post)
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        return Response({"liked": liked, "likes_count": post.likes.count()})

    @action(detail=True, methods=["get", "post"],
            permission_classes=[permissions.IsAuthenticatedOrReadOnly])
    def comments(self, request, pk=None):
        post = self.get_object()
        if request.method == "GET":
            qs = post.comments.select_related("author", "author__profile")
            return Response(CommentSerializer(qs, many=True, context={"request": request}).data)
        # POST
        if not request.user.is_authenticated:
            return Response({"detail": "Login required."}, status=status.HTTP_401_UNAUTHORIZED)
        ser = CommentSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.save(author=request.user, post=post)
        return Response(ser.data, status=status.HTTP_201_CREATED)


def models_q_filter(user, following_ids):
    """Build the visibility Q for the authenticated post list."""
    from django.db.models import Q
    return (
        Q(visibility=Post.PUBLIC)
        | Q(author=user)
        | (Q(visibility=Post.FRIENDS) & Q(author__in=following_ids))
    )


class CommentViewSet(viewsets.ModelViewSet):
    """`/api/comments/<id>/` — fetch / delete a comment."""

    queryset = Comment.objects.select_related("author", "author__profile", "post").all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    http_method_names = ["get", "delete", "head", "options"]


class ProfileDetail(APIView):
    """`GET /api/users/<username>/` — public profile."""

    permission_classes = [permissions.AllowAny]
    serializer_class = ProfilePublicSerializer

    @extend_schema(responses=ProfilePublicSerializer)
    def get(self, request, username):
        user = get_object_or_404(User.objects.select_related("profile"), username=username)
        ser = ProfilePublicSerializer(user.profile, context={"request": request})
        return Response(ser.data)


@extend_schema(
    request=None,
    responses={
        200: FollowToggleResponseSerializer,
        400: OpenApiResponse(description="Cannot follow yourself."),
    },
    description="Toggle follow for a user. Returns whether you're now following them.",
)
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def toggle_follow(request, username):
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return Response({"detail": "Cannot follow yourself."}, status=400)
    follow, created = Follow.objects.get_or_create(follower=request.user, following=target)
    if not created:
        follow.delete()
        following = False
    else:
        following = True
    return Response({"following": following, "followers_count": target.followers.count()})
