"""Seed the database with 10 realistic-looking demo users.

Each user gets:
    * A unique avatar (downloaded from picsum.photos when online; falls back to
      a locally generated gradient avatar if there's no network).
    * A cover image.
    * 3–5 posts, most with attached images and interest tags (the "forum" feed).
    * 1–2 stories.
    * Follow relationships, likes, comments, and replies.

Usage:
    python manage.py seed
    python manage.py seed --clear        # wipe demo data first

The default password for every demo user is `DemoPass!234`.
"""
import io
import random
import urllib.request
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Follow, Interest
from posts.models import Comment, Like, Post, PostImage, Story

User = get_user_model()

# Stable seed so repeat runs produce the same data.
RANDOM_SEED = 42

INTERESTS = [
    ("UI/UX",   "🎨", "#cfe5fa"),
    ("Music",   "🎵", "#f9c5d6"),
    ("Cooking", "🍳", "#f8e1c5"),
    ("Hiking",  "⛰️", "#d8c5f9"),
    ("Travel",  "✈️", "#cef0e3"),
    ("Reading", "📚", "#fae6c5"),
    ("Photo",   "📷", "#dfe2fb"),
    ("Fitness", "💪", "#fad6c5"),
]

# 10 internationally-named demo users — each with a backstory,
# a list of post bodies, optional location, and interest tags.
DEMO_USERS = [
    {
        "username": "emma_wilson",
        "first": "Emma", "last": "Wilson",
        "bio": "Product designer working on small, well-crafted apps. Coffee, color, and clean code.",
        "location": "Stockholm, Sweden",
        "website": "https://emmawilson.design",
        "interests": ["UI/UX", "Reading", "Photo"],
        "posts": [
            "Spent the morning iterating on a new onboarding flow — really happy with how the empty states turned out.",
            "Bought the new Inter typeface variable font and I'm already obsessed. Tiny detail, huge difference.",
            "Hot take: the best portfolios I've seen this year were under 5 pages. Less really is more.",
            "Coffee shop sketching session. Nothing beats paper for early concepts. ✏️",
        ],
    },
    {
        "username": "liam_anderson",
        "first": "Liam", "last": "Anderson",
        "bio": "Senior backend engineer @ a fintech. Loves Postgres, hates surprise NULLs.",
        "location": "Dublin, Ireland",
        "website": "",
        "interests": ["Reading", "Hiking", "Photo"],
        "posts": [
            "Wrote a 200-line migration today. Took 4 hours to write and 6 hours to test. Worth it.",
            "Reading 'Designing Data-Intensive Applications' for the 3rd time. Different things stick each time.",
            "Hike up Bray Head this weekend — first time the weather actually cooperated. Bring boots if you go.",
        ],
    },
    {
        "username": "sophia_martinez",
        "first": "Sophia", "last": "Martinez",
        "bio": "Travel writer and amateur food photographer. Currently in: anywhere with good light.",
        "location": "Lisbon, Portugal",
        "website": "https://sophiamtravels.com",
        "interests": ["Travel", "Cooking", "Photo"],
        "posts": [
            "Pastéis de nata are a religion in Lisbon and after this morning I think I've converted.",
            "Tip from a local: skip the famous queue at Belém and try the bakery two blocks behind it. Same recipe, no line.",
            "Chasing golden hour from rooftops again. The light in southern Europe is unfair to the rest of the world.",
            "New blog post up: 'Five Markets in Lisbon Worth Getting Lost In'. Link in bio.",
        ],
    },
    {
        "username": "noah_thompson",
        "first": "Noah", "last": "Thompson",
        "bio": "Mountain guide turned photographer. If it's outdoors and steep, I'm interested.",
        "location": "Banff, Canada",
        "website": "",
        "interests": ["Hiking", "Photo", "Fitness"],
        "posts": [
            "Sunrise from the summit of Mt Temple yesterday. Started at 3 a.m. — every step worth it.",
            "Pack tip: a good base layer beats an expensive shell. Source: 12 winters guiding in the Rockies.",
            "Saw three grizzlies and a wolverine this week. Fall in Banff is unbeatable.",
            "Reminder: leave no trace. The trails we love depend on the people who came before respecting them.",
        ],
    },
    {
        "username": "olivia_garcia",
        "first": "Olivia", "last": "Garcia",
        "bio": "Pastry chef. I make croissants and complain about humidity.",
        "location": "Madrid, Spain",
        "website": "https://oliviabakes.es",
        "interests": ["Cooking", "Reading"],
        "posts": [
            "Day 3 of perfecting brown-butter cookies. Crisp edges, chewy centers, slightly burnt-sugar smell — chef's kiss.",
            "Made fresh pasta from scratch with my grandmother's recipe today. The egg-to-flour ratio is everything.",
            "Hot take: home bakers shouldn't be afraid of salt. Most pastry recipes underuse it.",
        ],
    },
    {
        "username": "ethan_roberts",
        "first": "Ethan", "last": "Roberts",
        "bio": "Indie game developer. Currently shipping a small puzzle game written in Rust.",
        "location": "Berlin, Germany",
        "website": "https://ethan.games",
        "interests": ["UI/UX", "Music", "Reading"],
        "posts": [
            "Spent the entire weekend on the level editor. Nothing visible to players changed but the codebase finally feels good.",
            "Indie devs: please playtest with someone who has never seen a video game before. You'll learn more in 5 minutes than from any usability study.",
            "New synthwave playlist on repeat. Can't decide if it's helping me focus or hypnotizing me.",
        ],
    },
    {
        "username": "isabella_walker",
        "first": "Isabella", "last": "Walker",
        "bio": "Yoga teacher & wellness writer. Mornings are for stillness, evenings are for rosé.",
        "location": "Bali, Indonesia",
        "website": "",
        "interests": ["Fitness", "Reading", "Travel"],
        "posts": [
            "Sunrise practice on the beach this morning. There's something about salt air and savasana.",
            "Reminder: rest is a discipline, not a reward. Take the day off if your body asks for it.",
            "New 30-day breathwork challenge starting Monday — DM me if you want in.",
        ],
    },
    {
        "username": "mason_cooper",
        "first": "Mason", "last": "Cooper",
        "bio": "Drummer in a jazz quartet, occasional music teacher, full-time vinyl hoarder.",
        "location": "New Orleans, USA",
        "website": "",
        "interests": ["Music", "Photo"],
        "posts": [
            "Recording session went into overtime tonight. We tracked the same 8 bars maybe 40 times. Worth every take.",
            "Found a 1972 first pressing of 'Bitches Brew' at a thrift store today for €4. The universe is just.",
            "Practice tip for new drummers: 10 minutes of slow, perfect rudiments beats an hour of mediocre everything.",
        ],
    },
    {
        "username": "ava_mitchell",
        "first": "Ava", "last": "Mitchell",
        "bio": "Marine biologist. Half my photos are of fish, the other half are of coffee. Sorry not sorry.",
        "location": "Cape Town, South Africa",
        "website": "https://avareefdiary.com",
        "interests": ["Photo", "Travel", "Reading"],
        "posts": [
            "Tagged 12 sharks today as part of our coastal survey. Yes — they were all bigger than me.",
            "Field season writeup is going to take longer than the field season itself. As always.",
            "Snorkeled with a curious cuttlefish for 20 minutes. They are aliens with personalities. Don't @ me.",
        ],
    },
    {
        "username": "lucas_bennett",
        "first": "Lucas", "last": "Bennett",
        "bio": "Architect. Obsessed with concrete, sunlight, and small Mediterranean towns.",
        "location": "Athens, Greece",
        "website": "https://lucasbennett.studio",
        "interests": ["UI/UX", "Travel", "Photo"],
        "posts": [
            "Site visit in Hydra today. The way the white walls catch the Aegean light is a free design lesson.",
            "Spent the day sketching in cafes. Best CAD software ever invented: a 0.5mm pencil and a napkin.",
            "Architects: stop hiding behind renderings. Build the model. Touch the material. Walk the site.",
            "Coffee shop tour of Athens (informal): currently 4/10 visited. Will report back.",
        ],
    },
]

