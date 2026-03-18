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


# Run at module load (idempotent)
init_db()
bootstrap_admin()

# Ensure upload directory exists
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
CONTRACTS_FILE = 'contracts.csv'
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'history.json')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Store session data temporarily
session_data_store = {}

SESSION_MAX_AGE_HOURS = 24

def cleanup_old_sessions():
    """Delete sessions older than SESSION_MAX_AGE_HOURS and their processed files."""
    cutoff = datetime.now().timestamp() - SESSION_MAX_AGE_HOURS * 3600
    stale = [sid for sid, s in session_data_store.items()
             if s['timestamp'].timestamp() < cutoff]
    for sid in stale:
        for suffix in ('_invoice_details.csv', '_invoice_format.csv', '_report.pdf'):
            path = os.path.join(PROCESSED_FOLDER, sid + suffix)
            try:
                os.remove(path)
            except OSError:
                pass
        del session_data_store[sid]
    if stale:
        print(f"[OK] Cleaned up {len(stale)} old session(s)")

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
    """Persist summary to history.json if save_flag is True."""
    if not save_flag:
        return

    # Load existing history
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []

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

    entry = {
        'id': session_id,
        'saved_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'month_label': month_label,
        'date_range_raw': date_range_raw,
        'total_bw_pages': total_bw,
        'total_color_pages': total_color,
        'total_billable_pages': total_billable,
        'total_revenue_czk': round(total_revenue, 2),
        'org_breakdown': org_breakdown,
    }

    history.append(entry)

    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


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

                missing = calculator.validate_columns(csv_data)
                if missing:
                    preview = ', '.join(missing[:3]) + (f' … (+{len(missing)-3})' if len(missing) > 3 else '')
                    warnings.append(f"{filename}: chybějící sloupce — {preview}")

                override = customer_names.get(file.filename) or customer_names.get(filename)
                invoice_data = calculator.calculate_billable_volumes(csv_data, filename, override)
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
    session_data_store[session_id] = {
        'all_data': all_invoice_data,
        'timestamp': datetime.now()
    }

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

    if session_id not in session_data_store:
        return jsonify({'error': 'Session expired or invalid'})

    all_data = session_data_store[session_id]['all_data']

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
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception:
            history = []

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
    if not os.path.exists(HISTORY_FILE):
        return jsonify({'success': False})
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
        history = [e for e in history if e['id'] != entry_id]
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
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
