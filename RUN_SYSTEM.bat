@echo off
:: ============================================================
:: RUN_SYSTEM.bat
:: Full pipeline: data ingestion -> ML train -> signal gen -> dashboard
:: Use this when you want to refresh ALL data AND start the UI.
:: For dashboard-only (no refresh), use DASHBOARD_ONLY.bat instead.
:: ============================================================

title Hedge Fund Control Tower -- Full System Run

echo.
echo  =========================================
echo   CONTROL TOWER -- FULL SYSTEM RUN
echo   Step 1: Data ingestion
echo   Step 2: ML pipeline
echo   Step 3: Quant research engines
echo   Step 4: Start dashboard
echo  =========================================
echo.

cd /d "%~dp0"

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Make sure Python is on your PATH.
    pause
    exit /b 1
)

set PYTHONIOENCODING=utf-8
set FLASK_ENV=production
set FLASK_APP=flask_app.py

:: STEP 1: Main data pipeline
echo [STEP 1/4] Running data pipeline...
if exist brain-must-run.bat (
    call brain-must-run.bat
) else (
    echo [WARN] brain-must-run.bat not found -- skipping.
)
echo.

:: STEP 2: ML pipeline
echo [STEP 2/4] Running ML pipeline...
if exist ml_quant_finance_research\ml_research\stock_ml_lab\run_ml_pipeline.py (
    python ml_quant_finance_research\ml_research\stock_ml_lab\run_ml_pipeline.py
    if %ERRORLEVEL% neq 0 (
        echo [WARN] ML pipeline error. Dashboard will use last available ML state.
    ) else (
        echo [OK] ML pipeline complete.
    )
) else (
    echo [WARN] run_ml_pipeline.py not found -- skipping.
)
echo.

:: STEP 3: Quant research engines
echo [STEP 3/4] Running quant research engines...
if exist ml_quant_finance_research\run_all_research.bat (
    call ml_quant_finance_research\run_all_research.bat
) else (
    echo [WARN] run_all_research.bat not found -- skipping.
)
echo.

:: STEP 4: Start Flask dashboard
echo [STEP 4/4] Starting Flask dashboard...
echo [INFO] Opening http://localhost:5000
echo [INFO] Press Ctrl+C to stop.
echo.

start http://localhost:5000
python flask_app.py

pause