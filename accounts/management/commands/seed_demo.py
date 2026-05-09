"""Seed demo data: international users with full profiles, realistic posts,
and real-looking story photos.

Run with:
    python manage.py seed_demo                          # 40/250/20 default
    python manage.py seed_demo --users 40 --posts 250 --stories 20
    python manage.py seed_demo --offline                # skip image downloads (gradients only)
    python manage.py seed_demo --wipe                   # delete all demo_* users

Profiles are fully populated:
  - international (non-Turkish) names
  - avatar (ui-avatars.com initials)
  - cover photo (picsum.photos scenic)
  - bio + location + website + 2-4 interests
  - email_verified + onboarded

Stories use real scenic photos from Lorem Picsum (picsum.photos), themed
by topic (food / travel / city / nature / studio).
"""
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw

from accounts.models import Follow, Interest
from communities.models import Community, CommunityMember
from messaging.models import Conversation, Message
from posts.models import Comment, Like, Post, Story
from posts.views import _attach_hashtags

User = get_user_model()


def _bulk_download(url_name_pairs, max_workers=8, timeout=15):
    """Fetch many URLs in parallel. Input: list of (url, name, key) tuples.
    Returns: dict {key: ContentFile}. Failed entries are skipped.
    """
    results = {}

    def _fetch(item):
        url, name, key = item
        try:
            r = requests.get(url, timeout=timeout, allow_redirects=True)
            if r.ok and r.content:
                return key, ContentFile(r.content, name=name)
        except Exception:
            pass
        return key, None

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for key, content in ex.map(_fetch, url_name_pairs):
            if content is not None:
                results[key] = content
    return results


# ---------- name pools (no Turkish names) ----------------------------------

FIRST_NAMES = [
    # English / Anglo
    "Alex", "Maya", "Liam", "Nora", "Theo", "Sam", "Emma", "James", "Sophia",
    "Oliver", "Charlotte", "William", "Amelia", "Henry", "Mia", "Benjamin",
    "Harper", "Lucas", "Evelyn", "Mason", "Ava", "Ethan", "Isabella", "Noah",
    # European
    "Lea", "Lukas", "Anya", "Pieter", "Matteo", "Ines", "Erik", "Klara",
    "Aoife", "Niklas", "Sofia", "Mikael", "Elise", "Bjorn", "Camille",
    # Asian
    "Hiroshi", "Mei", "Aarav", "Yuki", "Priya", "Kenji", "Aiko", "Ravi",
    "Chen", "Hana", "Jun", "Sakura",
    # Latin / Iberian
    "Diego", "Camila", "Mateo", "Valentina", "Lucia", "Gabriel", "Isabela",
    # African / Middle-East
    "Zara", "Amir", "Yara", "Layla", "Tariq", "Nia", "Omar", "Sade",
]

LAST_NAMES = [
    # English / Anglo
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Martin", "Walker",
    "Wright", "Carter", "Mitchell", "Reed", "Bennett", "Murphy",
    # European
    "Schmidt", "Mueller", "Rossi", "Romano", "Garcia", "Martinez", "Hernandez",
    "Petrov", "Ivanov", "Kowalski", "Novak", "van Dijk", "Lindgren", "Eriksson",
    # Asian
    "Tanaka", "Suzuki", "Yamamoto", "Watanabe", "Chen", "Wang", "Li", "Kim",
    "Park", "Nguyen", "Patel", "Singh", "Sharma", "Khan",
    # Latin
    "Silva", "Santos", "Oliveira", "Ferreira", "Lopez", "Vargas",
]

# ---------- profile content ------------------------------------------------

LOCATIONS = [
    "London, UK", "Berlin, DE", "Lisbon, PT", "Tokyo, JP", "Sao Paulo, BR",
    "Cape Town, ZA", "Helsinki, FI", "Reykjavik, IS", "Toronto, CA",
    "Melbourne, AU", "Singapore", "Mumbai, IN", "Mexico City, MX",
    "Amsterdam, NL", "Stockholm, SE", "Dublin, IE", "Buenos Aires, AR",
    "Vancouver, CA", "Madrid, ES", "Vienna, AT", "Seoul, KR", "Barcelona, ES",
]

