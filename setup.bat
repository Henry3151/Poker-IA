@echo off
REM Poker AI Tournament Lab - instalacao (Windows). Requer Python 3.12+ (https://www.python.org/downloads/).
REM   setup.bat        instalacao completa (programa + testes)
REM   setup.bat leve   so o necessario para usar o programa (mais rapido e menor)
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3.12 -m venv .venv || py -3 -m venv .venv) else (python -m venv .venv)
if not exist .venv\Scripts\activate.bat (echo [ERRO] Nao foi possivel criar o ambiente virtual. Instale o Python 3.12+. & pause & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
set REQ=requirements-dev.txt
if /i "%1"=="leve" set REQ=requirements.txt
pip install --no-cache-dir -r %REQ% || (echo [ERRO] Falha ao instalar dependencias. & pause & exit /b 1)
pip install -e . --no-deps
echo.
echo Instalacao concluida (%REQ%).
echo   iniciar_lab.bat   abre o programa no navegador
echo   criar_atalho.bat  cria um atalho na area de trabalho
if /i not "%1"=="leve" echo   run_tests.bat     roda a suite de testes
pause
