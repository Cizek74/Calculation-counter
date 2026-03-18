# tests/conftest.py
import pytest
import tempfile
import os
import sys

# Admin bootstrap credentials (must match ADMIN_USER / ADMIN_PASSWORD env vars set in test_app)
ADMIN_USER = 'admin'
ADMIN_PASSWORD = 'AdminPass1!'

# All top-level modules that app.py imports at load time — must be evicted so env vars take effect
_APP_MODULES = {'app', 'contracts', 'calculator', 'reports', 'pdf_fonts'}


@pytest.fixture(scope='function')
def db_path():
    """Provide a temporary SQLite DB file per test, deleted afterwards."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    yield path
    # App uses per-request sqlite3 context managers (no persistent connection),
    # so deletion should succeed. OSError is suppressed for safety on Windows.
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture(scope='function')
def test_app(db_path, monkeypatch):
    """Flask app configured with an isolated temp DB."""
    monkeypatch.setenv('DB_FILE', db_path)
    monkeypatch.setenv('ADMIN_USER', ADMIN_USER)
    monkeypatch.setenv('ADMIN_PASSWORD', ADMIN_PASSWORD)

    # Force re-import of app and all project-local modules so env vars are picked up fresh
    for mod in list(sys.modules.keys()):
        if mod in _APP_MODULES:
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
    resp = client.post('/login', data={'username': ADMIN_USER, 'password': ADMIN_PASSWORD})
    assert resp.status_code == 302, (
        f"Admin login failed (status {resp.status_code}). "
        "Check that /login route exists and bootstrap_admin() ran."
    )
    return client
