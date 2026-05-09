"""Tests for posts app: post CRUD, permissions, likes, comments, stories, visibility, mentions."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Follow
from notifications.models import Notification

from .models import Bookmark, Comment, CommentLike, Like, Post, Story
from .templatetags.post_extras import (
    extract_hashtags,
    extract_mentions,
    linkify_post,
)

User = get_user_model()


class PostCreateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.client.login(username="alice", password="ComplexPass!234")

    def test_create_post(self):
        resp = self.client.post(reverse("posts:create"), {
            "body": "Hello world",
            "visibility": "public",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Post.objects.count(), 1)
        self.assertEqual(Post.objects.first().author, self.user)

    def test_quick_post(self):
        resp = self.client.post(reverse("posts:quick_create"), {
            "body": "Quick share",
            "visibility": "public",
        }, HTTP_REFERER="/posts/")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Post.objects.filter(body="Quick share").exists())

    def test_empty_post_rejected(self):
        resp = self.client.post(reverse("posts:create"), {
            "body": "",
            "visibility": "public",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Post.objects.count(), 0)

    def test_create_requires_login(self):
        self.client.logout()
        resp = self.client.post(reverse("posts:create"), {"body": "x", "visibility": "public"})
        self.assertEqual(resp.status_code, 302)


class PostPermissionTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.post = Post.objects.create(author=self.alice, body="Alice's post", visibility="public")

    def test_owner_can_update(self):
        self.client.login(username="alice", password="ComplexPass!234")
        resp = self.client.post(
            reverse("posts:update", kwargs={"pk": self.post.pk}),
            {"body": "Updated", "visibility": "public"},
        )
        self.assertEqual(resp.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.body, "Updated")

    def test_non_owner_cannot_update(self):
        self.client.login(username="bob", password="ComplexPass!234")
        resp = self.client.post(
            reverse("posts:update", kwargs={"pk": self.post.pk}),
            {"body": "Hacked", "visibility": "public"},
        )
        self.assertEqual(resp.status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.body, "Alice's post")

    def test_non_owner_cannot_delete(self):
        self.client.login(username="bob", password="ComplexPass!234")
        resp = self.client.post(reverse("posts:delete", kwargs={"pk": self.post.pk}))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_owner_can_delete(self):
        self.client.login(username="alice", password="ComplexPass!234")
        resp = self.client.post(reverse("posts:delete", kwargs={"pk": self.post.pk}))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())


class LikeTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.post = Post.objects.create(author=self.alice, body="Hi", visibility="public")
        self.client.login(username="bob", password="ComplexPass!234")

    def test_like(self):
        resp = self.client.post(reverse("posts:toggle_like", kwargs={"pk": self.post.pk}))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Like.objects.filter(user=self.bob, post=self.post).exists())

    def test_unlike(self):
        Like.objects.create(user=self.bob, post=self.post)
        self.client.post(reverse("posts:toggle_like", kwargs={"pk": self.post.pk}))
        self.assertFalse(Like.objects.filter(user=self.bob, post=self.post).exists())

    def test_like_unique_constraint(self):
        Like.objects.create(user=self.bob, post=self.post)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Like.objects.create(user=self.bob, post=self.post)

    def test_ajax_like(self):
        resp = self.client.post(
            reverse("posts:toggle_like", kwargs={"pk": self.post.pk}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["liked"])
        self.assertEqual(data["likes_count"], 1)


class CommentTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.post = Post.objects.create(author=self.alice, body="Hi", visibility="public")

    def test_create_comment(self):
        self.client.login(username="bob", password="ComplexPass!234")
        resp = self.client.post(
            reverse("posts:comment_create", kwargs={"pk": self.post.pk}),
            {"body": "Nice"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Comment.objects.count(), 1)

    def test_only_author_can_delete_own_comment(self):
        comment = Comment.objects.create(author=self.bob, post=self.post, body="Hi")
        # third user can't delete
        carol = User.objects.create_user(username="carol", password="ComplexPass!234")
        self.client.login(username="carol", password="ComplexPass!234")
        resp = self.client.post(reverse("posts:comment_delete", kwargs={"pk": comment.pk}))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())

    def test_post_owner_can_delete_any_comment_on_their_post(self):
        comment = Comment.objects.create(author=self.bob, post=self.post, body="Hi")
        self.client.login(username="alice", password="ComplexPass!234")
        resp = self.client.post(reverse("posts:comment_delete", kwargs={"pk": comment.pk}))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())


class BookmarkTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.post = Post.objects.create(author=self.alice, body="Hi", visibility=Post.PUBLIC)
        self.client.login(username="bob", password="ComplexPass!234")

    def test_bookmark_toggle(self):
        url = reverse("posts:toggle_bookmark", args=[self.post.pk])
        self.client.post(url)
        self.assertEqual(Bookmark.objects.count(), 1)
        self.client.post(url)
        self.assertEqual(Bookmark.objects.count(), 0)

    def test_ajax_bookmark_returns_json(self):
        resp = self.client.post(
            reverse("posts:toggle_bookmark", args=[self.post.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["bookmarked"])

    def test_unique_bookmark_constraint(self):
        Bookmark.objects.create(user=self.bob, post=self.post)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Bookmark.objects.create(user=self.bob, post=self.post)

    def test_saved_page_shows_bookmarks(self):
        Bookmark.objects.create(user=self.bob, post=self.post)
        resp = self.client.get(reverse("posts:saved"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Hi")


class CommentReplyAndLikeTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.post = Post.objects.create(author=self.alice, body="Hi", visibility=Post.PUBLIC)
        self.parent_comment = Comment.objects.create(author=self.alice, post=self.post, body="Top")

    def test_reply_creates_nested_comment(self):
        self.client.login(username="bob", password="ComplexPass!234")
        self.client.post(
            reverse("posts:comment_create", args=[self.post.pk]),
            {"body": "Reply!", "parent_id": self.parent_comment.pk},
        )
        reply = Comment.objects.get(body="Reply!")
        self.assertEqual(reply.parent, self.parent_comment)
        self.assertTrue(reply.is_reply)

    def test_reply_to_a_reply_flattens_to_parent(self):
        # First reply
        first = Comment.objects.create(
            author=self.bob, post=self.post, body="r1", parent=self.parent_comment,
        )
        # Reply to that reply — should land on the original parent
        self.client.login(username="alice", password="ComplexPass!234")
        self.client.post(
            reverse("posts:comment_create", args=[self.post.pk]),
            {"body": "r2", "parent_id": first.pk},
        )
        r2 = Comment.objects.get(body="r2")
        self.assertEqual(r2.parent, self.parent_comment)

    def test_comment_like_toggle(self):
        self.client.login(username="bob", password="ComplexPass!234")
        url = reverse("posts:toggle_comment_like", args=[self.parent_comment.pk])
        self.client.post(url)
        self.assertEqual(CommentLike.objects.count(), 1)
        self.client.post(url)
        self.assertEqual(CommentLike.objects.count(), 0)

    def test_ajax_comment_like(self):
        self.client.login(username="bob", password="ComplexPass!234")
        url = reverse("posts:toggle_comment_like", args=[self.parent_comment.pk])
        resp = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["liked"])
        self.assertEqual(data["likes_count"], 1)

    def test_comment_like_unique_constraint(self):
        CommentLike.objects.create(user=self.bob, comment=self.parent_comment)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            CommentLike.objects.create(user=self.bob, comment=self.parent_comment)


class CommentEditTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.post = Post.objects.create(author=self.alice, body="P", visibility=Post.PUBLIC)
        self.comment = Comment.objects.create(author=self.bob, post=self.post, body="original")

    def test_author_can_edit(self):
        self.client.login(username="bob", password="ComplexPass!234")
        resp = self.client.post(reverse("posts:comment_edit", args=[self.comment.pk]), {
            "body": "edited body",
        })
        self.assertEqual(resp.status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, "edited body")
        self.assertTrue(self.comment.edited)

    def test_non_author_cannot_edit(self):
        self.client.login(username="alice", password="ComplexPass!234")
        resp = self.client.post(reverse("posts:comment_edit", args=[self.comment.pk]), {
            "body": "hacked",
        })
        self.assertEqual(resp.status_code, 403)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, "original")

    def test_empty_edit_rejected(self):
        self.client.login(username="bob", password="ComplexPass!234")
        resp = self.client.post(reverse("posts:comment_edit", args=[self.comment.pk]), {
            "body": "   ",
        })
        # Either 302 to detail with error, or 400 ajax
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, "original")
        self.assertFalse(self.comment.edited)


class RepostTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.original = Post.objects.create(
            author=self.alice, body="Original post", visibility=Post.PUBLIC,
        )

    def test_repost_creates_new_post_with_quote(self):
        self.client.login(username="bob", password="ComplexPass!234")
        resp = self.client.post(reverse("posts:repost", args=[self.original.pk]), {
            "body": "", "visibility": "public",
        })
        self.assertEqual(resp.status_code, 302)
        repost = Post.objects.exclude(pk=self.original.pk).get()
        self.assertEqual(repost.author, self.bob)
        self.assertEqual(repost.quoted_post, self.original)
        self.assertTrue(repost.is_repost)
        self.assertFalse(repost.is_quote)

    def test_quote_repost_with_body(self):
        self.client.login(username="bob", password="ComplexPass!234")
        self.client.post(reverse("posts:repost", args=[self.original.pk]), {
            "body": "My take", "visibility": "public",
        })
        repost = Post.objects.get(body="My take")
        self.assertTrue(repost.is_quote)
        self.assertFalse(repost.is_repost)

    def test_reposting_a_repost_collapses_to_original(self):
        repost = Post.objects.create(
            author=self.bob, body="", visibility=Post.PUBLIC, quoted_post=self.original,
        )
        carol = User.objects.create_user(username="carol", password="ComplexPass!234")
        self.client.login(username="carol", password="ComplexPass!234")
        self.client.post(reverse("posts:repost", args=[repost.pk]), {
            "body": "", "visibility": "public",
        })
        carol_repost = Post.objects.get(author=carol)
        # carol's repost points at the original, not at bob's repost
        self.assertEqual(carol_repost.quoted_post, self.original)


class FeedTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        Post.objects.create(author=self.alice, body="Mine", visibility="public")
        Post.objects.create(author=self.bob, body="Stranger", visibility="public")

    def test_feed_requires_login(self):
        resp = self.client.get(reverse("posts:feed"))
        self.assertEqual(resp.status_code, 302)

    def test_feed_shows_only_own_and_followed_posts(self):
        self.client.login(username="alice", password="ComplexPass!234")
        resp = self.client.get(reverse("posts:feed"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mine")
        self.assertNotContains(resp, "Stranger")

    def test_explore_shows_all_public_posts(self):
        resp = self.client.get(reverse("posts:explore"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mine")
        self.assertContains(resp, "Stranger")

    def test_search_posts(self):
        resp = self.client.get(reverse("posts:search"), {"q": "Stranger"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Stranger")


class StoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="storyuser", password="ComplexPass!234")

    def test_active_excludes_expired(self):
        active = Story.objects.create(
            author=self.user,
            image="stories/x.jpg",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        Story.objects.create(
            author=self.user,
            image="stories/y.jpg",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertEqual(list(Story.active()), [active])

    def test_default_expiry_is_about_24_hours(self):
        s = Story.objects.create(author=self.user, image="stories/z.jpg")
        delta = s.expires_at - s.created_at
        self.assertGreaterEqual(delta, timedelta(hours=23, minutes=59))
        self.assertLessEqual(delta, timedelta(hours=24, minutes=1))


class VisibilityTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.carol = User.objects.create_user(username="carol", password="ComplexPass!234")
        # Carol follows Alice; Bob doesn't
        Follow.objects.create(follower=self.carol, following=self.alice)

        self.public = Post.objects.create(author=self.alice, body="Public", visibility=Post.PUBLIC)
        self.friends = Post.objects.create(author=self.alice, body="Friends", visibility=Post.FRIENDS)
        self.private = Post.objects.create(author=self.alice, body="Private", visibility=Post.PRIVATE)

    def test_anonymous_can_see_public_only(self):
        self.assertEqual(self.client.get(reverse("posts:detail", args=[self.public.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("posts:detail", args=[self.friends.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("posts:detail", args=[self.private.pk])).status_code, 404)

    def test_follower_sees_friends_only_post(self):
        self.client.login(username="carol", password="ComplexPass!234")
        self.assertEqual(self.client.get(reverse("posts:detail", args=[self.friends.pk])).status_code, 200)

    def test_non_follower_blocked_from_friends_post(self):
        self.client.login(username="bob", password="ComplexPass!234")
        self.assertEqual(self.client.get(reverse("posts:detail", args=[self.friends.pk])).status_code, 404)

    def test_owner_sees_own_private_post(self):
        self.client.login(username="alice", password="ComplexPass!234")
        self.assertEqual(self.client.get(reverse("posts:detail", args=[self.private.pk])).status_code, 200)

    def test_explore_excludes_non_public(self):
        # Use a unique-to-the-body marker so we don't collide with template chrome
        # like the visibility dropdown labels.
        Post.objects.all().delete()
        Post.objects.create(author=self.alice, body="VISIBLE_PUBLIC", visibility=Post.PUBLIC)
        Post.objects.create(author=self.alice, body="HIDDEN_FRIENDS", visibility=Post.FRIENDS)
        Post.objects.create(author=self.alice, body="HIDDEN_PRIVATE", visibility=Post.PRIVATE)
        resp = self.client.get(reverse("posts:explore"))
        self.assertContains(resp, "VISIBLE_PUBLIC")
        self.assertNotContains(resp, "HIDDEN_FRIENDS")
        self.assertNotContains(resp, "HIDDEN_PRIVATE")


class MentionAndHashtagTests(TestCase):
    def test_extract_mentions(self):
        self.assertEqual(
            sorted(extract_mentions("hi @alice and @bob_42, also @alice again")),
            ["alice", "bob_42"],
        )

    def test_extract_hashtags(self):
        self.assertEqual(
            sorted(extract_hashtags("loving #Hiking and #travel and #hiking")),
            ["hiking", "travel"],
        )

    def test_linkify_escapes_html(self):
        out = linkify_post("<script>x</script> #safe @user")
        self.assertNotIn("<script>", out)
        self.assertIn("post-mention", out)
        self.assertIn("post-hashtag", out)

    def test_post_creation_notifies_mentioned_users(self):
        author = User.objects.create_user(username="author", password="ComplexPass!234")
        target = User.objects.create_user(username="target", password="ComplexPass!234")
        self.client.login(username="author", password="ComplexPass!234")
        self.client.post(reverse("posts:create"), {
            "body": "Hello @target check this out", "visibility": "public",
        })
        self.assertTrue(
            Notification.objects.filter(
                recipient=target, actor=author, verb=Notification.MENTION,
            ).exists()
        )

    def test_self_mention_does_not_notify(self):
        author = User.objects.create_user(username="selfauthor", password="ComplexPass!234")
        self.client.login(username="selfauthor", password="ComplexPass!234")
        self.client.post(reverse("posts:create"), {
            "body": "Hi @selfauthor", "visibility": "public",
        })
        self.assertFalse(
            Notification.objects.filter(verb=Notification.MENTION, recipient=author).exists()
        )


class NotificationCreationTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.post = Post.objects.create(author=self.alice, body="Hi", visibility=Post.PUBLIC)

    def test_like_creates_notification(self):
        self.client.login(username="bob", password="ComplexPass!234")
        self.client.post(reverse("posts:toggle_like", args=[self.post.pk]))
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.alice, actor=self.bob, verb=Notification.LIKE
            ).exists()
        )

    def test_unlike_does_not_remove_notification(self):
        self.client.login(username="bob", password="ComplexPass!234")
        self.client.post(reverse("posts:toggle_like", args=[self.post.pk]))
        self.client.post(reverse("posts:toggle_like", args=[self.post.pk]))
        # The like is gone, but the original notification stays.
        self.assertEqual(Like.objects.count(), 0)
        self.assertEqual(Notification.objects.filter(verb=Notification.LIKE).count(), 1)

    def test_self_like_does_not_notify(self):
        self.client.login(username="alice", password="ComplexPass!234")
        self.client.post(reverse("posts:toggle_like", args=[self.post.pk]))
        self.assertEqual(Notification.objects.count(), 0)

    def test_comment_creates_notification(self):
        self.client.login(username="bob", password="ComplexPass!234")
        self.client.post(reverse("posts:comment_create", args=[self.post.pk]), {"body": "nice"})
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.alice, actor=self.bob, verb=Notification.COMMENT
            ).exists()
        )

    def test_follow_creates_notification(self):
        self.client.login(username="bob", password="ComplexPass!234")
        self.client.post(reverse("accounts:toggle_follow", args=[self.alice.username]))
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.alice, actor=self.bob, verb=Notification.FOLLOW
            ).exists()
        )
