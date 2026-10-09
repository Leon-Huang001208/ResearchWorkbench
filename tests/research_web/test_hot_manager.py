"""Owned Hot process identities are verified before any signal or RPC."""

import json
import tempfile
import signal
from types import SimpleNamespace
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
        with self.assertRaisesRegex(HotError, "hot_service_stopped"):
            self.manager.sources()

    def test_event_projections_use_reader_and_keep_filter_cutoff(self):
        with patch.object(self.manager, "_state", return_value={"port": 1234, "owner": {}}):
            with patch.object(self.manager, "_secret", return_value="reader") as secret:
                with patch("research_workbench_entrypoint.hot_manager.rpc", return_value={"cutoff": "2026-10-08T00:00:00Z", "items": []}) as call:
                    self.manager.events({"channelId": "gold", "cutoff": "2026-10-08T00:00:00Z", "offset": 20})
                    secret.assert_called_once_with("rpc-reader")
                    self.assertEqual(call.call_args.args[3], "events.list")
                    self.assertEqual(call.call_args.args[4]["offset"], 20)

    def test_brief_reads_and_export_use_reader_and_validate_identity(self):
        brief = "22222222-2222-4222-8222-222222222222"
        reply = {"briefId": brief, "version": 1, "contentHash": "a" * 64, "payload": {"schemaVersion": 1}}
        with patch.object(self.manager, "_state", return_value={"port": 1234, "owner": {}}), patch.object(self.manager, "_secret", return_value="reader") as secret:
            with patch("research_workbench_entrypoint.hot_manager.rpc", return_value=reply) as call:
                self.assertEqual(self.manager.brief_detail(brief, 1), reply)
                self.assertEqual(call.call_args.args[3], "brief.get")
                secret.assert_called_once_with("rpc-reader")
            with patch("research_workbench_entrypoint.hot_manager.rpc", return_value={**reply, "briefId": "foreign"}):
                with self.assertRaisesRegex(HotError, "hot_rpc_invalid"):
                    self.manager.brief_detail(brief, 1)
        with patch.object(self.manager, "_secret") as secret:
            with self.assertRaisesRegex(HotError, "hot_brief_identity_invalid"):
                self.manager.brief_detail("../foreign", 1)
            secret.assert_not_called()

    def test_brief_creation_keeps_unknown_uuid_and_rejects_input_before_keys(self):
        self.manager.directory.mkdir(mode=0o700)
        request = "11111111-1111-4111-8111-111111111111"
        params = {"briefId": request, "expectedVersion": 0, "eventIds": [request], "channelId": "macro", "cutoff": "2026-10-08T00:00:00Z"}
        with patch.object(self.manager, "_state", return_value={"port": 1234, "owner": {}}), patch("research_workbench_entrypoint.hot_manager.rpc", side_effect=HotError("hot_rpc_timeout")):
            result = self.manager.create_brief(params, request)
            self.assertEqual(result["state"], "outcome_unknown")
            self.assertEqual(result["requestId"], request)
        with patch.object(self.manager, "_secret") as secret:
            with self.assertRaisesRegex(HotError, "hot_brief_params_invalid"):
                self.manager.create_brief({**params, "expectedVersion": True}, request)
            secret.assert_not_called()

    def test_brief_export_assembles_fixed_version_chunks_and_rejects_hash_mismatch(self):
        import hashlib
        brief = "22222222-2222-4222-8222-222222222222"
        text = "&" * 32768 + "中文🙂"
        encoded = text.encode()
        base = {"briefId": brief, "version": 2, "contentHash": "a" * 64, "format": "markdown", "totalBytes": len(encoded), "textHash": hashlib.sha256(encoded).hexdigest()}
        chunks = [{**base, "offset": 0, "nextOffset": 32768, "text": "&" * 32768}, {**base, "offset": 32768, "nextOffset": None, "text": "中文🙂"}]
        with patch.object(self.manager, "_state", return_value={"port": 1234, "owner": {}}), patch.object(self.manager, "_secret", return_value="reader"):
            with patch("research_workbench_entrypoint.hot_manager.rpc", side_effect=chunks) as call:
                self.assertEqual(self.manager.brief_export(brief)["text"], text)
                self.assertEqual(call.call_args.args[4], {"briefId": brief, "version": 2, "offset": 32768})
            with patch("research_workbench_entrypoint.hot_manager.rpc", side_effect=[chunks[0], {**chunks[1], "text": "changed"}]):
                with self.assertRaisesRegex(HotError, "hot_rpc_invalid"):
                    self.manager.brief_export(brief, 2)

    def test_channel_control_unknown_keeps_uuid_and_uses_controller(self):
        self.manager.directory.mkdir(mode=0o700)
        request = "11111111-1111-4111-8111-111111111111"
        config = {"name": "Gold", "topics": [], "sourceIds": [], "importanceRules": []}
        with patch.object(self.manager, "_state", return_value={"port": 1234, "owner": {}}):
            for code in ("hot_rpc_timeout", "hot_rpc_response_untrusted", "hot_owner_stale"):
                with patch.object(self.manager, "_secret", return_value="controller") as secret:
                    with patch("research_workbench_entrypoint.hot_manager.rpc", side_effect=HotError(code)):
                        result = self.manager.configure_channel("gold", 0, config, request)
                        self.assertEqual(result["state"], "outcome_unknown")
                        self.assertEqual(result["requestId"], request)
                        secret.assert_called_once_with("rpc-controller")
            with patch("research_workbench_entrypoint.hot_manager.rpc", return_value={"channelId": "gold", "version": 1, "requestId": request, "config": config}):
                self.assertEqual(self.manager.configure_channel("gold", 0, config, request)["version"], 1)
            with patch("research_workbench_entrypoint.hot_manager.rpc", return_value={}):
                self.assertEqual(self.manager.configure_channel("gold", 0, config, request)["requestId"], request)
            with patch("research_workbench_entrypoint.hot_manager.rpc", side_effect=HotError("hot_channel_revision_conflict")):
                with self.assertRaisesRegex(HotError, "hot_channel_revision_conflict"):
                    self.manager.configure_channel("gold", 0, config, request)

    def test_event_control_validates_receipt_and_retains_unknown_request(self):
        self.manager.directory.mkdir(mode=0o700)
        request = "11111111-1111-4111-8111-111111111111"
        event = "22222222-2222-4222-8222-222222222222"
        change = {"type": "title", "id": event, "expected": 1, "title": "Human title"}
        with patch.object(self.manager, "_state", return_value={"port": 1234, "owner": {}}):
            with patch("research_workbench_entrypoint.hot_manager.rpc", return_value={"source": {"id": event, "revision": 2, "snapshot": {"state": "active", "title": "Human title", "manual": {"title": True}}}}):
                self.assertEqual(self.manager.correct_event(change, "Reviewed", request)["requestId"], request)
            with patch("research_workbench_entrypoint.hot_manager.rpc", return_value={"source": {"id": event, "revision": 999, "snapshot": {}}}):
                self.assertEqual(self.manager.correct_event(change, "Reviewed", request)["state"], "outcome_unknown")
            with patch.object(self.manager, "_secret") as secret:
                with self.assertRaisesRegex(HotError, "hot_event_correction_invalid"):
                    self.manager.correct_event({**change, "expected": True}, "Reviewed", request)
                secret.assert_not_called()

    def test_incomplete_operation_specific_receipts_keep_uuid(self):
        self.manager.directory.mkdir(mode=0o700)
        request = "11111111-1111-4111-8111-111111111111"
        event = "22222222-2222-4222-8222-222222222222"
        target = "33333333-3333-4333-8333-333333333333"
        cases = [
            ({"type": "channels", "id": event, "expected": 1, "channelIds": ["gold"]}, {"state": "active", "manual": {"channels": []}}),
            ({"type": "merge", "id": event, "expected": 1, "target": target, "targetExpected": 1}, {"state": "merged", "canonicalId": event, "materials": []}),
            ({"type": "split", "id": event, "expected": 1, "materialIds": [target], "title": "Split"}, {"state": "active", "materials": [], "manual": {"excluded": [target]}}),
        ]
        with patch.object(self.manager, "_state", return_value={"port": 1234, "owner": {}}):
            for change, snapshot in cases:
                response = {"source": {"id": event, "revision": 2, "snapshot": snapshot}, "target": {"id": target, "revision": 2, "snapshot": {"state": "active", "title": "Wrong", "materials": [], "manual": {"protected": []}}}}
                with patch("research_workbench_entrypoint.hot_manager.rpc", return_value=response):
                    value = self.manager.correct_event(change, "Reviewed", request)
                    self.assertEqual(value["state"], "outcome_unknown")
                    self.assertEqual(value["requestId"], request)

    def test_invalid_control_structure_never_resolves_key(self):
        event = "22222222-2222-4222-8222-222222222222"
        cases = [{"type": "title", "id": event, "expected": 1, "title": []},
                 {"type": "split", "id": event, "expected": 1, "materialIds": [], "title": "Split"},
                 {"type": "channels", "id": event, "expected": 1, "channelIds": ["gold", "gold"]}]
        with patch.object(self.manager, "_secret") as secret:
            for change in cases:
                with self.assertRaisesRegex(HotError, "hot_event_correction_invalid"):
                    self.manager.correct_event(change, "Reviewed")
            with self.assertRaisesRegex(HotError, "hot_channel_request_invalid"):
                self.manager.configure_channel("gold", 0, {"name": "Gold", "topics": True})
            secret.assert_not_called()

    def test_source_control_uses_controller_key_and_preserves_request_id(self):
        self.manager.directory.mkdir(mode=0o700)
        request = "11111111-1111-4111-8111-111111111111"
        with patch.object(self.manager, "_state", return_value={"port": 1234, "owner": {}}):
            with patch.object(self.manager, "_secret", return_value="test-controller") as secret:
                with patch("research_workbench_entrypoint.hot_manager.rpc", return_value={"sourceId": "fed", "revision": "3", "enabled": False, "requestId": request, "frequencySeconds": None}) as call:
                    self.manager.configure_source("fed", "2", False, 0, request)
                    secret.assert_called_once_with("rpc-controller")
                    self.assertEqual(call.call_args.args[3], "source.configure")
                    self.assertEqual(call.call_args.args[4], {"sourceId": "fed", "expectedRevision": "2", "enabled": False, "frequencySeconds": None})
                    self.assertEqual(call.call_args.args[5], request)

    def test_unknown_source_control_returns_id_for_safe_replay(self):
        self.manager.directory.mkdir(mode=0o700)
        request = "11111111-1111-4111-8111-111111111111"
        with patch.object(self.manager, "_state", return_value={"port": 1234, "owner": {}}):
            for code in ("hot_rpc_timeout", "hot_rpc_response_untrusted", "hot_owner_stale"):
                with patch("research_workbench_entrypoint.hot_manager.rpc", side_effect=HotError(code)):
                    value = self.manager.configure_source("fed", "0", False, request_id=request)
                    self.assertEqual(value["state"], "outcome_unknown")
                    self.assertEqual(value["requestId"], request)
            with patch("research_workbench_entrypoint.hot_manager.rpc", return_value={}):
                value = self.manager.configure_source("fed", "0", False, request_id=request)
                self.assertEqual(value["state"], "outcome_unknown")
                self.assertEqual(value["requestId"], request)

    def test_bad_source_frequency_does_not_resolve_credentials(self):
        self.manager.directory.mkdir(mode=0o700)
        with patch.object(self.manager, "_state", return_value={"port": 1234, "owner": {}}):
            with patch.object(self.manager, "_secret") as secret:
                with self.assertRaisesRegex(HotError, "hot_source_config_invalid"):
                    self.manager.configure_source("fed", "0", frequency=5)
                secret.assert_not_called()

    def test_malformed_rpc_frame_keeps_mutation_request_id(self):
        self.manager.directory.mkdir(mode=0o700)
        request = "11111111-1111-4111-8111-111111111111"
        class Peer:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return None
            def sendall(self, data):
                return None
            def settimeout(self, seconds):
                return None
            def recv(self, size):
                return b'{"data":1,"proof":"x"}\n'
        with patch.object(self.manager, "_state", return_value={"port": 1234, "owner": {}}):
            with patch("socket.create_connection", return_value=Peer()):
                value = self.manager.configure_source("fed", "0", False, request_id=request)
                self.assertEqual(value["state"], "outcome_unknown")
                self.assertEqual(value["requestId"], request)

    def test_zombie_fingerprint_is_stopped(self):
        with patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="Z Wed Oct 7 12:00:00 2026 node <defunct>")):
            self.assertIsNone(self.manager._fingerprint(123))

    def test_exiting_argv_is_observed_without_another_signal(self):
        with patch.object(self.manager, "_state", return_value={"pid": 123, "fingerprint": "original"}):
            with patch.object(self.manager, "_fingerprint", side_effect=["exiting argv", None]):
                with patch("time.sleep"), patch("os.kill") as killed:
                    self.assertEqual(self.manager._stop(), {"state": "stopped"})
                    killed.assert_called_once_with(123, signal.SIGTERM)

    def test_exit_at_escalation_boundary_is_stopped_without_kill(self):
        with patch.object(self.manager, "_state", return_value={"pid": 123, "fingerprint": "original"}):
            with patch.object(self.manager, "_fingerprint", side_effect=["original"] * 100 + [None]):
                with patch("time.sleep"), patch("os.kill") as killed:
                    self.assertEqual(self.manager._stop(), {"state": "stopped"})
                    killed.assert_called_once_with(123, signal.SIGTERM)

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
