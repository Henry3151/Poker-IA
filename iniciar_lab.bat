@echo off
REM Poker AI Tournament Lab - abre a interface local no navegador (servidor so em 127.0.0.1).
REM Feche esta janela (ou Ctrl+C) para encerrar o programa.
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
  echo Primeiro uso: rode setup.bat para instalar as dependencias.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
chcp 65001 >nul
python -m poker_lab.api.launch %*
if errorlevel 1 pause
