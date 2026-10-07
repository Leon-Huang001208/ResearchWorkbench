"""Hot stdlib configuration is separate from research and credential startup."""

import json
import tempfile
import unittest
import os
import io
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from research_workbench_entrypoint import hot


class HotEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.temporary.cleanup()

    def test_disabled_status_is_read_only(self):
        home = self.home / "uncreated"
        result = hot.status(Path("/project"), home)
        self.assertEqual(result["state"], "disabled")
        self.assertFalse(home.exists())


    def test_secret_config_is_rejected_before_writing(self):
        home = self.home / "new-home"
        with patch.object(hot, "normalize", side_effect=hot.HotError("hot_config_invalid")):
            with self.assertRaisesRegex(hot.HotError, "hot_config_invalid"):
                hot.save_settings(Path("/project"), home, {"password": "not-a-real-secret"})
        self.assertFalse(home.exists())


    def test_atomic_settings_keep_project_ownership(self):
        project = self.home / "project"
        project.mkdir()
        with patch.object(hot, "normalize", return_value={"enabled": True}):
            self.assertEqual(hot.save_settings(project, self.home, {})["state"], "configured")
            path = self.home / "hot" / "settings.json"
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text())["projectRoot"], str(project))
            with self.assertRaisesRegex(hot.HotError, "hot_foreign_config"):
                hot.save_settings(Path("/other-worktree"), self.home, {})


    def test_alias_directory_is_rejected(self):
        (self.home / "real").mkdir()
        (self.home / "hot").symlink_to(self.home / "real", target_is_directory=True)
        with self.assertRaisesRegex(hot.HotError, "hot_storage_unsafe"):
            hot.status(Path("/project"), self.home)

    def test_fifo_is_rejected_without_waiting_for_writer(self):
        path = self.home / "pipe"
        os.mkfifo(path)
        with self.assertRaisesRegex(hot.HotError, "hot_config_unsafe"):
            hot._read(path)

    def test_directory_errors_are_safe(self):
        with patch.object(hot, "normalize", return_value={"enabled": False}):
            with patch.object(Path, "mkdir", side_effect=PermissionError("private path")):
                with self.assertRaisesRegex(hot.HotError, "hot_storage_unavailable"):
                    hot.save_settings(Path("/project"), self.home, {})

    def test_unknown_arguments_do_not_echo_values(self):
        output = io.StringIO()
        with redirect_stderr(output):
            with self.assertRaises(SystemExit) as error:
                hot.dispatch(["status", "--password", "SENTINEL_DO_NOT_ECHO"], Path("/project"))
        self.assertEqual(error.exception.code, 2)
        self.assertNotIn("SENTINEL", output.getvalue())

    def test_fifo_log_does_not_block_and_saved_state_is_reported(self):
        project = self.home / "project"
        logs = project / "logs" / "hot"
        logs.mkdir(parents=True)
        os.mkfifo(logs / "configuration.jsonl")
        with patch.object(hot, "normalize", return_value={"enabled": False}):
            result = hot.save_settings(project, self.home, {})
        self.assertTrue(result["config_saved"])
        self.assertEqual(result["logging"], "unavailable")
        self.assertTrue((self.home / "hot" / "settings.json").exists())
