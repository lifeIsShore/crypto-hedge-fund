@echo off
setlocal enabledelayedexpansion
set PYTHONUTF8=1

echo ==========================================
echo  Starting Full Research Pipeline Execution
echo ==========================================

set BASE_DIR=%CD%

echo.
echo --- 1. Running General Research Notebooks ---
cd "%BASE_DIR%\general_research\notebooks"
python ..\run_notebooks.py

echo.
echo --- 2. Running Regime Engine (Quant Research) ---
cd "%BASE_DIR%\quant_research\regime_engine"
python run_engine.py --backfill

echo.
echo --- 3. Running PEAD Engine (Quant Research) ---
cd "%BASE_DIR%\quant_research\pead_engine"
python run_engine.py --backfill --refresh

echo.
echo --- 4. Running ML Research Notebooks ---
cd "%BASE_DIR%\ml_research\stock_ml_lab\notebooks"
for %%f in (*.ipynb) do (
    echo Executing %%f...
    jupyter nbconvert --to notebook --execute --inplace "%%f"
)

echo.
echo ==========================================
echo  Research Pipeline Completed Successfully
echo ==========================================
pause
