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
    assert 'již existuje'.encode('utf-8') in resp.data


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
            "SELECT is_active FROM users WHERE username='admin'"
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
