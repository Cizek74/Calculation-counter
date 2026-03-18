# Printing Volume Calculator - Gemini Context

This document provides essential context for interacting with the Printing Volume Calculator project. It complements the existing `CLAUDE.md` file, which contains detailed development guidelines and architecture notes.

## Project Overview

A Flask-based web application designed to process printer system CSV exports. It calculates billable print volumes (considering page multipliers for A3/A4 and duplex) and generates invoice-ready reports (CSV/PDF) with contract tracking.

- **Main Technologies:** Python 3, Flask, SQLite (Auth), ReportLab (PDF), Chart.js (Dashboard), Tailwind CSS (Frontend).
- **Target Users:** Administrators and Viewers (role-based access).
- **Primary Language:** Czech (UI and Reports).

## Building and Running

### Environment Setup
1. **Install Dependencies:**
   ```bash
   python -m pip install -r requirements.txt
   ```
   *Note: Ensure `waitress` is installed for production-like behavior.*

2. **Initialize Database:**
   The SQLite database (`users.db`) is automatically initialized on the first run.

3. **Environment Variables (Optional):**
   - `ADMIN_USER`: Initial admin username (default: `admin`).
   - `ADMIN_PASSWORD`: Initial admin password (default: `changeme`).
   - `SECRET_KEY`: Flask session secret.
   - `FLASK_DEBUG`: Set to `1` for development.
   - `DB_FILE`: Path to the SQLite DB.

### Running the Application
- **Development Server:**
  ```bash
  python app.py
  ```
- **Windows Launcher:**
  Execute `start_invoice_calculator.bat`.

## Key Commands

- **Testing:**
  ```bash
  pytest
  ```
- **Linting/Formatting:**
  No specific linter configured, but follow PEP 8 and existing styles in `app.py` and `calculator.py`.

## Architecture & Tech Stack

### Core Modules
| Module | Purpose |
| :--- | :--- |
| `app.py` | Entry point, routing, auth logic, session management, and history. |
| `calculator.py` | Core logic for parsing CSVs and calculating billable pages. |
| `contracts.py` | Management of printer contracts (loaded from `contracts.csv`). |
| `reports.py` | Generation of CSV outputs and ReportLab PDF documents. |
| `pdf_fonts.py` | Registration of fonts for PDF generation. |

### Data Storage
- **Users:** `users.db` (SQLite).
- **Contracts:** `contracts.csv` (Manual entry, primary key: Serial Number).
- **History:** `history.json` (Dashboard persistence).
- **Files:** `uploads/` (temp) and `processed/` (output, auto-deleted after 24h).

## Development Conventions

1. **Authentication:** All routes except `/login` and `/logout` require login. Admin-only routes use the `@admin_required` decorator.
2. **Business Logic:**
   - **Page Multipliers:** A3 is 2x A4; Duplex is 2x Simplex.
   - **Customer Identification:** Extracted from the CSV filename (highest priority: user override in UI).
3. **Session Management:** Processed data is stored in an in-memory `session_data_store` keyed by a UUID. Cleanup occurs every 24 hours.
4. **UI Design:** Uses Tailwind CSS via CDN and Glassmorphism aesthetics. Icons are provided by Lucide.

## Testing Strategy
- Tests are located in the `tests/` directory.
- `conftest.py` provides fixtures for an isolated temporary database and a logged-in admin client.
- Always run `pytest` before committing changes to ensure core logic and auth remain intact.

## Important Files
- `CLAUDE.md`: Primary developer guide (Architecture, Routes, UI specs).
- `app.py`: Main Flask application.
- `calculator.py`: Business logic for volume calculation.
- `templates/`: HTML templates (Czech language).
- `static/app.js`: Main frontend logic.
