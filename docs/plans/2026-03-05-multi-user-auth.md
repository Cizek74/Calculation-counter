# Multi-User Authentication Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace single-password auth with SQLite multi-user system (admin/viewer roles) with an admin user management UI at `/admin/users`.

**Architecture:** `users.db` SQLite file stores users with bcrypt-hashed passwords and roles. `session['user_id']` + `session['role']` replace `session['authenticated']`. Two decorators (`login_required`, `admin_required`) guard routes. Viewer UI restrictions injected via `current_role` Jinja2 variable passed from each protected route.

**Tech Stack:** Flask, flask-bcrypt, sqlite3 (stdlib), pytest, Flask test client

---

### Task 1: Install flask-bcrypt and set up test infrastructure

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Install dependencies**

```bash
pip install flask-bcrypt pytest
```

Expected: both install without errors.

**Step 2: Add flask-bcrypt to requirements.txt**

Open `requirements.txt`. Add a line:
```
flask-bcrypt
```

**Step 3: Create tests directory**

```bash
mkdir tests
```

Create an empty `tests/__init__.py` file.

**Step 4: Create `tests/conftest.py`**

```python
# tests/conftest.py
import pytest
import tempfile
import os
import sys


@pytest.fixture(scope='function')
def db_path():
    """Provide a temporary SQLite DB file per test, deleted afterwards."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture(scope='function')
def test_app(db_path, monkeypatch):
    """Flask app configured with an isolated temp DB."""
    monkeypatch.setenv('DB_FILE', db_path)
    monkeypatch.setenv('ADMIN_USER', 'admin')
    monkeypatch.setenv('ADMIN_PASSWORD', 'AdminPass1!')

    # Force re-import so env vars are picked up fresh each test
    for mod in list(sys.modules.keys()):
        if mod == 'app' or mod.startswith('app.'):
            del sys.modules[mod]

    import app as flask_app
    flask_app.app.config['TESTING'] = True
    flask_app.app.config['WTF_CSRF_ENABLED'] = False

    yield flask_app.app


@pytest.fixture(scope='function')
def client(test_app):
    return test_app.test_client()


@pytest.fixture(scope='function')
def admin_client(client):
    """Test client already logged in as admin."""
    client.post('/login', data={'username': 'admin', 'password': 'AdminPass1!'})
    return client
```

**Step 5: Verify pytest collects nothing (no failures)**

```bash
cd "C:\Users\cizeko\Desktop\Counting printer"
pytest tests/ -v
```

Expected: `no tests ran` or `collected 0 items` — no errors.

**Step 6: Commit**

```bash
git add requirements.txt tests/
git commit -m "chore: add flask-bcrypt and test infrastructure"
```

---

### Task 2: Database init and bootstrap admin

**Files:**
- Modify: `app.py` (add imports, constants, and two functions near the top, after existing imports)
- Create: `tests/test_auth.py`

**Step 1: Write failing tests**

Create `tests/test_auth.py`:

```python
import sqlite3


def test_init_db_creates_users_table(test_app, db_path):
    """users table exists after app import."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        assert cursor.fetchone() is not None


def test_bootstrap_creates_admin(test_app, db_path):
    """Bootstrap inserts admin user when table is empty."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT username, role FROM users WHERE username='admin'"
        ).fetchone()
    assert row is not None
    assert row[1] == 'admin'


def test_bootstrap_does_not_duplicate(test_app, db_path):
    """Calling bootstrap_admin() twice does not create a second admin row."""
    import app as flask_app
    flask_app.bootstrap_admin()
    with sqlite3.connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE username='admin'"
        ).fetchone()[0]
    assert count == 1
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_auth.py -v
```

Expected: FAIL — `init_db` and `bootstrap_admin` not defined yet.

**Step 3: Add DB code to app.py**

In `app.py`, add after the existing imports block (around line 11, after `import re`):

```python
import sqlite3
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt(app)

DB_FILE = os.environ.get(
    'DB_FILE',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')
)


def init_db():
    """Create users table if it doesn't exist."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'viewer',
                is_active     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT NOT NULL
            )
        ''')
        conn.commit()


def bootstrap_admin():
    """Insert a default admin account if the users table is empty."""
    admin_user = os.environ.get('ADMIN_USER', 'admin')
    admin_pass = os.environ.get('ADMIN_PASSWORD', 'changeme')
    if admin_pass == 'changeme':
        print('[WARNING] ADMIN_PASSWORD not set — using default "changeme". Change it!')
    with sqlite3.connect(DB_FILE) as conn:
        count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if count == 0:
            pw_hash = bcrypt.generate_password_hash(admin_pass).decode('utf-8')
            conn.execute(
                'INSERT INTO users (username, password_hash, role, is_active, created_at) '
                'VALUES (?, ?, ?, 1, ?)',
                (admin_user, pw_hash, 'admin',
                 datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
            )
            conn.commit()
            print(f'[OK] Bootstrap admin created: {admin_user}')


# Run at module load (idempotent)
init_db()
bootstrap_admin()
```

