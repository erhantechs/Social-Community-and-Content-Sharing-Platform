from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """Anyone can read; only the author can modify or delete."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return getattr(obj, "author_id", None) == request.user.id
