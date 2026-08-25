@echo off
:: ============================================================
:: DASHBOARD_ONLY.bat
:: Starts the Flask dashboard using LAST AVAILABLE data only.
:: Does NOT trigger any pipeline, ML run, or data refresh.
:: Use this after you have already run your main data script.
:: ============================================================

title Hedge Fund Dashboard (View-Only)

:: ── Venv Python — all project deps live here ──
set PYTHON=python

echo.
echo  =========================================
echo   CONTROL TOWER -- DASHBOARD ONLY MODE
echo   Using last available data. No refresh.
echo  =========================================
echo.

cd /d "%~dp0"

:: ── Auto-start Ollama (on-prem LLM used by the Briefing tab) ──
:: Skips silently if already running or if ollama isn't installed/on PATH —
:: the Briefing tab's Regenerate button will just report a connection error
:: rather than blocking the rest of the app.
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

:: Set environment: development mode for auto-reload
set FLASK_ENV=development
set FLASK_APP=flask_app.py
set DASHBOARD_ONLY=1
set PYTHONIOENCODING=utf-8

echo [INFO] Starting Flask dashboard in read-only mode...
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
