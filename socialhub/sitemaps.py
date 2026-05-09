"""Sitemaps for SEO. Lists public posts and user profiles so search
engines can crawl them without hitting auth-protected pages."""
from django.contrib.auth import get_user_model
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from posts.models import Post

User = get_user_model()


class StaticViewSitemap(Sitemap):
    """The site's evergreen public pages."""

    priority = 0.6
    changefreq = "weekly"

    def items(self):
        return ["posts:explore"]

    def location(self, item):
        return reverse(item)


class PostSitemap(Sitemap):
    """Every public post, ordered newest first."""

    changefreq = "daily"
    priority = 0.7

    def items(self):
        return Post.objects.filter(visibility=Post.PUBLIC).order_by("-created_at")[:5000]

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()


class ProfileSitemap(Sitemap):
    """Every user's public profile page."""

    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return User.objects.filter(is_active=True).only("username").order_by("username")

    def location(self, obj):
        return reverse("accounts:profile", kwargs={"username": obj.username})


sitemaps = {
    "static": StaticViewSitemap,
    "posts": PostSitemap,
    "profiles": ProfileSitemap,
}