BIOS = [
    "Backend dev who loves Django and good coffee. Building things that matter.",
    "Photographer / hiker / pasta enthusiast. Always chasing the golden hour.",
    "Building little tools. UI nerd. Saturday-morning bookstore lurker.",
    "Writer, runner, plant parent. Currently 3 books deep into the year.",
    "Music producer. Always shipping. DM me your favourite synth presets.",
    "Researcher / late-night reader. Notes app permanently open.",
    "Designer who codes. Cat-tax payable on first DM.",
    "Frontend by day, gardener by weekend. Tomatoes are winning.",
    "Coffee, code, and quiet mornings. Still trying to learn Spanish.",
    "Just here to share what I'm learning. Mostly software, sometimes baking.",
    "Product manager turning ideas into shipped things. Hot-takes welcome.",
    "Cyclist. Vinyl collector. Sometimes I write.",
    "Working on a small zine about typography. Open to chat about anything.",
    "Engineer at a tiny startup. Currently obsessed with type systems.",
    "Indie game dev / pixel artist / occasional streamer.",
    "Marathon hobbyist. Engineering manager. Dad to two huskies.",
    "Open-source maintainer. Conference speaker. Sourdough enthusiast.",
    "Studying ML, building side projects, and trying to drink more water.",
    "Writer of small things. Reader of long things. Watcher of slow films.",
    "Co-founder. Trying to make boring software a little less boring.",
]

WEBSITE_TLDS = ["com", "dev", "io", "me", "blog", "studio", "art"]


# ---------- post / comment / story content ---------------------------------

POST_TEMPLATES = [
    "Sunset over {place} today {tag}",
    "Reading list for the month {tag} - any recommendations?",
    "Tried a new pasta recipe tonight {tag} {tag2}",
    "Morning run: 8km along the river {tag}",
    "Best book I read this year, hands down. {tag}",
    "Coffee shop discovery: cold brew that actually slaps {tag}",
    "New album on repeat all weekend {tag}",
    "Took the long way home today. Worth it.",
    "If you're wondering, yes - {tag} pairs surprisingly well with {tag2}.",
    "Trying out {tag} for the first time - early thoughts: positive.",
    "First snow of the year. {place} is unreal in winter.",
    "Photo dump from last weekend's hike {tag}",
    "Currently rewatching that one show that actually held up. You know the one. {tag}",
    "Sourdough loaf number five - I think we're getting there {tag} {tag2}",
    "Just hung the gallery wall I've been planning for months {tag}",
    "Made jam from the garden plums today {tag} {tag2}",
    "Spent the morning at the farmer's market {tag}",
    "Three weeks of yoga and my back finally agrees with me {tag}",
    "Brought home a vinyl find I've been hunting for years {tag}",
    "Repotted half the apartment this weekend {tag}",
    "First half-marathon - never thought I'd say that {tag}",
    "Finally finished that 1000-piece puzzle. Worth every hour {tag}",
    "Made proper risotto for the first time. 25 minutes of stirring. Worth it {tag}",
    "Zine layout drafts for the next issue {tag} {tag2}",
    "Studio cleanup day. Every brush back where it belongs {tag}",
    "Picked up a new film stock for the trip {tag}",
    "Bonfire night with the neighbours {tag}",
    "Sunday brunch experiment: ricotta hotcakes {tag}",
    "Bookstore find of the year. Already 80 pages in {tag}",
    "Took the early train just to catch the morning light over {place}",
]

HASHTAG_POOL = [
    # Food & drink
    "cooking", "baking", "coffee", "pasta", "sourdough", "foodie", "brunch",
    "cocktails", "vegetarian",
    # Outdoors & fitness
    "photography", "travel", "hiking", "running", "cycling", "yoga", "fitness",
    "climbing", "surfing", "camping",
    # Arts & creativity
    "art", "design", "fashion", "music", "vinyl", "film", "ceramics",
    "sketching", "calligraphy", "writing",
    # Lifestyle & home
    "books", "minimalism", "gardening", "interiors", "journaling",
    "mindfulness", "podcasts",
]

COMMENT_TEMPLATES = [
    "Love this!", "Same here", "Where was this taken?", "Sharing this with my team.",
    "Underrated take.", "Yes - exactly this.", "Adding to my reading list.",
    "Have you tried {tag}? Pairs well.", "Solid write-up.", "Saved.",
    "Hard agree.", "Going to try this tonight.", "Beautiful shot.",
    "This is the way.", "Subscribed.", "Bookmarked for the weekend.",
    "Mind sharing the recipe?", "Such a clean approach.",
    "Curious how you handle the edge case at {tag}.",
    "Deeply relatable.", "I learned something today.",
]

DM_OPENERS = [
    "hey! how was the hike?",
    "yo, the album you mentioned is great",
    "morning! coffee at the usual spot?",
    "saw your sourdough on the feed - recipe??",
    "free this Saturday?",
    "loved the pasta photo last night",
    "did you ever finish that book?",
    "trying that bakery you posted about today",
    "you around this weekend?",
    "your shot from yesterday is unreal",
    "have you been to that cafe on the corner?",
    "checking in - how's the project?",
    "tomato update?",
    "did you catch the new podcast episode?",
    "got the climbing day on the calendar yet?",
    "those vinyl finds though",
    "are you doing the trail run tomorrow?",
]

