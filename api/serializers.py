"""DRF serializers for the public API."""
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import Profile
from posts.models import Comment, Post

User = get_user_model()


class AuthorSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "name", "avatar_url")

    @extend_schema_field(serializers.CharField)
    def get_name(self, obj):
        return obj.profile.name if hasattr(obj, "profile") else obj.username

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_avatar_url(self, obj):
        if hasattr(obj, "profile") and obj.profile.avatar:
            request = self.context.get("request")
            url = obj.profile.avatar.url
            return request.build_absolute_uri(url) if request else url
        return None


class CommentSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ("id", "post", "author", "body", "created_at")
        read_only_fields = ("post", "author", "created_at")


class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    image_url = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id", "author", "body", "image", "image_url",
            "location", "visibility",
            "likes_count", "comments_count", "is_liked",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "author", "likes_count", "comments_count", "is_liked",
            "image_url", "created_at", "updated_at",
        )
        extra_kwargs = {
            "image": {"write_only": True, "required": False},
        }

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None

    @extend_schema_field(serializers.BooleanField)
    def get_is_liked(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False


class ProfilePublicSerializer(serializers.ModelSerializer):
    user = AuthorSerializer(read_only=True)
    posts_count = serializers.IntegerField(source="user.posts.count", read_only=True)
    followers_count = serializers.IntegerField(source="user.followers.count", read_only=True)
    following_count = serializers.IntegerField(source="user.following.count", read_only=True)

    class Meta:
        model = Profile
        fields = (
            "user", "display_name", "bio", "location", "website",
            "posts_count", "followers_count", "following_count",
        )
