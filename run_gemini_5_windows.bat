@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto :not_installed
if not exist ".env" goto :key_missing
findstr /B /C:"GEMINI_API_KEY=" ".env" >nul 2>nul
if errorlevel 1 goto :key_missing
findstr /C:"your-gemini-api-key" ".env" >nul 2>nul
if not errorlevel 1 goto :key_missing

".venv\Scripts\python.exe" -m korean_prompt_robustness run-all ^
  --input data\examples\kite_pairs.jsonl ^
  --config configs\gemini.json ^
  --run-id gemini-5
if errorlevel 1 goto :run_failed

echo.
echo Gemini run finished. Results are in the results folder.
pause
exit /b 0

:not_installed
echo Run install_windows.bat first.
pause
exit /b 1

:key_missing
echo Open .env and add GEMINI_API_KEY=your-key first.
pause
exit /b 1

:run_failed
echo Gemini run failed. Review the message above and the JSONL error records.
pause
exit /b 1
