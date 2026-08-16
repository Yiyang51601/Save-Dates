@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo 正在创建虚拟环境...
  py -3 -m venv .venv
)

echo 正在检查依赖...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo 依赖安装失败。
  pause
  exit /b 1
)

echo 正在启动 Save Dates 应用窗口...
start "" ".venv\Scripts\pythonw.exe" -m save_dates
