@echo off
REM Start the Quant Engine Dashboard on Windows
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo.
echo ============================================================
echo  🚀 TRADE REPUBLIC QUANT ENGINE - DASHBOARD
echo ============================================================
echo.

python start.py

pause
