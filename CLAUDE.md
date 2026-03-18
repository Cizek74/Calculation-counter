# CLAUDE.md — Printing Volume Calculator

## Project Overview

A Flask web application that processes printer system CSV exports to calculate billable print volumes and generate invoice-ready reports with contract tracking. Protected by username/password authentication with role-based access (admin / viewer). Includes a persistent dashboard with month-over-month trend charts and per-report file downloads.

## Running the App

```bash
python app.py
# Opens at http://localhost:5000
```

Or use the Windows launcher: `start_invoice_calculator.bat`

Environment variables (optional):
```bat
set ADMIN_USER=admin
set ADMIN_PASSWORD=MySecretPassword
set SECRET_KEY=some-random-key
set PORT=5000
set FLASK_DEBUG=1        # enables debug mode (dev only)
```

In production the app uses **waitress** (4 threads). Falls back to Flask dev server if waitress is not installed.

## Installing Dependencies

```bash
python -m pip install Flask Werkzeug flask-bcrypt waitress reportlab python-dateutil
```

> Note: `requirements.txt` is incomplete — all packages above are required.

## Architecture

### Backend: `app.py` + supporting modules

`app.py` is the Flask entry point. Business logic is split into:

| Module | Purpose |
|--------|---------|
| `calculator.py` | `PrintingVolumeCalculator` — reads CSVs, calculates billable pages |
| `contracts.py` | `ContractManager` — loads `contracts.csv`, status/cost calculations |
| `reports.py` | `save_to_csv`, `create_invoice_format`, `generate_summary`, `generate_pdf_report` |
| `pdf_fonts.py` | Font registration for ReportLab; exposes `_FONT_REG`, `_FONT_BOLD`, `_FONT_MONO`, `_PDF_FONTS_OK` |

### Authentication & Users

- Users stored in **SQLite** (`users.db`), table `users` (id, username, password_hash, role, is_active, created_at)
- Passwords hashed with **flask-bcrypt**
- Roles: `admin` (full access) and `viewer` (read-only — cannot upload or generate reports)
- `@login_required` — redirects to `/login` if not logged in
- `@admin_required` — returns 403 JSON if role is not `admin`
- Default admin bootstrapped from `ADMIN_USER` / `ADMIN_PASSWORD` env vars on first run
- Session stores `user_id`, `username`, `role` in Flask signed cookie

### Session management
- Upload session data is stored in `session_data_store` (in-memory dict, keyed by 8-char UUID)
- Sessions older than `SESSION_MAX_AGE_HOURS` (24h) are automatically deleted along with their processed files
- Cleanup runs on every new upload via `cleanup_old_sessions()`

### Flask routes

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET/POST | `/login` | — | Login page |
| GET | `/logout` | — | Clears session, redirects to login |
| GET | `/` | login | Main app (index.html) |
| POST | `/upload` | admin | Accept CSVs, return printer list + contract info + duplicate detection |
| POST | `/generate_report` | admin | Filter selected printers, save CSV + PDF, optionally save to history |
| GET | `/download/<session_id>/<file_type>` | login | Download individual file (`details`, `invoice`, `pdf`) |
| GET | `/download_all/<session_id>` | login | Download ZIP of all three output files |
| GET | `/dashboard` | login | Dashboard page |
| GET | `/api/dashboard/data` | login | Returns `history` array + `contract_stats` JSON |
| POST | `/history/delete/<entry_id>` | admin | Remove one entry from `history.json` |
| GET | `/contracts/list` | login | List all contracts |
| POST | `/contracts/add` | admin | Add a contract |
| POST | `/contracts/edit/<serial>` | admin | Update a contract |
| POST | `/contracts/delete/<serial>` | admin | Delete a contract |
| POST | `/contracts/reload` | admin | Reload contracts from CSV |
| GET | `/admin/users` | admin | User management page |
| POST | `/admin/users` | admin | Create a new user |
| POST | `/admin/users/<id>/toggle-active` | admin | Activate/deactivate user |
| POST | `/admin/users/<id>/reset-password` | admin | Reset user password |

