@echo off
REM Para a sessao Open Poker em andamento (kill switch).
cd /d "%~dp0"
if not exist artifacts\openpoker mkdir artifacts\openpoker
echo stop> artifacts\openpoker\STOP
echo Kill switch criado. Apague artifacts\openpoker\STOP antes da proxima sessao.
pause
