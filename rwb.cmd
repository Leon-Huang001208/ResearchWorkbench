@echo off
setlocal EnableExtensions DisableDelayedExpansion
for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"
set "PYTHON_BIN=%PROJECT_ROOT%\.venv\Scripts\python.exe"

cd /d "%PROJECT_ROOT%"
py -3.12 -c "import sys; raise SystemExit(not sys.version_info >= (3,12))" >nul 2>&1
if not errorlevel 1 (
  py -3.12 -m research_workbench_entrypoint.bootstrap %*
  exit /b
)
python -c "import sys; raise SystemExit(not sys.version_info >= (3,12))" >nul 2>&1
if not errorlevel 1 (
  python -m research_workbench_entrypoint.bootstrap %*
  exit /b
)
if not exist "%PYTHON_BIN%" (
  echo Research Workbench requires host Python 3.12 or newer. Run setup-web.cmd first. 1>&2
  exit /b 1
)
"%PYTHON_BIN%" -m research_workbench_entrypoint.bootstrap %*
exit /b %errorlevel%
