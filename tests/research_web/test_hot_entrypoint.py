"""Hot stdlib configuration is separate from research and credential startup."""

import json
import tempfile
import unittest
import os
import io
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock
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

    def test_new_cli_commands_dispatch_filters_and_unknown_mutation_exit(self):
        manager = MagicMock()
        manager.events.return_value = {"cutoff": "2026-10-08T00:00:00Z", "items": []}
        manager.configure_channel.return_value = {"channelId": "gold", "version": 1}
        request = "11111111-1111-4111-8111-111111111111"
        manager.correct_event.return_value = {"state": "outcome_unknown", "requestId": request}
        config = {"name": "Gold", "topics": [], "sourceIds": [], "importanceRules": []}
        config_file = self.home / "channels.json"
        config_file.write_text(json.dumps({"version": 1, "channels": {"gold": config}}))
        change = {"type": "title", "id": request, "expected": 1, "title": "Human"}
        correction_file = self.home / "correction.json"
        correction_file.write_text(json.dumps(change))
        with patch("research_workbench_entrypoint.bootstrap.native_python", return_value=Path(os.sys.executable)):
            with patch.dict("sys.modules", {"app.research_web.credential_backend": SimpleNamespace(SystemKeyringBackend=lambda: object())}):
                with patch("research_workbench_entrypoint.hot_manager.HotManager", return_value=manager):
                    with redirect_stdout(io.StringIO()):
                        self.assertEqual(hot.dispatch(["events", "--channel", "gold", "--query", "bank", "--sort", "importance", "--limit", "5"], self.home), 0)
                        self.assertEqual(hot.dispatch(["channel-configure", "gold", "--expected-version", "0", "--file", str(config_file), "--request-id", request], self.home), 0)
                        self.assertEqual(hot.dispatch(["event-correct", "--file", str(correction_file), "--reason", "Reviewed", "--request-id", request], self.home), 1)
        manager.events.assert_called_once_with({"channelId": "gold", "q": "bank", "sort": "importance", "limit": 5, "offset": 0})
        manager.configure_channel.assert_called_once_with("gold", 0, config, request)
        manager.correct_event.assert_called_once_with(change, "Reviewed", request)


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


class DockerHotLogTests(unittest.TestCase):
    def test_configuration_log_uses_writable_private_home_in_guest(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory).resolve()
            with patch.dict('os.environ',{'RESEARCH_RUN_MODE':'web-prod','RESEARCH_CREDENTIAL_HOME':'/run/rwb-secrets/private','RWB_DATA_ROOT':str(home)},clear=True),patch('os.path.isfile',return_value=True):
                hot._record_configuration(Path('/read-only/project'),home)
            path=home/'hot/logs/configuration.jsonl'
            self.assertTrue(path.is_file())
            self.assertEqual(json.loads(path.read_text())['event'],'hot_configuration_saved')
