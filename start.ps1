# Start Parking Enforcement - Local setup (no Docker)
# Prerequisites: PostgreSQL running on localhost:5432, Python, Node.js

Write-Host "=== Starting Parking Enforcement (local) ===" -ForegroundColor Cyan

# 1. Init database (ensure tables exist)
Write-Host "`n[1/5] Initializing database..." -ForegroundColor Yellow
Set-Location backend
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
python init_db.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "DB init failed. Is Postgres running? Check DATABASE_URL in .env" -ForegroundColor Red
    Set-Location ..
    exit 1
}

# 2. Start backend (port 8002 to avoid conflict with other apps on 8000)
Write-Host "`n[2/5] Starting backend (http://localhost:8002)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONUNBUFFERED=1; cd '$PWD'; python -m uvicorn main:app --reload --host 0.0.0.0 --port 8002"
Set-Location ..

# 3. Start upload worker (processes video queue)
Write-Host "`n[3/5] Starting upload worker..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONUNBUFFERED=1; cd '$PWD\backend'; python run_upload_worker.py"
# Stay at project root for frontend steps

# 4. Install frontend deps if needed
Write-Host "`n[4/5] Checking frontend..." -ForegroundColor Yellow
Set-Location frontend
if (-not (Test-Path "node_modules")) { npm install }

# 5. Start frontend
Write-Host "`n[5/5] Starting frontend (http://localhost:5182)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; npm run dev"
Set-Location ..

Write-Host "`n=== All services started ===" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:5182" -ForegroundColor White
Write-Host "  Backend:  http://localhost:8002" -ForegroundColor White
Write-Host "  API docs: http://localhost:8002/docs" -ForegroundColor White
