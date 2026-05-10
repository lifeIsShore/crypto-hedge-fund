@echo off
:: ============================================================
::  Hedge Fund Control Tower — Quick Run Script
::  Runs: Regime Engine → PEAD Engine → ML Pipeline → Dashboard
:: ============================================================
setlocal
set PYTHONIOENCODING=utf-8
set ROOT=%~dp0

echo.
echo ============================================================
echo   STEP 1/3 — Macro Regime Engine
echo ============================================================
cd /d "%ROOT%ml_quant_finance_research\quant_research\regime_engine"
python run_engine.py
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Regime engine exited with error — continuing anyway
)

echo.
echo ============================================================
echo   STEP 2/3 — PEAD Engine
echo ============================================================
cd /d "%ROOT%ml_quant_finance_research\quant_research\pead_engine"
python run_engine.py --lookback 90
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] PEAD engine exited with error — continuing anyway
)

echo.
echo ============================================================
echo   STEP 3/3 — ML Pipeline  (this takes ~2 minutes)
echo ============================================================
cd /d "%ROOT%ml_quant_finance_research\ml_research\stock_ml_lab"
python run_ml_pipeline.py
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] ML pipeline exited with error — continuing anyway
)

echo.
echo ============================================================
echo   ALL ENGINES DONE — Launching Dashboard
echo ============================================================
cd /d "%ROOT%"
start "" streamlit run dashboard/app.py
echo Dashboard starting at http://localhost:8501
echo.
pause
