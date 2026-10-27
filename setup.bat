@echo off
REM Poker AI Tournament Lab - setup (Windows). Requires Python 3.12+ (https://www.python.org/downloads/).
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3.12 -m venv .venv || py -3 -m venv .venv) else (python -m venv .venv)
if not exist .venv\Scripts\activate.bat (echo [ERRO] Nao foi possivel criar o ambiente virtual. Instale o Python 3.12+. & pause & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-dev.txt || (echo [ERRO] Falha ao instalar dependencias. & pause & exit /b 1)
pip install -e . --no-deps
echo.
echo Instalacao concluida. Use run_tests.bat, run_demo.bat ou run_p7_evaluation.bat
pause