STORY_CAPTIONS = [
    "Morning vibes 🌅",
    "Today's mood",
    "Stop and look 👀",
    "Found this gem",
    "Working from here today",
    "The light right now",
    "Sunday slow",
    "Afternoon walk",
]

COMMENT_BODIES = [
    "Love this!", "So inspiring 🌟", "Where was this taken?",
    "Couldn't agree more.", "Thanks for sharing!", "Beautiful 🤩",
    "Saving this for later.", "Adding to my list 📌",
    "I needed to read this today.", "More of this please!",
]

REPLY_BODIES = [
    "Right? 🙌", "Glad you liked it!", "Thanks 💛",
    "More coming soon!", "Same here.", "Appreciate it.",
]


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _try_download(url, timeout=8):
    """Return raw image bytes, or None if anything goes wrong."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            if len(data) > 1000:  # plausible image
                return data
    except (URLError, TimeoutError, OSError):
        return None
    return None


def _gradient_image(width, height, seed_a, seed_b, label=""):
    """Generate a colourful gradient PNG locally — used when downloads fail."""
    from PIL import Image, ImageDraw, ImageFont

    rnd = random.Random(seed_a * 1000 + seed_b)
    c1 = (rnd.randint(120, 230), rnd.randint(120, 230), rnd.randint(180, 250))
    c2 = (rnd.randint(120, 230), rnd.randint(120, 230), rnd.randint(180, 250))

    img = Image.new("RGB", (width, height), c1)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        # interpolate between c1 and c2 from top to bottom
        t = y / max(height - 1, 1)
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    if label:
        try:
            font = ImageFont.load_default()
            tw, th = draw.textbbox((0, 0), label, font=font)[2:]
            draw.text(
                ((width - tw) / 2, (height - th) / 2),
                label,
                fill=(255, 255, 255),
                font=font,
            )
        except Exception:
            pass

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def _fetch_image(width, height, seed, label=""):
    """Try picsum.photos first; fall back to a local gradient."""
    url = f"https://picsum.photos/seed/{seed}/{width}/{height}"
    data = _try_download(url)
    if data:
        return data, "jpg"
    # Fallback
    return _gradient_image(width, height, abs(hash(seed)) % 1000, len(seed), label), "jpg"


def _avatar_image(seed, label):
    """Round-ish avatar — picsum if available, else solid initials."""
    url = f"https://i.pravatar.cc/300?u={seed}"
    data = _try_download(url)
    if data:
        return data, "jpg"
    # Fallback: gradient with initials
    return _gradient_image(300, 300, abs(hash(seed)) % 1000, 7, label), "jpg"


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Seed the database with 10 realistic demo users plus images, posts, stories."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete demo users / posts / interests / stories first.",
        )
        parser.add_argument(
            "--no-images", action="store_true",
            help="Skip image generation (much faster, but accounts will look bare).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(RANDOM_SEED)

        if options["clear"]:
            self.stdout.write("Clearing previous demo data…")
            usernames = [u["username"] for u in DEMO_USERS]
            # Old-style demo users from earlier seeds, too:
            legacy = [
                "george_lobko", "vitaly_boyko", "nick_shelburne", "brittni_lando",
                "ivan_shev", "anatoly_p", "lolita_earns", "silena",
            ]
            User.objects.filter(username__in=usernames + legacy).delete()
            Interest.objects.filter(name__in=[i[0] for i in INTERESTS]).delete()

        with_images = not options["no_images"]

        # ----- Interests -----
        interests_by_name = {}
        for name, icon, color in INTERESTS:
            obj, _ = Interest.objects.get_or_create(
                name=name, defaults={"icon": icon, "color": color},
            )
            obj.icon = icon
            obj.color = color
            obj.save()
            interests_by_name[name] = obj
        self.stdout.write(self.style.SUCCESS(f"Interests ready: {len(interests_by_name)}"))

        # ----- Users + Profiles -----
        created_users = []
        for spec in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "first_name": spec["first"],
                    "last_name": spec["last"],
                    "email": f"{spec['username']}@example.com",
                },
            )
            if created:
                user.set_password("DemoPass!234")
                user.save()

            profile = user.profile
            profile.display_name = f"{spec['first']} {spec['last']}"
            profile.bio = spec["bio"]
            profile.location = spec["location"]
            profile.website = spec["website"]

            if with_images and not profile.avatar:
                initials = (spec["first"][:1] + spec["last"][:1]).upper()
                data, ext = _avatar_image(spec["username"], initials)
                profile.avatar.save(
                    f"{spec['username']}_avatar.{ext}",
                    ContentFile(data),
                    save=False,
                )

            if with_images and not profile.cover:
                data, ext = _fetch_image(960, 320, f"cover-{spec['username']}")
                profile.cover.save(
                    f"{spec['username']}_cover.{ext}",
                    ContentFile(data),
                    save=False,
                )

            profile.save()
            profile.interests.set([interests_by_name[i] for i in spec["interests"]])
            created_users.append((user, spec))
            self.stdout.write(f"  - {spec['username']}")

        self.stdout.write(self.style.SUCCESS(
            f"Users: {len(created_users)} (password: DemoPass!234)"
        ))

        # ----- Posts -----
        all_post_objects = []
        for user, spec in created_users:
            user_interests = [interests_by_name[i] for i in spec["interests"]]
            user_posts = list(Post.objects.filter(author=user))
            # Skip if user already has posts (idempotent re-run)
            if user_posts:
                all_post_objects.extend(user_posts)
                continue

            for idx, body in enumerate(spec["posts"]):
                post = Post.objects.create(
                    author=user,
                    body=body,
                    location=random.choice(["", spec["location"]]),
                    visibility=Post.PUBLIC,
                )
                post.interests.set(random.sample(
                    user_interests, min(2, len(user_interests))
                ))

                if with_images:
                    data, ext = _fetch_image(
                        900, 600, f"{spec['username']}-post-{idx}",
                    )
                    post.image.save(
                        f"{spec['username']}_post_{idx}.{ext}",
                        ContentFile(data),
                        save=True,
                    )

                # Some posts get a gallery (extra images) — like the design.
                if with_images and idx % 3 == 0:
                    for j in range(2):
                        data, ext = _fetch_image(
                            500, 350, f"{spec['username']}-post-{idx}-extra-{j}",
                        )
                        pi = PostImage(post=post, order=j)
                        pi.image.save(
                            f"{spec['username']}_post_{idx}_extra_{j}.{ext}",
                            ContentFile(data),
                            save=True,
                        )

                all_post_objects.append(post)

        self.stdout.write(self.style.SUCCESS(
            f"Posts: {len(all_post_objects)} total"
        ))

        # ----- Stories -----
        story_count = 0
        for user, spec in created_users:
            if user.stories.exists():
                continue
            for k in range(random.randint(1, 2)):
                if with_images:
                    data, ext = _fetch_image(
                        720, 1080, f"{spec['username']}-story-{k}",
                    )
                    s = Story(
                        author=user,
                        caption=random.choice(STORY_CAPTIONS),
                    )
                    s.image.save(
                        f"{spec['username']}_story_{k}.{ext}",
                        ContentFile(data),
                        save=True,
                    )
                    story_count += 1
        self.stdout.write(self.style.SUCCESS(f"Stories: {story_count}"))

        # ----- Follows (each user follows 4–6 others) -----
        for user, _ in created_users:
            others = [u for u, _ in created_users if u != user]
            for target in random.sample(others, k=min(random.randint(4, 6), len(others))):
                Follow.objects.get_or_create(follower=user, following=target)
        self.stdout.write(self.style.SUCCESS(f"Follows: {Follow.objects.count()}"))

        # ----- Likes (~6 random posts each) -----
        for user, _ in created_users:
            for post in random.sample(all_post_objects, min(6, len(all_post_objects))):
                if post.author != user:
                    Like.objects.get_or_create(user=user, post=post)
        self.stdout.write(self.style.SUCCESS(f"Likes: {Like.objects.count()}"))

        # ----- Comments + replies -----
        comment_count = 0
        reply_count = 0
        for user, _ in created_users:
            for post in random.sample(all_post_objects, min(3, len(all_post_objects))):
                if post.author == user:
                    continue
                top = Comment.objects.create(
                    author=user, post=post,
                    body=random.choice(COMMENT_BODIES),
                )
                comment_count += 1
                # 30% chance the post author replies.
                if random.random() < 0.3:
                    Comment.objects.create(
                        author=post.author, post=post, parent=top,
                        body=random.choice(REPLY_BODIES),
                    )
                    reply_count += 1
        self.stdout.write(self.style.SUCCESS(
            f"Comments: {comment_count} (with {reply_count} replies)"
        ))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("[OK] Done. Try logging in as:"))
        self.stdout.write("   username: emma_wilson")
        self.stdout.write("   password: DemoPass!234")
