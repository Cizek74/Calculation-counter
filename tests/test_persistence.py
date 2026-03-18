import json
import sqlite3
import os
import pytest
from datetime import datetime

def test_db_init(test_app):
    """Verify that all required tables are created."""
    db_file = os.environ.get('DB_FILE')
    with sqlite3.connect(db_file) as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]
        assert 'users' in table_names
        assert 'history' in table_names
        assert 'sessions' in table_names

def test_history_migration(test_app, tmp_path, monkeypatch):
    """Verify that history.json is migrated to the history table."""
    db_file = os.environ.get('DB_FILE')
    history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'history.json')
    
    # Create a mock history.json
    mock_history = [
        {
            "id": "test_id",
            "saved_at": "2024-01-01T12:00:00",
            "month_label": "Leden 2024",
            "date_range_raw": "2024-01-01 - 2024-01-31",
            "total_bw_pages": 100,
            "total_color_pages": 50,
            "total_billable_pages": 150,
            "total_revenue_czk": 300.5,
            "org_breakdown": [{"customer": "Company A", "revenue_czk": 300.5}]
        }
    ]
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(mock_history, f)
    
    # Re-import app to trigger migration
    import sys
    _APP_MODULES = {'app', 'contracts', 'calculator', 'reports', 'pdf_fonts'}
    for mod in list(sys.modules.keys()):
        if mod in _APP_MODULES:
            del sys.modules[mod]
    
    import app
    
    with sqlite3.connect(db_file) as conn:
        row = conn.execute("SELECT id, month_label, total_revenue_czk FROM history").fetchone()
        assert row is not None
        assert row[0] == "test_id"
        assert row[1] == "Leden 2024"
        assert row[2] == 300.5

    # Verify history.json was backed up
    assert not os.path.exists(history_file)
    assert os.path.exists(history_file + '.bak')
    
    # Clean up
    os.remove(history_file + '.bak')

def test_session_persistence(admin_client, test_app):
    """Verify that session data is persisted in the database."""
    db_file = os.environ.get('DB_FILE')
    
    # Mock some data to upload
    # We'll skip the actual upload route and just insert into the sessions table directly
    # or just use the route but that's complex with CSV files.
    # Let's just verify the /upload route inserts into sessions.
    
    import io
    csv_content = (
        "Model,Serial Number,Date Range,"
        "A4/Letter-1sided-B&W (Report Interval),A4/Letter-1sided-Color (Report Interval),"
        "A4/Letter-2sided-B&W (Report Interval),A4/Letter-2sided-Color (Report Interval),"
        "A3/Ledger-1sided-B&W (Report Interval),A3/Ledger-1sided-Color (Report Interval),"
        "A3/Ledger-2sided-B&W (Report Interval),A3/Ledger-2sided-Color (Report Interval),"
        "A5-1sided-B&W (Report Interval),A5-1sided-Color (Report Interval),"
        "A5-2sided-B&W (Report Interval),A5-2sided-Color (Report Interval),"
        "A6-1sided-B&W (Report Interval),A6-1sided-Color (Report Interval),"
        "A6-2sided-B&W (Report Interval),A6-2sided-Color (Report Interval),"
        "B4/Legal-1sided-B&W (Report Interval),B4/Legal-1sided-Color (Report Interval),"
        "B4/Legal-2sided-B&W (Report Interval),B4/Legal-2sided-Color (Report Interval),"
        "B5-1sided-B&W (Report Interval),B5-1sided-Color (Report Interval),"
        "B5-2sided-B&W (Report Interval),B5-2sided-Color (Report Interval),"
        "Envelope-1sided-B&W (Report Interval),Envelope-1sided-Color (Report Interval),"
        "Envelope-2sided-B&W (Report Interval),Envelope-2sided-Color (Report Interval),"
        "Other-1sided-B&W (Report Interval),Other-1sided-Color (Report Interval),"
        "Other-2sided-B&W (Report Interval),Other-2sided-Color (Report Interval)\n"
        "ModelA,SerialA,2024-01-01 - 2024-01-31,10,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0\n"
    )
    
    data = {
        'files': (io.BytesIO(csv_content.encode('utf-8')), 'Firma ABC.csv')
    }
    
    resp = admin_client.post('/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert 'session_id' in json_data
    session_id = json_data['session_id']
    
    # Verify it is in DB
    with sqlite3.connect(db_file) as conn:
        row = conn.execute("SELECT id, data_json FROM sessions WHERE id = ?", (session_id,)).fetchone()
        assert row is not None
        assert row[0] == session_id
        session_data = json.loads(row[1])
        assert len(session_data) == 1
        assert session_data[0]['Serial_Number'] == 'SerialA'

def test_cleanup_sessions(test_app):
    """Verify that cleanup_old_sessions removes stale sessions."""
    db_file = os.environ.get('DB_FILE')
    
    # Insert a stale session
    stale_id = 'staleid1'
    old_timestamp = datetime.now().timestamp() - (25 * 3600) # 25 hours ago
    
    with sqlite3.connect(db_file) as conn:
        conn.execute(
            'INSERT INTO sessions (id, data_json, created_at) VALUES (?, ?, ?)',
            (stale_id, json.dumps([]), old_timestamp)
        )
        conn.commit()
    
    # Add a dummy file to processed/
    processed_dir = 'processed'
    os.makedirs(processed_dir, exist_ok=True)
    dummy_file = os.path.join(processed_dir, f'{stale_id}_report.pdf')
    with open(dummy_file, 'w') as f:
        f.write('dummy')
        
    import app
    app.cleanup_old_sessions()
    
    # Verify record is gone
    with sqlite3.connect(db_file) as conn:
        row = conn.execute("SELECT id FROM sessions WHERE id = ?", (stale_id,)).fetchone()
        assert row is None
        
    # Verify file is gone
    assert not os.path.exists(dummy_file)
