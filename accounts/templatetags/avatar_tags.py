"""Avatar helpers for templates.

`{% avatar user size="md" %}` renders either:
   * the user's uploaded avatar image, or
   * a colored circle with their initials, picked deterministically from the
     username so the same user always gets the same colour.
"""
import hashlib

from django import template
from django.utils.html import format_html

register = template.Library()

# Curated palette — saturated enough to read white text on, but not eye-burning.
PALETTE = [
    "#6e6df0",  # purple
    "#e25b8b",  # pink
    "#1aa67a",  # mint
    "#f7831b",  # orange
    "#ec4f76",  # rose
    "#4a48d6",  # indigo
    "#0f9bbf",  # teal
    "#b14fc7",  # magenta
    "#3a8fea",  # blue
    "#d4286b",  # cherry
]

SIZE_MAP = {
    "xs": 22,
    "sm": 28,
    "md": 36,
    "lg": 48,
    "xl": 110,
}


def _initials(user):
    """Get up to 2 initials — prefer first+last name, else first 2 chars of username."""
    if not user:
        return "?"
    fn = (getattr(user, "first_name", "") or "").strip()
    ln = (getattr(user, "last_name", "") or "").strip()
    if fn and ln:
        return (fn[0] + ln[0]).upper()
    if fn:
        return fn[:2].upper()
    name = getattr(user, "username", "") or "?"
    return name[:2].upper()


def _color_for(user):
    """Deterministic — same username → same color, every render."""
    seed = (getattr(user, "username", "") or "?").encode("utf-8")
    h = int(hashlib.md5(seed).hexdigest(), 16)
    return PALETTE[h % len(PALETTE)]


@register.simple_tag
def avatar(user, size="md", css_class=""):
    """Render the user's avatar — image if uploaded, initials disc otherwise."""
    if user is None:
        return ""

    px = SIZE_MAP.get(size, SIZE_MAP["md"])
    extra = f" {css_class}" if css_class else ""

    profile = getattr(user, "profile", None)
    if profile and profile.avatar:
        try:
            url = profile.avatar.url
        except ValueError:
            url = ""
        if url:
            return format_html(
                '<img src="{}" alt="{}" class="avatar avatar--{}{}" '
                'loading="lazy" decoding="async" width="{}" height="{}">',
                url, user.username, size, extra, px, px,
            )

    return format_html(
        '<span class="avatar avatar--{}{}" '
        'style="background:{};width:{}px;height:{}px;font-size:{}px" '
        'aria-label="{}">{}</span>',
        size, extra, _color_for(user), px, px, max(10, int(px / 2.6)),
        user.username, _initials(user),
    )
