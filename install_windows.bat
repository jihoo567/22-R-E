@echo off
setlocal
cd /d "%~dp0"

echo [1/5] Checking Python 3.10 or newer...
where py >nul 2>nul
if %errorlevel%==0 (
    set "KPR_PYTHON=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 goto :python_missing
    set "KPR_PYTHON=python"
)

%KPR_PYTHON% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto :python_old

echo [2/5] Creating virtual environment...
if not exist ".venv\Scripts\python.exe" (
    %KPR_PYTHON% -m venv .venv
    if errorlevel 1 goto :failed
)

echo [3/5] Installing benchmark...
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto :failed

echo [4/5] Preparing local settings and result folders...
if not exist ".env" copy /Y ".env.example" ".env" >nul
if not exist "results\responses" mkdir "results\responses"
if not exist "results\judgments" mkdir "results\judgments"
if not exist "results\scores" mkdir "results\scores"
if not exist "results\reports" mkdir "results\reports"

echo [5/5] Running tests...
".venv\Scripts\python.exe" -m unittest discover -s tests -q
if errorlevel 1 goto :failed

echo.
echo Installation completed successfully.
echo Edit .env to use Gemini: GEMINI_API_KEY=your-key
echo Then run run_mock_windows.bat or run_gemini_5_windows.bat.
pause
exit /b 0

:python_missing
echo Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/windows/
echo During setup, enable "Add Python to PATH", then run this file again.
pause
exit /b 1

:python_old
echo Python 3.10 or newer is required.
pause
exit /b 1

:failed
echo Installation or tests failed. Review the message above.
pause
exit /b 1
