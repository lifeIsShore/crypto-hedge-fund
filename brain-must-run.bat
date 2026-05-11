@echo off
SETLOCAL EnableDelayedExpansion

echo ============================================================
echo   HEDGE FUND CONTROL TOWER - SYSTEM SYNC
echo ============================================================

:: 1. DATA INGESTION
echo [1/5] Fetching latest market data (EUR prices + FX)...
python -m engine.data.ingestion
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Ingestion failed. Check internet/API keys.
    pause
    exit /b %ERRORLEVEL%
)

:: 2. REGIME & MACRO REFRESH
echo [2/5] Updating Market Regime (Risk-On/Off)...
python -m engine.alpha.regime_alpha
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Regime update failed.
    pause
    exit /b %ERRORLEVEL%
)

:: 3. OPTIONAL: FULL ML RESEARCH TRAINING
set /p train="[3/5] Do you want to run FULL ML training? (Takes a long time) (y/n): "
if /i "%train%"=="y" (
    echo [ACTION] Starting ML Quant Finance Research Lab...
    :: Adjust the path if your main research entry point is different
    python -m ml_quant_finance_research.ml_research.stock_ml_lab.run_ml_pipeline
    if %ERRORLEVEL% NEQ 0 (
        echo [WARNING] ML Training had issues. Check logs.
    )
) else (
    echo [SKIP] Using existing ML intelligence from last run.
)

:: 4. ML/PEAD MIRRORING
echo [4/5] Syncing Research State to Production...
python -m engine.alpha.pead_alpha --mirror-only
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Mirroring failed. Using last known state.
)

:: 5. PORTFOLIO RECONCILIATION
echo [5/5] Reconciling with your Portfolio CSV...
python -m engine.scheduler --pipeline-only
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Portfolio construction failed.
    pause
    exit /b %ERRORLEVEL%
)

echo ============================================================
echo   [SUCCESS] SYSTEM IS UP TO DATE AND TRUSTWORTHY
echo ============================================================
pause
