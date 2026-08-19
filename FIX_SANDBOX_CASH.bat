@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

:: ── Venv Python — all project deps live here ──
set PYTHON=python

echo ============================================================
echo   SANDBOX CASH RECONCILIATION
echo   Fixes the cash-double-count bug in sandbox_data.db
echo   (paper BUYs never deducted cash before today's fix)
echo   Real money / engine_data.db: NOT TOUCHED
echo ============================================================
echo.
echo [1/2] Dry run — showing what would change...
echo.
%PYTHON% fix_sandbox_cash.py --dry-run
echo.
echo ============================================================
set /p CONFIRM="Apply this fix now? A backup will be made first. (y/n): "
if /I "%CONFIRM%" NEQ "y" (
    echo Aborted — no changes made.
    pause
    exit /b 0
)
echo.
echo [2/2] Applying fix...
%PYTHON% fix_sandbox_cash.py

echo.
pause
