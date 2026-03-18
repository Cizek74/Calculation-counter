# Multi-User Authentication Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the single shared APP_PASSWORD with per-user SQLite accounts, two roles (admin / viewer), and an in-app admin UI at `/admin/users`.

**Architecture:** A new `users.py` module owns a SQLite `users.db` file and exposes a `UserManager` class. `app.py` imports it, replaces the single-password login with username+password auth, adds an `admin_required` decorator, and gains five admin routes. Three templates are updated/created.

**Tech Stack:** Python stdlib `sqlite3`, `werkzeug.security` (already installed — no new pip installs needed), Flask sessions, Jinja2, Tailwind CSS CDN, Lucide icons CDN.

---

### Task 1: Create `users.py` with UserManager

**Files:**
- Create: `users.py`

**Step 1: Create the file with this exact content**

```python
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

USERS_DB_DEFAULT = 'users.db'


class UserManager:
    def __init__(self, db_path=USERS_DB_DEFAULT):
        self.db_path = db_path
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT    NOT NULL UNIQUE,
                    password_hash TEXT    NOT NULL,
                    role          TEXT    NOT NULL DEFAULT 'viewer',
                    is_active     INTEGER NOT NULL DEFAULT 1,
                    created_at    TEXT    NOT NULL
                )
            ''')

    def bootstrap_admin(self, username, password):
        """Create initial admin account if the table is empty."""
        with self._conn() as conn:
            count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            if count == 0:
                pw_hash = generate_password_hash(password)
                conn.execute(
                    'INSERT INTO users (username, password_hash, role, is_active, created_at) VALUES (?, ?, ?, 1, ?)',
                    (username, pw_hash, 'admin', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                )
                print(f"[OK] Bootstrap admin '{username}' created")

    def create_user(self, username, password, role='viewer'):
        """Create a new user. Raises sqlite3.IntegrityError if username taken."""
        pw_hash = generate_password_hash(password)
        with self._conn() as conn:
            conn.execute(
                'INSERT INTO users (username, password_hash, role, is_active, created_at) VALUES (?, ?, ?, 1, ?)',
                (username, pw_hash, role, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )

    def authenticate(self, username, password):
        """Return user dict on success, None on failure (wrong creds or disabled)."""
        with self._conn() as conn:
            row = conn.execute(
                'SELECT id, username, password_hash, role, is_active FROM users WHERE username = ?',
                (username,)
            ).fetchone()
        if row is None:
            return None
        if not row['is_active']:
            return None
        if not check_password_hash(row['password_hash'], password):
            return None
        return {'id': row['id'], 'username': row['username'], 'role': row['role']}

    def get_all(self):
        """Return list of all users (no password_hash)."""
        with self._conn() as conn:
            rows = conn.execute(
                'SELECT id, username, role, is_active, created_at FROM users ORDER BY id'
            ).fetchall()
        return [
            {
                'id': r['id'],
                'username': r['username'],
                'role': r['role'],
                'is_active': bool(r['is_active']),
                'created_at': r['created_at'],
            }
            for r in rows
        ]

    def set_active(self, user_id, is_active):
        """Enable or disable a user account."""
        with self._conn() as conn:
            conn.execute(
                'UPDATE users SET is_active = ? WHERE id = ?',
                (1 if is_active else 0, user_id)
            )

    def reset_password(self, user_id, new_password):
        """Replace the user's password hash."""
        pw_hash = generate_password_hash(new_password)
        with self._conn() as conn:
            conn.execute(
                'UPDATE users SET password_hash = ? WHERE id = ?',
                (pw_hash, user_id)
            )

    def delete_user(self, user_id):
        """Delete a user. Raises ValueError if it would remove the last admin."""
        with self._conn() as conn:
            row = conn.execute('SELECT role FROM users WHERE id = ?', (user_id,)).fetchone()
            if row is None:
                return
            if row['role'] == 'admin':
                admin_count = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'admin'"
                ).fetchone()[0]
                if admin_count <= 1:
                    raise ValueError("Cannot delete the last admin account")
            conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
```

**Step 2: Verify Python syntax**

```bash
cd "C:\Users\cizeko\Desktop\Counting printer" && python -c "from users import UserManager; print('OK')"
```
Expected: `OK`

---

### Task 2: Update `app.py` — wire UserManager, replace login, add admin_required

**Files:**
- Modify: `app.py`

