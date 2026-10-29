@echo off
REM Exporta o modelo estrela para o Power BI (Parquet) e o reconcilia; nada e publicado se algum KPI divergir.
REM Requer os bancos de artifacts\p7\, artifacts\p7b\ e/ou artifacts\p7c\ (rode as avaliacoes antes).
cd /d "%~dp0"
call .venv\Scripts\activate.bat || (echo Rode setup.bat primeiro. & pause & exit /b 1)
poker-lab export powerbi --out artifacts\powerbi\latest || (echo [ERRO] exportacao recusada: veja artifacts\powerbi\latest.reconciliation_FAILED.json & pause & exit /b 1)
echo.
echo Pronto. No Power BI, aponte o parametro PastaExportacao para:
echo   %cd%\artifacts\powerbi\latest
echo e siga powerbi\GUIA_MONTAGEM_P8.md
pause
