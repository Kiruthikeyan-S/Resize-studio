@echo off
title Ratio Studio Launcher
echo ===================================================
echo   Starting Ratio Studio (Unified Single Port: 8000)
echo ===================================================

echo [1/3] Checking environment...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH! Please install Python 3.11+.
    pause
    exit /b 1
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] npm / Node.js not found in PATH! Please install Node.js.
    pause
    exit /b 1
)

echo [2/3] Building frontend production bundle for single-port hosting...
call npm run build --prefix frontend
if %errorlevel% neq 0 (
    echo [ERROR] Frontend build failed.
    pause
    exit /b 1
)

echo [3/3] Launching Unified Server (Frontend + Backend) on http://127.0.0.1:8000 ...
start "Ratio Studio - Unified Server" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

echo.
echo ===================================================
echo Ratio Studio is running on a SINGLE PORT!
echo Open your browser at: http://127.0.0.1:8000
echo Backend API Docs at:  http://127.0.0.1:8000/docs
echo ===================================================
timeout /t 3 >nul
start http://127.0.0.1:8000
