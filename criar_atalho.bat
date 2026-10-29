@echo off
REM Cria o atalho "Poker AI Lab" na area de trabalho, apontando para iniciar_lab.bat.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Poker AI Lab.lnk'));" ^
  "$s.TargetPath='%~dp0iniciar_lab.bat'; $s.WorkingDirectory='%~dp0'; $s.Description='Poker AI Tournament Lab (local)';" ^
  "$s.IconLocation=\"$env:SystemRoot\System32\shell32.dll,137\"; $s.Save(); Write-Host ('Atalho criado em ' + $d)"
pause
