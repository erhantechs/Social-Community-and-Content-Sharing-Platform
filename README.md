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

---

## Why Django? — How and why Django powers this project

This project is intentionally a "Django-first" build. Almost every feature you see — from authentication to the admin dashboard, from user-uploaded images to JSON API responses — leans on a part of Django that already exists, is battle-tested, and would otherwise take weeks to build from scratch.

Below is a tour of the Django features this project uses, mapped to where they live in the codebase, so you can read the source and see exactly *why* a Django-shaped solution was the right call.

### 1. The MVT (Model-View-Template) architecture

The whole repo is organised around Django's **MVT triad**, multiplied across five focused apps:

| Layer | What it does | Examples |
|-------|--------------|----------|
| **Models** (`models.py`) | Define the data and the rules that protect it | `Post`, `Profile`, `Follow`, `Like`, `Story`, `Conversation`, `Notification`, `Block`, `Bookmark` |
| **Views** (`views.py`) | Turn HTTP requests into responses, enforce business rules | `feed_view`, `post_create`, `toggle_like`, `PostUpdateView`, `thread`, `notification_dropdown` |
| **Templates** (`templates/`) | Render HTML using Django's template language | `base.html` (the dashboard shell), reusable partials like `_post_card.html` and `_comment.html` |

Splitting the project into multiple apps (`accounts`, `posts`, `notifications`, `messaging`, `api`) is also Django convention — each app is independently testable, removable, and reusable.

### 2. The ORM and relational integrity

Social platforms live and die on relationships: who follows who, whose post you liked, which comment is a reply to which. Django's **ORM** lets us model that with plain Python and have the database enforce correctness for us:

- **`ForeignKey` and `ManyToManyField`** wire users to posts, posts to interests, comments to parents (for replies).
- **`UniqueConstraint`** at the database level prevents duplicate likes (`Like`), duplicate follows (`Follow`), duplicate bookmarks (`Bookmark`), and duplicate blocks (`Block`) — even under a race condition.
- **`CheckConstraint`** prevents users from following or blocking themselves, enforced by the DB, not by view logic.
- **Custom `QuerySet` annotations** in [`posts/views.py`](posts/views.py) (`annotate_posts`) attach `like_count`, `comment_count`, `is_liked`, and `is_bookmarked` to every post in **one** SQL query — not N+1.

This means the truth of the social graph lives in the schema, not scattered across view code.

### 3. Built-in authentication

`django.contrib.auth` provides everything authentication needs out of the box: secure password hashing (PBKDF2 by default), session management, login/logout views, password reset emails, the `@login_required` decorator, and the `User` model. We extended it with a `Profile` (one-to-one) instead of subclassing — simpler, fewer migration headaches.

On top of that we added a **honeypot signup field** and a **cache-backed login throttle** (`accounts/throttle.py`) to stop bot signups and brute-force attempts.

### 4. The admin panel — for free

Every model in the project gets a fully-featured CRUD interface at `/admin/` simply by registering it (`admin.py`). For a social platform that's huge: moderating posts, banning users, inspecting follow graphs, browsing notifications and conversations — all without writing a single extra view. This is one of Django's most under-appreciated superpowers.

### 5. Forms, validation, and file uploads

Django's **`ModelForm`** binds HTML forms directly to models with automatic validation. We use it for signup, profile editing, post creation, comments, and stories. File uploads (avatars, cover images, post photos, story images) plug straight in via `ImageField` — Django writes them to `MEDIA_ROOT` and serves them in dev. Custom validators in `posts/forms.py` enforce file-size and content-type rules for uploads.

### 6. Templates, the Django template language, and custom tags

The template engine handles inheritance (`base.html`), partials (the reusable `_post_card.html` block), context processors (`unread_notification_count` available to every page), and custom template tags (`linkify_post` in [`posts/templatetags/post_extras.py`](posts/templatetags/post_extras.py) that turns `@mentions` and `#hashtags` into clickable links — safely, after escaping HTML).

### 7. Signals — automatic side-effects