**Step 1: Add import and constants near the top of app.py**

After the existing imports block, add:
```python
from users import UserManager
```

After the existing constants (`CONTRACTS_FILE`, `HISTORY_FILE`, etc.), add:
```python
USERS_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')
```

**Step 2: Initialize UserManager and bootstrap admin after the existing `calculator` / `contract_manager` lines**

After:
```python
calculator = PrintingVolumeCalculator()
contract_manager = ContractManager(CONTRACTS_FILE)
```

Add:
```python
ADMIN_USER     = os.environ.get('ADMIN_USER',     'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme')
user_manager = UserManager(USERS_DB)
user_manager.bootstrap_admin(ADMIN_USER, ADMIN_PASSWORD)
```

**Step 3: Add admin_required decorator**

After the existing `login_required` function, add:

```python
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return jsonify({'error': 'Forbidden'}), 403
        return f(*args, **kwargs)
    return decorated
```

**Step 4: Replace the login route**

Find and replace the entire login function:
```python
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('authenticated'):
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        if request.form.get('password') == APP_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('index'))
        error = 'Nesprávné heslo'
    return render_template('login.html', error=error)
```

Replace with:
```python
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('authenticated'):
        return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = user_manager.authenticate(username, password)
        if user:
            session['authenticated'] = True
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
        error = 'Nesprávné jméno nebo heslo'
    return render_template('login.html', error=error)
```

**Step 5: Protect generate_report and history/delete with admin_required**

Find:
```python
@app.route('/generate_report', methods=['POST'])
@login_required
def generate_report():
```
Replace decorator line with:
```python
@app.route('/generate_report', methods=['POST'])
@admin_required
def generate_report():
```

Find:
```python
@app.route('/history/delete/<entry_id>', methods=['POST'])
```
The decorator below it should also become `@admin_required`. Apply the same pattern.

**Step 6: Remove the APP_PASSWORD line**

Find and delete:
```python
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'changeme')
```

**Step 7: Verify the app imports cleanly**

```bash
cd "C:\Users\cizeko\Desktop\Counting printer" && python -c "import app; print('OK')"
```
Expected: `[OK] Bootstrap admin 'admin' created` (first run), then `OK`

---

### Task 3: Add admin routes to `app.py`

**Files:**
- Modify: `app.py` (append before `if __name__ == '__main__':`)

**Step 1: Add the five admin routes**

Find the line `if __name__ == '__main__':` near the bottom of `app.py` and insert the following block immediately before it:

```python
# ── Admin: user management ────────────────────────────────────────────────

@app.route('/admin/users')
@admin_required
def admin_users():
    users = user_manager.get_all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/users/add', methods=['POST'])
@admin_required
def admin_users_add():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password', '')
    role = data.get('role', 'viewer')
    if not username or not password:
        return jsonify({'error': 'Jméno a heslo jsou povinné'}), 400
    if role not in ('admin', 'viewer'):
        return jsonify({'error': 'Neplatná role'}), 400
    try:
        user_manager.create_user(username, password, role)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def admin_users_toggle(user_id):
    users = user_manager.get_all()
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify({'error': 'Uživatel nenalezen'}), 404
    new_state = not user['is_active']
    user_manager.set_active(user_id, new_state)
    return jsonify({'success': True, 'is_active': new_state})


@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def admin_users_reset_password(user_id):
    data = request.get_json(silent=True) or {}
    new_password = data.get('password', '')
    if not new_password:
        return jsonify({'error': 'Heslo nesmí být prázdné'}), 400
    user_manager.reset_password(user_id, new_password)
    return jsonify({'success': True})


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_users_delete(user_id):
    if session.get('username') and user_id == _get_session_user_id():
        return jsonify({'error': 'Nelze smazat vlastní účet'}), 400
    try:
        user_manager.delete_user(user_id)
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


def _get_session_user_id():
    """Helper: look up the current session user's id."""
    username = session.get('username')
    if not username:
        return None
    all_users = user_manager.get_all()
    match = next((u for u in all_users if u['username'] == username), None)
    return match['id'] if match else None
```

**Step 2: Verify**

```bash
cd "C:\Users\cizeko\Desktop\Counting printer" && python -c "import app; print('OK')"
```
Expected: `OK`

---

### Task 4: Update `templates/login.html` — add username field

**Files:**
- Modify: `templates/login.html`

**Step 1: Change subtitle**

