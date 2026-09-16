@echo off
setlocal EnableExtensions DisableDelayedExpansion
for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"
set "PYTHON_BIN=%PROJECT_ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON_BIN%" (
  echo Research Workbench Web environment is missing. Run setup-web.cmd first. 1>&2
  exit /b 1
)

if defined PYTHONPATH (
  set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%PROJECT_ROOT%"
)
cd /d "%PROJECT_ROOT%"
"%PYTHON_BIN%" -m research_workbench_entrypoint %*
exit /b %errorlevel%