### Frontend: `templates/index.html`
Single-page 4-step wizard in **Czech language**. Communicates with Flask via fetch/JSON. Includes a Dashboard link and logout button in the top-bar header. Step 2 panel has a "Uložit výsledky do dashboardu" checkbox (checked by default) above the generate button — uncheck for test runs.

Frontend JS is in `static/app.js`.

### Dashboard: `templates/dashboard.html`
Separate page at `/dashboard`. Loads data from `/api/dashboard/data`. Uses **Chart.js** (CDN) for charts. No extra npm/pip packages needed.

**Charts:**
- Monthly revenue line chart
- BW vs Color pages stacked bar chart
- Revenue by customer stacked bar chart (full width)

**History table columns:** Měsíc, Zákazníci, Tiskárny, ČB stránky, Barevné stránky, Tržby (Kč), Uloženo, Soubory (download buttons), delete button.

**Download buttons per history row** (added 2026-03):
- `file-text` icon → PDF report (`/download/<id>/pdf`)
- `table-2` icon → Invoice details CSV (`/download/<id>/details`)
- `receipt` icon → Invoice format CSV (`/download/<id>/invoice`)
- `archive` icon (primary/purple) → All files as ZIP (`/download_all/<id>`)
- Files are available for 24h after generation; if expired, a red toast notification is shown
- `downloadReport(sessionId, fileType)` JS function handles fetch + blob download + error toast
- `showToast(msg, type)` function renders a floating `.toast` div (auto-dismisses after 4s)

### Admin users page: `templates/admin_users.html`
Accessible at `/admin/users` (admin only). Lists all users with activate/deactivate toggle and password reset form. Create new user form at top of page.

## Key Business Logic

### Page multipliers (billable pages per physical sheet)
| Format | Simplex | Duplex |
|--------|---------|--------|
| A4, A5, A6, B5, Envelope, Other | 1 | 2 |
| A3, B4 | 2 | 4 |

### Customer identification
Customer name is extracted from the **CSV filename** (not file contents). Date suffixes and separators are stripped:
- `Firma ABC_20250101.csv` → `Firma ABC`
- `Location-Name.csv` → `Location Name`

### Duplicate serial number detection
After all files are processed, the upload route checks whether any `Serial_Number` appears in more than one source file. Duplicates are:
- Returned in the `duplicates` array in the JSON response
- Flagged with `is_duplicate: true` on each affected printer in `printer_list`
- Shown as a yellow warning banner above the printer table in the UI
- Highlighted with amber row background and ⚠ icon in the table

### Contract tracking (`contracts.csv`)
Required columns: `Serial_Number`, `Contract_Name`, `Customer_Location`, `Contract_Type`, `Start_Date`, `End_Date`, `Monthly_Fixed_Cost`, `BW_Cost_Per_Page`, `Color_Cost_Per_Page`, `Minimum_Monthly_Volume`, `Status`, `Notes`

Date formats accepted: `DD/MM/YY`, `DD/MM/YYYY`, `DD-MM-YYYY`, `YYYY-MM-DD`, `MM/DD/YYYY`

### Contract status colors
- **Green**: > 6 months remaining
- **Yellow**: 3–6 months
- **Orange**: ≤ 3 months
- **Red**: expired
- **Gray**: no contract data

### Months remaining calculation
Counts only **complete future months** starting from the 1st of next month. Does not count the current partial month.

### Dashboard history (`history.json`)
- Auto-created on first real report save; lives alongside `app.py`
- One entry per saved report; entries persist until manually deleted via dashboard UI
- `save_to_history` flag in the `/generate_report` POST body controls whether the result is persisted
- `month_label` is derived from the end date in `date_range_raw` using Czech month names
- `_save_to_history(session_id, summary, save_flag)` helper in `app.py` builds and appends each entry
- `_month_label_from_range()` parses the date range string (supports `YYYY-MM-DD HH:MM:SS` and other formats)