When a new `User` is created, a `Profile` is automatically created alongside it via a `post_save` signal in [`accounts/signals.py`](accounts/signals.py). The view layer never has to remember to do this. Notifications for likes, comments, follows, and mentions are also created from view code that runs alongside the action — keeping side-effects close to where they belong.

### 8. URL routing and reverse resolution

URL config is namespaced per app (`accounts:profile`, `posts:detail`, `messaging:thread`, etc.). Templates and views always use `{% url %}` and `reverse()` — never hard-coded paths — so renaming a URL anywhere updates every link automatically.

### 9. The Django REST Framework integration

For the `/api/` layer we added **DRF**, which itself is built on Django's class-based views. ViewSets, serializers, permission classes, throttling, token auth, and OpenAPI generation (`drf-spectacular`) all compose cleanly with the rest of the Django app — same auth, same models, same database. The Swagger UI at `/api/docs/` is auto-generated from the serializer + viewset metadata.

### 10. Security features Django gives you for free

Django ships with sensible defaults that the project benefits from automatically:

- **CSRF protection** on every POST form.
- **HTML escaping** by default in templates — XSS is opt-in, not opt-out.
- **Parameterised SQL queries** via the ORM — SQL injection isn't possible from query parameters.
- **Clickjacking protection** via `X-Frame-Options: DENY` (toggled in `settings.py` for production).
- **Secure session cookies, HSTS, secure proxy headers** — switched on automatically when `DEBUG=False`.
- **Password hashing** with PBKDF2 (configurable to Argon2).

A social platform that handled auth and SQL by hand would need months of security review. Django ships these safe defaults from day one.

### 11. Migrations

Every schema change in this project — adding `Comment.parent`, `Block`, `Bookmark`, `CommentLike`, indexing `Story.expires_at` — is a tracked migration file. `python manage.py migrate` applies them in order; `--clear seed` re-populates demo data on top. Schema evolution is reproducible for any teammate or for any production deploy.

### 12. The testing framework

84 tests covering signup, login, post CRUD, permissions, like/unlike, comments and replies, follow/unfollow, blocks, bookmarks, story expiry, visibility, mentions, hashtags, throttling, honeypot — all using `django.test.TestCase`, which spins up an isolated transactional test database for every run. CI (`.github/workflows/ci.yml`) runs them on every push.

### Why Django was the right framework for this specific project

A social community platform is exactly the kind of app Django was designed for:

1. **Lots of related entities** (users, posts, comments, follows…) → ORM + admin shine here.
2. **Auth is mission-critical** → don't roll your own; `django.contrib.auth` is enough.
3. **Content moderation matters** → the free admin panel saves weeks.
4. **Term-project timeframe** → "batteries-included" lets one developer ship in days, not months.
5. **Future scaling** → when traffic grows, swap SQLite → Postgres via `DATABASE_URL`, swap local media → S3 via `django-storages`, drop in Celery for background jobs — the framework grows with the project.

In short: Django provides the boring (but essential) 80% — auth, admin, ORM, forms, security, migrations — so all of the design and feature work in this repo could focus on the social-platform-specific 20%: feeds, stories, mentions, dark mode, notifications, messaging, the dashboard UI.

---

## 🚀 Run this project on your own machine — step by step

Just downloaded the repo from GitHub and don't know what to do next? This walkthrough takes you from "zero" to "logged in to a fully populated social platform" in about 5 minutes.

### Step 0 — Make sure you have what you need

| Tool | Minimum version | Check command |
|------|-----------------|---------------|
| **Python** | 3.11 or newer | `python --version` |
| **pip** | comes with Python | `pip --version` |
| **Git** *(optional — only if you used `git clone`)* | any recent | `git --version` |

If `python --version` says "command not found" or shows 3.10 or older, install the latest Python from https://www.python.org/downloads/ first. On Windows, **check the "Add Python to PATH" box** during install.

### Step 1 — Get the code

**Option A — with Git (recommended):**
```bash
git clone https://github.com/erhantechs/Social-Community-and-Content-Sharing-Platform.git
cd Social-Community-and-Content-Sharing-Platform
```

