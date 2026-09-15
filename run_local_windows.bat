@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto :not_installed
where ollama >nul 2>nul
if errorlevel 1 goto :ollama_missing

".venv\Scripts\python.exe" -m korean_prompt_robustness configure ^
  --test local ^
  --test-model qwen2.5:14b ^
  --judge local ^
  --judge-model qwen2.5:14b
if errorlevel 1 goto :run_failed

".venv\Scripts\python.exe" -m korean_prompt_robustness run ^
  data\examples\problems.jsonl ^
  --limit 5
if errorlevel 1 goto :run_failed

echo.
echo Finished. Responses were printed above and were not saved to files.
pause
exit /b 0

:not_installed
echo Run install_windows.bat first.
pause
exit /b 1

:ollama_missing
echo Ollama was not found. Install it, then run: ollama pull qwen2.5:14b
pause
exit /b 1

:run_failed
echo The run failed. Review the message above.
pause
exit /b 1