Find:
```html
            <p class="text-sm" style="color:rgba(255,255,255,.35);">Zadejte heslo pro přístup</p>
```
Replace with:
```html
            <p class="text-sm" style="color:rgba(255,255,255,.35);">Přihlaste se ke svému účtu</p>
```

**Step 2: Add username field above the password input**

Find:
```html
                <label for="password" class="field-label">Heslo</label>
```
Replace with:
```html
                <label for="username" class="field-label">Uživatelské jméno</label>
                <input
                    type="text"
                    id="username"
                    name="username"
                    autofocus
                    required
                    autocomplete="username"
                    placeholder="vaše jméno"
                    class="pw-input"
                    style="letter-spacing: normal;"
                >
                <label for="password" class="field-label">Heslo</label>
```

**Step 3: Remove `autofocus` from the password input** (username now gets it)

Find:
```html
                    autofocus
                    required
                    placeholder="••••••••"
```
Replace with:
```html
                    required
                    autocomplete="current-password"
                    placeholder="••••••••"
```

**Step 4: Verify the template renders**

Start the app and visit `http://localhost:5000/login` — confirm two fields are visible: Uživatelské jméno and Heslo.

---

### Task 5: Create `templates/admin_users.html`

**Files:**
- Create: `templates/admin_users.html`

