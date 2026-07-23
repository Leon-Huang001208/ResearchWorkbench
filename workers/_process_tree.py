"""跨平台进程树管理 — 保证 worker 子进程随 watchdog 退出而终止。

Windows 上 ``subprocess.Popen`` 启动的子进程不会因父进程退出而自动终止
（``proc.terminate()`` 也是直接 ``TerminateProcess``，不触发子进程信号 handler），
导致 watchdog 被强杀时 worker 沦为孤儿。本模块用 Windows Job Object
(``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``) 把子进程绑定到 watchdog 的 Job，
watchdog 进程退出（无论优雅还是强杀）时 OS 自动终止整个 Job 内的进程树。

非 Windows 平台依赖 POSIX 进程组（``start_new_session=True``）+ 信号 handler，
无需额外处理，``ensure_child_dies_with_parent`` 为 no-op。
"""

from __future__ import annotations

import sys
from typing import Any

from core.observability import get_logger

logger = get_logger(__name__)

_IS_WINDOWS = sys.platform.startswith("win")

# Windows Job Object 相关常量
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB = 0x00002000  # 别名，与上面等价


def _load_kernel32() -> Any:
    """加载 Windows kernel32.dll，返回 ctypes 库句柄。"""
    import ctypes

    return ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]


def _create_job_object() -> Any:
    """创建一个 KILL_ON_JOB_CLOSE 的 Job Object，返回句柄。"""
    import ctypes

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", ctypes.c_uint32),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.c_uint32),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.c_uint32),
            ("SchedulingClass", ctypes.c_uint32),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = _load_kernel32()
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise OSError(f"CreateJobObjectW failed: err={ctypes.get_last_error()}")

    info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    kernel32.SetInformationJobObject(
        handle,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    return handle


def _assign_process_to_job(job_handle: Any, pid: int) -> None:
    """把指定 PID 的进程加入 Job Object。"""
    import ctypes

    kernel32 = _load_kernel32()
    PROCESS_ALL_ACCESS = 0x1F0FFF
    inherit = False
    proc_handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, inherit, pid)
    if not proc_handle:
        raise OSError(f"OpenProcess(pid={pid}) failed: err={ctypes.get_last_error()}")
    try:
        if not kernel32.AssignProcessToJobObject(job_handle, proc_handle):
            raise OSError(
                f"AssignProcessToJobObject(pid={pid}) failed: err={ctypes.get_last_error()}"
            )
    finally:
        kernel32.CloseHandle(proc_handle)


def ensure_child_dies_with_parent(child_pid: int) -> Any | None:
    """把子进程绑定到当前进程的 Job Object，父进程退出时 OS 自动终止子进程。

    仅 Windows 生效；非 Windows 返回 None（依赖 POSIX 进程组）。
    返回 Job handle（需由调用方保持引用，handle 被 GC 回收时 Job 关闭，
    子进程立即被终止——因此调用方必须持有 handle 直到 watchdog 自身退出）。
    """
    if not _IS_WINDOWS:
        return None

    try:
        job_handle = _create_job_object()
        _assign_process_to_job(job_handle, child_pid)
        logger.info("Child bound to Job Object", pid=child_pid)
        return job_handle
    except (OSError, AttributeError) as e:
        # ctypes 不可用或 Win API 调用失败时降级，不阻断 worker 启动
        logger.warning(
            "Failed to bind child to Job Object, worker may orphan on hard kill",
            pid=child_pid,
            error=str(e),
        )
        return None
