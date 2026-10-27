@echo off
REM Full P7 evaluation (~5900 simulated tournaments; can take 1-2 hours on one core).
cd /d "%~dp0"
call .venv\Scripts\activate.bat || (echo Rode setup.bat primeiro. & pause & exit /b 1)
python scripts\run_p7_evaluation.py train || (pause & exit /b 1)
python scripts\run_p7_evaluation.py shard 0 1 || (pause & exit /b 1)
python scripts\run_p7_evaluation.py finalize 1 || (pause & exit /b 1)
python scripts\audit_mccfr.py
pause
