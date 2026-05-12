@echo off
SETLOCAL EnableDelayedExpansion
set PYTHONIOENCODING=utf-8

echo ============================================================
echo   HEDGE FUND CONTROL TOWER - UNIFIED SYSTEM RUNNER
echo ============================================================

:: 1. DATA INGESTION
echo [1/6] Syncing Market Data (Prices, FX, Fundamentals)...
python -m engine.data.ingestion
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Data sync failed.
    pause
    exit /b %ERRORLEVEL%
)

:: 2. MACRO & REGIME
echo [2/6] Updating Macro Regime Intelligence...
python -m engine.alpha.regime_alpha
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Regime engine failed - continuing with last state.
)

:: 3. RESEARCH SCREENING (PEAD)
echo [3/6] Running Earnings (PEAD) Screener...
cd /d "%~dp0ml_quant_finance_research\quant_research\pead_engine"
python run_engine.py --lookback 90
cd /d "%~dp0"

:: 4. OPTIONAL ML TRAINING
set /p train="[4/6] Run FULL ML training? (Takes ~10-45 mins) (y/n): "
if /i "%train%"=="y" (
    echo [ACTION] Training ML Models for 95 tickers...
    cd /d "%~dp0ml_quant_finance_research\ml_research\stock_ml_lab"
    python run_ml_pipeline.py
    cd /d "%~dp0"
) else (
    echo [SKIP] Using existing ML intelligence.
)

:: 5. MIRRORING & RECONCILIATION
echo [5/6] Mirroring Research to Production & Rebalancing...
python -m engine.alpha.pead_alpha --mirror-only
python -m engine.scheduler --pipeline-only

:: 6. LAUNCH DASHBOARD
echo [6/6] Launching Flask Control Tower...
echo Dashboard will be available at http://localhost:5000
start http://localhost:5000
python flask_app.py

echo ============================================================
echo   SYSTEM SHUTDOWN
echo ============================================================
pause