**Step 4: Run tests**

```bash
pytest tests/test_auth.py -v
```

Expected: all 3 pass.

**Step 5: Commit**

```bash
git add app.py tests/test_auth.py
git commit -m "feat: SQLite users table with bootstrap admin"
```

---

### Task 3: Replace auth decorators

**Files:**
- Modify: `app.py` — replace `login_required`, add `admin_required`
- Modify: `tests/test_auth.py` — add decorator tests

**Step 1: Write failing tests**

Append to `tests/test_auth.py`:

```python
def test_unauthenticated_redirects_to_login(client):
    """GET / without a session redirects to /login."""
    resp = client.get('/', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_viewer_upload_returns_403(client, db_path):
    """Viewer role cannot POST /upload — gets 403."""
    import app as flask_app
    pw = flask_app.bcrypt.generate_password_hash('vp').decode()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO users (username, password_hash, role, is_active, created_at) '
            'VALUES (?,?,?,1,?)',
            ('viewer1', pw, 'viewer', '2026-01-01T00:00:00')
        )
    client.post('/login', data={'username': 'viewer1', 'password': 'vp'})
    resp = client.post('/upload')
    assert resp.status_code == 403


def test_viewer_admin_page_returns_403(client, db_path):
    """Viewer cannot GET /admin/users."""
    import app as flask_app
    pw = flask_app.bcrypt.generate_password_hash('vp').decode()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO users (username, password_hash, role, is_active, created_at) '
            'VALUES (?,?,?,1,?)',
            ('viewer2', pw, 'viewer', '2026-01-01T00:00:00')
        )
    client.post('/login', data={'username': 'viewer2', 'password': 'vp'})
    resp = client.get('/admin/users')
    assert resp.status_code == 403
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_auth.py::test_viewer_upload_returns_403 -v
```

Expected: FAIL — old decorator uses `session['authenticated']`, upload not yet admin-restricted.

**Step 3: Replace decorators in app.py**

Find the `login_required` function (around line 54). Replace the entire function and add `admin_required` immediately after:

```python
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated
```

**Step 4: Run tests**

```bash
pytest tests/test_auth.py -v
```

Expected: the three new decorator tests pass. Login tests may still fail — that's fine, fixed in Task 4.

**Step 5: Commit**

```bash
git add app.py tests/test_auth.py
git commit -m "feat: admin_required decorator, replace session['authenticated'] with user_id"
```

---

### Task 4: Update /login and /logout routes + login.html

**Files:**
- Modify: `app.py` — `/login` and `/logout` routes
- Modify: `templates/login.html` — add username field, update subtitle

**Step 1: Write failing tests**

Append to `tests/test_auth.py`:

```python
def test_login_success_sets_session(client):
    """Valid admin credentials set user_id, role, username in session."""
    resp = client.post('/login',
                       data={'username': 'admin', 'password': 'AdminPass1!'})
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get('user_id') is not None
        assert sess.get('role') == 'admin'
        assert sess.get('username') == 'admin'


def test_login_wrong_password(client):
    """Wrong password shows error, does not set session."""
    resp = client.post('/login',
                       data={'username': 'admin', 'password': 'wrong'},
                       follow_redirects=True)
    assert b'Nesprávné' in resp.data
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_login_unknown_username(client):
    """Unknown username shows error."""
    resp = client.post('/login',
                       data={'username': 'nobody', 'password': 'anything'},
                       follow_redirects=True)
    assert b'Nesprávné' in resp.data


def test_inactive_user_cannot_login(client, db_path):
    """Disabled (is_active=0) user is rejected."""
    import app as flask_app
    pw = flask_app.bcrypt.generate_password_hash('pass').decode()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO users (username, password_hash, role, is_active, created_at) '
            'VALUES (?,?,?,0,?)',
            ('disabled_user', pw, 'viewer', '2026-01-01T00:00:00')
        )
    resp = client.post('/login',
                       data={'username': 'disabled_user', 'password': 'pass'},
                       follow_redirects=True)
    assert b'Nesprávné' in resp.data


def test_logout_clears_session(admin_client):
    """Logout clears user_id from session."""
    with admin_client.session_transaction() as sess:
        assert 'user_id' in sess
    admin_client.get('/logout')
    with admin_client.session_transaction() as sess:
        assert 'user_id' not in sess
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_auth.py::test_login_success_sets_session -v
```

