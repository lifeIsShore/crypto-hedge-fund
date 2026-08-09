@echo off
cd /d "%~dp0"
set SANDBOX_MODE=1
set PYTHONIOENCODING=utf-8

:: ── Venv Python — all project deps live here ──
set PYTHON=C:\Users\user\.venv\Scripts\python.exe

echo ============================================================
echo   HEDGE FUND SANDBOX — Paper Trading Mode
echo   Database: sandbox_data.db
echo   Real money: NONE
echo ============================================================
echo.
echo [1/3] Ensuring sandbox_data.db schema is up to date...
%PYTHON% -m engine.db.db
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Schema setup failed on sandbox_data.db - aborting before touching the pipeline.
    pause
    exit /b 1
)
echo.
echo [2/3] Initializing paper trading engine...
echo [3/3] Fetching market data ^& running pipeline (first run ingests full history, can take several minutes)...
echo.

%PYTHON% -m engine.scheduler --pipeline-only

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Sandbox pipeline encountered an issue. Check log output above.
) else (
    echo.
    echo ============================================================
    echo   SANDBOX RUN COMPLETE!
    echo   Paper trade log saved to sandbox_data.db
    echo ============================================================
)

echo.
pause

