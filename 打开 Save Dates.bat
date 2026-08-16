@echo off
cd /d "%~dp0"
if exist "dist\SaveDates\SaveDates.exe" (
  start "" "dist\SaveDates\SaveDates.exe"
  exit /b 0
)
call "%~dp0run.bat"
