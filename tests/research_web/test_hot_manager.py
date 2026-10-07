"""Owned Hot process identities are verified before any signal or RPC."""

import json
import tempfile
import signal
import unittest
from pathlib import Path
from unittest.mock import patch

from research_workbench_entrypoint.hot import HotError
from research_workbench_entrypoint.hot_manager import HotManager
from research_workbench_entrypoint.hot_postgres import IMAGE, ManagedPostgres


class MemoryCredentials:
    def get_password(self, service, account):
        return "a" * 64


class HotManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name).resolve()
        self.manager = HotManager(Path("/project"), self.home, MemoryCredentials())

    def tearDown(self):
        self.temporary.cleanup()

    def state(self):
        self.manager.directory.mkdir(mode=0o700)
        path = self.manager.state_path
        path.write_text(json.dumps({"version": 1, "projectRoot": "/project", "pid": 123,
                                   "fingerprint": "expected launch", "launchId": "a" * 32}))
        path.chmod(0o600)

    def test_missing_process_state_does_not_create_resources(self):
        self.assertEqual(self.manager.status(), {"state": "stopped"})
        self.assertFalse(self.manager.directory.exists())

    def test_reused_pid_is_never_signaled(self):
        self.state()
        with patch.object(self.manager, "_fingerprint", return_value="foreign process"):
            with patch("os.kill") as killed:
                with self.assertRaisesRegex(HotError, "hot_process_identity_mismatch"):
                    self.manager.stop()
                killed.assert_not_called()

    def test_foreign_project_state_is_rejected(self):
        self.state()
        self.manager.project = Path("/other-project")
        with self.assertRaisesRegex(HotError, "hot_process_foreign"):
            self.manager.status()

    def test_stopped_public_database_is_rejected_before_start(self):
        database = ManagedPostgres(self.home, "11111111-1111-4111-8111-111111111111")
        (self.home / "hot").mkdir(mode=0o700)
        secret = self.home / "hot" / "pg-secret-export" / "password"
        container = {
            "Config": {"Image": IMAGE, "Labels": {"rwb.hot.instance": database.instance}},
            "Mounts": [
                {"Type": "volume", "Name": database.volume, "Destination": "/var/lib/postgresql/data"},
                {"Type": "bind", "Source": str(secret), "Destination": "/run/rwb-pg-password", "RW": False},
            ],
            "HostConfig": {"PortBindings": {"5432/tcp": [{"HostIp": "0.0.0.0"}]}, "NetworkMode": "default"},
            "State": {"Running": False},
        }
        calls = []

        def docker(args, timeout=30):
            calls.append(args)
            if args[:2] == ["volume", "ls"]:
                return database.volume
            if args[:2] == ["volume", "inspect"]:
                return json.dumps([{"Labels": {"rwb.hot.instance": database.instance}}])
            if args[:2] == ["ps", "-a"]:
                return database.name
            if args[0] == "inspect":
                return json.dumps([container])
            self.fail("Unexpected Docker mutation: " + args[0])

        with patch.object(database, "_docker", side_effect=docker):
            with self.assertRaisesRegex(HotError, "hot_postgres_public_binding"):
                database.start("a" * 64)
        self.assertFalse(any(args[0] in ("start", "run") for args in calls))

    def test_unsafe_runtime_log_never_launches_child(self):
        self.manager.project = self.home / "project"
        self.manager.project.mkdir()
        self.manager.directory.mkdir(mode=0o700)
        identity = self.manager.directory / "identity.json"
        identity.write_text(json.dumps({"projectRoot": str(self.manager.project),
                                        "instanceId": "11111111-1111-4111-8111-111111111111"}))
        identity.chmod(0o600)
        runtime_log = self.manager.project / "logs" / "hot" / "runtime.log"
        runtime_log.parent.mkdir(parents=True)
        runtime_log.write_text("")
        runtime_log.chmod(0o644)
        config = {"enabled": True, "database": {"mode": "external", "secretRef": "worker",
                  "controllerUser": "controller", "controllerSecretRef": "controller"}}
        with patch.object(self.manager, "_config", return_value=config):
            with patch("subprocess.Popen") as launched:
                with self.assertRaisesRegex(HotError, "hot_start_failed"):
                    self.manager.start()
                launched.assert_not_called()

    def test_unknown_archive_prevents_repetition_before_configuration_or_credentials(self):
        self.manager.directory.mkdir(mode=0o700)
        journal = self.manager.directory / "archive-attempt.json"
        journal.write_text(json.dumps({"version": 1, "state": "outcome_unknown"}))
        journal.chmod(0o600)
        with patch.object(self.manager, "_config") as configured:
            with self.assertRaisesRegex(HotError, "hot_archive_outcome_unknown"):
                self.manager.archive("backup")
            configured.assert_not_called()

    def test_interrupted_archive_signals_and_reaps_child_and_records_unknown(self):
        self.manager.directory.mkdir(mode=0o700)
        identity = self.manager.directory / "identity.json"
        identity.write_text(json.dumps({"projectRoot": "/project", "instanceId": "11111111-1111-4111-8111-111111111111"}))
        identity.chmod(0o600)
        config = {"database": {"mode": "external"}, "retention": {"backupDirectory": "hot/backups"}}

        class InterruptedChild:
            def __init__(self):
                self.signals = []
                self.calls = 0
                self.returncode = None
            def communicate(self, payload=None, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    raise KeyboardInterrupt()
                self.returncode = 1
                return "", ""
            def poll(self):
                return self.returncode
            def send_signal(self, value):
                self.signals.append(value)

        child = InterruptedChild()
        with patch.object(self.manager, "_config", return_value=config):
            with patch("research_workbench_entrypoint.hot_manager._node", return_value="node"):
                with patch("subprocess.Popen", return_value=child):
                    with self.assertRaises(KeyboardInterrupt):
                        self.manager.archive("backup")
        self.assertEqual(child.signals, [signal.SIGTERM])
        self.assertEqual(child.calls, 2)
        value = json.loads((self.manager.directory / "archive-attempt.json").read_text())
        self.assertEqual(value["state"], "outcome_unknown")
