@echo off
setlocal EnableExtensions DisableDelayedExpansion
for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"
set "PYTHON_BIN=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "ENVIRONMENT_OWNER_ROOT=%PROJECT_ROOT%"

if defined PYTHONPATH (
  set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%PROJECT_ROOT%"
)
cd /d "%PROJECT_ROOT%"
if not exist "%PYTHON_BIN%" goto bootstrap
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 goto validate_environment_py
python3 -c "import sys" >nul 2>&1
if not errorlevel 1 goto validate_environment_python3
python -c "import sys" >nul 2>&1
if not errorlevel 1 goto validate_environment_python
goto validate_environment_candidate

:validate_environment_py
py -3.12 -c "import sys; from pathlib import Path; from research_workbench_entrypoint.web_contract import classify_python_environment; sys.exit(0 if classify_python_environment(Path(sys.argv[1])).issue is None else 1)" "%ENVIRONMENT_OWNER_ROOT%" >nul 2>&1
if errorlevel 1 goto bootstrap_unusable
goto probe_normal_entrypoint

:validate_environment_python3
python3 -c "import sys; from pathlib import Path; from research_workbench_entrypoint.web_contract import classify_python_environment; sys.exit(0 if classify_python_environment(Path(sys.argv[1])).issue is None else 1)" "%ENVIRONMENT_OWNER_ROOT%" >nul 2>&1
if errorlevel 1 goto bootstrap_unusable
goto probe_normal_entrypoint

:validate_environment_python
python -c "import sys; from pathlib import Path; from research_workbench_entrypoint.web_contract import classify_python_environment; sys.exit(0 if classify_python_environment(Path(sys.argv[1])).issue is None else 1)" "%ENVIRONMENT_OWNER_ROOT%" >nul 2>&1
if errorlevel 1 goto bootstrap_unusable
goto probe_normal_entrypoint

:validate_environment_candidate
"%PYTHON_BIN%" -c "import sys; from pathlib import Path; from research_workbench_entrypoint.web_contract import classify_python_environment; sys.exit(0 if classify_python_environment(Path(sys.argv[1])).issue is None else 1)" "%ENVIRONMENT_OWNER_ROOT%" >nul 2>&1
if errorlevel 1 goto bootstrap_unusable

:probe_normal_entrypoint
"%PYTHON_BIN%" -c "import click; import app.cli.main" >nul 2>&1
if errorlevel 1 goto bootstrap_unusable
"%PYTHON_BIN%" -m research_workbench_entrypoint %*
exit /b %errorlevel%

:bootstrap_unusable
set "RWB_BOOTSTRAP_PYTHON_ISSUE=python_environment_unusable"
goto bootstrap

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
