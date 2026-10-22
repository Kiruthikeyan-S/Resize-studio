# Ratio Studio - Unified Launcher for Windows PowerShell
Write-Host "========================================" -ForegroundColor Magenta
Write-Host " Starting Ratio Studio (Backend + Frontend)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Magenta

# Check Python and Node
Write-Host "[1/3] Checking environment..." -ForegroundColor Yellow

$pyPath = $null
try {
    $res = & python -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $res) {
        $pyPath = "python"
    }
} catch {}

if (-not $pyPath) {
    try {
        $res = & py -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $res) {
            $pyPath = "py"
        }
    } catch {}
}

if (-not $pyPath) {
    $candidates = @("C:\Python314\python.exe", "C:\Python313\python.exe", "C:\Python312\python.exe", "C:\Python311\python.exe") + @(Get-ChildItem -Path "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    foreach ($cand in $candidates) {
        if ($cand -and (Test-Path $cand)) {
            $pyPath = $cand
            break
        }
    }
}

$npm = Get-Command npm -ErrorAction SilentlyContinue

if (-not $pyPath) {
    Write-Error "Python 3.11+ not found in PATH or standard directories."
    exit 1
}
if (-not $npm) {
    Write-Error "npm not found in PATH."
    exit 1
}

# Start backend in a separate background PowerShell process
Write-Host "[2/3] Launching FastAPI Backend on http://127.0.0.1:8000 using $pyPath..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\backend'; & '$pyPath' -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

# Start frontend in current window
Write-Host "[3/3] Launching Vite Frontend on http://localhost:5173..." -ForegroundColor Green
cd "$PSScriptRoot\frontend"
npm run dev
