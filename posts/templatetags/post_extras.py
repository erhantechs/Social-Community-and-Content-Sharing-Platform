"""Template filters for post bodies and comments.

`linkify_post` is the main filter — it turns
    "Hi @alice check out #hiking with us"
into clickable mention and hashtag links, while keeping all other text safely
escaped (so XSS is not possible).
"""
import re

from django import template
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

MENTION_RE = re.compile(r"@([A-Za-z0-9_]{1,30})")
# Negative lookbehind also rejects `&` so we don't turn HTML numeric entities
# like `&#x27;` (apostrophe) or `&#39;` into a fake "#x27" hashtag link after
# the body has been HTML-escaped.
HASHTAG_RE = re.compile(r"(?<![\w&])#([A-Za-z0-9_]{1,40})")


def _replace_mentions_and_hashtags(escaped_text):
    """Operate on already-escaped text so we don't introduce XSS."""

    def mention_repl(m):
        username = m.group(1)
        url = reverse("accounts:profile", kwargs={"username": username})
        return f'<a class="post-mention" href="{url}">@{username}</a>'

    def hashtag_repl(m):
        tag = m.group(1)
        try:
            url = reverse("posts:tag", kwargs={"slug": tag.lower()})
        except Exception:
            url = reverse("posts:search") + f"?q=%23{tag}"
        return f'<a class="post-hashtag" href="{url}">#{tag}</a>'

    text = MENTION_RE.sub(mention_repl, escaped_text)
    text = HASHTAG_RE.sub(hashtag_repl, text)
    return text


@register.filter(name="linkify_post")
def linkify_post(value):
    """Escape, then linkify mentions and hashtags, then convert newlines to <br>."""
    if not value:
        return ""
    escaped = escape(value)
    escaped = _replace_mentions_and_hashtags(escaped)
    # Preserve newlines after escaping
    escaped = escaped.replace("\n", "<br>")
    return mark_safe(escaped)


def extract_mentions(text):
    """Return a list of unique usernames mentioned in `text`.

    Used by views to send mention-notifications.
    """
    if not text:
        return []
    return list({m.group(1) for m in MENTION_RE.finditer(text)})


def extract_hashtags(text):
    if not text:
        return []
    return list({m.group(1).lower() for m in HASHTAG_RE.finditer(text)})


@register.filter(name="comment_liked_by")
def comment_liked_by(comment, user):
    """Template helper — `{{ comment|comment_liked_by:user }}`."""
    if not user or not user.is_authenticated:
        return False
    return comment.is_liked_by(user)


@register.filter(name="reaction_of")
def reaction_of(post, user):
    """Template helper — `{{ post|reaction_of:user }}` returns the emoji code or ''."""
    if not user or not user.is_authenticated or not post:
        return ""
    return post.reaction_of(user) or ""


@register.filter(name="poll_voted_for")
def poll_voted_for(poll, user):
    """Returns list of option IDs the user voted for. Empty list if anonymous."""
    if not poll or not user or not user.is_authenticated:
        return []
    return poll.votes_for(user)


@register.filter(name="user_eq")
def user_eq(a, b):
    """`{{ user|user_eq:post.author }}` — True if the same User."""
    if not a or not b:
        return False
    a_id = getattr(a, "pk", None) or getattr(a, "id", None)
    b_id = getattr(b, "pk", None) or getattr(b, "id", None)
    return a_id is not None and a_id == b_id


@register.filter(name="can_pin")
def can_pin(post, user):
    """True if the user may pin/unpin this post.

    Allowed: the author themselves, or an owner/admin of the post's community.
    """
    if not user or not user.is_authenticated or not post:
        return False
    if post.author_id == user.id:
        return True
    if post.community_id and post.community.is_admin(user):
        return True
    return False