Expected: FAIL — login still uses old password-only logic.

**Step 3: Replace /login route in app.py**

Find the `login()` function (around line 157). Replace it entirely:

```python
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        with sqlite3.connect(DB_FILE) as conn:
            row = conn.execute(
                'SELECT id, password_hash, role, is_active FROM users WHERE username = ?',
                (username,)
            ).fetchone()
        if row and row[3] == 1 and bcrypt.check_password_hash(row[1], password):
            session['user_id'] = row[0]
            session['username'] = username
            session['role'] = row[2]
            return redirect(url_for('index'))
        error = 'Nesprávné přihlašovací údaje'
    return render_template('login.html', error=error)
```

Also find the `logout()` function and confirm it calls `session.clear()` (it already does — no change needed).

**Step 4: Update templates/login.html**

Find the `<form>` block (around line 186). Replace it with:

```html
<form method="POST" action="/login">
    <label for="username" class="field-label">Uživatelské jméno</label>
    <input
        type="text"
        id="username"
        name="username"
        autofocus
        required
        autocomplete="username"
        placeholder="admin"
        class="pw-input"
        style="letter-spacing: normal;"
    >
    <label for="password" class="field-label">Heslo</label>
    <input
        type="password"
        id="password"
        name="password"
        required
        autocomplete="current-password"
        placeholder="••••••••"
        class="pw-input"
    >
    <button type="submit" class="btn-login">
        <i data-lucide="log-in" class="w-4 h-4"></i>
        Přihlásit se
    </button>
</form>
```

Also update the subtitle `<p>` tag from `"Zadejte heslo pro přístup"` to `"Přihlaste se pro přístup"`.

**Step 5: Run tests**

```bash
pytest tests/test_auth.py -v
```

Expected: all pass.

**Step 6: Commit**

```bash
git add app.py templates/login.html tests/test_auth.py
git commit -m "feat: username+password login with bcrypt, update login.html"
```

---

### Task 5: Restrict write routes to admin

**Files:**
- Modify: `app.py` — apply `@admin_required` to `/upload`, `/generate_report`, `/history/delete/<entry_id>`
- Modify: `tests/test_auth.py` — add restriction tests

**Step 1: Write failing tests**

Append to `tests/test_auth.py`:

```python
def test_viewer_cannot_generate_report(client, db_path):
    """Viewer POST /generate_report gets 403."""
    import app as flask_app
    pw = flask_app.bcrypt.generate_password_hash('vp').decode()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO users (username, password_hash, role, is_active, created_at) '
            'VALUES (?,?,?,1,?)',
            ('viewer3', pw, 'viewer', '2026-01-01T00:00:00')
        )
    client.post('/login', data={'username': 'viewer3', 'password': 'vp'})
    resp = client.post('/generate_report',
                       data='{}',
                       content_type='application/json')
    assert resp.status_code == 403


def test_viewer_cannot_delete_history(client, db_path):
    """Viewer POST /history/delete/<id> gets 403."""
    import app as flask_app
    pw = flask_app.bcrypt.generate_password_hash('vp').decode()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO users (username, password_hash, role, is_active, created_at) '
            'VALUES (?,?,?,1,?)',
            ('viewer4', pw, 'viewer', '2026-01-01T00:00:00')
        )
    client.post('/login', data={'username': 'viewer4', 'password': 'vp'})
    resp = client.post('/history/delete/fake-session-id')
    assert resp.status_code == 403


def test_admin_upload_not_403(admin_client):
    """Admin POST /upload does not return 403 (may return other errors — that's fine)."""
    resp = admin_client.post('/upload')
    assert resp.status_code != 403
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_auth.py::test_viewer_cannot_delete_history -v
```

Expected: FAIL — history delete still uses `@login_required`.

**Step 3: Swap decorators in app.py**

Find the three routes and change `@login_required` to `@admin_required`:

```python
@app.route('/upload', methods=['POST'])
@admin_required          # <-- was @login_required
def upload_files():
    ...

@app.route('/generate_report', methods=['POST'])
@admin_required          # <-- was @login_required
def generate_report():
    ...

@app.route('/history/delete/<entry_id>', methods=['POST'])
@admin_required          # <-- was @login_required
def delete_history_entry(entry_id):
    ...
```

