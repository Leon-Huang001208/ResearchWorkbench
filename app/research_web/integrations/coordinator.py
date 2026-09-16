"""Persisted, privacy-safe orchestration for data and local integration probes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import tempfile
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from core.observability import get_logger

from .models import IntegrationItemStatus

log = get_logger(__name__)
Scope = Literal["all", "data", "local"]
TERMINAL_BATCH_STATES = {"completed", "completed_with_failures", "cancelled", "failed"}
PLANNED_LOCAL_ITEMS = {"folder_sync", "browser_extension", "local_mcp"}
SUMMARY_KEYS = ("available", "checking", "user_action", "system_fault", "not_delivered")
SAFE_TABBIT_STATUSES = {
    "ready",
    "disabled",
    "launcher_missing",
    "browser_offline",
    "unsupported_version",
    "instance_selection_required",
    "error",
}
SAFE_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")


class IntegrationStatusPersistenceError(RuntimeError):
    """Raised when unsafe persisted state cannot be atomically sanitized."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class IntegrationCoordinator:
    """Coordinate bounded probes while retaining only safe status evidence."""

    def __init__(
        self,
        state_root: Path,
        datahub,
        local_integrations,
        tabbit,
        *,
        probe_timeout_seconds: float = 20.0,
        idempotency_ttl_seconds: float = 300.0,
        max_retained_batches: int = 128,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.state_root = Path(state_root)
        self.state_path = self.state_root / "status.json"
        self.datahub = datahub
        self.local_integrations = local_integrations
        self.tabbit = tabbit
        self.probe_timeout_seconds = max(0.01, float(probe_timeout_seconds))
        self.idempotency_ttl_seconds = max(0.01, float(idempotency_ttl_seconds))
        self.max_retained_batches = max(1, int(max_retained_batches))
        self._monotonic = monotonic_clock
        self.records: dict[str, dict] = {}
        self.consents: dict[str, bool] = {}
        self.batches: dict[str, dict] = {}
        self.batch_tasks: dict[str, asyncio.Task] = {}
        self._idempotency_index: dict[tuple[Scope, str], str] = {}
        self.local_snapshot: dict | None = None
        self.tabbit_snapshot: dict | None = None
        self.closed = False
        self._loaded = False
        self._state_lock = threading.RLock()

    def load(self) -> None:
        """Restore safe evidence; changed configuration makes that evidence stale."""

        with self._state_lock:
            if self._loaded:
                return
            self._loaded = True
            try:
                if not self.state_path.exists():
                    return
                payload = json.loads(self.state_path.read_text(encoding="utf-8"))
                if payload.get("schema_version") != 1:
                    raise ValueError("unsupported integration status schema")
                records = payload.get("items", {})
                consents = payload.get("consents", {})
                if not isinstance(records, dict) or not isinstance(consents, dict):
                    raise TypeError("invalid integration status payload")
                self.records = {
                    key: deepcopy(value)
                    for key, value in records.items()
                    if isinstance(key, str) and isinstance(value, dict)
                }
                self.consents = {
                    key: value
                    for key, value in consents.items()
                    if isinstance(key, str) and isinstance(value, bool)
                }
                local_snapshot = payload.get("local_snapshot")
                tabbit_snapshot = payload.get("tabbit_snapshot")
                if isinstance(local_snapshot, dict):
                    self.local_snapshot = deepcopy(local_snapshot)
                safe_tabbit_snapshot = self._project_tabbit_snapshot(tabbit_snapshot)
                tabbit_snapshot_requires_rewrite = safe_tabbit_snapshot != tabbit_snapshot
                self.tabbit_snapshot = safe_tabbit_snapshot
                if tabbit_snapshot_requires_rewrite:
                    try:
                        self._persist_sync()
                    except Exception as exc:
                        self._loaded = False
                        self.records = {}
                        self.consents = {}
                        self.local_snapshot = None
                        self.tabbit_snapshot = None
                        log.warning(
                            "integration_tabbit_snapshot_sanitize_failed",
                            error_type=type(exc).__name__,
                        )
                        raise IntegrationStatusPersistenceError(
                            "unable to sanitize persisted integration status"
                        ) from exc
                    log.info("integration_tabbit_snapshot_sanitized")
                restored: dict[str, dict] = {}
                for source in self._data_sources():
                    item_id = f"data:{source['id']}"
                    record = self.records.get(item_id)
                    if not record:
                        continue
                    current = self._data_fingerprint(source)
                    if record.get("fingerprint") != current:
                        record["stale"] = True
                        continue
                    if record.get("probe_health") in {"healthy", "degraded", "unavailable"}:
                        restored[source["id"]] = {
                            "source_id": source["id"],
                            "status": "completed",
                            "health": record["probe_health"],
                            "failure_code": record.get("error_code"),
                            "duration_ms": record.get("duration_ms"),
                            "last_checked_at": record.get("last_attempt_at"),
                            "completed_at": record.get("last_attempt_at"),
                        }
                if restored:
                    self.datahub.restore_probe_statuses(restored)
                log.info("integration_status_restored", item_count=len(self.records))
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                self.records = {}
                self.consents = {}
                log.warning("integration_status_restore_failed", error_type=type(exc).__name__)

    def start(self) -> dict:
        self.load()
        return self.start_batch(
            scope="all", trigger="startup", idempotency_key=f"startup-{uuid4()}"
        )

    def start_batch(
        self,
        *,
        scope: Scope,
        trigger: Literal["startup", "manual"],
        idempotency_key: str,
    ) -> dict:
        if scope not in {"all", "data", "local"}:
            raise ValueError("invalid integration scope")
        with self._state_lock:
            if self.closed:
                raise RuntimeError("integration coordinator is closed")
            self.load()
            self._prune_batches()
            replay_id = self._idempotency_index.get((scope, idempotency_key))
            if replay_id is not None and replay_id in self.batches:
                return self._public_batch(self.batches[replay_id])
            for batch in self.batches.values():
                if batch["status"] not in TERMINAL_BATCH_STATES and self._scopes_overlap(
                    scope, batch["scope"]
                ):
                    self._register_idempotency_key(scope, idempotency_key, batch["id"])
                    return self._public_batch(batch)
            batch_id = str(uuid4())
            record: dict = {
                "id": batch_id,
                "scope": scope,
                "trigger": trigger,
                "idempotency_key": idempotency_key,
                "status": "queued",
                "error_code": None,
                "created_at": _now(),
                "completed_at": None,
                "retained_until": None,
                "items": {},
            }
            self.batches[batch_id] = record
            self._register_idempotency_key(scope, idempotency_key, batch_id)
            self.batch_tasks[batch_id] = asyncio.create_task(
                self._run_batch(batch_id), name=f"integration-probe-{scope}"
            )
        log.info("integration_probe_batch_started", batch_id=batch_id, scope=scope, trigger=trigger)
        return self._public_batch(record)

    @staticmethod
    def _scopes_overlap(left: Scope, right: Scope) -> bool:
        return left == "all" or right == "all" or left == right

    async def wait_batch(self, batch_id: str) -> dict:
        with self._state_lock:
            task = self.batch_tasks.get(batch_id)
        if task is not None:
            await asyncio.shield(task)
        return self.batch(batch_id)

    def batch(self, batch_id: str) -> dict:
        with self._state_lock:
            self._prune_batches()
            try:
                return self._public_batch(self.batches[batch_id])
            except KeyError as exc:
                raise KeyError("integration probe batch not found") from exc

    @staticmethod
    def _public_batch(record: dict) -> dict:
        return {
            key: deepcopy(record[key])
            for key in (
                "id",
                "scope",
                "trigger",
                "status",
                "error_code",
                "created_at",
                "completed_at",
                "items",
            )
        }

    def _prune_batches(self) -> None:
        now = self._monotonic()
        terminal_ids = [
            batch_id
            for batch_id, batch in self.batches.items()
            if batch["status"] in TERMINAL_BATCH_STATES
        ]
        remove_ids = {
            batch_id
            for batch_id in terminal_ids
            if self.batches[batch_id].get("retained_until", now) <= now
        }
        retained_ids = [batch_id for batch_id in terminal_ids if batch_id not in remove_ids]
        if len(retained_ids) > self.max_retained_batches:
            remove_ids.update(retained_ids[: -self.max_retained_batches])
        for batch_id in remove_ids:
            batch = self.batches.pop(batch_id, None)
            if batch is None:
                continue
            aliases = [
                key
                for key, indexed_batch_id in self._idempotency_index.items()
                if indexed_batch_id == batch_id
            ]
            for key in aliases:
                self._idempotency_index.pop(key, None)

    def _register_idempotency_key(self, scope: Scope, key: str, batch_id: str) -> None:
        index_key = (scope, key)
        self._idempotency_index.pop(index_key, None)
        self._idempotency_index[index_key] = batch_id
        max_keys = max(2, self.max_retained_batches * 2)
        while len(self._idempotency_index) > max_keys:
            oldest = next(iter(self._idempotency_index))
            self._idempotency_index.pop(oldest, None)

    async def _run_batch(self, batch_id: str) -> None:
        with self._state_lock:
            batch = self.batches[batch_id]
            batch["status"] = "checking"
        try:
            jobs = []
            if batch["scope"] in {"all", "data"}:
                jobs.append(self._probe_data(batch))
            if batch["scope"] in {"all", "local"}:
                jobs.append(self._probe_local(batch))
            await asyncio.gather(*jobs)
            with self._state_lock:
                batch["status"] = (
                    "completed_with_failures"
                    if any(item.get("status") == "failed" for item in batch["items"].values())
                    else "completed"
                )
        except asyncio.CancelledError:
            with self._state_lock:
                batch["status"] = "cancelled"
            raise
        except Exception as exc:  # noqa: BLE001 - batch errors are normalized at this boundary.
            with self._state_lock:
                batch["status"] = "failed"
                batch["error_code"] = "integration_probe_batch_failed"
            log.warning(
                "integration_probe_batch_failed",
                batch_id=batch_id,
                error_type=type(exc).__name__,
            )
        finally:
            with self._state_lock:
                batch["completed_at"] = _now()
                batch["retained_until"] = self._monotonic() + self.idempotency_ttl_seconds
            try:
                await self._persist()
            except Exception as exc:  # noqa: BLE001 - persistence failures become batch state.
                with self._state_lock:
                    batch["status"] = "failed"
                    batch["error_code"] = "integration_status_persist_failed"
                log.warning(
                    "integration_status_persist_failed",
                    batch_id=batch_id,
                    error_type=type(exc).__name__,
                )
            finally:
                with self._state_lock:
                    self.batch_tasks.pop(batch_id, None)
                    self._prune_batches()
                    status = batch["status"]
            log.info(
                "integration_probe_batch_completed",
                batch_id=batch_id,
                status=status,
            )

    async def _probe_data(self, batch: dict) -> None:
        public_limit = asyncio.Semaphore(4)
        vendor_limit = asyncio.Semaphore(1)

        async def probe_one(source: dict) -> None:
            item_id = f"data:{source['id']}"
            vendor = self._needs_consent(source)
            with self._state_lock:
                consented = self.consents.get(item_id, False)
            if vendor and not consented:
                with self._state_lock:
                    batch["items"][item_id] = {
                        "status": "skipped",
                        "error_code": "auto_probe_consent_required",
                    }
                    record = self.records.setdefault(item_id, {})
                    record.update(
                        fingerprint=self._data_fingerprint(source),
                        stale=bool(record.get("last_success_at")),
                        error_code="auto_probe_consent_required",
                    )
                return
            semaphore = vendor_limit if vendor else public_limit
            with self._state_lock:
                batch["items"][item_id] = {"status": "checking", "error_code": None}
            try:
                async with semaphore:
                    result = await asyncio.wait_for(
                        self.datahub.run_probe(
                            source["id"], f"integration-{batch['id']}-{source['id']}"
                        ),
                        timeout=self.probe_timeout_seconds,
                    )
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                result = {
                    "status": "completed",
                    "health": "unavailable",
                    "failure_code": "probe_timeout",
                    "last_checked_at": _now(),
                    "completed_at": _now(),
                }
                log.warning("integration_data_probe_timed_out", source_id=source["id"])
            except Exception as exc:  # noqa: BLE001 - normalize provider failures.
                result = {
                    "status": "completed",
                    "health": "unavailable",
                    "failure_code": "probe_failed",
                    "last_checked_at": _now(),
                    "completed_at": _now(),
                }
                log.warning(
                    "integration_data_probe_failed",
                    source_id=source["id"],
                    error_type=type(exc).__name__,
                )
            health = result.get("health", "unavailable")
            attempted = result.get("last_checked_at") or result.get("completed_at") or _now()
            with self._state_lock:
                record = self.records.setdefault(item_id, {})
                record.update(
                    fingerprint=self._data_fingerprint(source),
                    last_attempt_at=attempted,
                    probe_health=health,
                    error_code=result.get("failure_code"),
                    duration_ms=result.get("duration_ms"),
                    stale=False,
                )
                if health in {"healthy", "degraded"}:
                    record["last_success_at"] = attempted
                batch["items"][item_id] = {
                    "status": "completed",
                    "health": health,
                    "error_code": result.get("failure_code"),
                }

        await asyncio.gather(*(probe_one(source) for source in self._data_sources()))

    async def _probe_local(self, batch: dict) -> None:
        try:
            local_result = await asyncio.wait_for(
                self.local_integrations.run_probe(f"integration-{batch['id']}-local"),
                timeout=self.probe_timeout_seconds,
            )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            local_result = {
                "status": "failed",
                "error": {"code": "probe_timeout", "message": "本机能力检测超时"},
            }
            log.warning("integration_local_probe_timed_out")
        except Exception as exc:  # noqa: BLE001 - normalize local probe failures.
            local_result = {
                "status": "failed",
                "error": {"code": "local_probe_failed", "message": "本机能力检测失败"},
            }
            log.warning("integration_local_probe_failed", error_type=type(exc).__name__)
        snapshot = local_result.get("snapshot")
        if local_result.get("status") == "completed" and isinstance(snapshot, dict):
            with self._state_lock:
                self.local_snapshot = deepcopy(snapshot)
                for item in snapshot.get("items", []):
                    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                        continue
                    item_id = f"local:{item['id']}"
                    success = bool(item.get("callable"))
                    record = self.records.setdefault(item_id, {})
                    checked = (
                        item.get("last_checked_at") or snapshot.get("last_checked_at") or _now()
                    )
                    record.update(
                        fingerprint=self._local_fingerprint(item),
                        last_attempt_at=checked,
                        probe_health="healthy" if success else "unavailable",
                        error_code=None if success else "local_integration_unavailable",
                        stale=False,
                    )
                    if success:
                        record["last_success_at"] = item.get("last_verified_at") or checked
                    batch["items"][item_id] = {
                        "status": "completed",
                        "health": record["probe_health"],
                        "error_code": record["error_code"],
                    }
        else:
            with self._state_lock:
                error_code = (local_result.get("error") or {}).get("code", "local_probe_failed")
                checked = _now()
                stale_snapshot = deepcopy(self.local_snapshot) if self.local_snapshot else None
                if stale_snapshot is not None:
                    for item in stale_snapshot.get("items", []):
                        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                            continue
                        item["callable"] = False
                        item["status"] = "不可用"
                        item["message"] = "最新检测失败，旧状态不可继续作为可用证据"
                        item_id = f"local:{item['id']}"
                        record = self.records.setdefault(item_id, {})
                        record.update(
                            last_attempt_at=checked,
                            probe_health="unavailable",
                            error_code=error_code,
                            stale=bool(record.get("last_success_at")),
                        )
                        batch["items"][item_id] = {
                            "status": "failed",
                            "health": "unavailable",
                            "error_code": error_code,
                        }
                    stale_snapshot["last_checked_at"] = checked
                    self.local_snapshot = stale_snapshot
                batch["items"]["local:host"] = {
                    "status": "failed",
                    "error_code": error_code,
                }
        try:
            tabbit_snapshot = await self.tabbit.status()
            tabbit_ready = tabbit_snapshot.get("status") == "ready"
            checked = _now()
            with self._state_lock:
                self.tabbit_snapshot = self._project_tabbit_snapshot(tabbit_snapshot)
                record = self.records.setdefault("local:tabbit", {})
                record.update(
                    fingerprint=_fingerprint(self._safe_tabbit_snapshot()),
                    last_attempt_at=checked,
                    probe_health="healthy" if tabbit_ready else "unavailable",
                    error_code=(
                        None if tabbit_ready else f"tabbit_{tabbit_snapshot.get('status', 'error')}"
                    ),
                    stale=False,
                )
                if tabbit_ready:
                    record["last_success_at"] = checked
                batch["items"]["local:tabbit"] = {
                    "status": "completed",
                    "health": record["probe_health"],
                    "error_code": record["error_code"],
                }
        except Exception as exc:  # noqa: BLE001 - vendor boundary must return safe state.
            with self._state_lock:
                self.tabbit_snapshot = {"status": "error"}
                batch["items"]["local:tabbit"] = {
                    "status": "failed",
                    "error_code": "tabbit_probe_failed",
                }
            log.warning("integration_tabbit_probe_failed", error_type=type(exc).__name__)

    def set_auto_probe_consent(self, item_id: str, consent: bool) -> dict:
        if not item_id.startswith("data:"):
            raise ValueError("auto probe consent is only available for data sources")
        source_id = item_id.removeprefix("data:")
        if all(source["id"] != source_id for source in self._data_sources()):
            raise KeyError("integration item not found")
        with self._state_lock:
            self.consents[item_id] = consent
            record = self.records.setdefault(item_id, {})
            if not consent:
                record["stale"] = bool(record.get("last_success_at"))
                record["error_code"] = "auto_probe_consent_required"
            self._persist_sync()
        log.info("integration_auto_probe_consent_updated", item_id=item_id, consent=consent)
        return {"id": item_id, "consent": consent}

    def status(self, scope: Scope = "all") -> dict:
        if scope not in {"all", "data", "local"}:
            raise ValueError("invalid integration scope")
        with self._state_lock:
            self.load()
            self._prune_batches()
            items = []
            if scope in {"all", "data"}:
                items.extend(self._data_statuses())
            if scope in {"all", "local"}:
                items.extend(self._local_statuses())
            items = [
                IntegrationItemStatus.model_validate(item).model_dump(
                    mode="json", exclude_none=True
                )
                for item in items
            ]
            summary = {key: 0 for key in SUMMARY_KEYS}
            for item in items:
                summary[item["bucket"]] += 1
            summary["total"] = len(items)
            latest = max(self.batches.values(), key=lambda item: item["created_at"], default=None)
            return {
                "schema_version": 1,
                "generated_at": _now(),
                "scope": scope,
                "summary": summary,
                "items": items,
                "latest_batch": self._public_batch(latest) if latest is not None else None,
            }

    def _data_sources(self) -> list[dict]:
        catalog = self.datahub.catalog()
        connections = {
            item["id"]: item for item in self.datahub.connection_center().get("sources", [])
        }
        bindings: dict[str, list[str]] = {}
        for binding in catalog.get("bindings", []):
            if binding.get("implemented"):
                bindings.setdefault(binding["source_id"], []).append(binding["capability_id"])
        values = []
        for source in catalog.get("sources", []):
            if source.get("id") == "local_cache":
                continue
            merged = deepcopy(source)
            merged["connection"] = connections.get(source["id"], {})
            merged["capabilities"] = sorted(set(bindings.get(source["id"], [])))
            values.append(merged)
        return values

    def _data_fingerprint(self, source: dict) -> str:
        readiness = source.get("readiness", {})
        connection = source.get("connection", {})
        digest = None
        digest_reader = getattr(self.datahub, "source_configuration_digest", None)
        if callable(digest_reader):
            try:
                digest = digest_reader(source.get("id"))
            except Exception as exc:  # noqa: BLE001 - retain compatibility with older DataHubs.
                log.warning(
                    "integration_configuration_digest_failed",
                    source_id=source.get("id"),
                    error_type=type(exc).__name__,
                )
        return _fingerprint(
            {
                "source_id": source.get("id"),
                "implementation_completed": readiness.get("integration_completed"),
                "configured": connection.get("configured", readiness.get("configured")),
                "dependency_ready": connection.get(
                    "dependency_ready", readiness.get("dependency_ready")
                ),
                "allowed": connection.get("allowed", readiness.get("allowed")),
                "integration_state": connection.get(
                    "integration_state", readiness.get("integration_state")
                ),
                "configuration_digest": digest,
                "safe_connection_metadata": (
                    None
                    if digest is not None
                    else {
                        "configured": connection.get("configured"),
                        "secret_configured": connection.get("secret_configured"),
                        "dependency_ready": connection.get("dependency_ready"),
                        "allowed": connection.get("allowed"),
                        "integration_state": connection.get("integration_state"),
                        "restart_required": connection.get("restart_required"),
                        "warnings": connection.get("warnings", []),
                    }
                ),
            }
        )

    @staticmethod
    def _local_fingerprint(item: dict) -> str:
        return _fingerprint(
            {
                "id": item.get("id"),
                "discovery": item.get("discovery"),
                "authorization": item.get("authorization"),
                "capabilities": item.get("capabilities", []),
            }
        )

    @staticmethod
    def _needs_consent(source: dict) -> bool:
        return source.get("auth_type") != "none" or source.get("fee") != "free"

    def _data_statuses(self) -> list[dict]:
        values = []
        for source in self._data_sources():
            readiness = source.get("readiness", {})
            connection = source.get("connection", {})
            item_id = f"data:{source['id']}"
            record = self.records.get(item_id, {})
            configured = bool(connection.get("configured", readiness.get("configured")))
            implemented = bool(readiness.get("integration_completed"))
            dependency_ready = bool(
                connection.get("dependency_ready", readiness.get("dependency_ready"))
            )
            consent_required = self._needs_consent(source)
            authorized = configured and (not consent_required or self.consents.get(item_id, False))
            health = readiness.get("health") or record.get("probe_health") or "untested"
            stale = bool(record.get("stale")) or (
                bool(record.get("fingerprint"))
                and record.get("fingerprint") != self._data_fingerprint(source)
            )
            runtime_callable = bool(
                implemented
                and configured
                and dependency_ready
                and authorized
                and health in {"healthy", "degraded"}
                and not stale
            )
            checking = any(
                batch.get("status") in {"queued", "checking"} and item_id in batch.get("items", {})
                for batch in self.batches.values()
            )
            if not implemented:
                bucket, responsibility = "not_delivered", "developer"
            elif checking or health == "checking":
                bucket, responsibility = "checking", "system"
            elif not configured or not authorized:
                bucket, responsibility = "user_action", "user"
            elif not dependency_ready:
                bucket, responsibility = "system_fault", "system"
            elif runtime_callable:
                bucket, responsibility = "available", "system"
            else:
                bucket = "system_fault" if health == "unavailable" else "user_action"
                responsibility = "vendor" if health == "unavailable" else "user"
            values.append(
                {
                    "id": item_id,
                    "scope": "data",
                    "kind": "data_source",
                    "source_id": source["id"],
                    "label": source.get("name") or connection.get("label") or source["id"],
                    "registered": True,
                    "implementation_state": "implemented" if implemented else "not_delivered",
                    "configured": configured,
                    "authorized": authorized,
                    "probe_state": "checking" if checking else health,
                    "runtime_callable": runtime_callable,
                    "stages": {
                        "registration": "complete",
                        "authorization": "complete" if authorized else "pending",
                        "probe": "checking" if checking else health,
                        "adaptation": "complete" if implemented else "not_delivered",
                        "runtime": "complete" if runtime_callable else "pending",
                    },
                    "bucket": bucket,
                    "responsibility": responsibility,
                    "capabilities": source.get("capabilities", []),
                    "last_attempt_at": record.get("last_attempt_at")
                    or readiness.get("last_checked_at"),
                    "last_success_at": record.get("last_success_at"),
                    "stale": stale,
                    "error_code": record.get("error_code") or readiness.get("failure_code"),
                    "details": {
                        "auto_probe_consent": self.consents.get(item_id, False),
                        "auto_probe_consent_required": consent_required,
                    },
                }
            )
        return values

    def _local_statuses(self) -> list[dict]:
        values = []
        snapshot = self.local_snapshot or {}
        for item in snapshot.get("items", []):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                continue
            item_id = f"local:{item['id']}"
            record = self.records.get(item_id, {})
            implemented = item["id"] not in PLANNED_LOCAL_ITEMS
            runtime_callable = implemented and bool(item.get("callable"))
            if not implemented:
                bucket, responsibility = "not_delivered", "developer"
            elif runtime_callable:
                bucket, responsibility = "available", "system"
            elif item.get("authorization") in {"待授权", "未登录"}:
                bucket, responsibility = "user_action", "user"
            else:
                bucket, responsibility = "system_fault", "system"
            values.append(
                {
                    "id": item_id,
                    "scope": "local",
                    "kind": item.get("category", "local"),
                    "label": item.get("label", item["id"]),
                    "registered": True,
                    "implementation_state": "implemented" if implemented else "not_delivered",
                    "configured": item.get("discovery") in {"已发现", "不适用"},
                    "authorized": item.get("authorization") in {"无需授权", "已授权", "不适用"},
                    "probe_state": record.get("probe_health", "untested"),
                    "runtime_callable": runtime_callable,
                    "stages": {
                        "registration": "complete",
                        "authorization": item.get("authorization", "待授权"),
                        "probe": record.get("probe_health", "untested"),
                        "adaptation": "complete" if implemented else "not_delivered",
                        "runtime": "complete" if runtime_callable else "pending",
                    },
                    "bucket": bucket,
                    "responsibility": responsibility,
                    "capabilities": item.get("capabilities", []),
                    "last_attempt_at": record.get("last_attempt_at") or item.get("last_checked_at"),
                    "last_success_at": record.get("last_success_at")
                    or item.get("last_verified_at"),
                    "stale": bool(record.get("stale")),
                    "error_code": record.get("error_code"),
                    "details": {"message": item.get("message"), "detail": item.get("detail")},
                }
            )
        if self.tabbit_snapshot is not None:
            record = self.records.get("local:tabbit", {})
            tabbit_status = self.tabbit_snapshot.get("status")
            ready = tabbit_status == "ready"
            if ready:
                tabbit_bucket, tabbit_responsibility = "available", "system"
            elif tabbit_status in {
                "disabled",
                "instance_selection_required",
                "browser_offline",
            }:
                tabbit_bucket, tabbit_responsibility = "user_action", "user"
            elif tabbit_status == "unsupported_version":
                tabbit_bucket, tabbit_responsibility = "system_fault", "vendor"
            else:
                tabbit_bucket, tabbit_responsibility = "system_fault", "system"
            values.append(
                {
                    "id": "local:tabbit",
                    "scope": "local",
                    "kind": "browser",
                    "label": "Tabbit CLI",
                    "registered": True,
                    "implementation_state": "implemented",
                    "configured": bool(
                        self.tabbit_snapshot.get("applied_config", {}).get("browser_enabled")
                    ),
                    "authorized": ready,
                    "probe_state": record.get("probe_health", "untested"),
                    "runtime_callable": ready,
                    "stages": {
                        "registration": "complete",
                        "authorization": "complete" if ready else "pending",
                        "probe": record.get("probe_health", "untested"),
                        "adaptation": "complete",
                        "runtime": "complete" if ready else "pending",
                    },
                    "bucket": tabbit_bucket,
                    "responsibility": tabbit_responsibility,
                    "capabilities": ["browser_automation", "web_fetch"],
                    "last_attempt_at": record.get("last_attempt_at"),
                    "last_success_at": record.get("last_success_at"),
                    "stale": bool(record.get("stale")),
                    "error_code": record.get("error_code"),
                    "details": self._safe_tabbit_snapshot() or {},
                }
            )
        return values

    async def _persist(self) -> None:
        await asyncio.to_thread(self._persist_sync)

    def _persist_sync(self) -> None:
        with self._state_lock:
            self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            payload = {
                "schema_version": 1,
                "updated_at": _now(),
                "consents": deepcopy(self.consents),
                "items": deepcopy(self.records),
                "local_snapshot": deepcopy(self.local_snapshot),
                "tabbit_snapshot": self._safe_tabbit_snapshot(),
            }
            fd, temporary = tempfile.mkstemp(prefix=".status-", dir=self.state_root)
            descriptor_open = True
            try:
                if os.name != "nt":
                    os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    descriptor_open = False
                    json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.state_path)
                if os.name != "nt":
                    self.state_path.chmod(0o600)
            except Exception:
                if descriptor_open:
                    with suppress(OSError):
                        os.close(fd)
                with suppress(OSError):
                    Path(temporary).unlink()
                raise

    def _safe_tabbit_snapshot(self) -> dict | None:
        return self._project_tabbit_snapshot(self.tabbit_snapshot)

    @staticmethod
    def _project_tabbit_snapshot(snapshot: object) -> dict | None:
        if not isinstance(snapshot, dict):
            return None

        def safe_config(value: object) -> dict[str, bool]:
            config = value if isinstance(value, dict) else {}
            return {
                "browser_enabled": config.get("browser_enabled") is True,
                "web_fetch_enabled": config.get("web_fetch_enabled") is True,
                "instance_selected": config.get("instance_selected") is True
                or isinstance(config.get("instance_id"), str),
            }

        def safe_version(value: object) -> str | None:
            return (
                value
                if isinstance(value, str) and SAFE_VERSION_PATTERN.fullmatch(value) is not None
                else None
            )

        status = snapshot.get("status")
        raw_online = snapshot.get("online_instances")
        online_instances = (
            min(raw_online, 10_000)
            if isinstance(raw_online, int) and not isinstance(raw_online, bool) and raw_online >= 0
            else 0
        )
        saved = safe_config(snapshot.get("saved_config"))
        applied = safe_config(snapshot.get("applied_config"))
        return {
            "status": status if status in SAFE_TABBIT_STATUSES else "error",
            "browser_enabled": snapshot.get("browser_enabled") is True,
            "web_fetch_enabled": snapshot.get("web_fetch_enabled") is True,
            "saved_config": saved,
            "applied_config": applied,
            "restart_required": snapshot.get("restart_required") is True,
            "plugin_version": safe_version(snapshot.get("plugin_version")),
            "browser_version": safe_version(snapshot.get("browser_version")),
            "launcher_present": snapshot.get("launcher_present") is True,
            "cli_available": snapshot.get("cli_available") is True,
            "online_instances": online_instances,
            "instance_selection_required": status == "instance_selection_required",
        }

    async def close(self) -> None:
        with self._state_lock:
            self.closed = True
            tasks = list(self.batch_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        with self._state_lock:
            self.batch_tasks.clear()
        await self._persist()
