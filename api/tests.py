"""DRF API smoke tests."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from posts.models import Post

User = get_user_model()


class PostAPITests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")
        self.public = Post.objects.create(author=self.alice, body="Public post", visibility=Post.PUBLIC)
        Post.objects.create(author=self.alice, body="Private post", visibility=Post.PRIVATE)

    def test_anonymous_lists_only_public(self):
        resp = self.client.get(reverse("api:post-list"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        bodies = [p["body"] for p in data["results"]]
        self.assertIn("Public post", bodies)
        self.assertNotIn("Private post", bodies)

    def test_authenticated_create_post(self):
        self.client.login(username="bob", password="ComplexPass!234")
        resp = self.client.post(reverse("api:post-list"), {
            "body": "From the API", "visibility": "public",
        })
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Post.objects.filter(body="From the API", author=self.bob).exists())

    def test_unauth_cannot_create(self):
        resp = self.client.post(reverse("api:post-list"), {"body": "x", "visibility": "public"})
        self.assertIn(resp.status_code, (401, 403))

    def test_only_author_can_delete(self):
        self.client.login(username="bob", password="ComplexPass!234")
        resp = self.client.delete(reverse("api:post-detail", args=[self.public.pk]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Post.objects.filter(pk=self.public.pk).exists())

    def test_author_can_delete(self):
        self.client.login(username="alice", password="ComplexPass!234")
        resp = self.client.delete(reverse("api:post-detail", args=[self.public.pk]))
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Post.objects.filter(pk=self.public.pk).exists())

    def test_like_action_toggles(self):
        self.client.login(username="bob", password="ComplexPass!234")
        url = reverse("api:post-like", args=[self.public.pk])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["liked"])
        self.assertEqual(resp.json()["likes_count"], 1)
        # Toggle off
        resp = self.client.post(url)
        self.assertFalse(resp.json()["liked"])
        self.assertEqual(resp.json()["likes_count"], 0)

    def test_post_comment_via_api(self):
        self.client.login(username="bob", password="ComplexPass!234")
        url = reverse("api:post-comments", args=[self.public.pk])
        resp = self.client.post(url, {"body": "Nice"}, content_type="application/json")
        self.assertEqual(resp.status_code, 201)
        # GET back
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        bodies = [c["body"] for c in resp.json()]
        self.assertIn("Nice", bodies)


class FollowAPITests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="ComplexPass!234")
        self.bob = User.objects.create_user(username="bob", password="ComplexPass!234")

    def test_follow_toggle(self):
        self.client.login(username="bob", password="ComplexPass!234")
        url = reverse("api:user_follow", args=["alice"])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["following"])

    def test_user_detail(self):
        resp = self.client.get(reverse("api:user_detail", args=["alice"]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["user"]["username"], "alice")


class TokenAuthTests(TestCase):
    def test_token_obtain_then_use(self):
        User.objects.create_user(username="tokuser", password="ComplexPass!234")
        resp = self.client.post(reverse("api:obtain_token"), {
            "username": "tokuser", "password": "ComplexPass!234",
        })
        self.assertEqual(resp.status_code, 200)
        token = resp.json()["token"]
        # Use token to create a post
        resp = self.client.post(
            reverse("api:post-list"),
            {"body": "Token-authed", "visibility": "public"},
            HTTP_AUTHORIZATION=f"Token {token}",
        )
        self.assertEqual(resp.status_code, 201)
