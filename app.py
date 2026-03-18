from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
from functools import wraps
import csv
import json
from datetime import datetime
import os
import zipfile
from io import BytesIO
import uuid
import re
import sqlite3
from flask_bcrypt import Bcrypt

from pdf_fonts import _FONT_REG, _FONT_BOLD, _FONT_MONO, _PDF_FONTS_OK
from contracts import ContractManager
from calculator import PrintingVolumeCalculator
from reports import save_to_csv, create_invoice_format, generate_summary, generate_pdf_report

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'printing-volume-calculator-2025')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

bcrypt = Bcrypt(app)

DB_FILE = os.environ.get(
    'DB_FILE',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')
)


def init_db():
    """Create users, history and sessions tables if they don't exist."""
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
        conn.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id                    TEXT PRIMARY KEY,
                saved_at              TEXT NOT NULL,
                month_label           TEXT NOT NULL,
                date_range_raw        TEXT,
                total_bw_pages        INTEGER,
                total_color_pages     INTEGER,
                total_billable_pages  INTEGER,
                total_revenue_czk     REAL,
                org_breakdown_json    TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                data_json   TEXT NOT NULL,
                created_at  REAL NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS column_mappings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_name TEXT UNIQUE NOT NULL,
                mapping_json TEXT NOT NULL,
                created_at   TEXT NOT NULL
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
            try:
                conn.execute(
                    'INSERT INTO users (username, password_hash, role, is_active, created_at) '
                    'VALUES (?, ?, ?, 1, ?)',
                    (admin_user, pw_hash, 'admin',
                     datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
                )
                conn.commit()
                print(f'[OK] Bootstrap admin created: {admin_user}')
            except sqlite3.IntegrityError:
                pass  # Another worker already inserted the admin row; safe to ignore


def migrate_history_json():
    """One-time migration from history.json to history table."""
    history_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'history.json')
    if not os.path.exists(history_file):
        return

    with sqlite3.connect(DB_FILE) as conn:
        # Only migrate if history table is empty
        count = conn.execute('SELECT COUNT(*) FROM history').fetchone()[0]
        if count > 0:
            return

        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            for entry in history_data:
                conn.execute('''
                    INSERT INTO history (
                        id, saved_at, month_label, date_range_raw,
                        total_bw_pages, total_color_pages, total_billable_pages,
                        total_revenue_czk, org_breakdown_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    entry['id'], entry['saved_at'], entry['month_label'], entry['date_range_raw'],
                    entry['total_bw_pages'], entry['total_color_pages'], entry['total_billable_pages'],
                    entry['total_revenue_czk'], json.dumps(entry['org_breakdown'], ensure_ascii=False)
                ))
            conn.commit()
            print(f'[OK] Migrated {len(history_data)} entries from history.json to DB')
            
            # Optional: rename instead of delete for safety
            os.rename(history_file, history_file + '.bak')
        except Exception as e:
            print(f'[ERROR] History migration failed: {str(e)}')


# Run at module load (idempotent)
init_db()
bootstrap_admin()
migrate_history_json()

# Ensure upload directory exists
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
CONTRACTS_FILE = 'contracts.csv'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

SESSION_MAX_AGE_HOURS = 24

def cleanup_old_sessions():
    """Delete sessions older than SESSION_MAX_AGE_HOURS and their processed files."""
    cutoff = datetime.now().timestamp() - SESSION_MAX_AGE_HOURS * 3600
    
    with sqlite3.connect(DB_FILE) as conn:
        stale = conn.execute('SELECT id FROM sessions WHERE created_at < ?', (cutoff,)).fetchall()
        stale_ids = [row[0] for row in stale]
        
        for sid in stale_ids:
            for suffix in ('_invoice_details.csv', '_invoice_format.csv', '_report.pdf'):
                path = os.path.join(PROCESSED_FOLDER, sid + suffix)
                try:
                    os.remove(path)
                except OSError:
                    pass
        
        if stale_ids:
            conn.execute('DELETE FROM sessions WHERE created_at < ?', (cutoff,))
            conn.commit()
            print(f"[OK] Cleaned up {len(stale_ids)} old session(s) from DB")

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

# Initialize components
calculator = PrintingVolumeCalculator()
contract_manager = ContractManager(CONTRACTS_FILE)

CZECH_MONTHS = ["Leden","Únor","Březen","Duben","Květen","Červen",
                "Červenec","Srpen","Září","Říjen","Listopad","Prosinec"]

def _month_label_from_range(date_range_str):
    """Extract month label (Czech) from a date range string like '2025-09-30 ... - 2025-10-31 ...'"""
    try:
        # Take the last date in the range (after ' - ')
        parts = date_range_str.split(' - ')
        end_part = parts[-1].strip()
        # Try common formats
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d.%m.%Y %H:%M:%S', '%d.%m.%Y', '%d/%m/%Y'):
            try:
                dt = datetime.strptime(end_part, fmt)
                return f"{CZECH_MONTHS[dt.month - 1]} {dt.year}"
            except ValueError:
                continue
        # Fallback: first 10 chars as YYYY-MM-DD
        dt = datetime.strptime(end_part[:10], '%Y-%m-%d')
        return f"{CZECH_MONTHS[dt.month - 1]} {dt.year}"
    except Exception:
        return date_range_str


def _save_to_history(session_id, summary, save_flag):
    """Persist summary to history table in DB if save_flag is True."""
    if not save_flag:
        return

    # Pick date_range_raw from first customer detail
    date_range_raw = ''
    if summary.get('customer_details'):
        date_range_raw = summary['customer_details'][0].get('date_range', '')

    month_label = _month_label_from_range(date_range_raw) if date_range_raw else ''

    # Compute totals
    total_bw = summary.get('total_bw_all', 0)
    total_color = summary.get('total_color_all', 0)
    total_billable = total_bw + total_color

    total_revenue = 0.0
    org_breakdown = []

    for customer in summary.get('customer_details', []):
        cust_bw = customer.get('total_bw_billable', 0)
        cust_color = customer.get('total_color_billable', 0)
        cust_revenue = 0.0
        printer_count = customer.get('printers', 0)

        for machine in customer.get('machines', []):
            ci = machine.get('contract_info', {})
            if ci and ci.get('has_contract'):
                cust_revenue += ci.get('monthly_cost', 0) or 0

        total_revenue += cust_revenue
        org_breakdown.append({
            'customer': customer.get('customer', ''),
            'bw_pages': cust_bw,
            'color_pages': cust_color,
            'total_pages': cust_bw + cust_color,
            'revenue_czk': round(cust_revenue, 2),
            'printer_count': printer_count,
        })

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''
            INSERT INTO history (
                id, saved_at, month_label, date_range_raw,
                total_bw_pages, total_color_pages, total_billable_pages,
                total_revenue_czk, org_breakdown_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session_id,
            datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            month_label,
            date_range_raw,
            total_bw,
            total_color,
            total_billable,
            round(total_revenue, 2),
            json.dumps(org_breakdown, ensure_ascii=False)
        ))
        conn.commit()


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

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html',
                           current_role=session.get('role', 'viewer'),
                           current_username=session.get('username', ''))

@app.route('/upload', methods=['POST'])
@admin_required
def upload_files():
    cleanup_old_sessions()

    if 'files' not in request.files:
        return jsonify({'error': 'No files selected'})

    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'})

    # Optional per-file customer name overrides sent as JSON from the frontend
    try:
        customer_names = json.loads(request.form.get('customer_names', '{}'))
    except (ValueError, TypeError):
        customer_names = {}

    # Optional column mapping
    try:
        column_mapping = json.loads(request.form.get('column_mapping', '{}'))
    except (ValueError, TypeError):
        column_mapping = {}

    all_invoice_data = []
    errors = []
    warnings = []
    processed_files = []

    for file in files:
        if file and file.filename.endswith('.csv'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            try:
                csv_data, error = calculator.load_csv_data(filepath)
                if error:
                    errors.append(f"{filename}: {error}")
                    continue

                missing = calculator.validate_columns(csv_data, column_mapping)
                if missing:
                    # If this is the first file and no mapping was provided, 
                    # we might want to ask for mapping immediately.
                    # For simplicity, we only trigger mapping UI if it's the ONLY file 
                    # or if the user explicitly wants to map.
                    # But the requirement is to handle missing columns gracefully.
                    if len(files) == 1 or not all_invoice_data:
                        headers = list(csv_data[0].keys()) if csv_data else []
                        return jsonify({
                            'status': 'mapping_required',
                            'missing': missing,
                            'headers': headers,
                            'filename': filename,
                            'expected': calculator.EXPECTED_COLUMNS
                        })
                    
                    preview = ', '.join(missing[:3]) + (f' … (+{len(missing)-3})' if len(missing) > 3 else '')
                    warnings.append(f"{filename}: chybějící sloupce — {preview}")

                override = customer_names.get(file.filename) or customer_names.get(filename)
                invoice_data = calculator.calculate_billable_volumes(csv_data, filename, override, column_mapping)
                all_invoice_data.extend(invoice_data)
                processed_files.append(filename)

            except Exception as e:
                errors.append(f"{filename}: {str(e)}")
            finally:
                try:
                    os.remove(filepath)
                except OSError:
                    pass

    if not all_invoice_data:
        return jsonify({'error': 'No valid CSV files processed', 'details': errors})

    # Detect duplicate serial numbers that appear in more than one source file
    serial_sources = {}
    for record in all_invoice_data:
        serial = record['Serial_Number']
        source = record['Source_File']
        if serial not in serial_sources:
            serial_sources[serial] = {'sources': [], 'model': record['Printer_Model'], 'customers': []}
        if source not in serial_sources[serial]['sources']:
            serial_sources[serial]['sources'].append(source)
        customer = record['Customer']
        if customer not in serial_sources[serial]['customers']:
            serial_sources[serial]['customers'].append(customer)

    duplicates = [
        {'serial': s, 'model': info['model'], 'sources': info['sources'], 'customers': info['customers']}
        for s, info in serial_sources.items() if len(info['sources']) > 1
    ]
    duplicate_serials = {d['serial'] for d in duplicates}

    # Store data temporarily for filtering
    session_id = str(uuid.uuid4())[:8]
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            'INSERT INTO sessions (id, data_json, created_at) VALUES (?, ?, ?)',
            (session_id, json.dumps(all_invoice_data, ensure_ascii=False), datetime.now().timestamp())
        )
        conn.commit()

    # Return printer list for selection WITH CONTRACT INFO
    printer_list = []
    for record in all_invoice_data:
        serial = record['Serial_Number']
        contract = contract_manager.get_contract(serial)

        printer_info = {
            'customer': record['Customer'],
            'model': record['Printer_Model'],
            'serial': serial,
            'bw_pages': record['Billable_BW_Pages'],
            'color_pages': record['Billable_Color_Pages'],
            'total_pages': record['Total_Billable_Pages'],
            'date_range': record['Date_Range'],
            'has_contract': contract is not None,
            'is_duplicate': serial in duplicate_serials,
            'source_file': record['Source_File']
        }

        if contract:
            months_remaining = contract_manager.calculate_months_remaining(contract['end_date'])
            cost_info = contract_manager.calculate_monthly_cost(
                contract,
                record['Billable_BW_Pages'],
                record['Billable_Color_Pages']
            )

            printer_info.update({
                'contract_name': contract['contract_name'],
                'contract_type': contract['contract_type'],
                'contract_status': contract['status'],
                'months_remaining': months_remaining,
                'status_color': contract_manager.get_contract_status_color(months_remaining),
                'end_date': contract['end_date'],
                'monthly_cost': cost_info['total_cost'] if cost_info else 0,
                'fixed_cost': cost_info['fixed_cost'] if cost_info else 0,
                'page_cost': cost_info['page_cost'] if cost_info else 0
            })
        else:
            printer_info.update({
                'contract_name': 'No Contract',
                'contract_type': 'N/A',
                'contract_status': 'N/A',
                'months_remaining': None,
                'status_color': 'gray',
                'end_date': 'N/A',
                'monthly_cost': 0,
                'fixed_cost': 0,
                'page_cost': 0
            })

        printer_list.append(printer_info)

    return jsonify({
        'success': True,
        'files_processed': len(processed_files),
        'session_id': session_id,
        'printer_list': printer_list,
        'errors': errors,
        'warnings': warnings,
        'processed_files': processed_files,
        'duplicates': duplicates
    })

@app.route('/generate_report', methods=['POST'])
@admin_required
def generate_report():
    data = request.json
    session_id = data.get('session_id')
    selected_serials = data.get('selected_printers', [])
    save_to_history = data.get('save_to_history', False)

    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute('SELECT data_json FROM sessions WHERE id = ?', (session_id,)).fetchone()
    
    if not row:
        return jsonify({'error': 'Session expired or invalid'})

    all_data = json.loads(row[0])

    # Filter data based on selected serial numbers
    if selected_serials:
        filtered_data = [r for r in all_data if r['Serial_Number'] in selected_serials]
    else:
        filtered_data = all_data

    if not filtered_data:
        return jsonify({'error': 'No printers selected'})

    # Generate reports
    summary = generate_summary(filtered_data)
    invoice_format_data = create_invoice_format(filtered_data)

    # ADD CONTRACT INFO TO SUMMARY
    for customer in summary['customer_details']:
        for machine in customer['machines']:
            serial = machine['serial']
            contract = contract_manager.get_contract(serial)

            if contract:
                months_remaining = contract_manager.calculate_months_remaining(contract['end_date'])
                cost_info = contract_manager.calculate_monthly_cost(
                    contract,
                    machine['bw_billable'],
                    machine['color_billable']
                )

                machine['contract_info'] = {
                    'has_contract': True,
                    'contract_name': contract['contract_name'],
                    'contract_type': contract['contract_type'],
                    'contract_status': contract['status'],
                    'start_date': contract['start_date'],
                    'end_date': contract['end_date'],
                    'months_remaining': months_remaining,
                    'status_color': contract_manager.get_contract_status_color(months_remaining),
                    'monthly_cost': cost_info['total_cost'] if cost_info else 0,
                    'fixed_cost': cost_info['fixed_cost'] if cost_info else 0,
                    'page_cost': cost_info['page_cost'] if cost_info else 0
                }
            else:
                machine['contract_info'] = {
                    'has_contract': False,
                    'contract_name': 'No Contract',
                    'contract_type': 'N/A',
                    'contract_status': 'N/A',
                    'start_date': 'N/A',
                    'end_date': 'N/A',
                    'months_remaining': None,
                    'status_color': 'gray',
                    'monthly_cost': 0,
                    'fixed_cost': 0,
                    'page_cost': 0
                }

    # Save files
    detail_file = os.path.join(PROCESSED_FOLDER, f'{session_id}_invoice_details.csv')
    invoice_file = os.path.join(PROCESSED_FOLDER, f'{session_id}_invoice_format.csv')
    pdf_file = os.path.join(PROCESSED_FOLDER, f'{session_id}_report.pdf')

    save_to_csv(filtered_data, detail_file)
    save_to_csv(invoice_format_data, invoice_file)
    generate_pdf_report(summary, pdf_file)

    _save_to_history(session_id, summary, save_to_history)

    return jsonify({
        'success': True,
        'summary': summary,
        'session_id': session_id
    })

@app.route('/download/<session_id>/<file_type>')
@login_required
def download_file(session_id, file_type):
    if not re.match(r'^[0-9a-f]{8}$', session_id):
        return jsonify({'error': 'Invalid session ID'}), 400
    if file_type == 'details':
        filename = f'{session_id}_invoice_details.csv'
    elif file_type == 'invoice':
        filename = f'{session_id}_invoice_format.csv'
    elif file_type == 'pdf':
        filename = f'{session_id}_report.pdf'
    else:
        return "Invalid file type", 400

    filepath = os.path.join(PROCESSED_FOLDER, filename)
    if not os.path.exists(filepath):
        return "File not found", 404

    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/download_all/<session_id>')
@login_required
def download_all(session_id):
    if not re.match(r'^[0-9a-f]{8}$', session_id):
        return jsonify({'error': 'Invalid session ID'}), 400
    detail_file = os.path.join(PROCESSED_FOLDER, f'{session_id}_invoice_details.csv')
    invoice_file = os.path.join(PROCESSED_FOLDER, f'{session_id}_invoice_format.csv')
    pdf_file = os.path.join(PROCESSED_FOLDER, f'{session_id}_report.pdf')

    files_to_zip = []
    if os.path.exists(detail_file):
        files_to_zip.append((detail_file, f'invoice_details_{session_id}.csv'))
    if os.path.exists(invoice_file):
        files_to_zip.append((invoice_file, f'invoice_format_{session_id}.csv'))
    if os.path.exists(pdf_file):
        files_to_zip.append((pdf_file, f'report_{session_id}.pdf'))

    if not files_to_zip:
        return "Files not found", 404

    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path, zip_name in files_to_zip:
            zf.write(file_path, zip_name)

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'invoice_data_{session_id}.zip'
    )

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html',
                           current_role=session.get('role', 'viewer'),
                           current_username=session.get('username', ''))


@app.route('/api/dashboard/data')
@login_required
def dashboard_data():
    history = []
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute('''
            SELECT id, saved_at, month_label, date_range_raw,
                   total_bw_pages, total_color_pages, total_billable_pages,
                   total_revenue_czk, org_breakdown_json
            FROM history ORDER BY saved_at DESC
        ''').fetchall()
    
    for r in rows:
        history.append({
            'id': r[0],
            'saved_at': r[1],
            'month_label': r[2],
            'date_range_raw': r[3],
            'total_bw_pages': r[4],
            'total_color_pages': r[5],
            'total_billable_pages': r[6],
            'total_revenue_czk': r[7],
            'org_breakdown': json.loads(r[8])
        })

    contracts = contract_manager.get_all_contracts()
    active = [c for c in contracts if c.get('status') == 'Active']
    expiring_soon = [c for c in active if c.get('status_color') in ('orange', 'red')]

    return jsonify({
        'history': history,
        'contract_stats': {
            'total_active': len(active),
            'expiring_soon': len(expiring_soon),
        }
    })


@app.route('/history/delete/<entry_id>', methods=['POST'])
@admin_required
def history_delete(entry_id):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute('DELETE FROM history WHERE id = ?', (entry_id,))
            conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/contracts/list')
@login_required
def contracts_list():
    return jsonify({'contracts': contract_manager.get_all_contracts()})

@app.route('/contracts/add', methods=['POST'])
@admin_required
def contracts_add():
    data = request.get_json()
    try:
        contract_manager.add_contract(data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/contracts/edit/<serial>', methods=['POST'])
@admin_required
def contracts_edit(serial):
    data = request.get_json()
    try:
        contract_manager.update_contract(serial, data)
        return jsonify({'success': True})
    except (KeyError, ValueError) as e:
        return jsonify({'error': str(e)}), 400

@app.route('/contracts/delete/<serial>', methods=['POST'])
@admin_required
def contracts_delete(serial):
    try:
        contract_manager.delete_contract(serial)
        return jsonify({'success': True})
    except KeyError as e:
        return jsonify({'error': str(e)}), 404

@app.route('/contracts/reload', methods=['POST'])
@admin_required
def contracts_reload():
    contract_manager.reload()
    return jsonify({'success': True, 'count': len(contract_manager.contracts)})

# ── Column Mappings ──────────────────────────────────────────────────────────

@app.route('/api/mappings', methods=['GET'])
@login_required
def get_mappings():
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            'SELECT id, profile_name, mapping_json, created_at FROM column_mappings ORDER BY profile_name'
        ).fetchall()
    return jsonify({
        'mappings': [
            {'id': r[0], 'profile_name': r[1], 'mapping_json': json.loads(r[2]), 'created_at': r[3]}
            for r in rows
        ]
    })

@app.route('/api/mappings/save', methods=['POST'])
@admin_required
def save_mapping():
    data = request.json
    profile_name = data.get('profile_name', '').strip()
    mapping_json = data.get('mapping')
    
    if not profile_name or not mapping_json:
        return jsonify({'error': 'Name and mapping data are required'}), 400
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                'INSERT INTO column_mappings (profile_name, mapping_json, created_at) '
                'VALUES (?, ?, ?)',
                (profile_name, json.dumps(mapping_json), datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
            )
            conn.commit()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'error': f'Mapping profile "{profile_name}" already exists'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/mappings/delete/<int:mapping_id>', methods=['POST'])
@admin_required
def delete_mapping(mapping_id):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute('DELETE FROM column_mappings WHERE id = ?', (mapping_id,))
            conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    print("Kalkulacka tisku — Printing Volume Calculator")
    print("-" * 50)
    if debug:
        print(f"[DEV] http://localhost:{port}")
        app.run(debug=True, host='0.0.0.0', port=port)
    else:
        try:
            from waitress import serve
            import socket
            local_ip = socket.gethostbyname(socket.gethostname())
            print(f"[OK] http://localhost:{port}")
            print(f"[OK] http://{local_ip}:{port}  (sit)")
            print("Ukoncete pomoci Ctrl+C")
            print("-" * 50)
            serve(app, host='0.0.0.0', port=port, threads=4)
        except ImportError:
            print("[WARN] waitress neni nainstalovan — pouzivam vyvojovy server")
            print(f"[OK] http://localhost:{port}")
            app.run(debug=False, host='0.0.0.0', port=port)
