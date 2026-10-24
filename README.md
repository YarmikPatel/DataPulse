# ⚡ DataPulse — Data Quality & Pipeline Monitoring Platform

DataPulse is a full-stack web platform built for data engineers and analysts to inspect, profile, clean, and monitor datasets through automated data pipelines.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.14 / 3.12, Flask 3.x, Flask-SQLAlchemy, Flask-Login |
| **Data Engine** | Pandas, NumPy |
| **Database** | Supabase PostgreSQL (via transaction pooler port 6543) |
| **Audit Logging** | Google Sheets API (via Google Cloud Service Account) |
| **Frontend** | HTML5, CSS3, Bootstrap 5, JavaScript (ES6+), Chart.js |
| **Deployment** | Vercel Serverless Functions + GitHub |

---

## 🏗️ Architecture & Serverless Design

```
[Browser Client]  <== HTTPS ==>  [Vercel Serverless Flask App]
                                             |
                   +-------------------------+-------------------------+
                   |                                                   |
                   v (SQLAlchemy ORM)                                  v (HTTPS Google API)
       [Supabase PostgreSQL]                                   [Google Sheets Audit]
        - Users & Auth                                         - Timestamp
        - Datasets (Raw CSV in DB)                             - Event Type
        - Pipeline History                                     - Safe Metadata (No secrets)
        - Activity Logs
```

### Why Store CSV Data in Supabase PostgreSQL?
Vercel serverless functions have a read-only filesystem (except temporary `/tmp`, which is wiped as soon as an execution ends). By storing dataset contents directly inside PostgreSQL `TEXT` columns, DataPulse achieves **100% durable file retention with zero additional AWS S3 cloud storage costs**.

---

## 🐍 Python Version Compatibility

* **Recommended Versions:** **Python 3.14** or **Python 3.12** (Officially supported by Vercel serverless runtimes).
* **Important Note on Python 3.15:** If your system default is Python 3.15, note that it is an unreleased preview version not yet supported by Vercel or many C-extension wheels. Always use the project virtual environment configured with Python 3.14.

---

## 🚀 Quickstart Guide (Local Development)

### 1. Create and Activate Virtual Environment

Open PowerShell in the project directory:

```powershell
# Using Python 3.14:
& "C:\Users\kansa\AppData\Local\Programs\Python\Python314\python.exe" -m venv venv

# Activate the virtual environment:
.\venv\Scripts\Activate.ps1
```

*(If PowerShell script execution is restricted, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

### 2. Install Project Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:

```powershell
cp .env.example .env
```

Open `.env` in your text editor and configure your settings:

```ini
SECRET_KEY=your-random-secret-key-here
DATABASE_URL=postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

> **Offline Mode Note:** If `DATABASE_URL` is left empty, DataPulse automatically defaults to a local SQLite database (`datapulse_local.db`) so you can code and test offline.

### 4. Verify Database Connection

Run the built-in connection diagnostic:

```powershell
python test_db_connection.py
```

### 5. Launch Development Server

```powershell
python run.py
```

Open your browser at **http://127.0.0.1:5000**.
Check the health status API at **http://127.0.0.1:5000/api/health**.

---

## 🗄️ Database Schema Overview

1. **`users`**: User registration, authentication, and secure password hashes (`scrypt`).
2. **`datasets`**: Uploaded CSV metadata, row/col counts, and in-database raw CSV storage.
3. **`profiling_reports`**: Missing value statistics, duplicate counts, and health scores stored as JSON.
4. **`pipeline_runs`**: Execution history, duration in ms, rows dropped/imputed, and cleaned CSV text.
5. **`activity_logs`**: Durable audit log tracking actions with Google Sheets sync flags.

---

## ☁️ Vercel Deployment Blueprint

1. Push your repository to **GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: DataPulse Phase 1"
   git remote add origin https://github.com/your-username/datapulse.git
   git push -u origin main
   ```
2. Import the repository into **Vercel**:
   - Vercel automatically detects `vercel.json` and routes all requests to `api/index.py`.
3. Add Environment Variables in Vercel Project Settings:
   - `SECRET_KEY`
   - `DATABASE_URL` (Supabase transaction pooler port 6543)
   - `GOOGLE_SHEET_ID`
   - `GOOGLE_SERVICE_ACCOUNT_JSON`

---

## 🗺️ Project Development Roadmap

- [x] **Phase 1: Project Setup & Database Foundations** (Complete)
- [x] **Phase 2: Authentication & Modern Dashboard UI** (Complete)
- [ ] **Phase 3: Activity Logging & Google Sheets Sync**
- [ ] **Phase 4: CSV Ingestion & Interactive Profiler**
- [ ] **Phase 5: Cleaning Engine & Streaming CSV Downloads**
- [ ] **Phase 6: Pipeline Monitoring & Real-time Metrics**
- [ ] **Phase 7: Testing, Documentation & Vercel Deployment**
