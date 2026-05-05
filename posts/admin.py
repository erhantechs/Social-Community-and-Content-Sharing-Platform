from django.contrib import admin

from .models import Bookmark, Comment, CommentLike, Like, Post, PostImage, Story


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "short_body", "visibility", "created_at")
    list_filter = ("visibility", "created_at")
    search_fields = ("body", "author__username", "location")
    inlines = [PostImageInline]
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Body")
    def short_body(self, obj):
        return (obj.body[:60] + "…") if len(obj.body) > 60 else obj.body


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "post", "short_body", "created_at")
    search_fields = ("author__username", "body")

    @admin.display(description="Body")
    def short_body(self, obj):
        return (obj.body[:60] + "…") if len(obj.body) > 60 else obj.body


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "created_at")


@admin.register(CommentLike)
class CommentLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "comment", "created_at")


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "created_at")


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "caption", "created_at", "expires_at")
    list_filter = ("created_at", "expires_at")
