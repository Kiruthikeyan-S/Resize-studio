@echo off
title Ratio Studio Launcher
echo ===================================================
echo   Starting Ratio Studio (Backend + Frontend)
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

echo [2/3] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "Ratio Studio - Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

echo [3/3] Launching Vite Frontend on http://localhost:5173 ...
start "Ratio Studio - Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ===================================================
echo Ratio Studio is starting!
echo Open your browser at: http://localhost:5173
echo Backend API Docs at:  http://127.0.0.1:8000/docs
echo ===================================================
timeout /t 3 >nul
start http://localhost:5173
