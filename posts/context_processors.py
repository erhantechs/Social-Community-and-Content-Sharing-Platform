"""Template context processors that expose data needed across many pages.

Right now: the right-sidebar payload (stories, suggestions, trending hashtags,
interest recommendations). Caching is handled inside `_sidebar_context`.
"""
from .views import _sidebar_context


def sidebar(request):
    """Make stories / suggestions / trending_hashtags / recommendations
    available to every template that extends base.html."""
    try:
        return _sidebar_context(request)
    except Exception:
        # Never let a template-context error 500 the page.
        return {
            "stories": [],
            "suggestions": [],
            "recommendations": [],
            "trending_hashtags": [],
        }
