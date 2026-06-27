@echo off
cd /d "%~dp0"
set /p KODIPATH=Paste Kodi folder path and press Enter: 
py -3 builder\build_release.py "%KODIPATH%" --dry-run
if errorlevel 1 python builder\build_release.py "%KODIPATH%" --dry-run
pause