DM_REPLIES = [
    "amazing, definitely going back",
    "yes! it's been on repeat",
    "I'll be there in 20",
    "let me grab the recipe and DM",
    "yes please",
    "thanks! used the new lens",
    "almost done, last 50 pages",
    "let me know how it is",
    "yep, what's up?",
    "thank you, took it at golden hour",
    "yes - their cold brew slaps",
    "going well, almost done",
    "they are huge now lol",
    "yes! the segment on minimalism was great",
    "Saturday works",
    "I scored a first pressing!!",
    "yep, see you at 7",
    "running late but on my way",
    "send me the link?",
    "haha same",
]

DM_FOLLOWUPS = [
    "let me know when you're free",
    "want to grab dinner after?",
    "bring the camera",
    "any plans for the weekend?",
    "I might bring a friend, ok?",
    "we should do this more",
    "Saturday morning?",
    "wear good shoes lol",
    "let's talk more later",
    "save me a spot",
    "I'll send the address",
    "no worries, take your time",
    "no rush :)",
]

GROUP_CHATS_DATA = [
    ("Climbing weekends",
     ["anyone up for tomorrow?", "I'm in", "10am at the usual spot?",
      "can't tomorrow but Sunday yes", "shared the route in the doc",
      "thanks!", "any beginners welcome?", "bringing the new shoes",
      "weather forecast looks good", "see you all there", "running 10 min late",
      "no worries, we'll wait"]),
    ("Coffee crew",
     ["tasted that new bean today, lemon notes are wild", "where from??",
      "the small place on 5th", "going there tomorrow morning",
      "I'm in if you want company", "8:30?", "perfect", "save me a seat",
      "ordered yours already", "you're the best"]),
    ("Photo walk Saturdays",
     ["this Saturday: harbor at sunrise?", "yes",
      "how early?", "5:30 to catch the light",
      "ouch but in", "bringing the wide angle",
      "I'll do mostly black and white this time",
      "shooting on film today, going to be fun"]),
    ("Sourdough club",
     ["mine collapsed again", "what's your hydration?",
      "78%", "try 72 next time", "thanks, will do",
      "scoring tutorial that finally clicked: link soon",
      "yes please share", "uploaded to the doc"]),
]


COMMUNITIES_DATA = [
    ("Coffee Lovers",
     "For everyone who takes their coffee seriously. Pour-over tips, beans, gear, and the occasional bad latte.",
     "coffee"),
    ("Photography Club",
     "Share your shots, ask for feedback, learn together. From phone snaps to medium format - all welcome.",
     "photography"),
    ("Sourdough Bakers",
     "Levain schedules, scoring patterns, and bread photos that should not be this beautiful.",
     "sourdough"),
    ("Hikers United",
     "Trail reports, gear advice, weekend trip planning. All paces welcome.",
     "hiking"),
    ("Vintage Vinyl",
     "Records, turntables, and the hunt for that one rare pressing.",
     "vinyl"),
    ("Climbing Crew",
     "Routes, projects, beta, gym reports. From V0 to V12.",
     "climbing"),
    ("Gardeners Guild",
     "Tomatoes, succulents, balcony herbs - whatever grows in your patch.",
     "gardening"),
    ("Travel Stories",
     "Where you went, what you ate, what surprised you. Share the route.",
     "travel"),
    ("Film & TV Lovers",
     "Currently watching, hidden gems, and warm takes.",
     "film"),
    ("Minimalist Living",
     "Less stuff, more intention. Routines, swaps, and quiet wins.",
     "minimalism"),
    ("Yoga Daily",
     "Flows, postures, breathwork. Gentle reminders to roll out the mat.",
     "yoga"),
    ("Fashion & Style",
     "Outfits, secondhand finds, and what's in your rotation.",
     "fashion"),
]

STORY_THEMES = [
    ("Morning coffee", "coffee"),
    ("On the road", "road"),
    ("Studio session", "studio"),
    ("Weekend project", "workshop"),
    ("Sunset run", "sunset"),
    ("Quick break", "city"),
    ("New build day", "tech"),
    ("Pasta night", "food"),
    ("Bookstore find", "books"),
    ("View from the desk", "desk"),
    ("Trail day", "mountain"),
    ("Late-night code", "laptop"),
    ("Latte art", "cafe"),
    ("Vinyl haul", "music"),
    ("Garden update", "plants"),
    ("Sky over the city", "skyline"),
    ("Weekend escape", "beach"),
    ("Coffee #2", "coffee"),
    ("Gallery visit", "art"),
    ("First snow", "winter"),
    ("Studio gear", "studio"),
    ("Sunday brunch", "food"),
    ("Window seat", "train"),
    ("Workshop progress", "wood"),
    ("After-work walk", "street"),
    ("Bonfire night", "fire"),
]


# ---------- helpers --------------------------------------------------------

