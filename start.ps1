# Ratio Studio - Unified Launcher for Windows PowerShell
Write-Host "========================================" -ForegroundColor Magenta
Write-Host " Starting Ratio Studio (Single Port: 8000)" -ForegroundColor Cyan
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

# Build frontend static bundle
Write-Host "[2/3] Building frontend bundle..." -ForegroundColor Green
npm run build --prefix frontend
if ($LASTEXITCODE -ne 0) {
    Write-Error "Frontend build failed."
    exit 1
}

# Launch unified server
Write-Host "[3/3] Launching Unified Server on http://127.0.0.1:8000..." -ForegroundColor Green
Start-Process "http://127.0.0.1:8000"
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