**Step 1: Create the file with this exact content**

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
    <script>tailwind.config = { theme: { extend: { fontFamily: { sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'] } } } }</script>
    <script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>

    <style>
        :root {
            --accent:    #6366f1;
            --accent-2:  #8b5cf6;
            --glass-bg:  rgba(255,255,255,.04);
            --glass-bdr: rgba(255,255,255,.08);
            --text-hi:   #e2e8f0;
            --text-md:   #6b7296;
            --text-lo:   #363b5e;
        }
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Plus Jakarta Sans', system-ui, sans-serif;
            background: #080b1a;
            background-image:
                radial-gradient(ellipse 55% 45% at 20% 10%, rgba(99,102,241,.18) 0%, transparent 55%),
                radial-gradient(ellipse 45% 40% at 80% 90%, rgba(139,92,246,.14) 0%, transparent 55%);
            min-height: 100vh;
            color: var(--text-hi);
        }
        #app-topbar {
            height: 52px;
            display: flex; align-items: center; justify-content: space-between;
            padding: 0 20px;
            background: rgba(8,11,26,.85);
            border-bottom: 1px solid var(--glass-bdr);
            backdrop-filter: blur(16px);
            position: sticky; top: 0; z-index: 50;
        }
        .main-content { max-width: 860px; margin: 0 auto; padding: 32px 20px; }
        .card {
            background: var(--glass-bg);
            border: 1px solid var(--glass-bdr);
            border-radius: 16px;
            backdrop-filter: blur(24px);
        }
        .badge {
            display: inline-flex; align-items: center;
            font-size: 11px; font-weight: 700;
            padding: 3px 10px; border-radius: 20px;
            text-transform: uppercase; letter-spacing: .06em;
        }
        .badge-admin  { background: rgba(99,102,241,.15); color: #a5b4fc; border: 1px solid rgba(99,102,241,.3); }
        .badge-viewer { background: rgba(107,114,128,.12); color: #9ca3af; border: 1px solid rgba(107,114,128,.25); }
        .badge-active   { background: rgba(74,222,128,.10); color: #4ade80; border: 1px solid rgba(74,222,128,.25); }
        .badge-disabled { background: rgba(239,68,68,.10);  color: #f87171; border: 1px solid rgba(239,68,68,.25); }
        .btn {
            display: inline-flex; align-items: center; gap: 6px;
            font-size: 12px; font-weight: 700; border: none; border-radius: 8px;
            padding: 7px 14px; cursor: pointer; transition: all .18s;
            font-family: inherit;
        }
        .btn-primary {
            background: linear-gradient(135deg, var(--accent), var(--accent-2));
            color: #fff;
            box-shadow: 0 2px 12px rgba(99,102,241,.35);
        }
        .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(99,102,241,.50); }
        .btn-ghost {
            background: var(--glass-bg); color: var(--text-md);
            border: 1px solid var(--glass-bdr);
        }
        .btn-ghost:hover { color: var(--text-hi); border-color: rgba(255,255,255,.15); }
        .btn-danger { background: rgba(239,68,68,.12); color: #f87171; border: 1px solid rgba(239,68,68,.2); }
        .btn-danger:hover { background: rgba(239,68,68,.22); }
        table { width: 100%; border-collapse: collapse; }
        thead th {
            font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em;
            color: var(--text-md); padding: 10px 16px; text-align: left;
            border-bottom: 1px solid var(--glass-bdr);
        }
        tbody tr { border-bottom: 1px solid rgba(255,255,255,.04); transition: background .15s; }
        tbody tr:hover { background: rgba(255,255,255,.025); }
        tbody tr:last-child { border-bottom: none; }
        tbody td { padding: 12px 16px; font-size: 13px; vertical-align: middle; }
        .modal-overlay {
            position: fixed; inset: 0; z-index: 100;
            background: rgba(0,0,0,.65); backdrop-filter: blur(4px);
            display: flex; align-items: center; justify-content: center;
        }
        .modal-box {
            background: #111527;
            border: 1px solid var(--glass-bdr);
            border-radius: 20px;
            padding: 28px 32px;
            width: 100%; max-width: 380px;
            box-shadow: 0 24px 64px rgba(0,0,0,.6);
        }
        .field-label {
            display: block; font-size: 10px; font-weight: 700;
            text-transform: uppercase; letter-spacing: .1em;
            color: var(--text-md); margin-bottom: 6px;
        }
        .field-input {
            width: 100%;
            background: rgba(255,255,255,.055);
            border: 1px solid rgba(255,255,255,.10);
            border-radius: 10px;
            padding: 10px 13px;
            font-size: 13px; color: var(--text-hi);
            outline: none; transition: all .2s;
            font-family: inherit; margin-bottom: 16px;
        }
        .field-input:focus {
            border-color: rgba(99,102,241,.6);
            background: rgba(99,102,241,.08);
            box-shadow: 0 0 0 3px rgba(99,102,241,.12);
        }
        select.field-input { cursor: pointer; }
        select.field-input option { background: #111527; }
    </style>
</head>
<body>

<!-- Top bar -->
<header id="app-topbar">
    <div class="flex items-center gap-2 text-sm" style="color:var(--text-lo);">
        <span>Kalkulačka tisků</span>
        <i data-lucide="chevron-right" class="w-3.5 h-3.5" style="color:rgba(255,255,255,.15);"></i>
        <span class="font-bold" style="color:var(--text-hi);">Správa uživatelů</span>
    </div>
    <div class="flex items-center gap-3">
        <a href="/" class="btn btn-ghost text-xs">
            <i data-lucide="arrow-left" class="w-3.5 h-3.5"></i>
            Zpět do aplikace
        </a>
        <a href="/logout"
           class="flex items-center gap-1.5 text-xs font-semibold transition-colors"
           style="color:var(--text-lo);"
           onmouseover="this.style.color='#f87171'" onmouseout="this.style.color='var(--text-lo)'"
           title="Odhlásit se">
            <i data-lucide="log-out" class="w-3.5 h-3.5"></i>
            Odhlásit
        </a>
    </div>
</header>

<!-- Main -->
<main class="main-content">

    <!-- Page heading -->
    <div class="flex items-center justify-between mb-6">
        <div>
            <h1 class="text-xl font-extrabold" style="color:var(--text-hi);">Správa uživatelů</h1>
            <p class="text-sm mt-1" style="color:var(--text-md);">Přidávejte, upravujte a deaktivujte přístupy</p>
        </div>
        <button class="btn btn-primary" onclick="openAddModal()">
            <i data-lucide="user-plus" class="w-3.5 h-3.5"></i>
            Přidat uživatele
        </button>
    </div>

    <!-- User table -->
    <div class="card">
        <table>
            <thead>
                <tr>
                    <th>Uživatelské jméno</th>
                    <th>Role</th>
                    <th>Stav</th>
                    <th>Vytvořen</th>
                    <th style="text-align:right;">Akce</th>
                </tr>
            </thead>
            <tbody id="user-tbody">
                {% for user in users %}
                <tr id="row-{{ user.id }}">
                    <td class="font-semibold" style="color:var(--text-hi);">{{ user.username }}</td>
                    <td>
                        <span class="badge {{ 'badge-admin' if user.role == 'admin' else 'badge-viewer' }}">
                            {{ 'Admin' if user.role == 'admin' else 'Viewer' }}
                        </span>
                    </td>
                    <td>
                        <span class="badge {{ 'badge-active' if user.is_active else 'badge-disabled' }}" id="status-{{ user.id }}">
                            {{ 'Aktivní' if user.is_active else 'Zakázán' }}
                        </span>
                    </td>
                    <td style="color:var(--text-md); font-size:12px;">{{ user.created_at[:10] }}</td>
                    <td>
                        <div class="flex items-center gap-2 justify-end">
                            <button class="btn btn-ghost" onclick="toggleUser({{ user.id }}, {{ 'true' if user.is_active else 'false' }})"
                                    id="toggle-btn-{{ user.id }}" title="Aktivovat / deaktivovat">
                                <i data-lucide="{{ 'user-x' if user.is_active else 'user-check' }}" class="w-3.5 h-3.5" id="toggle-icon-{{ user.id }}"></i>
                            </button>
                            <button class="btn btn-ghost" onclick="openResetModal({{ user.id }}, '{{ user.username }}')" title="Resetovat heslo">
                                <i data-lucide="key" class="w-3.5 h-3.5"></i>
                            </button>
                            <button class="btn btn-danger" onclick="deleteUser({{ user.id }}, '{{ user.username }}')" title="Smazat">
                                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                            </button>
                        </div>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="5" style="text-align:center; color:var(--text-md); padding:32px;">Žádní uživatelé</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

</main>

<!-- Add user modal -->
<div class="modal-overlay hidden" id="add-modal">
    <div class="modal-box">
        <h2 class="text-base font-extrabold mb-5" style="color:var(--text-hi);">Přidat uživatele</h2>
        <label class="field-label">Uživatelské jméno</label>
        <input type="text" id="new-username" class="field-input" placeholder="jméno" autocomplete="off">
        <label class="field-label">Heslo</label>
        <input type="password" id="new-password" class="field-input" placeholder="••••••••">
        <label class="field-label">Role</label>
        <select id="new-role" class="field-input">
            <option value="viewer">Viewer — jen prohlížení</option>
            <option value="admin">Admin — plný přístup</option>
        </select>
        <div id="add-error" class="hidden text-xs font-semibold mb-3" style="color:#f87171;"></div>
        <div class="flex gap-3 justify-end mt-2">
            <button class="btn btn-ghost" onclick="closeAddModal()">Zrušit</button>
            <button class="btn btn-primary" onclick="submitAddUser()">Přidat</button>
        </div>
    </div>
</div>

<!-- Reset password modal -->
<div class="modal-overlay hidden" id="reset-modal">
    <div class="modal-box">
        <h2 class="text-base font-extrabold mb-1" style="color:var(--text-hi);">Resetovat heslo</h2>
        <p class="text-sm mb-5" style="color:var(--text-md);" id="reset-username-label"></p>
        <label class="field-label">Nové heslo</label>
        <input type="password" id="reset-password" class="field-input" placeholder="••••••••">
        <div id="reset-error" class="hidden text-xs font-semibold mb-3" style="color:#f87171;"></div>
        <div class="flex gap-3 justify-end mt-2">
            <button class="btn btn-ghost" onclick="closeResetModal()">Zrušit</button>
            <button class="btn btn-primary" onclick="submitReset()">Uložit</button>
        </div>
    </div>
</div>

<script>
    lucide.createIcons();

    let resetUserId = null;

    // ── Add modal ───────────────────────────────────────────
    function openAddModal() {
        document.getElementById('new-username').value = '';
        document.getElementById('new-password').value = '';
        document.getElementById('new-role').value = 'viewer';
        document.getElementById('add-error').classList.add('hidden');
        document.getElementById('add-modal').classList.remove('hidden');
        document.getElementById('new-username').focus();
    }
    function closeAddModal() {
        document.getElementById('add-modal').classList.add('hidden');
    }
    async function submitAddUser() {
        const username = document.getElementById('new-username').value.trim();
        const password = document.getElementById('new-password').value;
        const role     = document.getElementById('new-role').value;
        const errEl    = document.getElementById('add-error');
        errEl.classList.add('hidden');
        const res = await fetch('/admin/users/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, role }),
        });
        const data = await res.json();
        if (!data.success) {
            errEl.textContent = data.error || 'Chyba';
            errEl.classList.remove('hidden');
            return;
        }
        closeAddModal();
        location.reload();
    }

    // ── Toggle active ───────────────────────────────────────
    async function toggleUser(id, currentlyActive) {
        const res = await fetch(`/admin/users/${id}/toggle`, { method: 'POST' });
        const data = await res.json();
        if (!data.success) { alert(data.error); return; }
        const badge = document.getElementById(`status-${id}`);
        const icon  = document.getElementById(`toggle-icon-${id}`);
        if (data.is_active) {
            badge.textContent = 'Aktivní';
            badge.className = 'badge badge-active';
            icon.setAttribute('data-lucide', 'user-x');
        } else {
            badge.textContent = 'Zakázán';
            badge.className = 'badge badge-disabled';
            icon.setAttribute('data-lucide', 'user-check');
        }
        lucide.createIcons();
    }

    // ── Reset password modal ────────────────────────────────
    function openResetModal(id, username) {
        resetUserId = id;
        document.getElementById('reset-username-label').textContent = username;
        document.getElementById('reset-password').value = '';
        document.getElementById('reset-error').classList.add('hidden');
        document.getElementById('reset-modal').classList.remove('hidden');
        document.getElementById('reset-password').focus();
    }
    function closeResetModal() {
        document.getElementById('reset-modal').classList.add('hidden');
        resetUserId = null;
    }
    async function submitReset() {
        const password = document.getElementById('reset-password').value;
        const errEl    = document.getElementById('reset-error');
        errEl.classList.add('hidden');
        const res = await fetch(`/admin/users/${resetUserId}/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password }),
        });
        const data = await res.json();
        if (!data.success) {
            errEl.textContent = data.error || 'Chyba';
            errEl.classList.remove('hidden');
            return;
        }
        closeResetModal();
    }

    // ── Delete user ─────────────────────────────────────────
    async function deleteUser(id, username) {
        if (!confirm(`Opravdu smazat uživatele „${username}"?`)) return;
        const res = await fetch(`/admin/users/${id}/delete`, { method: 'POST' });
        const data = await res.json();
        if (!data.success) { alert(data.error); return; }
        const row = document.getElementById(`row-${id}`);
        if (row) row.remove();
    }

    // Close modals on backdrop click
    document.getElementById('add-modal').addEventListener('click', function(e) {
        if (e.target === this) closeAddModal();
    });
    document.getElementById('reset-modal').addEventListener('click', function(e) {
        if (e.target === this) closeResetModal();
    });
</script>
</body>
</html>
```

**Step 2: Verify the route renders**

Start the app, log in as admin, visit `http://localhost:5000/admin/users`. Confirm the table loads with at least the bootstrap admin account.

---

### Task 6: Add admin link to `index.html` and `dashboard.html`

**Files:**
- Modify: `templates/index.html`
- Modify: `templates/dashboard.html`

**Step 1: Add admin link in `index.html` top bar**

In `templates/index.html`, find the top-bar nav links block (the `<div class="flex items-center gap-3">` containing the Dashboard link and logout link):

```html
                <a href="/dashboard"
                   class="flex items-center gap-1.5 text-xs font-semibold transition-colors"
                   style="color:var(--text-lo);"
                   onmouseover="this.style.color='#a5b4fc'" onmouseout="this.style.color='var(--text-lo)'"
                   title="Přejít na dashboard">
                    <i data-lucide="bar-chart-2" class="w-3.5 h-3.5"></i>
                    Dashboard
                </a>
```

Insert the following block immediately after the closing `</a>` of the Dashboard link (before the logout link):

```html
                {% if session.role == 'admin' %}
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

**Step 2: Add admin link in `dashboard.html` top bar**

In `templates/dashboard.html`, find the top-bar right-side links block containing the logout link. Insert the admin link immediately before the logout `<a>` tag:

```html
        {% if session.role == 'admin' %}
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

**Step 3: Final end-to-end verification**

1. Start the app: `python app.py`
2. Visit `http://localhost:5000/login` — confirm two fields (username + password)
3. Log in as `admin` / `changeme` — confirm redirect to main app
4. Confirm "Uživatelé" link visible in top bar
5. Visit `/admin/users` — confirm user table and "Přidat uživatele" button
6. Add a new viewer user, log out, log in as that viewer
7. Confirm "Uživatelé" link NOT visible for viewer
8. Confirm viewer can upload and view reports but cannot generate reports (should get 403)
9. Log back in as admin, disable the viewer, log out, try logging in as viewer — should fail
