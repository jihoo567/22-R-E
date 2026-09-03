@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto :not_installed

".venv\Scripts\python.exe" -m korean_prompt_robustness run-all ^
  --input data\examples\kite_pairs.jsonl ^
  --config configs\mock.json ^
  --run-id mock-check
if errorlevel 1 goto :run_failed

echo.
echo Mock run finished. Results are in the results folder.
pause
exit /b 0

:not_installed
echo Run install_windows.bat first.
pause
exit /b 1

:run_failed
echo Mock run failed. Review the message above.
pause
exit /b 1