**Option B — ZIP download:**
1. On the GitHub page, click the green **`Code`** button → **Download ZIP**
2. Extract the ZIP somewhere convenient
3. Open a terminal in that extracted folder

### Step 2 — Create a virtual environment *(strongly recommended)*

A virtual environment keeps this project's libraries separate from anything else on your computer.

```bash
# Create it
python -m venv .venv

# Activate it
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (cmd):
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate
```

After activating you should see `(.venv)` at the start of your terminal prompt. From now on, every `python` and `pip` command goes into this isolated environment.

> **PowerShell error: "running scripts is disabled"?**
> Run once: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`, then activate again.

### Step 3 — Install the required Python packages

```bash
pip install -r requirements.txt
```

This pulls down Django, DRF, Pillow, WhiteNoise, and a few other libraries listed in `requirements.txt`. It usually takes 30-60 seconds.

### Step 4 — Set up the environment file

```bash
# Windows:
copy .env.example .env
# macOS / Linux:
cp .env.example .env
```

You can leave the defaults as-is for local development. The file is just there to override `SECRET_KEY`, `DEBUG`, and email/database settings if you need to.

### Step 5 — Create the database

```bash
python manage.py migrate
```

This creates a fresh `db.sqlite3` file with all the tables Django and the apps need. You should see a long list of `Applying ... OK` lines.

### Step 6 — Create your admin account

```bash
python manage.py createsuperuser
```

Enter a username, email (optional), and password when prompted. This account is what you'll use to log in to `/admin/`.

### Step 7 *(optional but recommended)* — Load the demo data

Want to see a populated dashboard immediately? Run:

```bash
python manage.py seed
```

This creates 10 demo users with real avatars, cover photos, posts, stories, follows, likes, and comments. Wait ~30 seconds for the images to download from picsum.photos / pravatar.cc. (No network? It falls back to gradient placeholders.)

After this finishes, you can log in as **`emma_wilson`** with password **`DemoPass!234`** (or any of the 10 demo users — see the *Demo accounts* table above).

### Step 8 — Start the server

```bash
python manage.py runserver
```

You should see:

```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

### Step 9 — Open it in your browser

Visit:

| URL | What you'll see |
|-----|-----------------|
| http://127.0.0.1:8000/ | Redirects to the feed (login required) |
| http://127.0.0.1:8000/posts/ | Personalized feed |
| http://127.0.0.1:8000/posts/explore/ | Public posts |
| http://127.0.0.1:8000/admin/ | Admin panel (use the superuser from Step 6) |
| http://127.0.0.1:8000/api/docs/ | Interactive API documentation (Swagger UI) |
| http://127.0.0.1:8000/healthz/ | Health-check JSON `{"status":"ok"}` |

### Step 10 *(optional)* — Run the test suite

```bash
python manage.py test
```

You should see `Ran 84 tests in ...s` followed by `OK`. If any tests fail, something in your environment is off.

---

### 🔧 Common problems and quick fixes

| Symptom | Fix |
|---------|-----|
| `python: command not found` | Install Python 3.11+ from python.org. Tick "Add Python to PATH" on Windows. |
| `ModuleNotFoundError: No module named 'django'` | Forgot to activate the venv (Step 2) or skipped Step 3. |
| `OperationalError: no such table: ...` | Skipped Step 5. Run `python manage.py migrate`. |
| Port 8000 already in use | `python manage.py runserver 8001` — uses a different port. |
| Permission denied when activating venv on PowerShell | `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` then retry. |
| Login throws "Too many login attempts" (429) | You hit the rate limiter. Wait 5 minutes or restart the dev server. |

### 🛑 How to stop the server

Press **`Ctrl + C`** in the terminal where the server is running.

When you come back later, you only need to repeat steps **2 (activate venv)** and **8 (runserver)** — everything else is already set up.

---

That's it. You should now have a fully working SocialHub running locally. If you run into something not covered above, open an issue on GitHub or check the rest of this README — most edge cases are documented in the *Setup* and *Deployment* sections higher up.
