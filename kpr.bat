@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 goto :run_py_launcher

where python >nul 2>nul
if errorlevel 1 (
    echo [kpr] Python 3.10 or newer was not found.
    echo [kpr] Install Python and run this command again.
    exit /b 1
)

python "%~dp0kpr.py" %*
exit /b %errorlevel%

:run_py_launcher
py -3 "%~dp0kpr.py" %*
exit /b %errorlevel%