def _gradient_image(name="img.jpg", size=(480, 720)):
    """PIL-rendered linear gradient — used as offline fallback."""
    img = Image.new("RGB", size, color=(0, 0, 0))
    draw = ImageDraw.Draw(img)
    c1 = tuple(random.randint(120, 240) for _ in range(3))
    c2 = tuple(random.randint(120, 240) for _ in range(3))
    h = size[1]
    for y in range(h):
        t = y / h
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        draw.line([(0, y), (size[0], y)], fill=(r, g, b))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return ContentFile(buf.getvalue(), name=name)


def _download(url, name, timeout=15):
    """Fetch a URL, return ContentFile or None on failure."""
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True)
        if r.ok and r.content:
            return ContentFile(r.content, name=name)
    except Exception:
        pass
    return None


def _fetch_random_portraits(n, offline=False):
    """Bulk-fetch n real-looking portrait URLs from randomuser.me.

    Pulls in batches because the API caps individual calls. Returns a list
    of URL strings; falls back to an empty list (caller substitutes a gradient)
    if anything goes wrong or `offline=True`.
    """
    if offline or n <= 0:
        return []
    urls = []
    page = 1
    BATCH = 100  # randomuser.me handles this comfortably
    while len(urls) < n:
        want = min(BATCH, n - len(urls))
        url = (
            "https://randomuser.me/api/"
            f"?results={want}&inc=picture&page={page}"
            "&nat=us,gb,fr,de,jp,br,nl,es,it,au,ca,no,ch,nz,ie"
            "&seed=socialhub-demo"
        )
        try:
            r = requests.get(url, timeout=20)
            if not r.ok:
                break
            results = r.json().get("results", [])
            if not results:
                break
            for u in results:
                urls.append(u["picture"]["large"])
        except Exception:
            break
        page += 1
    return urls[:n]


def _avatar_for(user, photo_url=None, offline=False):
    if offline:
        return _gradient_image(name=f"{user.username}_avatar.jpg", size=(256, 256))
    if photo_url:
        img = _download(photo_url, f"{user.username}_avatar.jpg")
        if img:
            return img
    # Fallback: ui-avatars initials → gradient.
    name = f"{user.first_name}+{user.last_name}".replace(" ", "+")
    fallback_url = (
        f"https://ui-avatars.com/api/"
        f"?name={name}&size=256&background=random&color=fff&font-size=0.45&bold=true"
    )
    img = _download(fallback_url, f"{user.username}_avatar.png")
    return img or _gradient_image(name=f"{user.username}_avatar.jpg", size=(256, 256))


def _cover_for(user, offline=False):
    if offline:
        return _gradient_image(name=f"{user.username}_cover.jpg", size=(1200, 400))
    seed = abs(hash("cover-" + user.username)) % 10000
    url = f"https://picsum.photos/seed/cover-{seed}/1200/400"
    img = _download(url, f"{user.username}_cover.jpg")
    return img or _gradient_image(name=f"{user.username}_cover.jpg", size=(1200, 400))


def _story_image(idx, theme_tag, offline=False):
    if offline:
        return _gradient_image(name=f"story_{idx:03d}.jpg", size=(480, 720))
    seed = abs(hash(f"story-{theme_tag}-{idx}")) % 10000
    url = f"https://picsum.photos/seed/{seed}/480/720"
    img = _download(url, f"story_{idx:03d}.jpg")
    return img or _gradient_image(name=f"story_{idx:03d}.jpg", size=(480, 720))


def _website_for(user):
    tld = random.choice(WEBSITE_TLDS)
    return f"https://{user.username.replace('_', '')}.{tld}"


# ---------- command --------------------------------------------------------

