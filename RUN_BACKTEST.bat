@echo off
setlocal enabledelayedexpansion
echo ========================================================
echo   CONTROL TOWER — BACKTEST SUITE
echo ========================================================
echo.
echo This will run the complete backtest suite.
echo The Walk-Forward engine may take several minutes to run
echo depending on the size of your price history.
echo.

:: Optional: allow passing a --note from the command line
:: Usage: RUN_BACKTEST.bat "my note here"
set "NOTE=%~1"

:: Generate a shared run ID (YYYYMMDD_HHMMSS) so all three scripts
:: write their artifacts into the same run folder.
for /f "tokens=1-6 delims=/-:. " %%a in ("%date% %time%") do (
    set "DATE_PART=%%c%%b%%a"
    set "TIME_PART=%%d%%e%%f"
)
:: Normalise: time can have leading space on single-digit hours (e.g. " 9:05")
set "TIME_PART=%TIME_PART: =0%"
set "RUN_ID=%DATE_PART%_%TIME_PART%"

echo Run ID: %RUN_ID%
echo.

echo [1/3] Running Walk-Forward Engine...
if defined NOTE (
    python backtests\walk_forward.py --run-id %RUN_ID% --note "%NOTE%"
) else (
    python backtests\walk_forward.py --run-id %RUN_ID%
)
if %errorlevel% neq 0 (
    echo X Walk-Forward Engine failed.
    goto :end
)

echo.
echo [2/3] Running Alpha IC Evaluation (saving to same run folder)...
python backtests\alpha_eval.py --run-id %RUN_ID%
if %errorlevel% neq 0 (
    echo X Alpha IC Evaluation failed.
    goto :end
)

echo.
echo [3/3] Running Performance Metrics (Standalone Check)...
python backtests\metrics.py
if %errorlevel% neq 0 (
    echo X Performance Metrics failed.
    goto :end
)

echo.
echo ========================================================
echo   BACKTEST COMPLETE!
echo   Run ID : %RUN_ID%
echo   Folder : backtests\runs\%RUN_ID%\
echo   Open http://localhost:5000/backtest/history to browse all runs.
echo ========================================================

:end
pause
