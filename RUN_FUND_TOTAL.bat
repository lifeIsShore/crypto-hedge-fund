@echo off
SETLOCAL EnableDelayedExpansion
set PYTHONIOENCODING=utf-8

:: ── Venv Python — all project deps (sqlalchemy, aiohttp, etc.) live here ──
set PYTHON=python

echo ============================================================
echo   HEDGE FUND CONTROL TOWER - UNIFIED SYSTEM RUNNER
echo ============================================================

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

:: 1. DATA INGESTION
echo [1/6] Syncing Market Data (Prices, FX, Fundamentals)...
%PYTHON% -m engine.data.ingestion
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Data sync failed.
    pause
    exit /b %ERRORLEVEL%
)

:: 2. MACRO & REGIME
echo [2/6] Updating Macro Regime Intelligence (Global)...
cd /d "%~dp0ml_quant_finance_research\quant_research\regime_engine"
%PYTHON% run_engine.py --region ALL
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Regime engine failed - continuing with last state.
)
cd /d "%~dp0"

:: 3. RESEARCH SCREENING (PEAD)
echo [3/6] Running Earnings (PEAD) Screener...
cd /d "%~dp0ml_quant_finance_research\quant_research\pead_engine"
%PYTHON% run_engine.py --lookback 90
cd /d "%~dp0"

:: 4. OPTIONAL ML TRAINING
echo.
echo [4/6] ML INTELLIGENCE UPDATE
set train=n
set /p train="Do you want to run FULL ML training? (Takes ~10-45 mins) (y/n): "

if /i "!train!"=="y" (
    echo [ACTION] Training ML Models...
    cd /d "%~dp0ml_quant_finance_research\ml_research\stock_ml_lab"
    %PYTHON% run_ml_pipeline.py
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo [CRITICAL ERROR] The ML Pipeline crashed. 
        echo Please check the error message above.
        pause
    )
    cd /d "%~dp0"
) else (
    echo [SKIP] Using existing ML intelligence.
)

:: 5. MIRRORING & RECONCILIATION
echo [5/6] Mirroring Research to Production ^& Rebalancing...
%PYTHON% -m engine.alpha.pead_alpha --mirror-only
%PYTHON% -m engine.scheduler --pipeline-only

:: 5b. BRIEFING NARRATIVE
:: Regenerates the on-prem LLM summary from the data this run just produced.
:: Fails soft (non-zero exit is swallowed) — a stuck/offline Ollama should
:: never block the dashboard from launching. The Regenerate button on the
:: Briefing tab still works standalone if this step is skipped.
echo [5b/6] Regenerating Briefing narrative (on-prem LLM)...
%PYTHON% -m engine.briefing.generate_cli

:: 6. LAUNCH DASHBOARD
echo [6/6] Launching Flask Control Tower...

for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /c:"IPv4 Address"') do set LOCAL_IP=%%i
if defined LOCAL_IP set LOCAL_IP=%LOCAL_IP: =%
if not defined LOCAL_IP set LOCAL_IP=your-local-ip

echo Dashboard will be available locally at http://localhost:5000
echo Dashboard will be available on LAN at http://%LOCAL_IP%:5000
start http://localhost:5000
%PYTHON% flask_app.py

echo ============================================================
echo   SYSTEM SHUTDOWN
echo ============================================================
pause
