@echo off
set SANDBOX_MODE=1
echo Running Crypto Hedge Fund Engine (Sandbox Mode)
python -m engine.scheduler %*
pause
