# Local setup (no Docker)

## Prerequisites

1. **PostgreSQL** – Install and run on `localhost:5432`
   - Windows: [PostgreSQL installer](https://www.postgresql.org/download/windows/)
   - Or: `winget install PostgreSQL.PostgreSQL`
   - Create database `postgres` (or set `DATABASE_URL` in `backend/.env`)

2. **Python 3.10+** – Backend and worker
   ```powershell
   cd backend
   pip install -r requirements.txt
   ```

3. **Node.js 18+** – Frontend
   ```powershell
   cd frontend
   npm install
   ```

## Configuration

- Copy `backend/.env.example` to `backend/.env`
- Default: `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres`
- Adjust if your Postgres user/password differs

## Start all services

From project root:

```powershell
.\start.ps1
```

This opens separate windows for:
1. **Backend** – http://localhost:8000 (API at /api, docs at /docs)
2. **Upload worker** – Processes video queue
3. **Frontend** – http://localhost:5182

Or start manually:

```powershell
# Terminal 1 – backend
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 – worker
cd backend
python run_upload_worker.py

# Terminal 3 – frontend
cd frontend
npm run dev
```
