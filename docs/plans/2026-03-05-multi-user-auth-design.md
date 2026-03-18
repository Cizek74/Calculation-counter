# Multi-User Authentication — Design Doc
Date: 2026-03-05

## Overview

Replace the single-password Flask session with a SQLite-backed multi-user system. Two roles: `admin` (full access) and `viewer` (read-only). Admin UI for user management at `/admin/users`.

## Database

File: `users.db` (alongside `app.py`, not tracked in git)

```sql
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'viewer',
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);
```

Bootstrap: on startup, `init_db()` creates the table if absent. `bootstrap_admin()` runs once — if the table is empty, inserts one admin account from env vars `ADMIN_USER` (default `admin`) and `ADMIN_PASSWORD` (default `changeme`). Prints a console warning if defaults are used.

## Dependencies

- `flask-bcrypt` — password hashing (new install required)
- `sqlite3` — Python stdlib, no install needed

## Auth Flow

Session keys (replace `session['authenticated']`):
- `session['user_id']` (int)
- `session['username']` (str)
- `session['role']` (`'admin'` | `'viewer'`)

Decorators:
- `login_required` — checks `session['user_id']`; redirects to `/login` if missing
- `admin_required` — wraps `login_required`; returns 403 JSON if role != `'admin'`

Login form: adds `username` field above password. Error message: generic "Nesprávné přihlašovací údaje" (no hint which field failed).

## Route Access Matrix

| Route                              | Viewer | Admin |
|------------------------------------|--------|-------|
| GET /                              | yes (UI restricted) | yes |
| POST /upload                       | 403    | yes   |
| POST /generate_report              | 403    | yes   |
| GET /download/<sid>/<type>         | yes    | yes   |
| GET /download_all/<sid>            | yes    | yes   |
| GET /dashboard                     | yes    | yes   |
| POST /history/delete/<id>          | 403    | yes   |
| GET /admin/users                   | 403    | yes   |
| POST /admin/users (create)         | 403    | yes   |
| POST /admin/users/<id>/reset-password | 403 | yes   |
| POST /admin/users/<id>/toggle-active  | 403 | yes   |

## Admin UI (`/admin/users`)

New template `templates/admin_users.html` — same dark navy / glassmorphism design, Czech labels.

- User table: username, role badge (indigo=admin, gray=viewer), status dot (active/disabled), created date, actions
- Actions: Reset password (inline form), Toggle active/disabled (cannot self-disable)
- Add user form at bottom: username, password, role selector
- Same top bar as index.html (Dashboard link + logout + Admin link)
- Admin link in top bar visible only when `session['role'] == 'admin'`

## Viewer Restrictions on `/`

Flask passes `current_role` to `render_template('index.html', current_role=...)`.

UI changes for viewer role:
- Upload drop-zone: `pointer-events:none; opacity:.4` + overlay tooltip "Pouze pro administrátory"
- "Zpracovat soubory" button: `disabled`
- "Generovat report" button: `disabled`
- Info banner below top bar: "Prihlaseni jako prohlizec — nahravani a generovani reportu je zakazano"

## Files Changed

- `app.py` — auth system replacement, new routes, role checks
- `templates/login.html` — add username field
- `templates/index.html` — viewer restriction UI
- `templates/dashboard.html` — add Admin link in top bar (conditional)
- `templates/admin_users.html` — new file
- `requirements.txt` — add flask-bcrypt
