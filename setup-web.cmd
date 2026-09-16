@echo off
setlocal EnableExtensions DisableDelayedExpansion
for %%I in ("%~dp0.") do set "PROJECT_ROOT=%%~fI"

where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
  if not errorlevel 1 (
    py -3.12 "%PROJECT_ROOT%\scripts\setup_web.py" %*
    exit /b %errorlevel%
  )
)

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.12 was not found. Install it and run setup-web.cmd again. 1>&2
  exit /b 1
)
python "%PROJECT_ROOT%\scripts\setup_web.py" %*
exit /b %errorlevel%
