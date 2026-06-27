@echo off
cd /d "%~dp0"
set /p KODIPATH=Paste Kodi folder path and press Enter: 
set /p VERSION=Build version (example 1.0): 
if "%VERSION%"=="" set VERSION=1.0
py -3 builder\build_release.py "%KODIPATH%" --version "%VERSION%" --name LiorBuild --base-url https://lioryo.github.io/KodiBuild/
if errorlevel 1 python builder\build_release.py "%KODIPATH%" --version "%VERSION%" --name LiorBuild --base-url https://lioryo.github.io/KodiBuild/
pause
