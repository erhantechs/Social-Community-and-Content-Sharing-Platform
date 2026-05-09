"""GDPR-style data export — bundles a user's data into a downloadable ZIP.

Includes: profile, posts, comments, likes, bookmarks, follows, messages,
notifications, communities, social accounts. Excludes anything
private to other users (e.g. messages other people sent us are included
because they're addressed to us, but other people's posts are not).
"""
import io
import json
import zipfile
from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone

User = get_user_model()


def _serialize_user(user):
    p = user.profile
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "profile": {
            "display_name": p.display_name,
            "bio": p.bio,
            "location": p.location,
            "website": p.website,
            "email_verified": p.email_verified,
            "two_factor_enabled": p.two_factor_enabled,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "interests": list(p.interests.values_list("name", flat=True)),
        },
    }


def _serialize_posts(user):
    rows = []
    for p in user.posts.all().order_by("created_at"):
        rows.append({
            "id": p.id,
            "body": p.body,
            "location": p.location,
            "visibility": p.visibility,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
            "image": p.image.name if p.image else None,
            "extra_images": [im.image.name for im in p.extra_images.all()],
            "interests": list(p.interests.values_list("name", flat=True)),
            "hashtags": list(p.hashtags.values_list("name", flat=True)),
            "community": p.community.name if p.community_id else None,
            "quoted_post_id": p.quoted_post_id,
            "likes_count": p.likes.count(),
            "comments_count": p.comments.count(),
        })
    return rows


def _serialize_comments(user):
    rows = []
    for c in user.comments.all().order_by("created_at"):
        rows.append({
            "id": c.id,
            "post_id": c.post_id,
            "parent_id": c.parent_id,
            "body": c.body,
            "created_at": c.created_at.isoformat(),
            "edited": c.edited,
        })
    return rows


def _serialize_messages(user):
    """All messages either sent by the user or received in their conversations."""
    rows = []
    for conv in user.conversations.all().order_by("created_at"):
        for m in conv.messages.all().order_by("created_at"):
            rows.append({
                "conversation_id": conv.id,
                "is_group": conv.is_group,
                "group_name": conv.name if conv.is_group else None,
                "from_username": m.sender.username,
                "from_me": m.sender_id == user.id,
                "body": m.body,
                "created_at": m.created_at.isoformat(),
            })
    return rows


def _serialize_follows(user):
    return {
        "following": list(
            user.following.values_list("following__username", flat=True)
        ),
        "followers": list(
            user.followers.values_list("follower__username", flat=True)
        ),
    }


def _serialize_likes(user):
    return [
        {"post_id": pk, "created_at": ts.isoformat()}
        for pk, ts in user.likes.values_list("post_id", "created_at")
    ]


def _serialize_bookmarks(user):
    return [
        {"post_id": pk, "created_at": ts.isoformat()}
        for pk, ts in user.bookmarks.values_list("post_id", "created_at")
    ]


def _serialize_notifications(user):
    return [
        {
            "verb": n.verb,
            "actor_username": n.actor.username if n.actor_id else None,
            "post_id": n.post_id,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in user.notifications.all().order_by("created_at")
    ]


def _serialize_communities(user):
    return [
        {
            "name": m.community.name,
            "slug": m.community.slug,
            "role": m.role,
            "status": m.status,
            "joined_at": m.joined_at.isoformat(),
        }
        for m in user.community_memberships.select_related("community")
    ]


def _serialize_social_accounts(user):
    return [
        {
            "provider": s.provider,
            "email": s.email,
            "linked_at": s.created_at.isoformat(),
        }
        for s in user.social_accounts.all()
    ]


def build_export(user) -> tuple[bytes, str]:
    """Return (zip_bytes, suggested_filename)."""
    snapshot = {
        "format_version": 1,
        "exported_at": timezone.now().isoformat(),
        "user": _serialize_user(user),
        "posts": _serialize_posts(user),
        "comments": _serialize_comments(user),
        "likes": _serialize_likes(user),
        "bookmarks": _serialize_bookmarks(user),
        "follows": _serialize_follows(user),
        "messages": _serialize_messages(user),
        "notifications": _serialize_notifications(user),
        "communities": _serialize_communities(user),
        "social_accounts": _serialize_social_accounts(user),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "data.json",
            json.dumps(snapshot, ensure_ascii=False, indent=2),
        )
        zf.writestr(
            "README.txt",
            (
                "SocialHub data export\n"
                "=====================\n"
                f"Exported for: {user.username}\n"
                f"Exported at: {snapshot['exported_at']}\n\n"
                "Contents:\n"
                "  data.json — complete machine-readable snapshot of your account.\n"
                "\n"
                "Notes:\n"
                "  • Image files are referenced by storage path (not bundled).\n"
                "  • Messages from group chats include other participants' messages\n"
                "    where you were a participant.\n"
                "  • Two-factor secrets and password hashes are NEVER exported.\n"
            ),
        )
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"socialhub-export-{user.username}-{stamp}.zip"
    return buf.getvalue(), filename


@login_required
def data_export(request):
    """Synchronous export — for accounts up to a few thousand items this is
    fine; for very large accounts a Celery job would be better."""
    blob, filename = build_export(request.user)
    response = HttpResponse(blob, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = str(len(blob))
    return response