**Step 4: Run tests**

```bash
pytest tests/test_auth.py -v
```

Expected: all pass.

**Step 5: Commit**

```bash
git add app.py tests/test_auth.py
git commit -m "feat: restrict upload/generate/history-delete to admin role"
```

---

### Task 6: Admin user management routes

**Files:**
- Modify: `app.py` — add four new routes
- Create: `tests/test_admin.py`

**Step 1: Write failing tests**

Create `tests/test_admin.py`:

```python
import sqlite3
import pytest


def test_admin_can_view_users_page(admin_client):
    resp = admin_client.get('/admin/users')
    assert resp.status_code == 200


def test_viewer_cannot_view_users_page(client, db_path):
    import app as flask_app
    pw = flask_app.bcrypt.generate_password_hash('vp').decode()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO users (username,password_hash,role,is_active,created_at) VALUES (?,?,?,1,?)',
            ('va1', pw, 'viewer', '2026-01-01T00:00:00')
        )
    client.post('/login', data={'username': 'va1', 'password': 'vp'})
    resp = client.get('/admin/users')
    assert resp.status_code == 403


def test_admin_can_create_user(admin_client, db_path):
    resp = admin_client.post('/admin/users', data={
        'username': 'newviewer',
        'password': 'Secure123!',
        'role': 'viewer'
    }, follow_redirects=True)
    assert resp.status_code == 200
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT role FROM users WHERE username='newviewer'"
        ).fetchone()
    assert row is not None
    assert row[0] == 'viewer'


def test_create_duplicate_username_shows_error(admin_client):
    resp = admin_client.post('/admin/users', data={
        'username': 'admin',
        'password': 'Secure123!',
        'role': 'viewer'
    }, follow_redirects=True)
    assert b'již existuje' in resp.data


def test_admin_can_toggle_user_inactive(admin_client, db_path):
    import app as flask_app
    pw = flask_app.bcrypt.generate_password_hash('p').decode()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO users (username,password_hash,role,is_active,created_at) VALUES (?,?,?,1,?)',
            ('toguser', pw, 'viewer', '2026-01-01T00:00:00')
        )
        uid = conn.execute(
            "SELECT id FROM users WHERE username='toguser'"
        ).fetchone()[0]
    admin_client.post(f'/admin/users/{uid}/toggle-active', follow_redirects=True)
    with sqlite3.connect(db_path) as conn:
        active = conn.execute(
            'SELECT is_active FROM users WHERE id=?', (uid,)
        ).fetchone()[0]
    assert active == 0


def test_admin_cannot_disable_self(admin_client, db_path):
    with sqlite3.connect(db_path) as conn:
        uid = conn.execute(
            "SELECT id FROM users WHERE username='admin'"
        ).fetchone()[0]
    admin_client.post(f'/admin/users/{uid}/toggle-active', follow_redirects=True)
    with sqlite3.connect(db_path) as conn:
        active = conn.execute(
            'SELECT is_active FROM users WHERE username=\'admin\''
        ).fetchone()[0]
    assert active == 1


def test_admin_can_reset_password(admin_client, db_path):
    import app as flask_app
    pw = flask_app.bcrypt.generate_password_hash('oldpass').decode()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO users (username,password_hash,role,is_active,created_at) VALUES (?,?,?,1,?)',
            ('resetuser', pw, 'viewer', '2026-01-01T00:00:00')
        )
        uid = conn.execute(
            "SELECT id FROM users WHERE username='resetuser'"
        ).fetchone()[0]
    admin_client.post(
        f'/admin/users/{uid}/reset-password',
        data={'new_password': 'NewPass999!'},
        follow_redirects=True
    )
    with sqlite3.connect(db_path) as conn:
        new_hash = conn.execute(
            'SELECT password_hash FROM users WHERE id=?', (uid,)
        ).fetchone()[0]
    assert flask_app.bcrypt.check_password_hash(new_hash, 'NewPass999!')
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_admin.py -v
```

Expected: all FAIL — routes don't exist.

**Step 3: Add admin routes to app.py**

Add the following four routes at the end of `app.py`, before the `if __name__ == '__main__':` block:

