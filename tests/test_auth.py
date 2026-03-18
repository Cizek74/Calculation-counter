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
    assert 'Nesprávné'.encode('utf-8') in resp.data
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_login_unknown_username(client):
    """Unknown username shows error."""
    resp = client.post('/login',
                       data={'username': 'nobody', 'password': 'anything'},
                       follow_redirects=True)
    assert 'Nesprávné'.encode('utf-8') in resp.data


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
    assert 'Nesprávné'.encode('utf-8') in resp.data


def test_logout_clears_session(admin_client):
    """Logout clears user_id from session."""
    with admin_client.session_transaction() as sess:
        assert 'user_id' in sess
    admin_client.get('/logout')
    with admin_client.session_transaction() as sess:
        assert 'user_id' not in sess


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


def test_viewer_can_get_index(client, db_path):
    """Viewer can GET / (returns 200, not 403), and response contains role marker."""
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
    assert 'viewer'.encode() in resp.data
