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
