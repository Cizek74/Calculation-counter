# Multi-User Authentication Design

**Date:** 2026-03-04
**Status:** Approved

## Goal

Replace the single shared `APP_PASSWORD` with per-user accounts (username + bcrypt password), two roles (admin / viewer), and an in-app admin UI for managing users — no file editing required.

---

## Data Model

**File:** `users.db` (SQLite, sits alongside `contracts.csv`)

```sql
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'viewer',  -- 'admin' | 'viewer'
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL
);
```

Passwords hashed with **bcrypt** via `flask-bcrypt`.

**Bootstrap:** On first startup (empty table), auto-create one admin account from:
- `ADMIN_USER` env var (default: `admin`)
- `ADMIN_PASSWORD` env var (default: `changeme`)

The existing `APP_PASSWORD` env var is retired.

---

## New Module: `users.py`

`UserManager` class — owns all DB interaction:

| Method | Purpose |
|--------|---------|
| `__init__(db_path)` | Opens/creates DB, runs migrations |
| `bootstrap_admin(username, password)` | Creates first admin if table empty |
| `create_user(username, password, role)` | Hashes + inserts new user |
| `authenticate(username, password)` | Returns user dict or None |
| `get_all()` | Returns list of all users (no password_hash) |
| `set_active(user_id, is_active)` | Enable / disable account |
| `reset_password(user_id, new_password)` | Rehash + update |
| `delete_user(user_id)` | Hard delete (only if not the last admin) |

---

## Session

On successful login, Flask session stores:
```python
session['authenticated'] = True
session['username'] = user['username']
session['role'] = user['role']   # 'admin' | 'viewer'
```

---

## Decorators

Two decorators in `app.py`:

- **`@login_required`** — existing, unchanged behaviour; redirects to `/login` if not authenticated
- **`@admin_required`** — wraps `login_required`; also checks `session['role'] == 'admin'`, returns 403 if not

---

## Role Permissions

| Route | Viewer | Admin |
|-------|--------|-------|
| `GET /` | ✅ | ✅ |
| `POST /upload` | ✅ | ✅ |
| `POST /generate_report` | ❌ | ✅ |
| `GET /download/<id>/<type>` | ✅ | ✅ |
| `GET /download_all/<id>` | ✅ | ✅ |
| `GET /dashboard` | ✅ | ✅ |
| `GET /api/dashboard/data` | ✅ | ✅ |
| `POST /history/delete/<id>` | ❌ | ✅ |
| `GET /admin/users` | ❌ | ✅ |
| `POST /admin/users/add` | ❌ | ✅ |
| `POST /admin/users/<id>/toggle` | ❌ | ✅ |
| `POST /admin/users/<id>/reset-password` | ❌ | ✅ |
| `POST /admin/users/<id>/delete` | ❌ | ✅ |

---

## Routes Added / Modified

### Modified
- `GET/POST /login` — form gains `username` field; validates username + password against DB
- `GET /logout` — unchanged behaviour

### Added
- `GET /admin/users` — admin user management page
- `POST /admin/users/add` — create new user (JSON body: `{username, password, role}`)
- `POST /admin/users/<id>/toggle` — flip `is_active`
- `POST /admin/users/<id>/reset-password` — set new password
- `POST /admin/users/<id>/delete` — delete user (guard: can't delete last admin or yourself)

---

## Admin UI (`/admin/users`)

A new page in the same dark glassmorphism style as the rest of the app.

**Layout:**
- Top bar with "Správa uživatelů" heading and "Přidat uživatele" button
- Table: Username | Role | Status (active/disabled badge) | Created | Actions
- Actions per row: Toggle active/disable, Reset password (modal), Delete
- "Add user" opens an inline modal: username, password, role dropdown

**No separate template file for the modal** — it's inline HTML in `admin_users.html`, shown/hidden with JS.

The admin UI link appears in the top bar of `index.html` and `dashboard.html` **only when `session['role'] == 'admin'`** (rendered via Jinja2 `{% if session.role == 'admin' %}`).

---

## Login Page Changes

`login.html` gains a **username field** above the password field — same glass input style. Label: `UŽIVATELSKÉ JMÉNO`. The subtitle changes from "Zadejte heslo pro přístup" to "Přihlaste se ke svému účtu".

---

## Files Changed

| File | Change |
|------|--------|
| `users.py` | **New** — UserManager class |
| `app.py` | Modified login route, add admin_required decorator, add admin routes, retire APP_PASSWORD |
| `templates/login.html` | Add username field |
| `templates/admin_users.html` | **New** — admin user management page |
| `templates/index.html` | Add admin link in top bar (admin only) |
| `templates/dashboard.html` | Add admin link in top bar (admin only) |
| `requirements.txt` | Add `flask-bcrypt` |

---

## Security Notes

- Passwords never stored or logged in plaintext
- Cannot delete the last admin account (guard in `UserManager.delete_user`)
- Cannot delete your own account (guard in the route)
- Disabled accounts are rejected at login even with correct password
- `admin_required` always runs `login_required` first — no bypass possible
- `app.secret_key` should be changed to a random value for any shared deployment
