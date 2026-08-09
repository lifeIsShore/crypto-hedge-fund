@echo off
SETLOCAL EnableDelayedExpansion
set PYTHONIOENCODING=utf-8

:: ── Venv Python — all project deps (sqlalchemy, aiohttp, etc.) live here ──
set PYTHON=C:\Users\user\.venv\Scripts\python.exe

echo ============================================================
echo   HEDGE FUND CONTROL TOWER - UNIFIED SYSTEM RUNNER
echo ============================================================

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
echo [5/6] Mirroring Research to Production & Rebalancing...
%PYTHON% -m engine.alpha.pead_alpha --mirror-only
%PYTHON% -m engine.scheduler --pipeline-only

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
