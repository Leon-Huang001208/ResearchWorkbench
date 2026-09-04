@echo off
setlocal enabledelayedexpansion
REM ============================================================================
REM Research Workbench Windows 桌面端后端启动脚本 (cmd 原生, 不需要 Git Bash)
REM
REM 用法:
REM   scripts\desktop\run_backend.cmd
REM   scripts\desktop\run_backend.cmd --port 8766
REM   scripts\desktop\run_backend.cmd --host 0.0.0.0 --port 8765 --reload
REM
REM 默认带 --reload 以支持开发时自动重载 Python 代码
REM ============================================================================

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%..\.."

REM ── 解析 Python 解释器 ───────────────────────────────────────────
set "PYTHON_BIN="

REM 1. 环境变量覆盖
if defined RESEARCH_PYTHON (
    if exist "%RESEARCH_PYTHON%" (
        set "PYTHON_BIN=%RESEARCH_PYTHON%"
    )
)

REM 2. research_workbench conda 环境 (最高优先级自动探测)
if not defined PYTHON_BIN (
    if exist "%USERPROFILE%\AppData\Local\anaconda3\envs\research_workbench\python.exe" (
        set "PYTHON_BIN=%USERPROFILE%\AppData\Local\anaconda3\envs\research_workbench\python.exe"
    )
)
if not defined PYTHON_BIN (
    if exist "%USERPROFILE%\anaconda3\envs\research_workbench\python.exe" (
        set "PYTHON_BIN=%USERPROFILE%\anaconda3\envs\research_workbench\python.exe"
    )
)
if not defined PYTHON_BIN (
    if exist "%USERPROFILE%\miniforge3\envs\research_workbench\python.exe" (
        set "PYTHON_BIN=%USERPROFILE%\miniforge3\envs\research_workbench\python.exe"
    )
)

REM 3. 系统 Anaconda base
if not defined PYTHON_BIN (
    if exist "%USERPROFILE%\AppData\Local\anaconda3\python.exe" (
        set "PYTHON_BIN=%USERPROFILE%\AppData\Local\anaconda3\python.exe"
    )
)
if not defined PYTHON_BIN (
    if exist "%USERPROFILE%\anaconda3\python.exe" (
        set "PYTHON_BIN=%USERPROFILE%\anaconda3\python.exe"
    )
)

REM 4. PATH 上的 python / python3
if not defined PYTHON_BIN (
    where python3 >nul 2>&1 && (
        for /f "delims=" %%i in ('where python3') do set "PYTHON_BIN=%%i"
    )
)
if not defined PYTHON_BIN (
    where python >nul 2>&1 && (
        for /f "delims=" %%i in ('where python') do set "PYTHON_BIN=%%i"
    )
)

REM ── 检查是否找到 Python ────────────────────────────────────────
if not defined PYTHON_BIN (
    echo [ERROR] Cannot find Python interpreter.
    echo         Set RESEARCH_PYTHON env var or install Anaconda with research_workbench environment.
    exit /b 1
)

echo [Research Workbench] Using Python: %PYTHON_BIN%

REM ── 设置桌面环境变量 ──────────────────────────────────────────
set "RESEARCH_DESKTOP=1"
set "RESEARCH_DESKTOP_URL=http://127.0.0.1:8765"
set "RESEARCH_DEV=1"

REM ── 默认启用 reload（如果命令行没有传 --reload 则追加）────────
set "HAS_RELOAD=0"
:parse_args
if "%~1"=="" goto :run
if /i "%~1"=="--reload" set "HAS_RELOAD=1"
shift
goto :parse_args

:run
REM 重新组装参数，如果没传 --reload 就加上
set "ALL_ARGS=%*"
if !HAS_RELOAD!==0 (
    set "ALL_ARGS=--reload !ALL_ARGS!"
)

REM ── 启动前清理 __pycache__（防止 .pyc 损坏导致 ACCESS_VIOLATION）──
REM    反复 taskkill 强杀进程中 .pyc 文件可能处于半写状态，导致下次
REM    Python 导入时 C 扩展 DLL 出现 use-after-free 内存访问违规。
echo [Pre-start] Cleaning __pycache__ directories...
for /d /r "%REPO_ROOT%" %%D in (__pycache__) do (
    if exist "%%D" rd /s /q "%%D" 2>nul
)

REM ── 启动前清理占用端口的僵尸进程 ─────────────────────────────
REM    uvicorn --reload fork 出的 worker 子进程在父进程被杀后可能
REM    残留在 Windows 上继续占用端口，导致下次启动失败。
REM    macOS 版有 restart_app.sh 的 lsof 清理，此处为 Windows 等价逻辑。
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R ":8765.*LISTENING" 2^>nul') do (
    echo [Pre-start] Killing stale process on port 8765: PID=%%P
    taskkill /F /PID %%P >nul 2>&1
)
timeout /t 2 /nobreak >nul 2>&1

REM ── 启动后端 ──────────────────────────────────────────────────
cd /d "%REPO_ROOT%"
"%PYTHON_BIN%" "%REPO_ROOT%\scripts\desktop\backend_launcher.py" !ALL_ARGS!

set "EXIT_CODE=%ERRORLEVEL%"
exit /b %EXIT_CODE%
