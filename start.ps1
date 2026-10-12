# Ratio Studio - Unified Launcher for Windows PowerShell
Write-Host "========================================" -ForegroundColor Magenta
Write-Host " Starting Ratio Studio (Backend + Frontend)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Magenta

# Check Python and Node
Write-Host "[1/3] Checking environment..." -ForegroundColor Yellow
$py = Get-Command python -ErrorAction SilentlyContinue
$npm = Get-Command npm -ErrorAction SilentlyContinue

if (-not $py) {
    Write-Error "Python not found in PATH."
    exit 1
}
if (-not $npm) {
    Write-Error "npm not found in PATH."
    exit 1
}

# Start backend in a separate background PowerShell process
Write-Host "[2/3] Launching FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

# Start frontend in current window
Write-Host "[3/3] Launching Vite Frontend on http://localhost:5173..." -ForegroundColor Green
cd frontend
npm run dev