```python
# ── Admin user management ────────────────────────────────────────────────────

def _get_all_users():
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            'SELECT id, username, role, is_active, created_at FROM users ORDER BY created_at'
        ).fetchall()
    return [
        {'id': r[0], 'username': r[1], 'role': r[2],
         'is_active': bool(r[3]), 'created_at': r[4]}
        for r in rows
    ]


@app.route('/admin/users', methods=['GET'])
@admin_required
def admin_users():
    return render_template('admin_users.html',
                           users=_get_all_users(),
                           current_username=session['username'])


@app.route('/admin/users', methods=['POST'])
@admin_required
def admin_create_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'viewer')
    if role not in ('admin', 'viewer'):
        role = 'viewer'

    error = None
    if not username or not password:
        error = 'Vyplňte uživatelské jméno a heslo.'
    else:
        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        try:
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute(
                    'INSERT INTO users (username, password_hash, role, is_active, created_at) '
                    'VALUES (?,?,?,1,?)',
                    (username, pw_hash, role,
                     datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
                )
        except sqlite3.IntegrityError:
            error = f'Uživatel „{username}" již existuje.'

    if error:
        return render_template('admin_users.html',
                               users=_get_all_users(),
                               current_username=session['username'],
                               error=error)
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def admin_toggle_active(user_id):
    if user_id == session['user_id']:
        return render_template('admin_users.html',
                               users=_get_all_users(),
                               current_username=session['username'],
                               error='Nemůžete deaktivovat vlastní účet.')
    with sqlite3.connect(DB_FILE) as conn:
        current = conn.execute(
            'SELECT is_active FROM users WHERE id=?', (user_id,)
        ).fetchone()
        if current:
            conn.execute(
                'UPDATE users SET is_active=? WHERE id=?',
                (0 if current[0] else 1, user_id)
            )
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def admin_reset_password(user_id):
    new_password = request.form.get('new_password', '')
    if new_password:
        pw_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                'UPDATE users SET password_hash=? WHERE id=?',
                (pw_hash, user_id)
            )
    return redirect(url_for('admin_users'))
```

**Step 4: Run tests**

```bash
pytest tests/test_admin.py -v
```

