import json
import sqlite3
import os
import pytest

def test_dashboard_export_pdf(admin_client, test_app):
    """Verify that dashboard export endpoint returns a PDF."""
    db_file = os.environ.get('DB_FILE')
    
    # 1. Insert a mock history record
    entry_id = 'test_export_id'
    with sqlite3.connect(db_file) as conn:
        conn.execute('''
            INSERT INTO history (
                id, saved_at, month_label, date_range_raw,
                total_bw_pages, total_color_pages, total_billable_pages,
                total_revenue_czk, org_breakdown_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry_id, '2024-01-01T12:00:00', 'Leden 2024', '2024-01-01 - 2024-01-31',
            100, 50, 150, 300.0, json.dumps([{'customer': 'Test Corp', 'revenue_czk': 300.0}])
        ))
        conn.commit()
    
    # 2. Call export endpoint
    resp = admin_client.get(f'/api/dashboard/export/{entry_id}')
    
    # 3. Verify response
    assert resp.status_code == 200
    assert resp.mimetype == 'application/pdf'
    assert resp.headers['Content-Disposition'].startswith('attachment; filename=Summary_Leden_2024_test_export_id.pdf')
    assert len(resp.data) > 0

def test_dashboard_export_not_found(admin_client, test_app):
    """Verify 404 for invalid entry ID."""
    resp = admin_client.get('/api/dashboard/export/non_existent_id')
    assert resp.status_code == 404
