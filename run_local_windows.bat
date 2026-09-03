@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto :not_installed
where ollama >nul 2>nul
if errorlevel 1 goto :ollama_missing

".venv\Scripts\python.exe" -m korean_prompt_robustness run-all ^
  --input data\examples\kite_pairs.jsonl ^
  --config configs\local_test_local_judge.json ^
  --run-id local-test-local-judge
if errorlevel 1 goto :run_failed

echo.
echo Local run finished. Results are in the results folder.
pause
exit /b 0

:not_installed
echo Run install_windows.bat first.
pause
exit /b 1

:ollama_missing
echo Ollama was not found. Install it from https://ollama.com/download/windows
echo Then run: ollama pull gemma3:4b
echo And run:  ollama pull qwen3:8b
pause
exit /b 1

:run_failed
echo Local run failed. Review the message above and the JSONL error records.
pause
exit /b 1
