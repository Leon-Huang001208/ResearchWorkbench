"""Owned Native Hot process lifecycle. Credentials stay in backend and private stdin."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import selectors
import signal
import socket
import re
import secrets
import subprocess
import time
import stat
try:
    import fcntl
except ImportError:
    fcntl = None
import shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

from .hot import HotError, _node, _no_alias, _read, normalize, save_settings

log = logging.getLogger(__name__)


def rpc(port: int, owner: dict, key: str, operation: str, params: dict | None = None,
        request_id: str | None = None) -> dict | list:
    request_id = request_id or str(uuid4())
    body = {"protocol": "rwb-hot/v1", "id": request_id, **owner, "op": operation, "params": params or {}, "sentAt": int(time.time() * 1000)}
    try:
        data = base64.urlsafe_b64encode(json.dumps(body, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).decode().rstrip("=")
    except (ValueError, TypeError):
        raise HotError("hot_rpc_request_invalid") from None
    proof = hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
    payload = json.dumps({"data": data, "proof": proof}).encode() + b"\n"
    if len(payload) > 65536:
        raise HotError("hot_rpc_request_limit")
    try:
        deadline = time.monotonic() + 5
        with socket.create_connection(("127.0.0.1", port), timeout=5) as peer:
            peer.sendall(payload)
            received = b""
            while b"\n" not in received:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise HotError("hot_rpc_timeout")
                peer.settimeout(remaining)
                chunk = peer.recv(65536)
                if not chunk or len(received) + len(chunk) > 1048576:
                    raise HotError("hot_rpc_incomplete")
                received += chunk
        frame = json.loads(received.split(b"\n")[0])
        if not isinstance(frame, dict) or not isinstance(frame.get("data"), str) or not isinstance(frame.get("proof"), str):
            raise HotError("hot_rpc_response_untrusted")
        expected = hmac.new(key.encode(), frame["data"].encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, frame["proof"]):
            raise HotError("hot_rpc_response_untrusted")
        result = json.loads(base64.urlsafe_b64decode(frame["data"] + "=" * (-len(frame["data"]) % 4)))
        if not isinstance(result, dict) or type(result.get("ok")) is not bool:
            raise HotError("hot_rpc_response_untrusted")
        if result.get("id") != request_id or result.get("protocol") != "rwb-hot/v1":
            raise HotError("hot_rpc_response_untrusted")
        if not result.get("ok"):
            code = result.get("code")
            known = ("hot_source_config_invalid", "hot_source_request_invalid", "hot_source_revision_conflict",
                     "hot_source_request_conflict", "hot_source_unknown", "hot_owner_stale", "hot_rpc_denied",
                     "hot_channel_request_invalid", "hot_channel_request_conflict", "hot_channel_revision_conflict", "hot_channel_control_denied",
                     "hot_channel_invalid", "hot_channel_rule_invalid", "hot_channel_source_unknown", "hot_channel_unknown",
                     "hot_event_identity_invalid", "hot_event_revision_invalid", "hot_event_revision_conflict", "hot_event_unknown",
                     "hot_event_correction_invalid", "hot_event_request_conflict", "hot_event_control_denied", "hot_event_text_invalid",
                     "hot_event_split_invalid", "hot_event_merge_invalid", "hot_event_reassign_invalid", "hot_event_manual_conflict",
                     "hot_event_link_cycle", "hot_event_link_depth", "hot_event_graph_limit", "hot_event_alias_requires_canonical",
                     "hot_projection_params_invalid", "hot_projection_cutoff_invalid", "hot_projection_cutoff_required",
                     "hot_projection_sort_invalid", "hot_projection_channel_invalid", "hot_projection_channel_unknown",
                     "hot_projection_event_invalid", "hot_projection_event_unknown")
            raise HotError(code if code in known else "hot_rpc_unavailable")
        return result["result"]
    except HotError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise HotError("hot_rpc_unavailable") from None


class HotManager:
    """One project-owned process. Never stops a database or deletes a volume."""

    def __init__(self, project: Path, home: Path, credentials):
        self.project = project
        self.home = home
        self.credentials = credentials
        self.directory = home / "hot"
        self.state_path = self.directory / "process.json"
        self.service = "ResearchWorkbench.Hot." + hashlib.sha256(str(home).encode()).hexdigest()[:24]

    def _config(self) -> dict:
        record = _read(self.directory / "settings.json", private=True)
        if record.get("projectRoot") != str(self.project):
            raise HotError("hot_foreign_config")
        return normalize(self.project, record["config"])

    def _secret(self, account: str) -> str:
        try:
            value = self.credentials.get_password(self.service, account)
        except Exception:
            raise HotError("hot_credentials_unavailable") from None
        if not isinstance(value, str) or not value or len(value) > 4096:
            raise HotError("hot_credentials_missing")
        return value

    def _ensure_secret(self, account: str) -> str:
        try:
            value = self.credentials.get_password(self.service, account)
            if value is None:
                value = secrets.token_hex(32)
                self.credentials.set_password(self.service, account, value)
            if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
                raise HotError("hot_generated_secret_invalid")
            return value
        except HotError:
            raise
        except Exception:
            raise HotError("hot_credentials_unavailable") from None

    def setup(self, migration_user: str = "postgres", migration_account: str = "hot-migration-database") -> dict:
        with self._lock():
            if self._state() is not None:
                raise HotError("hot_setup_requires_stopped")
            config = self._config()
            self._dependencies()
            identity_path = self.directory / "identity.json"
            _no_alias(identity_path)
            if identity_path.exists():
                identity = _read(identity_path, private=True)
                if identity.get("projectRoot") != str(self.project):
                    raise HotError("hot_process_foreign")
            else:
                identity = {"projectRoot": str(self.project), "instanceId": str(uuid4())}
                descriptor = os.open(identity_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(descriptor, "w") as stream:
                    json.dump(identity, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
            controller_key = self._ensure_secret("rpc-controller")
            self._ensure_secret("rpc-reader")
            managed = config["database"]["mode"] == "managed"
            if managed:
                from .hot_postgres import ManagedPostgres

                admin_password = self._ensure_secret("hot-postgres-admin")
                server = ManagedPostgres(self.home, identity["instanceId"]).start(admin_password)
                config["database"].update({key: server[key] for key in ("host", "port")})
                worker_password = self._ensure_secret(config["database"]["secretRef"])
                controller_password = self._ensure_secret(config["database"]["controllerSecretRef"])
                migration_user = "postgres"
            else:
                admin_password = self._secret(migration_account)
                worker_password = self._secret(config["database"]["secretRef"])
                controller_password = self._secret(config["database"]["controllerSecretRef"])
            payload = {"config": config, "instanceId": identity["instanceId"], "controllerToken": controller_key,
                       "migrationUser": migration_user, "migrationPassword": admin_password,
                       "createRoles": managed, "workerPassword": worker_password, "controllerPassword": controller_password}
            try:
                result = subprocess.run([_node(), str(self.project / "services/hot/scripts/setup.ts")], input=json.dumps(payload),
                                        capture_output=True, text=True, timeout=60, cwd=self.project)
                value = json.loads(result.stdout)
                if result.returncode or value.get("state") != "configured":
                    phase = value.get("phase")
                    raise HotError("hot_setup_failed_" + phase if phase in ("input", "ownership", "roles", "migration", "identity", "queue", "grants") else "hot_setup_failed")
            except (OSError, ValueError, subprocess.SubprocessError):
                raise HotError("hot_setup_failed") from None
            saved = save_settings(self.project, self.home, config)
            if saved.get("logging") == "unavailable":
                raise HotError("hot_config_saved_log_unavailable")
            log.info("hot_setup_completed")
            return {"state": "configured", "databaseMode": config["database"]["mode"], "schema": config["database"]["schema"]}

    def _dependencies(self) -> None:
        package = self.project / "services" / "hot"
        expected = {"postgres": "3.4.9", "pg-boss": "12.34.0", "fast-xml-parser": "5.11.1"}
        try:
            ready = all(_read(package / "node_modules" / name / "package.json").get("version") == version for name, version in expected.items())
        except HotError:
            ready = False
        if ready:
            return
        npm = shutil.which("npm")
        if not npm:
            raise HotError("hot_dependency_installer_missing")
        environment = {key: value for key, value in os.environ.items() if key in {"HOME", "PATH", "TMPDIR", "TEMP", "TMP", "http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"}}
        environment["PATH"] = str(Path(_node()).parent) + os.pathsep + environment.get("PATH", "")
        try:
            result = subprocess.run([npm, "ci", "--ignore-scripts", "--no-fund", "--no-audit"], cwd=package,
                                    env=environment, capture_output=True, timeout=180)
            if result.returncode:
                raise HotError("hot_dependencies_failed")
        except (OSError, subprocess.SubprocessError):
            raise HotError("hot_dependencies_failed") from None
        log.info("hot_dependencies_installed")

    def _fingerprint(self, pid: int) -> str | None:
        try:
            result = subprocess.run(["ps", "-ww", "-p", str(pid), "-o", "stat=", "-o", "lstart=", "-o", "command="], capture_output=True, text=True, timeout=3)
            fields = result.stdout.strip().split(maxsplit=1)
            output = fields[1] if len(fields) == 2 and "Z" not in fields[0] else ""
            return output if result.returncode == 0 and output and "<defunct>" not in output else None
        except (OSError, subprocess.SubprocessError):
            raise HotError("hot_process_probe_failed") from None

    def _state(self) -> dict | None:
        _no_alias(self.state_path)
        if not self.state_path.exists():
            return None
        state = _read(self.state_path, private=True)
        if state.get("projectRoot") != str(self.project) or state.get("version") != 1:
            raise HotError("hot_process_foreign")
        if not isinstance(state.get("pid"), int) or state["pid"] <= 1 or not isinstance(state.get("fingerprint"), str):
            raise HotError("hot_process_invalid")
        current = self._fingerprint(state["pid"])
        if current is None:
            return None
        launch_id = state.get("launchId")
        expected = str(self.project / "services/hot/scripts/serve.ts")
        if not isinstance(launch_id, str) or not re.fullmatch(r"[0-9a-f]{32}", launch_id):
            raise HotError("hot_process_invalid")
        if current != state["fingerprint"] or not current.endswith(" " + expected + " " + launch_id):
            raise HotError("hot_process_identity_mismatch")
        return state

    def status(self) -> dict:
        state = self._state()
        if state is None:
            return {"state": "stopped"}
        value = rpc(state["port"], state["owner"], self._secret("rpc-reader"), "status")
        if not isinstance(value, dict):
            raise HotError("hot_rpc_invalid")
        return {"state": "initialized", "pid": state["pid"], **value}

    def sources(self) -> list:
        """Read source coverage without scheduling or launching collection."""
        state = self._state()
        if state is None:
            raise HotError("hot_service_stopped")
        value = rpc(state["port"], state["owner"], self._secret("rpc-reader"), "sources")
        if not isinstance(value, list):
            raise HotError("hot_rpc_invalid")
        return value

    def _read_projection(self, operation: str, params: dict) -> dict:
        if operation not in ("channels", "events.list", "event.detail"):
            raise HotError("hot_projection_operation_invalid")
        state = self._state()
        if state is None:
            raise HotError("hot_service_stopped")
        value = rpc(state["port"], state["owner"], self._secret("rpc-reader"), operation, params)
        list_key = "reports" if operation == "event.detail" else "items"
        if not isinstance(value, dict) or not isinstance(value.get("cutoff"), str) or not isinstance(value.get(list_key), list):
            raise HotError("hot_rpc_invalid")
        log.info("hot_projection_read")
        return value

    def channels(self, cutoff: str | None = None) -> dict:
        return self._read_projection("channels", {"cutoff": cutoff} if cutoff else {})

    def events(self, filters: dict | None = None) -> dict:
        return self._read_projection("events.list", filters or {})

    def event_detail(self, event_id: str, cutoff: str | None = None, report_offset: int = 0, report_limit: int = 20) -> dict:
        params = {"eventId": event_id, "reportOffset": report_offset, "reportLimit": report_limit}
        if cutoff:
            params["cutoff"] = cutoff
        return self._read_projection("event.detail", params)

    def _control_projection(self, operation: str, params: dict, request_id: str | None, valid_receipt) -> dict:
        if operation not in ("channel.configure", "event.correct"):
            raise HotError("hot_control_operation_invalid")
        if request_id is not None and (not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", request_id)):
            raise HotError("hot_control_request_invalid")
        try:
            if len(json.dumps(params, ensure_ascii=False, allow_nan=False).encode()) > 48000:
                raise HotError("hot_control_request_limit")
        except (ValueError, TypeError):
            raise HotError("hot_control_request_invalid") from None
        request_id = str(UUID(request_id)) if request_id else str(uuid4())
        if self._state() is None:
            raise HotError("hot_service_stopped")
        with self._lock():
            state = self._state()
            if state is None:
                raise HotError("hot_service_stopped")
            try:
                value = rpc(state["port"], state["owner"], self._secret("rpc-controller"), operation, params, request_id)
                valid = valid_receipt(value, request_id)
            except HotError as error:
                if str(error) not in ("hot_rpc_unavailable", "hot_rpc_timeout", "hot_rpc_incomplete", "hot_rpc_response_untrusted", "hot_owner_stale"):
                    raise
                valid = False
            except (KeyError, TypeError, ValueError):
                valid = False
            if not valid:
                log.warning("hot_control_outcome_unknown")
                return {"state": "outcome_unknown", "code": "hot_control_outcome_unknown", "operation": operation, "requestId": request_id}
            log.info("hot_control_saved")
            return {**value, "requestId": request_id}

    def configure_channel(self, channel_id: str, expected_version: int, config: dict, request_id: str | None = None) -> dict:
        if not isinstance(channel_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", channel_id) or type(expected_version) is not int or not 0 <= expected_version <= 1000000 or not isinstance(config, dict):
            raise HotError("hot_channel_request_invalid")
        def text(value, maximum):
            return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum
        if set(config) - {"name", "topics", "sourceIds", "importanceRules", "rules"} or not text(config.get("name"), 100):
            raise HotError("hot_channel_request_invalid")
        for field in ("topics", "sourceIds", "importanceRules"):
            if not isinstance(config.get(field), list) or len(config[field]) > 50 or any(not text(item, 500) for item in config[field]):
                raise HotError("hot_channel_request_invalid")
        if "rules" in config:
            if not isinstance(config["rules"], list) or len(config["rules"]) > 30:
                raise HotError("hot_channel_request_invalid")
            seen = set()
            for rule in config["rules"]:
                if not isinstance(rule, dict) or set(rule) - {"id", "keywords", "requireOfficial", "relevance", "importance"} or not isinstance(rule.get("id"), str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", rule["id"]) or rule["id"] in seen:
                    raise HotError("hot_channel_request_invalid")
                seen.add(rule["id"])
                if not isinstance(rule.get("keywords"), list) or not 1 <= len(rule["keywords"]) <= 20 or any(not text(item, 80) for item in rule["keywords"]) or ("requireOfficial" in rule and type(rule["requireOfficial"]) is not bool):
                    raise HotError("hot_channel_request_invalid")
                if any(type(rule.get(field)) is not int or not 0 <= rule[field] <= 100 for field in ("relevance", "importance")):
                    raise HotError("hot_channel_request_invalid")
        def receipt(value, request):
            return (isinstance(value, dict) and value.get("channelId") == channel_id and type(value.get("version")) is int
                    and value["version"] == expected_version + 1 and value.get("requestId") == request and value.get("config") == config)
        return self._control_projection("channel.configure", {"channelId": channel_id, "expectedVersion": expected_version, "config": config}, request_id, receipt)

    def correct_event(self, change: dict, reason: str, request_id: str | None = None) -> dict:
        fields = {"title": {"title"}, "merge": {"target", "targetExpected"}, "split": {"materialIds", "title"},
                  "reassign": {"target", "targetExpected", "materialIds"}, "channels": {"channelIds"}}
        def uuid_value(value):
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value):
                raise HotError("hot_event_correction_invalid")
            return str(UUID(value))
        if not isinstance(change, dict) or not isinstance(change.get("type"), str) or change["type"] not in fields or set(change) != fields[change["type"]] | {"id", "expected", "type"} or not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
            raise HotError("hot_event_correction_invalid")
        change = dict(change)
        change["id"] = uuid_value(change["id"])
        if type(change["expected"]) is not int or not 0 <= change["expected"] <= 1000000:
            raise HotError("hot_event_correction_invalid")
        if "target" in change:
            change["target"] = uuid_value(change["target"])
            if type(change["targetExpected"]) is not int or not 0 <= change["targetExpected"] <= 1000000:
                raise HotError("hot_event_correction_invalid")
            if change["target"] == change["id"]:
                raise HotError("hot_event_correction_invalid")
        if "title" in change and (not isinstance(change["title"], str) or not change["title"].strip() or len(change["title"]) > 500):
            raise HotError("hot_event_correction_invalid")
        if "materialIds" in change:
            if not isinstance(change["materialIds"], list) or not 1 <= len(change["materialIds"]) <= 200:
                raise HotError("hot_event_correction_invalid")
            change["materialIds"] = sorted(uuid_value(item) for item in change["materialIds"])
            if len(set(change["materialIds"])) != len(change["materialIds"]):
                raise HotError("hot_event_correction_invalid")
        if "channelIds" in change:
            if not isinstance(change["channelIds"], list) or len(change["channelIds"]) > 50 or any(not isinstance(item, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", item) for item in change["channelIds"]) or len(set(change["channelIds"])) != len(change["channelIds"]):
                raise HotError("hot_event_correction_invalid")
            change["channelIds"] = sorted(change["channelIds"])
        def material_refs(value):
            if not isinstance(value, list):
                return None
            refs = set()
            for item in value:
                if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", item["id"]) or type(item.get("revision")) is not int or item["revision"] < 1 or item.get("relation") not in ("same_occurrence", "composite"):
                    return None
                refs.add((item["id"], item["revision"], item["relation"]))
            return refs
        def receipt(value, _request):
            if not isinstance(value, dict) or not isinstance(value.get("source"), dict):
                return False
            source = value["source"]
            if source.get("id") != change["id"] or type(source.get("revision")) is not int or source["revision"] != change["expected"] + 1 or not isinstance(source.get("snapshot"), dict):
                return False
            snapshot = source["snapshot"]
            if snapshot.get("state") != ("merged" if change["type"] == "merge" else "active"):
                return False
            manual = snapshot.get("manual")
            if change["type"] == "title":
                return snapshot.get("title") == change["title"] and isinstance(manual, dict) and manual.get("title") is True
            if change["type"] == "channels":
                return isinstance(manual, dict) and manual.get("channels") == change["channelIds"]
            if change["type"] in ("merge", "reassign", "split"):
                target = value.get("target")
                if not isinstance(target, dict) or not isinstance(target.get("snapshot"), dict) or target["snapshot"].get("state") != "active":
                    return False
                target_snapshot = target["snapshot"]
                target_manual = target_snapshot.get("manual")
                source_refs, target_refs = material_refs(snapshot.get("materials")), material_refs(target_snapshot.get("materials"))
                protected = material_refs(target_manual.get("protected")) if isinstance(target_manual, dict) else None
                if source_refs is None or target_refs is None or protected is None:
                    return False
                if change["type"] == "merge":
                    if snapshot.get("canonicalId") != change["target"] or not source_refs <= target_refs or not source_refs <= protected:
                        return False
                else:
                    moved = set(change["materialIds"])
                    target_moved = {ref for ref in target_refs if ref[0] in moved}
                    if any(ref[0] in moved for ref in source_refs) or {ref[0] for ref in target_moved} != moved or not target_moved <= protected or not isinstance(manual, dict) or not isinstance(manual.get("excluded"), list) or not moved <= set(manual["excluded"]):
                        return False
                if change["type"] == "split":
                    target_id = target.get("id")
                    return (isinstance(target_id, str) and re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", target_id) is not None
                            and type(target.get("revision")) is int and target["revision"] == 1 and target_snapshot.get("title") == change["title"] and target_manual.get("title") is True)
                return target.get("id") == change["target"] and type(target.get("revision")) is int and target["revision"] == change["targetExpected"] + 1
            return True
        return self._control_projection("event.correct", {"change": change, "reason": reason}, request_id, receipt)

    def configure_source(self, source: str, revision: str, enabled: bool | None = None,
                         frequency: int | None = None, request_id: str | None = None) -> dict:
        """Conditional source control; the reader key never authorizes this operation."""
        with self._lock():
            state = self._state()
            if state is None:
                raise HotError("hot_service_stopped")
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", source) or not re.fullmatch(r"[0-9]{1,18}", revision):
                raise HotError("hot_source_config_invalid")
            if enabled is not None and type(enabled) is not bool:
                raise HotError("hot_source_config_invalid")
            if frequency is not None and (type(frequency) is not int or frequency != 0 and not 60 <= frequency <= 86400):
                raise HotError("hot_source_config_invalid")
            if request_id is not None and not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", request_id):
                raise HotError("hot_source_request_invalid")
            params = {"sourceId": source, "expectedRevision": revision}
            if enabled is not None:
                params["enabled"] = enabled
            if frequency is not None:
                params["frequencySeconds"] = None if frequency == 0 else frequency
            if len(params) == 2:
                raise HotError("hot_source_config_invalid")
            request_id = request_id or str(uuid4())
            request_id = str(UUID(request_id))
            try:
                value = rpc(state["port"], state["owner"], self._secret("rpc-controller"), "source.configure", params, request_id)
            except HotError as error:
                if str(error) not in ("hot_rpc_unavailable", "hot_rpc_timeout", "hot_rpc_incomplete", "hot_rpc_response_untrusted", "hot_owner_stale"):
                    raise
                log.warning("hot_source_control_outcome_unknown")
                return {"state": "outcome_unknown", "code": "hot_source_control_outcome_unknown",
                        "sourceId": source, "requestId": request_id}
            if not isinstance(value, dict) or value.get("sourceId") != source or value.get("requestId") != request_id or type(value.get("enabled")) is not bool or value.get("revision") != str(int(revision) + 1) or "frequencySeconds" not in value or (value["frequencySeconds"] is not None and (type(value["frequencySeconds"]) is not int or not 60 <= value["frequencySeconds"] <= 86400)):
                log.warning("hot_source_control_outcome_unknown")
                return {"state": "outcome_unknown", "code": "hot_source_control_outcome_unknown",
                        "sourceId": source, "requestId": request_id}
            log.info("hot_source_configuration_saved")
            return value

    @contextmanager
    def _lock(self):
        if fcntl is None:
            raise HotError("hot_platform_not_verified")
        path = self.directory / "lifecycle.lock"
        _no_alias(path)
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise HotError("hot_lock_unsafe")
            deadline = time.monotonic() + 5
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise HotError("hot_lifecycle_busy") from None
                    time.sleep(0.05)
            yield
        finally:
            os.close(descriptor)

    def start(self) -> dict:
        with self._lock():
            return self._start()

    def archive(self, operation: str, directory: Path | None = None, target_database: str | None = None,
                migration_user: str = "postgres", migration_account: str = "hot-migration-database") -> dict:
        """Backup a stopped installation; restore only into another database's absent schema."""
        with self._lock():
            if self._state() is not None:
                raise HotError("hot_archive_requires_stopped")
            journal = self.directory / "archive-attempt.json"
            _no_alias(journal)
            if journal.exists() and _read(journal, private=True).get("state") in ("running", "outcome_unknown"):
                raise HotError("hot_archive_outcome_unknown")
            config = self._config()
            identity = _read(self.directory / "identity.json", private=True)
            if identity.get("projectRoot") != str(self.project):
                raise HotError("hot_process_foreign")
            if config["database"]["mode"] == "managed":
                from .hot_postgres import ManagedPostgres

                password = self._secret("hot-postgres-admin")
                server = ManagedPostgres(self.home, identity["instanceId"]).start(password)
                config["database"].update({key: server[key] for key in ("host", "port")})
                migration_user = "postgres"
            else:
                password = self._secret(migration_account)
            if operation == "backup":
                parent = self.home / config["retention"]["backupDirectory"]
                _no_alias(parent)
                parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                info = parent.stat()
                if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                    raise HotError("hot_archive_unsafe")
                directory = parent / ("backup-" + uuid4().hex)
            elif operation != "restore" or directory is None:
                raise HotError("hot_archive_input_invalid")
            _no_alias(directory)
            payload = {"operation": operation, "config": config, "instanceId": identity["instanceId"],
                       "controllerToken": self._secret("rpc-controller"), "directory": str(directory),
                       "targetDatabase": target_database, "migrationUser": migration_user,
                       "migrationPassword": password}
            attempt = {"version": 1, "state": "running", "operation": operation,
                       "targetDatabase": target_database, "directory": str(directory)}
            def record(state):
                attempt["state"] = state
                fd = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
                with os.fdopen(fd, "w") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                        raise HotError("hot_archive_journal_unsafe")
                    stream.truncate(0)
                    json.dump(attempt, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
            record("running")
            child = None
            try:
                child = subprocess.Popen([_node(), str(self.project / "services/hot/scripts/archive.ts")],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         text=True, cwd=self.project, start_new_session=True)
                try:
                    output, _ = child.communicate(json.dumps(payload), timeout=240)
                except subprocess.TimeoutExpired:
                    child.send_signal(signal.SIGTERM)
                    try:
                        child.communicate(timeout=90)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.communicate(timeout=5)
                    record("outcome_unknown")
                    raise HotError("hot_archive_outcome_unknown") from None
                value = json.loads(output)
                if value.get("code") == "hot_archive_outcome_unknown":
                    record("outcome_unknown")
                    raise HotError("hot_archive_outcome_unknown")
                record("completed" if child.returncode == 0 else "failed")
                if child.returncode or value.get("state") not in ("backed_up", "restored_paused"):
                    phase = value.get("phase")
                    allowed = ("input", "tools", "backup", "verify", "target", "restore", "inventory")
                    raise HotError("hot_archive_failed_" + phase if phase in allowed else "hot_archive_failed")
            except (OSError, ValueError, subprocess.SubprocessError):
                record("outcome_unknown")
                raise HotError("hot_archive_outcome_unknown") from None
            except BaseException:
                # Ctrl-C must also cancel the independent Node session and wait for cleanup.
                if child is not None and child.poll() is None:
                    child.send_signal(signal.SIGTERM)
                    try:
                        child.communicate(timeout=90)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.communicate(timeout=5)
                    record("outcome_unknown")
                elif attempt["state"] == "running":
                    record("outcome_unknown")
                raise
            finally:
                if child is not None and child.poll() is None:
                    child.send_signal(signal.SIGTERM)
                    try:
                        child.communicate(timeout=90)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.communicate(timeout=5)
                    record("outcome_unknown")
            log.info("hot_archive_completed operation=%s", operation)
            return value

    def _start(self) -> dict:
        if os.name != "posix":
            raise HotError("hot_platform_not_verified")
        if self._state() is not None:
            return self.status()
        config = self._config()
        if not config["enabled"]:
            raise HotError("hot_disabled")
        identity = _read(self.directory / "identity.json", private=True)
        if identity.get("projectRoot") != str(self.project):
            raise HotError("hot_process_foreign")
        if config["database"]["mode"] == "managed":
            from .hot_postgres import ManagedPostgres

            server = ManagedPostgres(self.home, identity["instanceId"]).start(self._secret("hot-postgres-admin"))
            actual = {key: server[key] for key in ("host", "port")}
            if any(config["database"][key] != value for key, value in actual.items()):
                config["database"].update(actual)
                save_settings(self.project, self.home, config)
        payload = {"config": config, "instanceId": identity["instanceId"], "mode": "native",
                   "workerPassword": self._secret(config["database"]["secretRef"]),
                   "controllerUser": config["database"]["controllerUser"],
                   "controllerPassword": self._secret(config["database"]["controllerSecretRef"]),
                   "controllerToken": self._secret("rpc-controller"), "readerToken": self._secret("rpc-reader")}
        if config.get("model", {}).get("enabled"):
            from .bootstrap import native_python
            from app.research_web import PINNED_DSH_COMMIT

            source = Path(os.environ.get("RESEARCH_DSH_SOURCE", str(self.home.parent / "runtime" / "dsh" / PINNED_DSH_COMMIT))).expanduser().resolve()
            payload["nativeModel"] = {"source": str(source), "credentials": {
                "python": str(native_python(self.project)),
                "bridge": str(self.project / "app/research_web/model_credentials.py"),
                "dataHome": str(self.home),
            }}
        launch_id = uuid4().hex
        path = self.project / "logs" / "hot" / "runtime.log"
        _no_alias(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        child = None
        try:
            with os.fdopen(descriptor, "wb") as errors:
                info = os.fstat(errors.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                    raise HotError("hot_log_unsafe")
                child = subprocess.Popen([_node(), str(self.project / "services/hot/scripts/serve.ts"), launch_id],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                                         cwd=self.project, start_new_session=True)
                packet = json.dumps(payload).encode()
                if len(packet) > 65536:
                    raise HotError("hot_bootstrap_limit")
                os.set_blocking(child.stdin.fileno(), False)
                os.set_blocking(child.stdout.fileno(), False)
                written = 0
                received = b""
                deadline = time.monotonic() + 15
                with selectors.DefaultSelector() as selector:
                    selector.register(child.stdout, selectors.EVENT_READ)
                    selector.register(child.stdin, selectors.EVENT_WRITE)
                    while b"\n" not in received:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise HotError("hot_start_timeout")
                        events = selector.select(remaining)
                        if not events:
                            raise HotError("hot_start_timeout")
                        for selected, _ in events:
                            if selected.fileobj is child.stdin:
                                try:
                                    written += os.write(child.stdin.fileno(), packet[written:])
                                except BlockingIOError:
                                    continue
                                if written == len(packet):
                                    selector.unregister(child.stdin)
                                    child.stdin.close()
                            else:
                                chunk = os.read(child.stdout.fileno(), 4096)
                                if not chunk or len(received) + len(chunk) > 65536:
                                    raise HotError("hot_start_failed")
                                received += chunk
                    ready = json.loads(received.split(b"\n")[0])
                if ready.get("state") != "initialized" or ready.get("pid") != child.pid or ready.get("launchId") != launch_id:
                    raise HotError("hot_start_failed")
                state = {"version": 1, "projectRoot": str(self.project), "pid": child.pid, "port": ready["port"],
                         "owner": ready["owner"], "launchId": launch_id, "fingerprint": self._fingerprint(child.pid)}
                temporary = self.directory / ("process-" + uuid4().hex + ".tmp")
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "w") as output:
                    json.dump(state, output)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.state_path)
                result = self.status()
                child.stdout.close()
                log.info("hot_process_started")
                return result
        except BaseException:
            if child is not None:
                child.kill()
                child.wait(timeout=5)
            raise HotError("hot_start_failed") from None

    def stop(self) -> dict:
        if not self.directory.exists():
            return {"state": "stopped"}
        with self._lock():
            return self._stop()

    def _stop(self) -> dict:
        state = self._state()
        if state is None:
            return {"state": "stopped"}
        os.kill(state["pid"], signal.SIGTERM)
        for _ in range(100):
            current = self._fingerprint(state["pid"])
            if current is None:
                log.info("hot_process_stopped")
                return {"state": "stopped"}
            # Exiting argv may briefly change before the PID vanishes. Do not signal
            # a changed identity; only observe until the bounded escalation recheck.
            time.sleep(0.05)
        # Revalidate the exact original process immediately before escalation.
        final = self._fingerprint(state["pid"])
        if final is None:
            log.info("hot_process_stopped")
            return {"state": "stopped"}
        if final != state["fingerprint"]:
            raise HotError("hot_process_identity_mismatch")
        os.kill(state["pid"], signal.SIGKILL)
        raise HotError("hot_stop_requires_recheck")

    def restart(self) -> dict:
        with self._lock():
            self._stop()
            return self._start()
