@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "assets\icon.ico" (
  if exist ".venv\Scripts\python.exe" ".venv\Scripts\python.exe" assets\make_icon.py
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_shortcuts.ps1"
