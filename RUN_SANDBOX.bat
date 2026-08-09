@echo off
set SANDBOX_MODE=1
set PYTHONIOENCODING=utf-8

echo ============================================================
echo   HEDGE FUND SANDBOX — Paper Trading Mode
echo   Database: sandbox_data.db
echo   Real money: NONE
echo ============================================================

python -m engine.scheduler --pipeline-only
echo.
echo Sandbox run complete. Check sandbox_data.db for paper trade log.
pause
