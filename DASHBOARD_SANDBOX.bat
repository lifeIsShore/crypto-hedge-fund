@echo off
:: ============================================================
:: DASHBOARD_SANDBOX.bat
:: Starts the Flask dashboard connected to sandbox_data.db.
:: Allows viewing Paper Trading portfolio, signals, and trades.
:: ============================================================

title Hedge Fund Dashboard — Sandbox / Paper Trading Mode

:: ── Venv Python ──
set PYTHON=C:\Users\user\.venv\Scripts\python.exe

echo.
echo  ============================================================
echo   CONTROL TOWER -- SANDBOX (PAPER TRADING) DASHBOARD
echo   Database: sandbox_data.db
echo  ============================================================
echo.

cd /d "%~dp0"

:: Check Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Make sure Python is on your PATH.
    pause
    exit /b 1
)

:: Set environment flags
set FLASK_ENV=development
set FLASK_APP=flask_app.py
set DASHBOARD_ONLY=1
set SANDBOX_MODE=1
set PYTHONIOENCODING=utf-8

echo [INFO] Starting Flask dashboard in SANDBOX mode...
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /c:"IPv4 Address"') do set LOCAL_IP=%%i
if defined LOCAL_IP set LOCAL_IP=%LOCAL_IP: =%
if not defined LOCAL_IP set LOCAL_IP=your-local-ip

echo [INFO] Opening http://localhost:5000 in your browser.
echo [INFO] LAN Access: http://%LOCAL_IP%:5000
echo [INFO] Press Ctrl+C to stop.
echo.

start http://localhost:5000
%PYTHON% flask_app.py

pause
