# Screenshots

Place captured PNG screenshots in this folder. The main project README looks for these filenames:

| Filename            | Page                                                                  |
|---------------------|-----------------------------------------------------------------------|
| `feed.png`          | Logged-in feed (`/posts/`)                                            |
| `explore.png`       | Public explore page (`/posts/explore/`)                               |
| `profile.png`       | A user profile (`/accounts/profile/<username>/`)                      |
| `post_detail.png`   | A post with comments (`/posts/<id>/`)                                 |
| `login.png`         | Login screen (`/accounts/login/`)                                     |
| `signup.png`        | Signup screen (`/accounts/signup/`)                                   |
| `mobile.png`        | The feed at mobile width (Chrome DevTools, ~390 px wide)              |

## How to capture

```bash
python manage.py migrate
python manage.py seed
python manage.py runserver
```

Open Chrome / Firefox / Edge, log in as `george_lobko` / `DemoPass!234`, and use:

- **Chrome / Edge:** Right-click → *Inspect* → Cmd/Ctrl + Shift + P → "Capture full size screenshot"
- **Firefox:** Right-click → *Take Screenshot* → "Save full page"

Crop / resize each capture to ~1280 px wide (or leave full-page) and drop them in this folder using the filenames above. The README will pick them up automatically.
