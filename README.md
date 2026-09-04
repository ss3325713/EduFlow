# EduFlow Academy — Coaching Institute Management System

A modern, production-grade web application built with **Python (Flask)**, **SQLAlchemy**, **Bootstrap 5**, and **Chart.js** designed for coaching institutes, academies, and educational centers.

---

## Key Features

- **Multi-Portal Architecture**: Dedicated responsive web portals & dashboards for:
  - **Super Admin / Owner**: Full system analytics, financial collection charts, institute settings, audit logs, staff management.
  - **Administrator / Staff**: Admissions CRM, student registration, batch management, fee collection & receipt generation.
  - **Teacher / Faculty**: Workload tracker, batch student lists, bulk attendance marking, exam score entry, homework assignment, and study material uploads.
  - **Student**: Profile overview, attendance rate, fee dues, active homework, study resource downloads, and exam scorecards.
  - **Parent**: Multi-child linking, combined attendance percentage tracking, fee balances, and exam performance.
- **REST API Layer (`/api/v1/`)**: Mobile-ready token authentication endpoints for future Android / iOS application development.
- **Financial & Fee Management**: Customizable fee structures, partial/installment payments, receipt generation with printable CSS layout, and payment reversal auditing.
- **Admissions CRM Pipeline**: Track potential students through `New -> Contacted -> Interested -> Follow-up -> Converted` with 1-click student account creation.
- **Timetable Collision Engine**: Real-time validation preventing double-booking of teachers or batches during slot creation.

---

## Technology Stack

- **Backend**: Python 3.12, Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, PyJWT
- **Database**: SQLite (Development) / PostgreSQL / MySQL compatible via `DATABASE_URL`
- **Frontend**: HTML5, Modern CSS Design Tokens, Jinja2 Templates, Bootstrap 5, Chart.js, Bootstrap Icons
- **Testing**: pytest

---

## Quick Start & Local Setup

### 1. Prerequisites
Ensure Python 3.10+ is installed on your system.

### 2. Setup Environment & Install Dependencies
```bash
cd /home/sumit/.gemini/antigravity/scratch/eduflow_academy

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Initialize & Seed Database
Run the automated database seed script to populate sample classes, batches, fee structures, students, teachers, and demo accounts:

```bash
python seed.py
```

### 4. Demo Login Credentials
| Role | Username | Password |
| :--- | :--- | :--- |
| **Super Admin** | `admin` | `Admin@123` |
| **Staff Admin** | `staff1` | `Staff@123` |
| **Teacher** | `dr_smith` | `Teacher@123` |
| **Student** | `student1` | `Student@123` |
| **Parent** | `parent1` | `Parent@123` |

### 5. Launch Development Server
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

Run pytest to verify authentication, role permissions, batch capacity limits, and fee calculation logic:

```bash
PYTHONPATH=. pytest tests/
```

---

## Production Deployment Notes

1. Set `FLASK_ENV=production` in your environment variables.
2. Provide a strong `SECRET_KEY` and `JWT_SECRET_KEY`.
3. Configure PostgreSQL database:
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost:5432/eduflow_db"
   ```
4. Run Gunicorn or uWSGI behind Nginx:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:8000 "run:app"
   ```
