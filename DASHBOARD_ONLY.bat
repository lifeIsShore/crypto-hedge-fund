@echo off
:: ============================================================
:: DASHBOARD_ONLY.bat
:: Starts the Flask dashboard using LAST AVAILABLE data only.
:: Does NOT trigger any pipeline, ML run, or data refresh.
:: Use this after you have already run your main data script.
:: ============================================================

title Hedge Fund Dashboard (View-Only)

echo.
echo  =========================================
echo   CONTROL TOWER -- DASHBOARD ONLY MODE
echo   Using last available data. No refresh.
echo  =========================================
echo.

cd /d "%~dp0"

:: Check Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Make sure Python is on your PATH.
    pause
    exit /b 1
)

:: Set environment: production mode, no scheduler
set FLASK_ENV=production
set FLASK_APP=flask_app.py
set DASHBOARD_ONLY=1
set PYTHONIOENCODING=utf-8

echo [INFO] Starting Flask dashboard in read-only mode...
echo [INFO] Opening http://localhost:5000 in your browser.
echo [INFO] Press Ctrl+C to stop.
echo.

start http://localhost:5000
python flask_app.py

pause