class Command(BaseCommand):
    help = "Seed demo international users, posts, stories and interactions."

    DEFAULT_INTERESTS = [
        "Cooking", "Fitness", "Hiking", "Music", "Photo",
        "Reading", "Travel", "UI/UX", "Coffee", "Cinema",
        "Gaming", "Cycling", "Writing", "Design", "Open Source",
    ]

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=40)
        parser.add_argument("--posts", type=int, default=250)
        # Default = users * 1.5 so every demo user has at least one active story.
        parser.add_argument("--stories", type=int, default=60)
        parser.add_argument("--communities", type=int, default=12,
                            help="Number of topical communities to create.")
        parser.add_argument("--dms", type=int, default=4,
                            help="DM conversations per demo user.")
        parser.add_argument("--groups", type=int, default=4,
                            help="Number of group chats to create.")
        parser.add_argument("--seed", type=int, default=None)
        parser.add_argument("--offline", action="store_true",
                            help="Skip image downloads (gradient placeholders).")
        parser.add_argument("--wipe", action="store_true",
                            help="Delete all demo_* users and exit.")

    def handle(self, *args, **opts):
        if opts["seed"] is not None:
            random.seed(opts["seed"])

        if opts["wipe"]:
            n, _ = User.objects.filter(username__startswith="demo_").delete()
            self.stdout.write(self.style.SUCCESS(f"Wiped {n} demo records."))
            return

        offline = opts["offline"]
        n_users = opts["users"]
        n_posts = opts["posts"]
        n_stories = opts["stories"]

        if offline:
            self.stdout.write(self.style.WARNING("Offline mode: gradient placeholders only."))

        self._ensure_interests()

        self.stdout.write(f"Creating {n_users} users with full profiles...")
        users = self._make_users(n_users, offline=offline)
        self.stdout.write(self.style.SUCCESS(f"  -> {len(users)} users created."))

        self.stdout.write("Building follow graph...")
        n_follows = self._make_follows(users)
        self.stdout.write(self.style.SUCCESS(f"  -> {n_follows} follow edges."))

        self.stdout.write(f"Creating {n_posts} posts (round-robin, with images)...")
        posts = self._make_posts(users, n_posts, offline=offline)
        self.stdout.write(self.style.SUCCESS(f"  -> {len(posts)} posts created."))

        self.stdout.write("Adding likes / reactions...")
        n_likes = self._make_likes(users, posts)
        self.stdout.write(self.style.SUCCESS(f"  -> {n_likes} reactions added."))

        self.stdout.write("Adding comments...")
        n_comments = self._make_comments(users, posts)
        self.stdout.write(self.style.SUCCESS(f"  -> {n_comments} comments added."))

        self.stdout.write(f"Creating {n_stories} stories with real photos...")
        n_st = self._make_stories(users, n_stories, offline=offline)
        self.stdout.write(self.style.SUCCESS(f"  -> {n_st} stories created."))

        n_communities = opts["communities"]
        self.stdout.write(f"Creating {n_communities} communities...")
        n_c = self._make_communities(users, n_communities, offline=offline)
        self.stdout.write(self.style.SUCCESS(f"  -> {n_c} communities created."))

        n_dms = opts["dms"]
        n_groups = opts["groups"]
        self.stdout.write(f"Creating DM conversations ({n_dms} per demo user) and {n_groups} group chats...")
        dm_count, msg_count = self._make_dms(users, per_user=n_dms)
        self.stdout.write(self.style.SUCCESS(
            f"  -> {dm_count} DM conversations, {msg_count} messages."
        ))
        g_count, g_msg = self._make_groups(users, n=n_groups)
        self.stdout.write(self.style.SUCCESS(
            f"  -> {g_count} group chats, {g_msg} messages."
        ))

        empty_filled, empty_msgs = self._populate_empty_conversations(users)
        if empty_filled:
            self.stdout.write(self.style.SUCCESS(
                f"  -> populated {empty_filled} previously-empty conversations with {empty_msgs} messages."
            ))

        # Wipe sidebar/cached data so the running server picks up the new content
        # immediately without waiting for the 60s TTL to expire.
        cache.clear()

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Demo users: demo_001 ... demo_{n_users:03d}, password = demo12345."
            f"\nCache cleared — refresh the browser to see the new content."
        ))

    # ---------- builders ---------------------------------------------------

    def _ensure_interests(self):
        for name in self.DEFAULT_INTERESTS:
            Interest.objects.get_or_create(name=name)

    def _existing_demo_count(self):
        return User.objects.filter(username__startswith="demo_").count()

    def _make_users(self, n, offline=False):
        all_interests = list(Interest.objects.all())
        start = self._existing_demo_count()

        # Bulk-fetch n real-looking portrait URLs once (much faster than per-user).
        if not offline:
            self.stdout.write("    fetching portraits from randomuser.me...")
        portrait_urls = _fetch_random_portraits(n, offline=offline)
        if not offline and portrait_urls:
            self.stdout.write(self.style.SUCCESS(
                f"    -> {len(portrait_urls)} portraits ready."
            ))

        # Bulk-download all avatars + covers in parallel.
        download_jobs = []
        username_list = []
        for i in range(n):
            username = f"demo_{start + i + 1:03d}"
            username_list.append(username)
            avatar_url = portrait_urls[i] if i < len(portrait_urls) else None
            if avatar_url and not offline:
                download_jobs.append((avatar_url, f"{username}_avatar.jpg", f"avatar:{username}"))
            cover_seed = abs(hash("cover-" + username)) % 10000
            cover_url = f"https://picsum.photos/seed/cover-{cover_seed}/1200/400"
            if not offline:
                download_jobs.append((cover_url, f"{username}_cover.jpg", f"cover:{username}"))

        if download_jobs:
            self.stdout.write(f"    downloading {len(download_jobs)} images in parallel...")
        downloaded = _bulk_download(download_jobs, max_workers=10) if download_jobs else {}

        users = []
        for i in range(n):
            idx = start + i + 1
            username = username_list[i]
            if User.objects.filter(username=username).exists():
                continue
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password="demo12345",
                first_name=first,
                last_name=last,
            )
            profile = user.profile
            profile.display_name = f"{first} {last}"
            profile.bio = random.choice(BIOS)
            profile.location = random.choice(LOCATIONS)
            profile.website = _website_for(user)
            profile.email_verified = True
            profile.onboarded = True
            avatar = downloaded.get(f"avatar:{username}") or _gradient_image(
                name=f"{username}_avatar.jpg", size=(256, 256)
            )
            profile.avatar.save(avatar.name, avatar, save=False)
            cover = downloaded.get(f"cover:{username}") or _gradient_image(
                name=f"{username}_cover.jpg", size=(1200, 400)
            )
            profile.cover.save(cover.name, cover, save=False)
            profile.save()
            if all_interests:
                k = random.randint(2, min(4, len(all_interests)))
                profile.interests.set(random.sample(all_interests, k))
            users.append(user)
            if (i + 1) % 10 == 0:
                self.stdout.write(f"    ... {i+1}/{n}")
        return users

    def _make_follows(self, users):
        if len(users) < 2:
            return 0
        edges = 0
        for u in users:
            n_follow = random.randint(2, min(15, len(users) - 1))
            targets = random.sample([x for x in users if x.id != u.id], n_follow)
            for t in targets:
                _, created = Follow.objects.get_or_create(follower=u, following=t)
                if created:
                    edges += 1
        return edges

    def _make_posts(self, users, n, offline=False):
        """Distribute n posts across users round-robin so every user has at
        least floor(n / len(users)) posts, then a random tail. Every post
        gets a downloaded picsum image."""
        if not users:
            return []
        posts = []
        now = timezone.now()

        # Phase 1: round-robin author assignment ensures even distribution.
        authors = []
        for i in range(n):
            authors.append(users[i % len(users)])
        # Shuffle so post created_at order is mixed across authors.
        random.shuffle(authors)

        # Phase 2: bulk-download all post images in parallel.
        if not offline:
            self.stdout.write(f"    downloading {n} post images in parallel...")
        download_jobs = []
        for i in range(n):
            seed = abs(hash(f"post-img-{i}")) % 10000
            url = f"https://picsum.photos/seed/{seed}/800/600"
            download_jobs.append((url, f"post_{i:04d}.jpg", f"post:{i}"))
        images = _bulk_download(download_jobs, max_workers=12) if not offline else {}

        # Phase 3: create posts sequentially.
        for i in range(n):
            author = authors[i]
            tag1 = "#" + random.choice(HASHTAG_POOL)
            tag2 = "#" + random.choice(HASHTAG_POOL)
            place = random.choice(LOCATIONS).split(",")[0]
            template = random.choice(POST_TEMPLATES)
            body = template.format(tag=tag1, tag2=tag2, place=place)
            offset_minutes = random.randint(0, 30 * 24 * 60)
            created_at = now - timedelta(minutes=offset_minutes)
            post = Post.objects.create(
                author=author,
                body=body,
                location=random.choice(LOCATIONS) if random.random() < 0.3 else "",
                visibility=Post.PUBLIC,
            )
            img = images.get(f"post:{i}") or _gradient_image(
                name=f"post_{i:04d}.jpg", size=(800, 600)
            )
            post.image.save(img.name, img, save=True)
            Post.objects.filter(pk=post.pk).update(created_at=created_at, updated_at=created_at)
            _attach_hashtags(post, post.body)
            posts.append(post)
            if (i + 1) % 50 == 0:
                self.stdout.write(f"    ... {i+1}/{n}")
        return posts

    def _make_likes(self, users, posts):
        n = 0
        emojis = [Like.HEART, Like.HEART, Like.HEART, Like.LAUGH,
                  Like.FIRE, Like.WOW, Like.CLAP, Like.SAD]
        for post in posts:
            cap = max(0, int(random.gammavariate(2.0, 2.5)))
            cap = min(cap, len(users) - 1)
            if cap == 0:
                continue
            likers = random.sample([u for u in users if u.id != post.author_id], cap)
            for u in likers:
                Like.objects.create(user=u, post=post, emoji=random.choice(emojis))
                n += 1
        return n

    def _make_comments(self, users, posts):
        n = 0
        target_posts = random.sample(posts, k=int(len(posts) * 0.4))
        for post in target_posts:
            for _ in range(random.randint(1, 4)):
                commenter = random.choice([u for u in users if u.id != post.author_id])
                tag = "#" + random.choice(HASHTAG_POOL)
                body = random.choice(COMMENT_TEMPLATES).format(tag=tag)
                Comment.objects.create(post=post, author=commenter, body=body)
                n += 1
        return n

    def _make_stories(self, users, n, offline=False):
        """Ensure every user has at least one active story; if `n` is bigger
        than the user count, the extras are sprinkled randomly. All story
        images are real picsum photos pulled in parallel."""
        if not users:
            return 0

        # Build the author list: every user appears at least once, then random extras.
        authors = list(users)
        random.shuffle(authors)
        while len(authors) < n:
            authors.append(random.choice(users))
        authors = authors[:max(n, len(users))]
        n = len(authors)

        # Phase 1: bulk-download all story images in parallel.
        if not offline:
            self.stdout.write(f"    downloading {n} story photos in parallel...")
        download_jobs = []
        themes = []
        for i in range(n):
            caption, theme_tag = random.choice(STORY_THEMES)
            themes.append(caption)
            seed = abs(hash(f"story-{theme_tag}-{i}")) % 10000
            url = f"https://picsum.photos/seed/{seed}/480/720"
            download_jobs.append((url, f"story_{i:03d}.jpg", f"story:{i}"))
        images = _bulk_download(download_jobs, max_workers=10) if not offline else {}

        # Phase 2: create stories sequentially.
        now = timezone.now()
        created = 0
        for i in range(n):
            img = images.get(f"story:{i}") or _gradient_image(
                name=f"story_{i:03d}.jpg", size=(480, 720)
            )
            story = Story.objects.create(
                author=authors[i],
                image=img,
                caption=themes[i],
            )
            offset_min = random.randint(5, 22 * 60)
            new_created = now - timedelta(minutes=offset_min)
            new_expires = new_created + timedelta(hours=24)
            Story.objects.filter(pk=story.pk).update(
                created_at=new_created,
                expires_at=new_expires,
            )
            created += 1
            if (i + 1) % 10 == 0:
                self.stdout.write(f"    ... {i+1}/{n}")
        return created

    def _make_communities(self, users, n, offline=False):
        """Create up to `n` topical communities, each with avatar, cover,
        owner, 1-2 admins, 5-20 members, and 4-10 community-tagged posts."""
        if not users:
            return 0
        templates = COMMUNITIES_DATA[:n]

        # Skip any community names that already exist (idempotent re-runs).
        templates = [t for t in templates if not Community.objects.filter(name=t[0]).exists()]
        if not templates:
            return 0

        # Phase 1: bulk-download avatars + covers in parallel.
        download_jobs = []
        for i, (name, _, theme) in enumerate(templates):
            seed = abs(hash("comm-" + name)) % 10000
            download_jobs.append((
                f"https://picsum.photos/seed/comm-avatar-{seed}/256/256",
                f"comm_{i}_avatar.jpg",
                f"avatar:{i}",
            ))
            download_jobs.append((
                f"https://picsum.photos/seed/comm-cover-{seed}/1200/400",
                f"comm_{i}_cover.jpg",
                f"cover:{i}",
            ))
        if not offline and download_jobs:
            self.stdout.write(f"    downloading {len(download_jobs)} community images...")
        images = _bulk_download(download_jobs, max_workers=10) if not offline else {}

        # Phase 2: create communities, members, and tag a few posts.
        n_created = 0
        for i, (name, desc, theme) in enumerate(templates):
            owner = random.choice(users)
            community = Community.objects.create(
                name=name,
                description=desc,
                owner=owner,
                privacy=Community.PUBLIC,
            )
            avatar = images.get(f"avatar:{i}") or _gradient_image(
                name=f"comm_{i}_avatar.jpg", size=(256, 256)
            )
            community.avatar.save(avatar.name, avatar, save=False)
            cover = images.get(f"cover:{i}") or _gradient_image(
                name=f"comm_{i}_cover.jpg", size=(1200, 400)
            )
            community.cover.save(cover.name, cover, save=False)
            community.save()

            # Owner membership.
            CommunityMember.objects.create(
                community=community, user=owner,
                role=CommunityMember.OWNER, status=CommunityMember.ACTIVE,
            )

            # Pick 5-20 random members (no overlap with owner).
            pool = [u for u in users if u.id != owner.id]
            n_members = random.randint(min(5, len(pool)), min(20, len(pool)))
            chosen = random.sample(pool, n_members)
            n_admins = random.randint(1, 2)
            for u in chosen[:n_admins]:
                CommunityMember.objects.create(
                    community=community, user=u,
                    role=CommunityMember.ADMIN, status=CommunityMember.ACTIVE,
                )
            for u in chosen[n_admins:]:
                CommunityMember.objects.create(
                    community=community, user=u,
                    role=CommunityMember.MEMBER, status=CommunityMember.ACTIVE,
                )

            # Tag 4-10 of the community's members' existing posts as community posts.
            member_ids = [owner.id] + [u.id for u in chosen]
            qs = Post.objects.filter(
                author_id__in=member_ids, community__isnull=True,
            ).order_by("?")
            target = qs[:random.randint(4, 10)]
            for p in target:
                p.community = community
                p.save(update_fields=["community"])

            n_created += 1
        return n_created

    # ---------- messaging --------------------------------------------------

    def _populate_dm(self, conv, u1, u2, n_msgs=None):
        """Generate a realistic alternating dialogue between two users.
        Backdates timestamps within the last 7 days. Last 1-3 messages stay
        unread for whoever didn't send them, so the inbox shows badges."""
        n_msgs = n_msgs or random.randint(4, 12)
        senders = [u1, u2] if random.random() > 0.5 else [u2, u1]
        # Anchor the first message somewhere in the past 7 days, then pile up.
        base = timezone.now() - timedelta(
            days=random.uniform(0.05, 7.0)
        )
        running = base
        last_msgs = []
        for i in range(n_msgs):
            sender = senders[i % 2]
            if i == 0:
                body = random.choice(DM_OPENERS)
            elif i % 4 == 0:
                body = random.choice(DM_FOLLOWUPS)
            else:
                body = random.choice(DM_REPLIES)
            running = running + timedelta(minutes=random.randint(2, 240))
            msg = Message.objects.create(
                conversation=conv, sender=sender, body=body,
            )
            Message.objects.filter(pk=msg.pk).update(created_at=running)
            last_msgs.append(msg)

        # Mark the last 1-3 messages as unread (typical inbox state); older as read.
        unread_tail = random.randint(1, min(3, len(last_msgs)))
        if len(last_msgs) > unread_tail:
            Message.objects.filter(
                pk__in=[m.pk for m in last_msgs[:-unread_tail]]
            ).update(is_read=True)

        # Bump conversation.updated_at so inbox sorts naturally.
        Conversation.objects.filter(pk=conv.pk).update(updated_at=running)
        return len(last_msgs)

    def _make_dms(self, users, per_user=4):
        """For each demo user, ensure they have ~per_user DMs with messages."""
        if len(users) < 2:
            return 0, 0
        convs_created = 0
        msgs_created = 0
        for user in users:
            # Skip if user already has plenty of populated DMs.
            existing = Conversation.objects.filter(
                participants=user, is_group=False,
            ).filter(messages__isnull=False).distinct().count()
            if existing >= per_user:
                continue
            need = per_user - existing
            partner_pool = [u for u in users if u.id != user.id]
            partners = random.sample(partner_pool, min(need, len(partner_pool)))
            for partner in partners:
                conv = Conversation.between(user, partner)
                if conv.messages.exists():
                    continue
                n = self._populate_dm(conv, user, partner)
                convs_created += 1
                msgs_created += n
        return convs_created, msgs_created

    def _make_groups(self, users, n=4):
        """Create up to `n` group chats among demo users with realistic banter."""
        if len(users) < 3 or n <= 0:
            return 0, 0
        templates = GROUP_CHATS_DATA[:n]
        created = 0
        msgs = 0
        for name, scripted_msgs in templates:
            if Conversation.objects.filter(name=name, is_group=True).exists():
                continue
            creator = random.choice(users)
            n_members = random.randint(2, 4)
            members = random.sample(
                [u for u in users if u.id != creator.id], n_members,
            )
            conv = Conversation.create_group(
                creator=creator, name=name, members=members,
            )
            participants = [creator] + list(members)

            base = timezone.now() - timedelta(days=random.uniform(0.2, 5.0))
            running = base
            sender_idx = 0
            for body in scripted_msgs:
                running = running + timedelta(minutes=random.randint(1, 90))
                # Quasi-natural alternation: occasionally same sender, mostly varied.
                if random.random() < 0.6:
                    sender_idx = (sender_idx + 1) % len(participants)
                sender = participants[sender_idx]
                m = Message.objects.create(
                    conversation=conv, sender=sender, body=body,
                )
                Message.objects.filter(pk=m.pk).update(created_at=running)
                msgs += 1

            # Last 1-2 messages stay unread.
            recent = list(conv.messages.order_by("-created_at")[2:])
            if recent:
                Message.objects.filter(pk__in=[m.pk for m in recent]).update(is_read=True)
            Conversation.objects.filter(pk=conv.pk).update(updated_at=running)
            created += 1
        return created, msgs

    def _populate_empty_conversations(self, users):
        """Find any existing 1-to-1 conversation that has no messages
        (e.g., DMs that a non-demo user opened from a profile but never typed in)
        and populate it. Catches things like emma_wilson's empty inbox."""
        empty = Conversation.objects.filter(
            messages__isnull=True, is_group=False,
        ).distinct()
        n_filled = 0
        n_msgs = 0
        for conv in empty:
            u1, u2 = conv.user_a, conv.user_b
            if not (u1 and u2):
                continue
            n = self._populate_dm(conv, u1, u2)
            n_filled += 1
            n_msgs += n
        return n_filled, n_msgs
