# EduFlow Academy — Coaching Institute Management System

A modern, production-grade web application built with **Python (Flask)**, **SQLAlchemy**, **Bootstrap 5**, and **Chart.js** designed for coaching institutes, academies, and educational centers.

---

## Key Features

- **Multi-Portal Architecture**: Dedicated responsive web portals & dashboards for:
  - **Super Admin / Owner**: Full system analytics, financial collection charts, institute settings, audit logs, staff management.
  - **Administrator / Staff**: Admissions CRM, student registration, batch management, fee collection & receipt generation.
  - **Teacher / Faculty**: Workload tracker, batch student lists, bulk attendance marking, exam score entry, homework assignment, subject announcements, and study material uploads.
  - **Student**: Profile overview, attendance rate, fee status, active homework, batch-isolated study resource downloads, and individual exam performance scorecards.
  - **Parent**: Multi-child linking, combined attendance percentage tracking, fee balances, and exam performance.
- **Account Management & Soft Deletion**: Two-stage account management where accounts can be soft-disabled (blocking login while preserving academic records) before optional permanent deletion.
- **Regional & Currency Customization**: Dynamic site-wide currency formatting filter (`| currency`) with automatic timezone and country preset mapping.
- **Exam Performance & PDF Generation**: Comprehensive student scorecards featuring comparative performance bar charts (Student vs Class Highest vs Average) and printable PDF reports.
- **REST API Layer (`/api/v1/`)**: Mobile-ready token authentication endpoints for future Android / iOS application development.
- **Financial & Fee Management**: Customizable fee structures, partial/installment payments, receipt generation with printable CSS layout, and payment reversal auditing.
- **Admissions CRM Pipeline**: Track potential students through `New -> Contacted -> Interested -> Follow-up -> Converted` with 1-click student account creation.
- **Timetable Collision Engine**: Real-time validation preventing double-booking of teachers or batches during slot creation.

---

## Technology Stack

- **Backend**: Python 3.10+, Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, PyJWT
- **Database**: SQLite (Development) / PostgreSQL / MySQL compatible via `DATABASE_URL`
- **Frontend**: HTML5, Modern CSS Design Tokens, Jinja2 Templates, Bootstrap 5, Chart.js, Bootstrap Icons
- **Testing**: pytest

---

## Quick Start & Local Setup

### 1. Clone Repository & Setup Environment
```bash
git clone https://github.com/ss3325713/EduFlow.git
cd EduFlow

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Initialize & Seed Database
Run the automated database seed script to initialize tables and populate sample classes, batches, fee structures, and initial test accounts:

```bash
python seed.py
```

> **Note**: Default credentials for seeded test accounts are generated securely by `seed.py`. Refer to `seed.py` when initializing your local environment.

### 3. Launch Development Server
```bash
python run.py
```
Open your browser at `http://127.0.0.1:5000` to log in.

---

## REST API Endpoints (`/api/v1/`)

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/v1/auth/login` | `POST` | Authenticates user & returns JWT Token |
| `/api/v1/students` | `GET` | Returns list of active students |
| `/api/v1/teachers` | `GET` | Returns faculty list |
| `/api/v1/batches` | `GET` | Returns batch directory |
| `/api/v1/attendance` | `GET / POST` | Fetch or submit attendance records |
| `/api/v1/announcements` | `GET` | Returns notice feed |

---

## Test Suite Execution

Run `pytest` to verify authentication, role permissions, batch capacity limits, and fee calculation logic:

```bash
PYTHONPATH=. pytest tests/
```

---

## Production Deployment Notes

1. Set `FLASK_ENV=production` in your environment variables.
2. Provide a strong `SECRET_KEY` and `JWT_SECRET_KEY`.
3. Configure database URL:
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost:5432/eduflow_db"
   ```
4. Run Gunicorn or uWSGI behind Nginx:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:8000 "run:app"
   ```

---

## License

This project is licensed under the MIT License.
