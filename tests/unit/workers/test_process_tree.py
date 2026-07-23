"""workers/_process_tree.py 单元测试 — Job Object 进程树绑定"""

import sys

import pytest


class TestEnsureChildDiesWithParent:
    """测试 ensure_child_dies_with_parent"""

    @pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")
    def test_windows_returns_job_handle_for_real_process(self):
        """Windows 上对一个真实短命子进程应返回非 None 的 Job handle"""
        import subprocess

        from workers._process_tree import ensure_child_dies_with_parent

        # 启动一个能存活几秒的子进程（ping -n 5 约存活 4 秒）
        proc = subprocess.Popen(
            ["ping", "-n", "5", "127.0.0.1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            handle = ensure_child_dies_with_parent(proc.pid)
            # Windows 上应返回 Job handle（非 None）
            assert handle is not None
        finally:
            proc.terminate()
            proc.wait()

    def test_non_windows_returns_none(self, monkeypatch):
        """非 Windows 平台应返回 None（依赖 POSIX 进程组）"""
        from workers import _process_tree

        monkeypatch.setattr(_process_tree, "_IS_WINDOWS", False)
        handle = _process_tree.ensure_child_dies_with_parent(99999)
        assert handle is None

    @pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")
    def test_windows_child_killed_when_job_handle_closed(self):
        """显式 CloseHandle(Job) 后，子进程应被 OS 自动终止（KILL_ON_JOB_CLOSE 语义）

        模拟 watchdog 进程退出时 OS 关闭其持有的 Job handle。
        注意：ctypes 返回的整数句柄不会因 Python 变量 del 而关闭，
        必须显式 CloseHandle；真实场景下 watchdog 进程退出时 OS 会自动关闭。
        """
        import ctypes
        import subprocess
        import time

        from workers._process_tree import ensure_child_dies_with_parent

        proc = subprocess.Popen(
            ["ping", "-n", "30", "127.0.0.1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            handle = ensure_child_dies_with_parent(proc.pid)
            assert handle is not None
            # 子进程此时应存活
            assert proc.poll() is None

            # 显式关闭 Job handle（模拟 watchdog 进程退出时 OS 回收 handle）
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
            kernel32.CloseHandle(handle)
            # 给 OS 一点时间回收 Job 并终止子进程
            time.sleep(0.5)

            # 子进程应已被 Job 终止
            import psutil

            alive = psutil.pid_exists(proc.pid)
            assert not alive, "子进程应在 Job handle 关闭后被自动终止"
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
