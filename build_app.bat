@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo 正在创建虚拟环境...
  py -3 -m venv .venv
)

echo 正在安装打包依赖...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt pyinstaller
if errorlevel 1 (
  echo 依赖安装失败。
  pause
  exit /b 1
)

echo 正在生成图标...
".venv\Scripts\python.exe" assets\make_icon.py

echo 正在打包 Windows 应用（可能需要一两分钟）...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm SaveDates.spec
if errorlevel 1 (
  echo 打包失败。
  pause
  exit /b 1
)

echo.
echo 完成。可双击运行：
echo   dist\SaveDates\SaveDates.exe
echo 关闭窗口后仍会在托盘里监听新邮件，右键托盘图标可退出。
echo.
pause
