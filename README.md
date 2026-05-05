<p align="center">
  <img src="static/images/logo.svg" alt="SocialHub" height="56">
</p>

# SocialHub — Social Community & Content Sharing Platform

A modern social media web application built with Django, where users can create profiles, share posts (text + images), follow each other, like and comment on posts, post 24-hour stories, browse a personalized feed, explore public content, and discover people through interest-based recommendations.

The UI is inspired by a contemporary social-media dashboard design: a left sidebar with the user profile and primary nav, a card-based central feed, and a right sidebar with stories, suggestions, and interest recommendations.

> Term project for the Django course. The code aims to be production-quality so it can be deployed and presented as-is.

---

## Table of contents

1. [Features](#features)
2. [Technology stack](#technology-stack)
3. [Project structure](#project-structure)
4. [Models & architecture](#models--architecture)
5. [Setup](#setup)
6. [Environment variables](#environment-variables)
7. [Running tests](#running-tests)
8. [Seeding demo data](#seeding-demo-data)
9. [Screenshots](#screenshots)
10. [Deployment](#deployment)
11. [Grading-scheme alignment](#grading-scheme-alignment)
12. [License](#license)

---

## Features

### Core
- **Authentication** — sign up, log in, log out, password reset (built-in Django views).
- **User profiles** — auto-created on signup with avatar, cover image, bio, location, website, and interests. Profile pages show post count, follower count, and following count.
- **Posts (CRUD)** — create, read, update, delete with text body, optional image, location, and visibility (`public`, `friends-only`, `private`).
- **Likes** — toggle with a single click; AJAX-powered, no page reload.
- **Comments** — add and delete (only by author or post owner).
- **Follow / unfollow** — directional relationships; AJAX-powered.
- **Personalized feed** — posts from people you follow plus your own. Filterable: *Recents*, *Friends*, *Popular*.
- **Explore** — public feed of all recent posts; filterable by interest tag.
- **Stories** — 24-hour ephemeral image posts with optional caption.
- **Search** — search posts by body/location/author/tag, search users by name/username.
- **Notifications** — receive notifications when someone likes, comments on your post, or follows you. Unread badge in the sidebar.
- **Interest-based recommendations** — color-coded interest chips; filter the explore feed by tag.
- **Pagination** — 10 posts per page on feed, 12 on explore.
- **Responsive** — desktop, tablet, and mobile layouts.

### Advanced
1. **Authentication system** — Django auth + custom signup form requiring email; password reset built-in.
2. **Authorization & permissions** — class-based views use `UserPassesTestMixin` to make sure only the post author can edit/delete a post; comments can only be deleted by their author or the post owner.
3. **AJAX dynamic like and follow** — `fetch()` + JSON endpoints; CSRF token from cookie.
4. **Search & filtering** — multi-field search across posts and users.
5. **Pagination** — Django's `Paginator` everywhere a list might grow.
6. **Query optimization** — `select_related` + `prefetch_related` everywhere it counts; counts and "is liked" are aggregated with `annotate(Count(...), Exists(...))` so the feed renders in a single query.
7. **Database constraints** — `UniqueConstraint` prevents duplicate likes and duplicate follows; `CheckConstraint` prevents self-follow at the DB level.
8. **24-hour stories** — automatic expiry via timestamp comparison.

---

## Technology stack

| Layer       | Tool                                       |
|-------------|--------------------------------------------|
| Backend     | Django 4.2, Python 3.11+                   |
| Database    | SQLite (dev) — easily swappable for Postgres |
| Frontend    | Bootstrap 5.3, Bootstrap Icons, custom CSS |
| Forms       | Django ModelForm + `widget_tweaks`-free templates |
| AJAX        | `fetch` API + JSON endpoints               |
| Static files| WhiteNoise (compressed manifest in prod)   |
| Images      | Pillow                                      |
| Server      | Gunicorn (production); Django dev server (local) |

---

## Project structure

```
Social Community and Content Sharing Platform/
├── manage.py
├── requirements.txt
├── Procfile                    # for Render / Heroku
├── runtime.txt
├── .env.example
├── .gitignore
├── README.md
├── socialhub/                  # Django project (settings, urls)
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── views.py                # custom 404 / 500 handlers
│   ├── wsgi.py
│   └── asgi.py
├── accounts/                   # users, profiles, follows, interests
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   ├── admin.py
│   ├── signals.py              # auto-creates Profile on User creation
│   ├── tests.py
│   └── migrations/
├── posts/                      # posts, images, comments, likes, stories
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   ├── admin.py
│   ├── tests.py
│   ├── management/commands/seed.py
│   └── migrations/
├── notifications/              # in-app notifications
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   ├── context_processors.py   # exposes unread count globally
│   └── migrations/
├── templates/
│   ├── base.html               # the dashboard shell (left/main/right)
│   ├── partials/               # _post_card, _right_sidebar, _pagination
│   ├── posts/                  # feed, explore, post_detail, post_form, …
│   ├── accounts/               # profile, edit_profile, search_users, follow_list
│   ├── registration/           # login, signup, password reset templates
│   ├── notifications/list.html
│   └── errors/                 # 404, 500
├── static/
│   ├── css/main.css            # dashboard styling
│   └── js/main.js              # AJAX like + AJAX follow
└── media/                      # uploaded user files (avatars, post images)
```

---

## Models & architecture

```
User (Django auth)
 └─1:1─ Profile (avatar, cover, bio, location, website, interests m2m)
 └─m:n─ Follow → User      (UniqueConstraint + CheckConstraint(no self-follow))
 └─1:n─ Post (body, image, visibility, interests m2m)
 │       └─1:n─ PostImage   (extra gallery images)
 │       └─1:n─ Comment     (cascade-deletes on post delete)
 │       └─1:n─ Like        (UniqueConstraint per user/post)
 └─1:n─ Story               (auto-expires after 24h via expires_at)
 └─1:n─ Notification        (recipient/actor/verb/post)

Interest (Music, Cooking, Hiking, …)
 └─m:n─ Profile, Post
```

Key design choices:
- `Profile` is a separate one-to-one extension of the built-in `User` (over a custom `AbstractUser`) — keeps Django auth simple and avoids migration headaches.
- `Follow` is its own model rather than a `ManyToManyField(User, through="Follow")` — makes timestamp-based ordering and notifications cleaner.
- Likes use a `UniqueConstraint` rather than logic checks — race conditions are impossible.
- Posts have a `visibility` field; the post detail view enforces it server-side.
- The feed query annotates `like_count`, `comment_count`, and `is_liked` in a single round-trip — no N+1.

---

## Setup

### Prerequisites
- Python 3.11+
- pip (or `pipx` / `uv` / `poetry` if you prefer)

### Steps

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd "Social Community and Content Sharing Platform"

# 2. (Optional but recommended) create a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment file
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux

# 5. Run migrations
python manage.py migrate

# 6. Create a superuser
python manage.py createsuperuser

# 7. (Optional) Seed demo data — 8 users, posts, follows, likes, comments
python manage.py seed

# 8. Run the dev server
python manage.py runserver
```

Open http://127.0.0.1:8000/ in a browser. The root URL redirects to the feed.

After running `seed`, you can log in as any demo user:
- Username: `george_lobko`, `vitaly_boyko`, `nick_shelburne`, `brittni_lando`, `ivan_shev`, `anatoly_p`, `lolita_earns`, `silena`
- Password: `DemoPass!234`

---

## Environment variables

| Variable                | Default                              | Notes                                          |
|-------------------------|--------------------------------------|------------------------------------------------|
| `DJANGO_SECRET_KEY`     | (insecure default — change!)         | Generate: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG`          | `true`                               | Set to `false` in production.                  |
| `DJANGO_ALLOWED_HOSTS`  | `localhost,127.0.0.1,*`              | Comma-separated; use real domains in prod.     |

---

## Running tests

```bash
python manage.py test
```

The test suite covers:
- Signup creates user + profile, rejects duplicate email
- Login / logout flows
- Profile page renders, edit profile requires login
- Follow / unfollow toggling, can't follow self, unique-follow constraint, AJAX JSON response
- User search
- Post create / quick post / empty post rejection / login required
- Post update & delete permissions (only owner)
- Like / unlike toggling, like-uniqueness constraint, AJAX JSON response
- Comment create, only-author-or-post-owner can delete
- Feed filters (own + followed posts only), explore (all public), post search

**32 tests, all passing.**

---

## Seeding demo data

```bash
python manage.py seed              # add demo data
python manage.py seed --clear      # drop demo data first, then re-seed
```

Creates 8 interest tags, 8 demo users (with bios + interests), random posts, follows, likes, and comments. Lets you screenshot a populated dashboard immediately after install.

---

## Screenshots

Drop your screenshots in [`docs/screenshots/`](docs/screenshots/) using the filenames below. See [`docs/screenshots/README.md`](docs/screenshots/README.md) for capture instructions.

| Page | File |
|------|------|
| Home feed (sidebar + posts + suggestions) | ![Feed](docs/screenshots/feed.png) |
| Explore (public posts, interest filters)  | ![Explore](docs/screenshots/explore.png) |
| User profile (cover, avatar, stats)       | ![Profile](docs/screenshots/profile.png) |
| Post detail with comments                 | ![Post detail](docs/screenshots/post_detail.png) |
| Login                                     | ![Login](docs/screenshots/login.png) |
| Signup                                    | ![Signup](docs/screenshots/signup.png) |
| Mobile responsive view                    | ![Mobile](docs/screenshots/mobile.png) |

To capture all of them in one go:
```bash
python manage.py migrate
python manage.py seed
python manage.py runserver
# Login as `george_lobko` / `DemoPass!234`
```

---

## Deployment

### Render (recommended free tier)

1. Push the project to a GitHub repository.
2. On https://render.com, create a new **Web Service**.
3. Connect the repo. Render auto-detects the `Procfile`.
4. Build command:
   ```
   pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate
   ```
5. Start command:
   ```
   gunicorn socialhub.wsgi
   ```
6. Add environment variables under **Environment**:
   - `DJANGO_SECRET_KEY` = (a fresh random string)
   - `DJANGO_DEBUG` = `false`
   - `DJANGO_ALLOWED_HOSTS` = `your-app.onrender.com`
7. Click **Create Web Service**.

### PythonAnywhere

1. Upload or `git clone` your project to PythonAnywhere.
2. Create a virtualenv and `pip install -r requirements.txt`.
3. In the **Web** tab, set the WSGI file to point at `socialhub.wsgi`.
4. Add a static-files mapping: URL `/static/` → directory `/home/<you>/<project>/staticfiles`, and `/media/` → `<project>/media`.
5. In a console, run:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --no-input
   python manage.py createsuperuser
   ```
6. Reload the web app.

### Notes for production

- WhiteNoise serves compressed static files via the `STATICFILES_STORAGE` set in `settings.py` (only when `DEBUG=False`).
- Media files (user uploads) are stored on local disk by default. For Render's free tier, attach a persistent disk; for production, use S3 with `django-storages`.
- The `if not DEBUG:` block in `settings.py` enables `SECURE_*` cookie flags, `XSS` filter, `X-Frame-Options=DENY`, etc.

---

## Grading-scheme alignment

| Criterion                   | Pts | How it's covered |
|-----------------------------|-----|------------------|
| Core Functionality          | 25  | All required features (auth, posts CRUD, images, likes, comments, follows, feed, explore, search, profile, stories) implemented. |
| Database Design             | 15  | Eight related models, FK + M2M relationships, `related_name`, timestamps, `__str__`, indexes, `UniqueConstraint` for likes/follows, `CheckConstraint` against self-follow. |
| Frontend & UX               | 15  | Bootstrap-based responsive UI with custom dashboard CSS that mirrors the reference design — sidebar nav, profile card, card-based feed, stories grid, suggestions list, interest chips, composer, hover states, empty states, error messages. |
| Advanced Features           | 15  | Auth + permissions, AJAX likes & follows, search, pagination, query optimization, DB constraints, signals, custom 404/500. |
| Code Quality                | 10  | Apps separated by concern; no N+1 queries; meaningful names; signals; class-based views where they help; thin views. |
| Documentation               | 10  | This README, plus inline docstrings on each module, plus a `seed` management command for demos. |
| Testing                     | 5   | 32 tests covering signup, login, follow/unfollow, post CRUD, post permissions, likes, comments, feed filtering, search. |
| Deployment                  | 5   | `requirements.txt`, `Procfile`, `runtime.txt`, `.env.example`, WhiteNoise, security headers, deployment notes for Render & PythonAnywhere. |
| **Bonus**                   | 5   | Notifications app with unread-badge context processor; 24-hour stories with auto-expiry; interest-based content filtering; seed command for demo data. |

---

## License

MIT — feel free to learn from, fork, and adapt.

---

## Demo accounts

After running `python manage.py seed`, log in with any of these.

> ⚠️ **Development credentials only.** Change them (or wipe the demo data with `python manage.py seed --clear` and create your own users) before deploying anywhere public.

### Admin

| URL | Username | Password |
|-----|----------|----------|
| `http://127.0.0.1:8000/admin/` | `admin` | `AdminPass!234` |

If you didn't create the admin yet:
```bash
python manage.py createsuperuser
```

### Demo users (10 — all share the same password)

> **Password for every demo user:** `DemoPass!234`

| # | Username | Full name | Location | Role |
|---|----------|-----------|----------|------|
| 1 | `emma_wilson` | Emma Wilson | Stockholm, Sweden | Product designer |
| 2 | `liam_anderson` | Liam Anderson | Dublin, Ireland | Backend engineer |
| 3 | `sophia_martinez` | Sophia Martinez | Lisbon, Portugal | Travel writer |
| 4 | `noah_thompson` | Noah Thompson | Banff, Canada | Mountain guide & photographer |
| 5 | `olivia_garcia` | Olivia Garcia | Madrid, Spain | Pastry chef |
| 6 | `ethan_roberts` | Ethan Roberts | Berlin, Germany | Indie game developer |
| 7 | `isabella_walker` | Isabella Walker | Bali, Indonesia | Yoga teacher |
| 8 | `mason_cooper` | Mason Cooper | New Orleans, USA | Jazz drummer |
| 9 | `ava_mitchell` | Ava Mitchell | Cape Town, South Africa | Marine biologist |
| 10 | `lucas_bennett` | Lucas Bennett | Athens, Greece | Architect |

Each demo user has a real avatar, cover image, posts with photos, 1–2 stories, follow relationships, likes and comments — populated automatically by the `seed` command.