**history.json entry shape:**
```json
{
  "id": "<session_id>",
  "saved_at": "2025-10-31T15:30:45",
  "month_label": "Říjen 2025",
  "date_range_raw": "2025-09-30 10:09:00 - 2025-10-31 10:09:00",
  "total_bw_pages": 5420,
  "total_color_pages": 320,
  "total_billable_pages": 5740,
  "total_revenue_czk": 1842.50,
  "org_breakdown": [
    { "customer": "...", "bw_pages": 308, "color_pages": 0, "total_pages": 308, "revenue_czk": 73.92, "printer_count": 2 }
  ]
}
```

## Output Files (saved to `processed/`)

For each session (`{session_id}`):
- `{session_id}_invoice_details.csv` — one row per printer with billable BW/color/total pages
- `{session_id}_invoice_format.csv` — pivot table with printers as columns (invoice-ready)
- `{session_id}_report.pdf` — professional PDF summary with per-location breakdown

Sessions and their output files are auto-deleted after 24 hours on the next upload.

## File Structure

```
app.py                        # Flask routes + auth + history helpers
calculator.py                 # PrintingVolumeCalculator class
contracts.py                  # ContractManager class
reports.py                    # CSV/PDF generation functions
pdf_fonts.py                  # ReportLab font registration
users.db                      # SQLite user database (auto-created, not in git)
contracts.csv                 # Printer contract data (not in git)
history.json                  # Persistent dashboard history (auto-created, not in git)
requirements.txt              # Incomplete — see Installing Dependencies above
start_invoice_calculator.bat  # Windows launch script
templates/
  index.html                  # Czech-language single-page UI (4-step wizard)
  login.html                  # Username/password login page
  dashboard.html              # Dashboard: charts, history table, per-report downloads
  admin_users.html            # User management page (admin only)
static/
  app.js                      # All frontend JS for index.html
uploads/                      # Temporary file staging (auto-cleaned after processing)
processed/                    # Generated reports (CSV + PDF, auto-deleted after 24h)
```

## CSV Input Format

Input CSVs must contain these columns (among others):
- `Model`, `Serial Number`, `Date Range`
- `A4/Letter-1sided-B&W (Report Interval)`, `A4/Letter-2sided-Color (Report Interval)`, etc.
- Full set: A4, A3, A5, A6, B4/Legal, B5, Envelope, Other × 1sided/2sided × B&W/Color

## UI Design System

- Font: **Plus Jakarta Sans** (Google Fonts CDN)
- Icons: **Lucide** (unpkg CDN)
- CSS: **Tailwind CSS** (CDN, JIT)
- Dark navy base: `#080b1a` with radial gradient orbs (indigo/violet)
- Glassmorphism: `rgba(255,255,255,.04)` bg + `blur(24px)` backdrop-filter
- CSS variables: `--accent` (`#6366f1`), `--accent-2` (`#8b5cf6`), `--glass-bg`, `--glass-bdr`, `--text-hi/md/lo`
- Gradient buttons: `.btn-primary` (indigo→violet), `.btn-secondary` (glass), `.btn-danger` (red tint)
- Stat cards: `.sc-violet/blue/green/amber` with gradient backgrounds
- Language: Czech throughout all UI text

## Notes for Development

- Production server: **waitress** (`serve(app, host='0.0.0.0', port=port, threads=4)`)
- Debug mode enabled only when `FLASK_DEBUG=1` env var is set
- `app.secret_key` defaults to `'printing-volume-calculator-2025'` — override via `SECRET_KEY` env var for any shared environment
- Uploaded files are deleted immediately after processing (`os.remove`)
- `processed/` files are auto-deleted after 24 hours on the next upload
- Currency references in UI are CZK (Czech Koruna / Kč)
- Chart.js is loaded from CDN (`cdn.jsdelivr.net`) — no install needed
