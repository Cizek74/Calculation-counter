import json
import sqlite3
import os
import pytest
from calculator import PrintingVolumeCalculator

def test_calculator_with_mapping():
    """Verify that the calculator correctly uses column mapping."""
    calc = PrintingVolumeCalculator()
    
    # Non-standard CSV data
    csv_data = [
        {
            'Stroj': 'Canon IR 3025',
            'S/N': 'XYZ123',
            'Období': '2024-01-01 - 2024-01-31',
            'BW_Total': '1000',
            'Color_Total': '500'
        }
    ]
    
    # Mapping dict: {Expected: Actual}
    mapping = {
        'Model': 'Stroj',
        'Serial Number': 'S/N',
        'Date Range': 'Období',
        'A4/Letter-1sided-B&W (Report Interval)': 'BW_Total',
        'A4/Letter-1sided-Color (Report Interval)': 'Color_Total'
    }
    
    results = calc.calculate_billable_volumes(csv_data, "test.csv", mapping=mapping)
    
    assert len(results) == 1
    assert results[0]['Printer_Model'] == 'Canon IR 3025'
    assert results[0]['Serial_Number'] == 'XYZ123'
    assert results[0]['Billable_BW_Pages'] == 1000
    assert results[0]['Billable_Color_Pages'] == 500

def test_api_mappings(admin_client, test_app):
    """Verify mapping API endpoints."""
    # 1. Save mapping
    mapping = {'Model': 'Stroj', 'Serial Number': 'S/N'}
    resp = admin_client.post('/api/mappings/save', json={
        'profile_name': 'Canon Profile',
        'mapping': mapping
    })
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True
    
    # 2. List mappings
    resp = admin_client.get('/api/mappings')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['mappings']) == 1
    assert data['mappings'][0]['profile_name'] == 'Canon Profile'
    assert data['mappings'][0]['mapping_json'] == mapping
    
    mapping_id = data['mappings'][0]['id']
    
    # 3. Delete mapping
    resp = admin_client.post(f'/api/mappings/delete/{mapping_id}')
    assert resp.status_code == 200
    assert resp.get_json()['success'] is True
    
    # 4. Verify deleted
    resp = admin_client.get('/api/mappings')
    assert len(resp.get_json()['mappings']) == 0

def test_upload_trigger_mapping(admin_client, test_app):
    """Verify that uploading a CSV with missing columns returns mapping_required status."""
    import io
    csv_content = "WrongHeader1,WrongHeader2\nValue1,Value2\n"
    data = {
        'files': (io.BytesIO(csv_content.encode('utf-8')), 'test_missing.csv')
    }
    
    resp = admin_client.post('/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    json_data = resp.get_json()
    assert json_data['status'] == 'mapping_required'
    assert 'Model' in json_data['missing']
    assert 'WrongHeader1' in json_data['headers']
