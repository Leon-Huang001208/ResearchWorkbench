"""Worker Watchdog 单元测试"""

from unittest.mock import patch


class TestWatchdogCmdBuild:
    """测试 workers/watchdog.py 的子进程命令/环境构造"""

    def test_dev_mode_cmd_uses_module_flag(self):
        from workers.watchdog import _build_worker_cmd

        with patch("workers.watchdog._is_frozen", return_value=False):
            cmd = _build_worker_cmd("knowledge_worker", None)

        # dev 模式：[python_executable, "-m", "workers.knowledge_worker"]
        assert cmd[1:] == ["-m", "workers.knowledge_worker"]

    def test_frozen_mode_cmd_uses_exe_only(self):
        from workers.watchdog import _build_worker_cmd

        with patch("workers.watchdog._is_frozen", return_value=True):
            cmd = _build_worker_cmd("knowledge_worker", None)

        # frozen 模式只传 exe 路径，运行模式由环境变量区分
        assert len(cmd) == 1

    def test_dev_mode_env_no_worker_mode_flag(self):
        from workers.watchdog import _build_worker_env

        with patch("workers.watchdog._is_frozen", return_value=False):
            env = _build_worker_env(None)

        assert "RESEARCH_WORKER_MODE" not in env
        assert "RESEARCH_WORKER_ID" not in env

    def test_frozen_mode_env_injects_worker_mode(self):
        from workers.watchdog import _build_worker_env

        with patch("workers.watchdog._is_frozen", return_value=True):
            env = _build_worker_env(None)

        assert env["RESEARCH_WORKER_MODE"] == "1"

    def test_frozen_knowledge_worker_env_removes_watchdog_mode_flags(self):
        from workers.watchdog import _build_worker_env

        with patch.dict(
            "os.environ",
            {
                "RESEARCH_WATCHDOG_MODE": "1",
                "RESEARCH_SCHEDULER_WATCHDOG_MODE": "1",
            },
        ):
            with patch("workers.watchdog._is_frozen", return_value=True):
                env = _build_worker_env(None)

        assert "RESEARCH_WATCHDOG_MODE" not in env
        assert "RESEARCH_SCHEDULER_WATCHDOG_MODE" not in env
        assert env["RESEARCH_WORKER_MODE"] == "1"

    def test_frozen_scheduler_worker_env_removes_watchdog_mode_flags(self):
        from workers.watchdog import _build_worker_env

        with patch.dict(
            "os.environ",
            {
                "RESEARCH_WATCHDOG_MODE": "1",
                "RESEARCH_SCHEDULER_WATCHDOG_MODE": "1",
            },
        ):
            with patch("workers.watchdog._is_frozen", return_value=True):
                env = _build_worker_env(None, "RESEARCH_SCHEDULER_MODE")

        assert "RESEARCH_WATCHDOG_MODE" not in env
        assert "RESEARCH_SCHEDULER_WATCHDOG_MODE" not in env
        assert env["RESEARCH_SCHEDULER_MODE"] == "1"

    def test_worker_id_injected_into_env(self):
        from workers.watchdog import _build_worker_env

        with patch("workers.watchdog._is_frozen", return_value=True):
            env = _build_worker_env(3)

        assert env["RESEARCH_WORKER_MODE"] == "1"
        assert env["RESEARCH_WORKER_ID"] == "3"

    def test_worker_id_injected_even_in_dev_mode(self):
        from workers.watchdog import _build_worker_env

        with patch("workers.watchdog._is_frozen", return_value=False):
            env = _build_worker_env(7)

        assert env["RESEARCH_WORKER_ID"] == "7"
