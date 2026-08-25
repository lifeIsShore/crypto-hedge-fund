@echo off
:: ============================================================
:: DASHBOARD_SANDBOX.bat
:: Starts the Flask dashboard pointed at sandbox_data.db (paper
:: trades only, no real money). Shows the orange "SANDBOX" badge
:: and top banner instead of the green "LIVE" badge — see
:: templates/base.html's sandbox_mode block.
:: Does NOT trigger any pipeline run — run RUN_SANDBOX.bat first
:: to generate today's paper trades.
:: ============================================================

title Hedge Fund Dashboard (SANDBOX / Paper Trades)

:: ── Venv Python — all project deps live here ──
set PYTHON=python

echo.
echo  =========================================
echo   CONTROL TOWER -- SANDBOX DASHBOARD
echo   Viewing sandbox_data.db (paper trades)
echo   Real money: NONE
echo  =========================================
echo.

cd /d "%~dp0"

:: ── Auto-start Ollama (on-prem LLM used by the Briefing tab) ──
where ollama >nul 2>&1
if %ERRORLEVEL% equ 0 (
    tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >nul
    if errorlevel 1 (
        echo [INFO] Starting Ollama server for the Briefing tab...
        start "Ollama" /min ollama serve
        timeout /t 2 /nobreak >nul
    ) else (
        echo [INFO] Ollama server already running.
    )
) else (
    echo [WARN] Ollama not found on PATH — Briefing narrative generation will be unavailable.
)

:: Check Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Make sure Python is on your PATH.
    pause
    exit /b 1
)

:: Set environment: SANDBOX_MODE routes engine/db/db.py to sandbox_data.db
:: and flips the dashboard banner/badge to SANDBOX (see flask_app.py
:: inject_metadata() + templates/base.html).
set FLASK_ENV=development
set FLASK_APP=flask_app.py
set DASHBOARD_ONLY=1
set SANDBOX_MODE=1
set PYTHONIOENCODING=utf-8

echo [INFO] Starting Flask dashboard in SANDBOX read-only mode...
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
