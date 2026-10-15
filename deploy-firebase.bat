@echo off
title Deploy Ratio Studio to Firebase
echo ========================================================
echo   Building and Deploying Ratio Studio to Firebase
echo ========================================================

cd /d %~dp0frontend
echo [1/3] Building frontend production bundle...
call npm run build

echo [2/3] Checking Firebase authentication...
call firebase deploy --only hosting
if %errorlevel% neq 0 (
    echo.
    echo [NOTE] Firebase login needed. Opening browser to authenticate...
    call firebase login --reauth
    echo.
    echo [3/3] Deploying to Firebase Hosting...
    call firebase deploy --only hosting
)

echo.
echo ========================================================
echo   Deployment completed!
echo   Live URL: https://resizeap.web.app
echo ========================================================
pause
