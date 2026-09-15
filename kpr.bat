@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo The virtual environment was not found. Run install_windows.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" -m korean_prompt_robustness %*
exit /b %errorlevel%
