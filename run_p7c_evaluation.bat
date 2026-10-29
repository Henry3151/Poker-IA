@echo off
REM P7c final robustness evaluation (6.000 torneios simulados; ~1,5-3 h em um nucleo).
REM Seed congelada 20261029. Resultados em artifacts\p7c\ (fora do Git).
cd /d "%~dp0"
call .venv\Scripts\activate.bat || (echo Rode setup.bat primeiro. & pause & exit /b 1)
python scripts\p7c_final.py shard 0 1 || (pause & exit /b 1)
python scripts\p7c_final.py finalize 1 || (pause & exit /b 1)
python scripts\p7c_integrity.py artifacts\p7c\final.db > artifacts\p7c\p7c_integrity.json || (echo [ERRO] verificacao de integridade falhou & pause & exit /b 1)
python scripts\p7c_steal_analysis.py
echo.
echo Pronto. Relatorio: artifacts\p7c\p7c_final_report.json  Integridade: artifacts\p7c\p7c_integrity.json
pause
