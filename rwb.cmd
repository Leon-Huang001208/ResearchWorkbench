@echo off
setlocal EnableExtensions DisableDelayedExpansion
for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"
set "PYTHON_BIN=%PROJECT_ROOT%\.venv\Scripts\python.exe"

if defined PYTHONPATH (
  set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%PROJECT_ROOT%"
)
cd /d "%PROJECT_ROOT%"
if not exist "%PYTHON_BIN%" goto bootstrap
"%PYTHON_BIN%" -c "import click; import app.cli.main" >nul 2>&1
if errorlevel 1 (
  set "RWB_BOOTSTRAP_PYTHON_ISSUE=python_environment_unusable"
  goto bootstrap
)
"%PYTHON_BIN%" -m research_workbench_entrypoint %*
exit /b %errorlevel%

:bootstrap
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 goto bootstrap_py
where python3 >nul 2>&1
if not errorlevel 1 goto bootstrap_python3
where python >nul 2>&1
if not errorlevel 1 goto bootstrap_python
echo python_runtime_unavailable 1>&2
echo Run setup-web.cmd --repair --no-start ^(macOS: ./setup-web.sh --repair --no-start^). 1>&2
exit /b 1

:bootstrap_py
py -3.12 -m research_workbench_entrypoint.web_bootstrap %*
exit /b %errorlevel%

:bootstrap_python3
python3 -m research_workbench_entrypoint.web_bootstrap %*
exit /b %errorlevel%

:bootstrap_python
python -m research_workbench_entrypoint.web_bootstrap %*
exit /b %errorlevel%
