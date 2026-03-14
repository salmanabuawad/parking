# Start backend, frontend, and upload worker (run from parking folder).
# Requires: Postgres running, backend/.env configured.

$root = $PSScriptRoot
if (-not $root) { $root = Get-Location }

Write-Host "Starting backend (port 8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; python run_backend.py" -WindowStyle Normal

Start-Sleep -Seconds 1

Write-Host "Starting frontend (Vite)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev" -WindowStyle Normal

Start-Sleep -Seconds 1

Write-Host "Starting upload worker..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; python run_upload_worker.py" -WindowStyle Normal

Write-Host "Done. Backend: http://localhost:8000  Frontend: http://localhost:5173 (see Vite window if port changed)" -ForegroundColor Green
