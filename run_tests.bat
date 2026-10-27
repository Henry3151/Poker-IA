@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat || (echo Rode setup.bat primeiro. & pause & exit /b 1)
python -m pytest
pause
