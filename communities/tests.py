"""Tests for communities."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import Community, CommunityMember

User = get_user_model()


class CommunityModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="x")

    def test_slug_auto_populates(self):
        c = Community.objects.create(name="My Cool Group", owner=self.owner)
        self.assertEqual(c.slug, "my-cool-group")

    def test_slug_collisions_increment(self):
        Community.objects.create(name="Hiking", owner=self.owner)
        c2 = Community.objects.create(name="Hiking ", owner=self.owner)  # different name
        # Different name "Hiking " strips to "hiking" — slug must dedupe.
        self.assertNotEqual(c2.slug, "hiking")

    def test_role_and_member_helpers(self):
        c = Community.objects.create(name="Gardeners", owner=self.owner)
        CommunityMember.objects.create(
            community=c, user=self.owner,
            role=CommunityMember.OWNER, status=CommunityMember.ACTIVE,
        )
        self.assertEqual(c.role_of(self.owner), CommunityMember.OWNER)
        self.assertTrue(c.is_admin(self.owner))
        self.assertEqual(c.member_count, 1)


class CommunityViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="x")
        self.user = User.objects.create_user(username="alice", password="x")
        self.community = Community.objects.create(name="Builders", owner=self.owner)
        CommunityMember.objects.create(
            community=self.community, user=self.owner,
            role=CommunityMember.OWNER, status=CommunityMember.ACTIVE,
        )

    def test_list_anon(self):
        r = self.client.get(reverse("communities:list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Builders")

    def test_detail_anon(self):
        r = self.client.get(reverse("communities:detail", kwargs={"slug": self.community.slug}))
        self.assertEqual(r.status_code, 200)

    def test_join_public(self):
        self.client.login(username="alice", password="x")
        r = self.client.post(
            reverse("communities:join", kwargs={"slug": self.community.slug}),
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.community.is_member(self.user))

    def test_join_private_creates_pending(self):
        priv = Community.objects.create(
            name="Secret Garden", owner=self.owner, privacy=Community.PRIVATE,
        )
        CommunityMember.objects.create(
            community=priv, user=self.owner,
            role=CommunityMember.OWNER, status=CommunityMember.ACTIVE,
        )
        self.client.login(username="alice", password="x")
        self.client.post(
            reverse("communities:join", kwargs={"slug": priv.slug}),
            follow=True,
        )
        self.assertTrue(priv.has_pending_request(self.user))
        self.assertFalse(priv.is_member(self.user))

    def test_leave(self):
        CommunityMember.objects.create(
            community=self.community, user=self.user,
            role=CommunityMember.MEMBER, status=CommunityMember.ACTIVE,
        )
        self.client.login(username="alice", password="x")
        self.client.post(
            reverse("communities:leave", kwargs={"slug": self.community.slug}),
            follow=True,
        )
        self.assertFalse(self.community.is_member(self.user))

    def test_owner_cannot_leave(self):
        self.client.login(username="owner", password="x")
        self.client.post(
            reverse("communities:leave", kwargs={"slug": self.community.slug}),
            follow=True,
        )
        # Owner is still a member.
        self.assertTrue(self.community.is_member(self.owner))

    def test_manage_only_admin(self):
        self.client.login(username="alice", password="x")
        r = self.client.get(reverse("communities:manage", kwargs={"slug": self.community.slug}))
        self.assertEqual(r.status_code, 403)
        self.client.login(username="owner", password="x")
        r = self.client.get(reverse("communities:manage", kwargs={"slug": self.community.slug}))
        self.assertEqual(r.status_code, 200)

    def test_create_community(self):
        self.client.login(username="alice", password="x")
        r = self.client.post(reverse("communities:create"), {
            "name": "Bookworms",
            "description": "We read.",
            "privacy": Community.PUBLIC,
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        c = Community.objects.get(name="Bookworms")
        self.assertTrue(c.is_member(self.user))
        self.assertEqual(c.role_of(self.user), CommunityMember.OWNER)