Expected: all pass (except `test_admin_can_view_users_page` which needs the template — that's Task 7).

**Step 5: Commit**

```bash
git add app.py tests/test_admin.py
git commit -m "feat: admin user management routes"
```

---

### Task 7: Create admin_users.html template

**Files:**
- Create: `templates/admin_users.html`

No unit test — covered by `test_admin_can_view_users_page` from Task 6.

**Step 1: Create `templates/admin_users.html`**

```html
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Správa uživatelů — Kalkulačka tisků</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>tailwind.config = { theme: { extend: { fontFamily: { sans: ['"Plus Jakarta Sans"','system-ui','sans-serif'] } } } }</script>
    <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
    <style>
        :root {
            --accent: #6366f1; --accent-2: #8b5cf6;
            --glass-bg: rgba(255,255,255,.04); --glass-bdr: rgba(255,255,255,.09);
            --text-hi: rgba(255,255,255,.92); --text-md: rgba(255,255,255,.55); --text-lo: rgba(255,255,255,.30);
        }
        body {
            font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
            background: #080b1a;
            background-image:
                radial-gradient(ellipse 55% 45% at 25% 15%, rgba(99,102,241,.18) 0%, transparent 55%),
                radial-gradient(ellipse 45% 40% at 75% 85%, rgba(139,92,246,.14) 0%, transparent 55%);
            min-height: 100vh; color: var(--text-hi);
        }
        .topbar {
            display: flex; align-items: center; justify-content: space-between;
            padding: 14px 24px;
            background: rgba(8,11,26,.85); border-bottom: 1px solid var(--glass-bdr);
            backdrop-filter: blur(20px); position: sticky; top: 0; z-index: 50;
        }
        .glass-card {
            background: var(--glass-bg); border: 1px solid var(--glass-bdr);
            border-radius: 16px; backdrop-filter: blur(24px); padding: 24px;
        }
        .btn-primary {
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            color: #fff; font-weight: 700; font-size: 13px; border: none; border-radius: 10px;
            padding: 10px 18px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
            transition: all .2s; box-shadow: 0 4px 16px rgba(99,102,241,.35); font-family: inherit;
        }
        .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 8px 24px rgba(99,102,241,.5); }
        .btn-ghost {
            background: rgba(255,255,255,.06); color: var(--text-md); font-weight: 600; font-size: 13px;
            border: 1px solid var(--glass-bdr); border-radius: 10px;
            padding: 8px 14px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px;
            transition: all .2s; font-family: inherit; text-decoration: none;
        }
        .btn-ghost:hover { background: rgba(255,255,255,.10); color: var(--text-hi); }
        .btn-sm { padding: 5px 10px; font-size: 12px; border-radius: 8px; }
        .field-label { display: block; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: var(--text-lo); margin-bottom: 6px; }
        .field-input {
            width: 100%; background: rgba(255,255,255,.055); border: 1px solid rgba(255,255,255,.10);
            border-radius: 10px; padding: 10px 14px; font-size: 13px; color: var(--text-hi);
            outline: none; transition: all .2s; font-family: inherit;
        }
        .field-input:focus { border-color: rgba(99,102,241,.6); background: rgba(99,102,241,.08); box-shadow: 0 0 0 3px rgba(99,102,241,.12); }
        .badge-admin { background: rgba(99,102,241,.18); color: #a5b4fc; border: 1px solid rgba(99,102,241,.3); border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 700; }
        .badge-viewer { background: rgba(255,255,255,.07); color: var(--text-md); border: 1px solid var(--glass-bdr); border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 700; }
        .dot-on { width: 7px; height: 7px; border-radius: 50%; background: #4ade80; box-shadow: 0 0 6px rgba(74,222,128,.6); display: inline-block; }
        .dot-off { width: 7px; height: 7px; border-radius: 50%; background: rgba(255,255,255,.2); display: inline-block; }
        .error-box { background: rgba(239,68,68,.09); border: 1px solid rgba(239,68,68,.25); border-radius: 10px; padding: 11px 14px; display: flex; align-items: center; gap: 10px; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--text-lo); padding: 0 16px 12px; text-align: left; }
        td { padding: 13px 16px; font-size: 13px; border-top: 1px solid rgba(255,255,255,.05); vertical-align: top; }
        tr:hover td { background: rgba(255,255,255,.02); }
        .reset-form { display: none; margin-top: 8px; }
        .reset-form.open { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    </style>
</head>
<body>

<header class="topbar">
    <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;">
            <i data-lucide="printer" style="width:16px;height:16px;color:#fff;"></i>
        </div>
        <span style="font-weight:800;font-size:15px;color:var(--text-hi);">Kalkulačka tisků</span>
        <i data-lucide="chevron-right" style="width:14px;height:14px;color:rgba(255,255,255,.2);"></i>
        <span style="font-size:13px;color:var(--text-md);">Správa uživatelů</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px;">
        <a href="/" class="btn-ghost btn-sm">
            <i data-lucide="layout-dashboard" style="width:13px;height:13px;"></i> Aplikace
        </a>
        <a href="/dashboard" class="btn-ghost btn-sm">
            <i data-lucide="bar-chart-2" style="width:13px;height:13px;"></i> Dashboard
        </a>
        <a href="/logout" class="btn-ghost btn-sm" style="color:rgba(248,113,113,.7);"
           onmouseover="this.style.color='#f87171'" onmouseout="this.style.color='rgba(248,113,113,.7)'">
            <i data-lucide="log-out" style="width:13px;height:13px;"></i> Odhlásit
        </a>
    </div>
</header>

<main style="max-width:920px;margin:0 auto;padding:32px 24px;">

    {% if error %}
    <div class="error-box" style="margin-bottom:24px;">
        <i data-lucide="alert-circle" style="width:16px;height:16px;color:#f87171;flex-shrink:0;"></i>
        <span style="font-size:13px;font-weight:600;color:rgba(248,113,113,.9);">{{ error }}</span>
    </div>
    {% endif %}

    <!-- User table -->
    <div class="glass-card" style="margin-bottom:24px;">
        <h2 style="font-size:16px;font-weight:800;margin-bottom:20px;color:var(--text-hi);">Uživatelé</h2>
        <table>
            <thead>
                <tr>
                    <th>Uživatelské jméno</th>
                    <th>Role</th>
                    <th>Stav</th>
                    <th>Vytvořeno</th>
                    <th>Akce</th>
                </tr>
            </thead>
            <tbody>
            {% for user in users %}
            <tr>
                <td style="font-weight:600;color:var(--text-hi);">
                    {{ user.username }}
                    {% if user.username == current_username %}
                    <span style="font-size:10px;color:var(--text-lo);margin-left:6px;">(vy)</span>
                    {% endif %}
                </td>
                <td>
                    {% if user.role == 'admin' %}
                    <span class="badge-admin">Admin</span>
                    {% else %}
                    <span class="badge-viewer">Prohlížeč</span>
                    {% endif %}
                </td>
                <td>
                    {% if user.is_active %}
                    <span class="dot-on"></span>
                    <span style="font-size:12px;color:#4ade80;margin-left:5px;">Aktivní</span>
                    {% else %}
                    <span class="dot-off"></span>
                    <span style="font-size:12px;color:var(--text-lo);margin-left:5px;">Deaktivován</span>
                    {% endif %}
                </td>
                <td style="color:var(--text-md);font-size:12px;">{{ user.created_at[:10] }}</td>
                <td>
                    <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-start;">
                        {% if user.username != current_username %}
                        <form method="POST" action="/admin/users/{{ user.id }}/toggle-active">
                            <button type="submit" class="btn-ghost btn-sm">
                                {% if user.is_active %}
                                <i data-lucide="user-x" style="width:12px;height:12px;"></i> Deaktivovat
                                {% else %}
                                <i data-lucide="user-check" style="width:12px;height:12px;"></i> Aktivovat
                                {% endif %}
                            </button>
                        </form>
                        {% endif %}
                        <button class="btn-ghost btn-sm" onclick="toggleReset({{ user.id }})">
                            <i data-lucide="key" style="width:12px;height:12px;"></i> Reset hesla
                        </button>
                        <form method="POST" action="/admin/users/{{ user.id }}/reset-password"
                              class="reset-form" id="reset-{{ user.id }}">
                            <input type="password" name="new_password" required
                                   placeholder="Nové heslo"
                                   class="field-input"
                                   style="width:160px;padding:7px 10px;font-size:12px;">
                            <button type="submit" class="btn-primary" style="padding:7px 12px;font-size:12px;">
                                Uložit
                            </button>
                        </form>
                    </div>
                </td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- Add user -->
    <div class="glass-card">
        <h2 style="font-size:16px;font-weight:800;margin-bottom:20px;color:var(--text-hi);">Přidat uživatele</h2>
        <form method="POST" action="/admin/users"
              style="display:grid;grid-template-columns:1fr 1fr auto auto;gap:16px;align-items:end;">
            <div>
                <label class="field-label">Uživatelské jméno</label>
                <input type="text" name="username" required class="field-input" placeholder="nový.uživatel">
            </div>
            <div>
                <label class="field-label">Heslo</label>
                <input type="password" name="password" required class="field-input" placeholder="••••••••">
            </div>
            <div>
                <label class="field-label">Role</label>
                <select name="role" class="field-input" style="cursor:pointer;">
                    <option value="viewer">Prohlížeč</option>
                    <option value="admin">Admin</option>
                </select>
            </div>
            <div>
                <button type="submit" class="btn-primary">
                    <i data-lucide="user-plus" style="width:14px;height:14px;"></i>
                    Přidat
                </button>
            </div>
        </form>
    </div>

</main>

<script>
    lucide.createIcons();
    function toggleReset(id) {
        const form = document.getElementById('reset-' + id);
        form.classList.toggle('open');
        if (form.classList.contains('open')) form.querySelector('input').focus();
    }
</script>
</body>
</html>
```

**Step 2: Run all tests**

```bash
pytest tests/ -v
```

Expected: all pass including `test_admin_can_view_users_page`.

**Step 3: Commit**

```bash
git add templates/admin_users.html
git commit -m "feat: admin users management page (admin_users.html)"
```

---

### Task 8: Viewer restrictions on index.html + admin links in top bars

**Files:**
- Modify: `app.py` — pass `current_role` and `current_username` to `index()` and `dashboard()`
- Modify: `templates/index.html` — viewer banner, disabled upload/generate, admin link in top bar
- Modify: `templates/dashboard.html` — admin link in top bar
- Modify: `tests/test_auth.py` — add viewer index test

**Step 1: Write failing test**

Append to `tests/test_auth.py`:

```python
def test_viewer_can_get_index(client, db_path):
    """Viewer can GET / (returns 200, not 403)."""
    import app as flask_app
    pw = flask_app.bcrypt.generate_password_hash('vp').decode()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            'INSERT INTO users (username,password_hash,role,is_active,created_at) VALUES (?,?,?,1,?)',
            ('vwr7', pw, 'viewer', '2026-01-01T00:00:00')
        )
    client.post('/login', data={'username': 'vwr7', 'password': 'vp'})
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'viewer' in resp.data
```

**Step 2: Run to verify failure**

```bash
pytest tests/test_auth.py::test_viewer_can_get_index -v
```

Expected: FAIL — `current_role` not yet passed to the template.

**Step 3: Update `index()` and `dashboard()` routes in app.py**

Find the `index()` route:
```python
@app.route('/')
@login_required
def index():
    return render_template('index.html',
                           current_role=session.get('role', 'viewer'),
                           current_username=session.get('username', ''))
```

Find the `dashboard()` route and update it similarly:
```python
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html',
                           current_role=session.get('role', 'viewer'),
                           current_username=session.get('username', ''))
```

**Step 4: Add admin link to index.html top bar**

In `templates/index.html`, find the top-bar right-side links (around line 350). Add an admin link between the Dashboard link and the logout link:

```html
{% if current_role == 'admin' %}
<a href="/admin/users"
   class="flex items-center gap-1.5 text-xs font-semibold transition-colors"
   style="color:var(--text-lo);"
   onmouseover="this.style.color='#a5b4fc'" onmouseout="this.style.color='var(--text-lo)'"
   title="Správa uživatelů">
    <i data-lucide="users" class="w-3.5 h-3.5"></i>
    Uživatelé
</a>
{% endif %}
```

**Step 5: Add viewer banner to index.html**

In `templates/index.html`, find `<main class="flex-1 overflow-y-auto p-6" id="mainContent">` (around line 370). Add immediately after the opening `<main>` tag:

```html
{% if current_role == 'viewer' %}
<div style="margin-bottom:16px;padding:11px 16px;background:rgba(99,102,241,.10);border:1px solid rgba(99,102,241,.25);border-radius:12px;display:flex;align-items:center;gap:10px;">
    <i data-lucide="info" style="width:15px;height:15px;color:#a5b4fc;flex-shrink:0;"></i>
    <span style="font-size:13px;color:rgba(165,180,252,.85);">Přihlášen jako prohlížeč — nahrávání a generování reportů je zakázáno.</span>
</div>
{% endif %}
```

**Step 6: Add viewer JS restrictions to index.html**

At the bottom of `templates/index.html`, just before `</body>`, add:

```html
{% if current_role == 'viewer' %}
<script>
(function () {
    // Disable upload zone (id="uploadSection")
    var zone = document.getElementById('uploadSection');
    if (zone) { zone.style.pointerEvents = 'none'; zone.style.opacity = '0.4'; zone.title = 'Pouze pro administrátory'; }

    // Disable file input (id="fileInput")
    var fi = document.getElementById('fileInput');
    if (fi) fi.disabled = true;

    // Disable process button (id="processBtn")
    var pb = document.getElementById('processBtn');
    if (pb) pb.disabled = true;

    // Disable generate button — find by onclick attribute
    document.querySelectorAll('button[onclick="generateReport()"]').forEach(function(btn) {
        btn.disabled = true;
    });
})();
</script>
{% endif %}
```

**Step 7: Add admin link to dashboard.html top bar**

In `templates/dashboard.html`, find the top-bar right-side links (around line 164). Add the admin link between "Zpět do aplikace" and the logout link:

```html
{% if current_role == 'admin' %}
<a href="/admin/users" class="btn btn-secondary text-xs">
    <i data-lucide="users" class="w-3.5 h-3.5"></i>
    Uživatelé
</a>
{% endif %}
```

**Step 8: Run all tests**

```bash
pytest tests/ -v
```

Expected: all pass.

**Step 9: Commit**

```bash
git add app.py templates/index.html templates/dashboard.html tests/test_auth.py
git commit -m "feat: viewer UI restrictions on index, admin link in top bars"
```

---

### Task 9: Final smoke test and .gitignore

**Files:**
- Modify: `.gitignore` — ensure `users.db` is excluded

**Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all pass, no errors.

**Step 2: Update .gitignore**

Open `.gitignore`. Add if not already present:
```
users.db
```

**Step 3: Manual smoke test checklist**

```bash
python app.py
```

- `http://localhost:5000` → redirects to `/login`
- Login as `admin` / `changeme` (or env var value) → lands on main page
- See "Uživatelé" link in top bar → `/admin/users` loads with user table
- Add a viewer user (e.g. `test` / `test123`, role Prohlížeč)
- Logout → login as `test` / `test123`
- Blue info banner visible on main page
- Upload zone is greyed out and non-clickable
- `POST /upload` returns 403 (open dev tools, try drag-drop)
- `/admin/users` shows 403 JSON response
- Logout → login as admin → disable `test` user
- Logout → try logging in as `test` → get "Nesprávné přihlašovací údaje"

**Step 4: Final commit**

```bash
git add .gitignore
git commit -m "chore: add users.db to .gitignore"
```
