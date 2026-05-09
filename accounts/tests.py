"""Tests for accounts app: signup, login, follow/unfollow, profile."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Block, Follow, Profile

User = get_user_model()


class SignupTests(TestCase):
    def test_signup_creates_user_and_profile(self):
        resp = self.client.post(reverse("accounts:signup"), {
            "username": "alice",
            "email": "alice@example.com",
            "first_name": "Alice",
            "last_name": "A",
            "password1": "ComplexPass!234",
            "password2": "ComplexPass!234",
        })
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="alice")
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_signup_rejects_duplicate_email(self):
        User.objects.create_user(username="bob", email="b@x.com", password="ComplexPass!234")
        resp = self.client.post(reverse("accounts:signup"), {
            "username": "bob2",
            "email": "b@x.com",
            "password1": "ComplexPass!234",
            "password2": "ComplexPass!234",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "already exists")


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="carol", email="c@x.com", password="ComplexPass!234"
        )

    def test_login_success(self):
        resp = self.client.post(reverse("accounts:login"), {
            "username": "carol", "password": "ComplexPass!234",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.id)

    def test_login_failure(self):
        resp = self.client.post(reverse("accounts:login"), {
            "username": "carol", "password": "wrong",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout(self):
        self.client.login(username="carol", password="ComplexPass!234")
        resp = self.client.post(reverse("accounts:logout"))
        self.assertEqual(resp.status_code, 302)


class ProfileTests(TestCase):
    def test_profile_page_renders(self):
        u = User.objects.create_user(username="dave", password="ComplexPass!234")
        resp = self.client.get(reverse("accounts:profile", kwargs={"username": "dave"}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "dave")

    def test_edit_profile_requires_login(self):
        resp = self.client.get(reverse("accounts:edit_profile"))
        self.assertEqual(resp.status_code, 302)


class FollowTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.client.login(username="alice", password="ComplexPass!234")

    def test_follow_creates_relationship(self):
        resp = self.client.post(
            reverse("accounts:toggle_follow", kwargs={"username": "bob"})
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Follow.objects.filter(follower=self.alice, following=self.bob).exists())

    def test_unfollow_removes_relationship(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        self.client.post(reverse("accounts:toggle_follow", kwargs={"username": "bob"}))
        self.assertFalse(Follow.objects.filter(follower=self.alice, following=self.bob).exists())

    def test_cannot_follow_self(self):
        resp = self.client.post(
            reverse("accounts:toggle_follow", kwargs={"username": "alice"}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 400)

    def test_unique_follow_constraint(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        # Same pair shouldn't be insertable twice (handled at DB level)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Follow.objects.create(follower=self.alice, following=self.bob)

    def test_ajax_follow_returns_json(self):
        resp = self.client.post(
            reverse("accounts:toggle_follow", kwargs={"username": "bob"}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["following"])
        self.assertEqual(data["followers_count"], 1)


class SearchTests(TestCase):
    def test_search_users(self):
        User.objects.create_user(username="searchable_user", password="x")
        resp = self.client.get(reverse("accounts:search_users"), {"q": "searchable"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "searchable_user")


class BlockTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.client.login(username="alice", password="ComplexPass!234")

    def test_block_creates_record(self):
        self.client.post(reverse("accounts:toggle_block", args=["bob"]))
        self.assertTrue(Block.objects.filter(blocker=self.alice, blocked=self.bob).exists())

    def test_block_removes_existing_follows(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        Follow.objects.create(follower=self.bob, following=self.alice)
        self.client.post(reverse("accounts:toggle_block", args=["bob"]))
        self.assertFalse(Follow.objects.filter(follower=self.alice, following=self.bob).exists())
        self.assertFalse(Follow.objects.filter(follower=self.bob, following=self.alice).exists())

    def test_blocked_user_cannot_be_followed(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        resp = self.client.post(
            reverse("accounts:toggle_follow", args=["bob"]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Follow.objects.filter(follower=self.alice, following=self.bob).exists())

    def test_unblock(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        self.client.post(reverse("accounts:toggle_block", args=["bob"]))
        self.assertFalse(Block.objects.filter(blocker=self.alice, blocked=self.bob).exists())

    def test_cannot_block_self(self):
        resp = self.client.post(
            reverse("accounts:toggle_block", args=["alice"]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 400)

    def test_blocked_list_renders(self):
        Block.objects.create(blocker=self.alice, blocked=self.bob)
        resp = self.client.get(reverse("accounts:blocked_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "bob")


class BlockHidesContentTests(TestCase):
    """Block must hide posts/comments/mentions everywhere — not just on profile."""

    def setUp(self):
        from notifications.models import Notification
        from posts.models import Comment, Post
        self.Post = Post
        self.Comment = Comment
        self.Notification = Notification

        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.bob_post = Post.objects.create(
            author=self.bob, body="HIDE_ME_BOB_POST", visibility=Post.PUBLIC,
        )
        Block.objects.create(blocker=self.alice, blocked=self.bob)

    def test_explore_hides_blocked_user_post(self):
        self.client.login(username="alice", password="ComplexPass!234")
        resp = self.client.get(reverse("posts:explore"))
        self.assertNotContains(resp, "HIDE_ME_BOB_POST")

    def test_search_hides_blocked_user_post(self):
        self.client.login(username="alice", password="ComplexPass!234")
        resp = self.client.get(reverse("posts:search"), {"q": "HIDE_ME"})
        self.assertNotContains(resp, "HIDE_ME_BOB_POST")

    def test_post_detail_hides_blocked_user_comments(self):
        alice_post = self.Post.objects.create(
            author=self.alice, body="alice", visibility=self.Post.PUBLIC,
        )
        self.Comment.objects.create(
            author=self.bob, post=alice_post, body="HIDE_ME_BOB_COMMENT",
        )
        self.client.login(username="alice", password="ComplexPass!234")
        resp = self.client.get(reverse("posts:detail", args=[alice_post.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "HIDE_ME_BOB_COMMENT")

    def test_blocked_user_mention_does_not_notify(self):
        # Bob mentions alice, but alice has blocked bob — no notification.
        self.client.login(username="bob", password="ComplexPass!234")
        self.client.post(reverse("posts:create"), {
            "body": "Hey @alice", "visibility": "public",
        })
        self.assertFalse(
            self.Notification.objects.filter(
                recipient=self.alice, actor=self.bob,
                verb=self.Notification.MENTION,
            ).exists()
        )

    def test_api_post_list_hides_blocked_user(self):
        self.client.login(username="alice", password="ComplexPass!234")
        resp = self.client.get("/api/posts/")
        self.assertEqual(resp.status_code, 200)
        bodies = [p["body"] for p in resp.json()["results"]]
        self.assertNotIn("HIDE_ME_BOB_POST", bodies)


class MuteTests(TestCase):
    def setUp(self):
        from accounts.models import Mute
        self.Mute = Mute
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.client.login(username="alice", password="ComplexPass!234")

    def test_mute_creates_record(self):
        self.client.post(reverse("accounts:toggle_mute", args=["bob"]))
        self.assertTrue(self.Mute.objects.filter(muter=self.alice, muted=self.bob).exists())

    def test_unmute_via_toggle(self):
        self.Mute.objects.create(muter=self.alice, muted=self.bob)
        self.client.post(reverse("accounts:toggle_mute", args=["bob"]))
        self.assertFalse(self.Mute.objects.filter(muter=self.alice, muted=self.bob).exists())

    def test_cannot_mute_self(self):
        resp = self.client.post(
            reverse("accounts:toggle_mute", args=["alice"]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 400)

    def test_muted_user_post_hidden_from_explore(self):
        from posts.models import Post
        self.Mute.objects.create(muter=self.alice, muted=self.bob)
        Post.objects.create(author=self.bob, body="HIDDEN_BY_MUTE", visibility=Post.PUBLIC)
        resp = self.client.get(reverse("posts:explore"))
        self.assertNotContains(resp, "HIDDEN_BY_MUTE")

    def test_muted_user_can_still_be_followed(self):
        # Mute is silent — the muted user is unaware, so following them still works.
        self.Mute.objects.create(muter=self.alice, muted=self.bob)
        resp = self.client.post(
            reverse("accounts:toggle_follow", args=["bob"]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200)


class EmailVerificationTests(TestCase):
    def test_signup_sends_verification_email(self):
        from django.core import mail
        self.client.post(reverse("accounts:signup"), {
            "username": "alice",
            "email": "alice@example.com",
            "password1": "ComplexPass!234",
            "password2": "ComplexPass!234",
        })
        u = User.objects.get(username="alice")
        self.assertFalse(u.profile.email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verify", mail.outbox[0].subject.lower())

    def test_verification_link_marks_profile_verified(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        from accounts.verification import verification_token
        u = User.objects.create_user(username="bob", email="b@x.com", password="ComplexPass!234")
        uidb64 = urlsafe_base64_encode(force_bytes(u.pk))
        token = verification_token.make_token(u)
        resp = self.client.get(reverse("accounts:verify_email", args=[uidb64, token]))
        self.assertEqual(resp.status_code, 302)
        u.profile.refresh_from_db()
        self.assertTrue(u.profile.email_verified)

    def test_invalid_token_does_not_verify(self):
        u = User.objects.create_user(username="carol", email="c@x.com", password="ComplexPass!234")
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        uidb64 = urlsafe_base64_encode(force_bytes(u.pk))
        resp = self.client.get(reverse("accounts:verify_email", args=[uidb64, "bad-token"]))
        self.assertEqual(resp.status_code, 302)
        u.profile.refresh_from_db()
        self.assertFalse(u.profile.email_verified)


class HoneypotTests(TestCase):
    def test_filled_honeypot_blocks_signup(self):
        resp = self.client.post(reverse("accounts:signup"), {
            "username": "spammer",
            "email": "s@s.com",
            "password1": "ComplexPass!234",
            "password2": "ComplexPass!234",
            "website_url": "http://spam.com",  # bot fills this
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="spammer").exists())


class LoginThrottleTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        User.objects.create_user(username="victim", password="ComplexPass!234")

    def test_too_many_failed_logins_blocks(self):
        for _ in range(10):
            self.client.post(reverse("accounts:login"), {
                "username": "victim", "password": "wrong",
            })
        # 11th attempt — should be 429
        resp = self.client.post(reverse("accounts:login"), {
            "username": "victim", "password": "wrong",
        })
        self.assertEqual(resp.status_code, 429)

    def test_successful_login_resets_counter(self):
        for _ in range(5):
            self.client.post(reverse("accounts:login"), {"username": "victim", "password": "wrong"})
        # success
        self.client.post(reverse("accounts:login"), {"username": "victim", "password": "ComplexPass!234"})
        self.client.logout()
        # 5 more failures should still be allowed (counter was reset)
        for _ in range(5):
            self.client.post(reverse("accounts:login"), {"username": "victim", "password": "wrong"})
        resp = self.client.post(reverse("accounts:login"), {"username": "victim", "password": "wrong"})
        self.assertNotEqual(resp.status_code, 429)


class TwoFactorTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # avoid login-throttle bleed-through from sibling test classes
        self.user = User.objects.create_user(
            username="bob", email="bob@example.com", password="SecretPass!234",
        )
        self.client.login(username="bob", password="SecretPass!234")

    def test_setup_then_enable_with_valid_token(self):
        import pyotp
        # GET seeds the secret
        resp = self.client.get(reverse("accounts:two_factor_setup"))
        self.assertEqual(resp.status_code, 200)
        secret = self.client.session.get("tfa_setup_secret")
        self.assertTrue(secret)
        # Enable with a fresh TOTP
        resp = self.client.post(reverse("accounts:two_factor_setup"), {
            "token": pyotp.TOTP(secret).now(),
        })
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.two_factor_enabled)

    def test_setup_rejects_bad_token(self):
        self.client.get(reverse("accounts:two_factor_setup"))
        resp = self.client.post(reverse("accounts:two_factor_setup"), {"token": "000000"})
        # Stays on the form (200) and 2FA is NOT enabled.
        self.assertEqual(resp.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.two_factor_enabled)

    def test_login_with_2fa_redirects_to_verify(self):
        import pyotp
        from .models import TwoFactorSecret
        secret = pyotp.random_base32()
        TwoFactorSecret.objects.create(user=self.user, secret=secret)
        self.user.profile.two_factor_enabled = True
        self.user.profile.save()
        self.client.logout()
        resp = self.client.post(reverse("accounts:login"), {
            "username": "bob", "password": "SecretPass!234",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/2fa/verify/", resp["Location"])
        # Submit a valid TOTP and we should be logged in.
        resp = self.client.post(reverse("accounts:two_factor_verify"), {
            "code": pyotp.TOTP(secret).now(),
        })
        self.assertEqual(resp.status_code, 302)


class DataExportTests(TestCase):
    def test_export_returns_zip(self):
        import io, json, zipfile
        u = User.objects.create_user(username="exporter", password="x")
        self.client.login(username="exporter", password="x")
        resp = self.client.get(reverse("accounts:data_export"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/zip")
        zf = zipfile.ZipFile(io.BytesIO(b"".join(resp.streaming_content)
                                        if resp.streaming else resp.content))
        self.assertIn("data.json", zf.namelist())
        data = json.loads(zf.read("data.json"))
        self.assertEqual(data["user"]["username"], "exporter")
