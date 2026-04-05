# Jewel India ERP

A full-stack ERP system built for jewellery retail businesses. Covers manufacturing, inventory, sales, purchases, accounting, CRM, and more — with a per-company app licensing system.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.2, Django REST Framework |
| Frontend | React 18, Vite, Tailwind CSS, shadcn/ui |
| Database | PostgreSQL (production), SQLite (development) |
| Auth | Token-based authentication |
| Task Scheduling | APScheduler (CRM automation) |

---

## Project Structure

```
jewel-india-erp/
├── backend/          # Django project
│   ├── accounting/
│   ├── contacts/         # CRM & Contacts (ledger, occasions)
│   ├── goldrates/
│   ├── inventory/
│   ├── licensing/        # App subscription & licensing system
│   ├── manufacturing/
│   ├── mastersconfig/    # Setup masters (company, branch, retail, items, etc.)
│   ├── purchase/
│   ├── sales/
│   ├── userauth/
│   ├── ai_layer/
│   ├── jewel_test/       # Django settings & root URLs
│   ├── manage.py
│   └── requirements.txt
└── frontend/         # React + Vite app
    ├── src/
    │   ├── components/
    │   ├── config/
    │   ├── contexts/
    │   ├── services/
    │   └── App.jsx
    ├── package.json
    └── vite.config.js
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+ and Yarn
- PostgreSQL 14+ (for production) or SQLite (for local dev)

---

## Backend Setup

### 1. Create and activate a virtual environment

```bash
cd backend
python -m venv env

# Windows
env\Scripts\activate

# macOS / Linux
source env/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example below and save it as `backend/.env`:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (leave as-is for SQLite dev, or configure PostgreSQL)
# DB_ENGINE=django.db.backends.postgresql
# DB_NAME=jewel_india
# DB_USER=postgres
# DB_PASSWORD=yourpassword
# DB_HOST=localhost
# DB_PORT=5432

CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# Optional: OpenAI API key for AI Assistant module
OPENAI_API_KEY=
```

To generate a Django secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Create a superadmin user

```bash
python manage.py createsuperuser
```

### 6. Start the development server

```bash
python manage.py runserver
```

Backend runs at **http://127.0.0.1:8000**

---

## Frontend Setup

### 1. Install dependencies

```bash
cd frontend
yarn install
```

### 2. Start the development server

```bash
yarn dev
```

Frontend runs at **http://localhost:5173**

### 3. Configure the API base URL

On first load, the app will show a **Base URL** configuration screen. Enter:

```
http://127.0.0.1:8000/
```

---

## Django Admin

Access the vendor admin panel at **http://127.0.0.1:8000/admin/**

Log in with your superadmin credentials. From here you can:
- Manage company subscriptions and licensed apps
- View audit logs
- Configure system settings

---

## App Licensing

The ERP uses a per-app subscription model. Each company can be licensed for specific modules:

| Module | Code | Type |
|--------|------|------|
| Setup & Masters | `core_masters` | Core (always on) |
| CRM & Contacts | `crm` | Core (always on) |
| User & Access | `core_auth` | Core (always on) |
| Gold Rates | `gold_rates` | Core (always on) |
| CRM Occasions | `crm_occasions` | Add-on |
| Manufacturing | `manufacturing` | Add-on |
| Purchases | `purchases` | Add-on |
| Sales | `sales` | Core (always on) |
| Inventory | `inventory` | Add-on |
| Financial Accounting | `accounting` | Core (always on) |
| AI Assistant | `ai` | Add-on |

To configure for a new company: go to Django Admin → Company Subscriptions → add subscription and toggle the desired apps.

---

## Running Both Servers

Open two terminals:

**Terminal 1 — Backend:**
```bash
cd backend
env\Scripts\activate   # or source env/bin/activate on Mac/Linux
python manage.py runserver
```

**Terminal 2 — Frontend:**
```bash
cd frontend
yarn dev
```

---

## Production Build

```bash
# Frontend
cd frontend
yarn build
# Output is in frontend/dist/

# Backend — collect static files
cd backend
python manage.py collectstatic
```

For production deployment, run the backend with **Gunicorn** behind **Nginx** and serve the frontend `dist/` folder as static files.

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | Yes | `True` for dev, `False` for prod |
| `ALLOWED_HOSTS` | Yes | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | Yes | Allowed frontend origins |
| `DB_ENGINE` | No | Database engine (default: SQLite) |
| `DB_NAME` | No | Database name |
| `DB_USER` | No | Database user |
| `DB_PASSWORD` | No | Database password |
| `DB_HOST` | No | Database host |
| `DB_PORT` | No | Database port |
| `OPENAI_API_KEY` | No | OpenAI key for AI Assistant module |
