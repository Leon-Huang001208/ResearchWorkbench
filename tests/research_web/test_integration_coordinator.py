"""Unified integration status, consent, persistence and probe-batch contracts."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research_web.integrations import IntegrationCoordinator
from app.research_web.integrations import coordinator as coordinator_module
from app.research_web.integrations.routes import router


def office_success(target):
    suffix = {"excel": ".xlsx", "word": ".docx", "powerpoint": ".pptx"}[target]
    return {
        "outcome": "available",
        "diagnostics": {
            "run_id": "a" * 32,
            "artifact_name": "research-workbench-" + "a" * 32 + suffix,
            "last_completed_step": "document_closed",
            "function_outcome": "available",
            "cleanup_outcome": "confirmed",
        },
    }


def data_source(
    source_id: str,
    *,
    auth: str = "none",
    fee: str = "free",
    configured: bool = True,
    dependency_ready: bool = True,
    integrated: bool = True,
) -> dict:
    state = (
        "disabled"
        if not integrated
        else (
            "blocked_config"
            if not configured
            else "blocked_dependency" if not dependency_ready else "ready"
        )
    )
    return {
        "id": source_id,
        "name": source_id.upper(),
        "auth_type": auth,
        "fee": fee,
        "readiness": {
            "code_exists": True,
            "integration_completed": integrated,
            "configured": configured,
            "dependency_ready": dependency_ready,
            "allowed": integrated,
            "callable": integrated and configured and dependency_ready,
            "integration_state": state,
            "health": "untested",
            "last_checked_at": None,
            "failure_code": None,
            "duration_ms": None,
        },
    }


class FakeDataHub:
    def __init__(self, sources: list[dict], *, delay: float = 0.002):
        self.sources = {row["id"]: deepcopy(row) for row in sources}
        self.delay = delay
        self.active_public = 0
        self.active_vendor = 0
        self.max_public = 0
        self.max_vendor = 0
        self.calls: list[str] = []
        self.restored: dict[str, dict] = {}
        self.configuration_digests = {row["id"]: f"digest-{row['id']}" for row in sources}

    def catalog(self) -> dict:
        rows = list(deepcopy(self.sources).values())
        return {
            "sources": rows,
            "capabilities": [],
            "bindings": [
                {
                    "source_id": row["id"],
                    "capability_id": "search_news",
                    "implemented": row["readiness"]["integration_completed"],
                }
                for row in rows
            ],
        }

    def connection_center(self) -> dict:
        sources = []
        for row in self.sources.values():
            readiness = row["readiness"]
            sources.append(
                {
                    "id": row["id"],
                    "label": row["name"],
                    "auth_kind": row["auth_type"],
                    "configured": readiness["configured"],
                    "secret_configured": readiness["configured"] and row["auth_type"] != "none",
                    "probe_status": readiness["health"],
                    "integration_completed": readiness["integration_completed"],
                    "dependency_ready": readiness["dependency_ready"],
                    "allowed": readiness["allowed"],
                    "callable": readiness["callable"],
                    "integration_state": readiness["integration_state"],
                    "fee": row["fee"],
                    "warnings": [],
                }
            )
        return {"groups": [], "sources": sources, "platform": {}, "migration": {}}

    def source_configuration_digest(self, source_id: str) -> str:
        return self.configuration_digests[source_id]

    async def run_probe(self, source_id: str, idempotency_key: str) -> dict:
        del idempotency_key
        source = self.sources[source_id]
        vendor = source["auth_type"] != "none" or source["fee"] == "possibly_metered"
        if vendor:
            self.active_vendor += 1
            self.max_vendor = max(self.max_vendor, self.active_vendor)
        else:
            self.active_public += 1
            self.max_public = max(self.max_public, self.active_public)
        self.calls.append(source_id)
        try:
            await asyncio.sleep(self.delay)
            readiness = source["readiness"]
            healthy = readiness["integration_state"] == "ready"
            readiness.update(
                health="healthy" if healthy else "unavailable",
                last_checked_at="2026-09-15T04:00:00+00:00",
                failure_code=None if healthy else readiness["integration_state"],
                duration_ms=2,
                callable=healthy,
            )
            return {
                "id": f"probe-{source_id}",
                "source_id": source_id,
                "status": "completed",
                "health": readiness["health"],
                "failure_code": readiness["failure_code"],
                "duration_ms": 2,
                "last_checked_at": readiness["last_checked_at"],
                "completed_at": readiness["last_checked_at"],
            }
        finally:
            if vendor:
                self.active_vendor -= 1
            else:
                self.active_public -= 1

    def restore_probe_statuses(self, probes: dict[str, dict]) -> None:
        self.restored = deepcopy(probes)
        for source_id, probe in probes.items():
            if source_id in self.sources:
                self.sources[source_id]["readiness"].update(
                    health=probe["health"],
                    last_checked_at=probe["last_checked_at"],
                    failure_code=probe.get("failure_code"),
                    duration_ms=probe.get("duration_ms"),
                )


class FailingCatalogDataHub(FakeDataHub):
    def catalog(self) -> dict:
        raise ValueError("catalog unavailable")


class FakeLocalIntegrations:
    def __init__(self):
        self.calls = 0

    async def run_probe(self, idempotency_key: str) -> dict:
        del idempotency_key
        self.calls += 1
        await asyncio.sleep(0)
        return {
            "id": "local-probe",
            "status": "completed",
            "snapshot": {
                "platform": "macos",
                "service": {"online": True, "label": "本机服务在线"},
                "summary": {"available": 1, "needs_attention": 1, "total": 2},
                "categories": [
                    {
                        "id": "local_service",
                        "label": "本机服务",
                        "item_ids": ["research_web_service"],
                    },
                    {"id": "folders", "label": "文件夹", "item_ids": ["folder_sync"]},
                ],
                "items": [
                    {
                        "id": "research_web_service",
                        "category": "local_service",
                        "label": "Research Web 本机服务",
                        "discovery": "已发现",
                        "authorization": "无需授权",
                        "verification": "已验证",
                        "callable": True,
                        "status": "可用",
                        "message": "服务在线",
                        "detail": "",
                        "capabilities": ["local_service"],
                        "actions": [],
                        "last_checked_at": "2026-09-15T04:00:00+00:00",
                        "last_verified_at": "2026-09-15T04:00:00+00:00",
                    },
                    {
                        "id": "folder_sync",
                        "category": "folders",
                        "label": "双向文件同步",
                        "discovery": "未发现",
                        "authorization": "待配置",
                        "verification": "待验证",
                        "callable": False,
                        "status": "待配置",
                        "message": "尚未交付",
                        "detail": "",
                        "capabilities": ["file_sync"],
                        "actions": [],
                        "last_checked_at": "2026-09-15T04:00:00+00:00",
                        "last_verified_at": None,
                    },
                ],
                "last_checked_at": "2026-09-15T04:00:00+00:00",
            },
        }

    async def close(self) -> None:
        return None


class ToggleLocalIntegrations(FakeLocalIntegrations):
    def __init__(self):
        super().__init__()
        self.fail = False

    async def run_probe(self, idempotency_key: str) -> dict:
        if self.fail:
            self.calls += 1
            return {
                "id": "local-probe-failed",
                "status": "failed",
                "error": {"code": "probe_timeout", "message": "本机能力检测超时"},
            }
        return await super().run_probe(idempotency_key)


def test_local_unknowns_are_not_faults_and_bridge_is_not_double_counted(tmp_path):
    coordinator = IntegrationCoordinator(
        tmp_path, FakeDataHub([]), FakeLocalIntegrations(), FakeTabbit()
    )
    rows = []
    for identifier, status, discovery, verification in [
        ("excel_app", "可用", "已发现", "已验证"),
        ("excel_automation_bridge", "可用", "已发现", "已验证"),
        ("word_app", "待验证", "已发现", "待验证"),
        ("powerpoint_app", "异常", "已发现", "异常"),
        ("wind_terminal", "待验证", "已发现", "待验证"),
        ("ifind_terminal", "不适用", "不适用", "不适用"),
        ("chrome_app", "待验证", "已发现", "待验证"),
        ("edge_app", "未发现", "未发现", "不适用"),
    ]:
        rows.append(
            {
                "id": identifier,
                "status": status,
                "discovery": discovery,
                "verification": verification,
                "authorization": "无需授权",
                "callable": status == "可用",
                "category": "office",
            }
        )
    coordinator.local_snapshot = {"items": rows}
    result = coordinator.status("local")
    buckets = {item["id"]: item["bucket"] for item in result["items"]}
    assert buckets["local:wind_terminal"] == "unverified"
    assert buckets["local:ifind_terminal"] == "not_applicable"
    assert buckets["local:edge_app"] == "not_detected"
    assert buckets["local:powerpoint_app"] == "system_fault"
    assert result["summary"]["available"] == 1
    assert result["summary"]["total"] == 7


def test_local_status_reads_current_manager_evidence_instead_of_cached_success(tmp_path):
    local = FakeLocalIntegrations()
    current = {
        "items": [
            {
                "id": "word_app",
                "category": "office",
                "label": "Word",
                "status": "待验证",
                "discovery": "已发现",
                "authorization": "无需授权",
                "verification": "待验证",
                "callable": False,
                "last_verified_at": "2026-09-15T00:00:00Z",
            }
        ],
        "last_checked_at": "2026-10-09T03:00:00Z",
    }
    local.snapshot = lambda: deepcopy(current)
    coordinator = IntegrationCoordinator(tmp_path, FakeDataHub([]), local, FakeTabbit())
    coordinator.local_snapshot = {"items": [{**current["items"][0], "callable": True}]}
    result = coordinator.status("local")
    assert result["items"][0]["runtime_callable"] is False
    assert result["items"][0]["bucket"] == "stale"
    assert result["local_snapshot"]["last_checked_at"] == current["last_checked_at"]


class FakeTabbit:
    async def status(self) -> dict:
        return {
            "status": "ready",
            "browser_enabled": False,
            "web_fetch_enabled": False,
            "saved_config": {
                "browser_enabled": False,
                "web_fetch_enabled": False,
                "instance_id": None,
            },
            "applied_config": {
                "browser_enabled": True,
                "web_fetch_enabled": False,
                "instance_id": None,
            },
            "restart_required": True,
            "plugin_version": "0.3.4",
            "browser_version": "1.13.23",
            "launcher_present": True,
            "cli_available": True,
            "online_instances": 1,
            "selected_instance": "ABCDEF0123456789",
            "instances": [
                {
                    "id": "ABCDEF0123456789",
                    "name": "Alice /Users/alice/Library/Tabbit",
                    "online": True,
                    "profile_path": "/Users/alice/Library/Tabbit/Profile",
                }
            ],
            "user_data_dir": "/Users/alice/Library/Tabbit",
        }


@pytest.mark.asyncio
async def test_probe_batches_deduplicate_limit_concurrency_and_require_vendor_consent(tmp_path):
    sources = [data_source(f"public_{index}") for index in range(8)]
    sources.extend(
        [
            data_source("vendor_a", auth="api_key", fee="possibly_metered"),
            data_source("vendor_b", auth="account", fee="account"),
        ]
    )
    datahub = FakeDataHub(sources, delay=0.01)
    coordinator = IntegrationCoordinator(
        tmp_path / "integrations", datahub, FakeLocalIntegrations(), FakeTabbit()
    )

    first = coordinator.start_batch(scope="data", trigger="manual", idempotency_key="batch-key-a")
    duplicate = coordinator.start_batch(
        scope="data", trigger="manual", idempotency_key="batch-key-b"
    )
    assert duplicate["id"] == first["id"]
    result = await coordinator.wait_batch(first["id"])

    assert result["status"] == "completed"
    assert datahub.max_public == 4
    assert "vendor_a" not in datahub.calls and "vendor_b" not in datahub.calls
    assert result["items"]["data:vendor_a"]["status"] == "skipped"
    assert result["items"]["data:vendor_a"]["error_code"] == "auto_probe_consent_required"
    vendor_status = next(
        item for item in coordinator.status("data")["items"] if item["id"] == "data:vendor_a"
    )
    assert vendor_status["details"] == {
        "auto_probe_consent": False,
        "auto_probe_consent_required": True,
    }

    coordinator.set_auto_probe_consent("data:vendor_a", True)
    coordinator.set_auto_probe_consent("data:vendor_b", True)
    second = coordinator.start_batch(scope="data", trigger="manual", idempotency_key="batch-key-c")
    await coordinator.wait_batch(second["id"])
    assert datahub.max_vendor == 1
    assert {"vendor_a", "vendor_b"}.issubset(datahub.calls)
    await coordinator.close()


@pytest.mark.asyncio
async def test_completed_probe_batch_replays_same_scope_and_idempotency_key(tmp_path):
    datahub = FakeDataHub([data_source("cls")])
    coordinator = IntegrationCoordinator(
        tmp_path / "integrations", datahub, FakeLocalIntegrations(), FakeTabbit()
    )

    first = coordinator.start_batch(
        scope="data", trigger="manual", idempotency_key="stable-replay-key"
    )
    completed = await coordinator.wait_batch(first["id"])
    replay = coordinator.start_batch(
        scope="data", trigger="manual", idempotency_key="stable-replay-key"
    )

    assert replay == completed
    assert datahub.calls == ["cls"]
    await coordinator.close()


@pytest.mark.asyncio
async def test_overlapping_active_batch_registers_merged_idempotency_alias(tmp_path):
    datahub = FakeDataHub([data_source("cls")])
    coordinator = IntegrationCoordinator(
        tmp_path / "integrations", datahub, FakeLocalIntegrations(), FakeTabbit()
    )

    first = coordinator.start_batch(
        scope="data", trigger="manual", idempotency_key="active-alias-key-a"
    )
    merged = coordinator.start_batch(
        scope="data", trigger="manual", idempotency_key="active-alias-key-b"
    )
    completed = await coordinator.wait_batch(first["id"])
    replay = coordinator.start_batch(
        scope="data", trigger="manual", idempotency_key="active-alias-key-b"
    )

    assert merged["id"] == first["id"]
    assert replay == completed
    assert datahub.calls == ["cls"]
    await coordinator.close()


@pytest.mark.asyncio
async def test_probe_batch_retention_is_bounded_and_expires(tmp_path):
    now = [100.0]
    coordinator = IntegrationCoordinator(
        tmp_path / "integrations",
        FakeDataHub([data_source("cls")]),
        FakeLocalIntegrations(),
        FakeTabbit(),
        idempotency_ttl_seconds=10,
        max_retained_batches=2,
        monotonic_clock=lambda: now[0],
    )

    completed = []
    for key in ("retained-key-a", "retained-key-b", "retained-key-c"):
        batch = coordinator.start_batch(scope="data", trigger="manual", idempotency_key=key)
        completed.append(await coordinator.wait_batch(batch["id"]))

    with pytest.raises(KeyError):
        coordinator.batch(completed[0]["id"])
    assert coordinator.batch(completed[2]["id"])["status"] == "completed"

    replay = coordinator.start_batch(
        scope="data", trigger="manual", idempotency_key="retained-key-b"
    )
    assert replay["id"] == completed[1]["id"]

    now[0] += 11
    with pytest.raises(KeyError):
        coordinator.batch(completed[1]["id"])
    with pytest.raises(KeyError):
        coordinator.batch(completed[2]["id"])
    await coordinator.close()


@pytest.mark.asyncio
async def test_snapshot_restores_last_success_and_invalidates_changed_configuration(tmp_path):
    source = data_source("cls")
    first_hub = FakeDataHub([source])
    first = IntegrationCoordinator(
        tmp_path / "integrations", first_hub, FakeLocalIntegrations(), FakeTabbit()
    )
    batch = first.start_batch(scope="data", trigger="manual", idempotency_key="persist-a")
    await first.wait_batch(batch["id"])
    before = first.status("data")["items"][0]
    assert before["last_success_at"] == "2026-09-15T04:00:00+00:00"
    assert before["stale"] is False
    await first.close()

    changed = data_source("cls", dependency_ready=False)
    second_hub = FakeDataHub([changed])
    second = IntegrationCoordinator(
        tmp_path / "integrations", second_hub, FakeLocalIntegrations(), FakeTabbit()
    )
    second.load()
    restored = second.status("data")["items"][0]

    assert restored["last_success_at"] == before["last_success_at"]
    assert restored["stale"] is True
    assert restored["runtime_callable"] is False
    assert restored["bucket"] == "system_fault"
    assert second_hub.restored == {}
    payload = (tmp_path / "integrations/status.json").read_text(encoding="utf-8")
    assert "token" not in payload.lower() and "password" not in payload.lower()
    if os.name != "nt":
        assert (tmp_path / "integrations/status.json").stat().st_mode & 0o077 == 0
    await second.close()


@pytest.mark.asyncio
async def test_configuration_digest_change_stales_evidence_without_persisting_config(tmp_path):
    state_root = tmp_path / "integrations"
    secret_value = "super-secret-config-value"
    first_hub = FakeDataHub([data_source("wind")])
    first_hub.source_configuration_digest = lambda _source_id: coordinator_module._fingerprint(
        {"endpoint": secret_value, "secret_configured": True}
    )
    first = IntegrationCoordinator(state_root, first_hub, FakeLocalIntegrations(), FakeTabbit())
    batch = first.start_batch(
        scope="data", trigger="manual", idempotency_key="configuration-digest-a"
    )
    await first.wait_batch(batch["id"])
    await first.close()

    second_hub = FakeDataHub([data_source("wind")])
    second_hub.source_configuration_digest = lambda _source_id: coordinator_module._fingerprint(
        {"endpoint": "changed.internal", "secret_configured": True}
    )
    second = IntegrationCoordinator(state_root, second_hub, FakeLocalIntegrations(), FakeTabbit())
    second.load()

    restored = second.status("data")["items"][0]
    persisted = (state_root / "status.json").read_text(encoding="utf-8")
    assert restored["stale"] is True
    assert restored["runtime_callable"] is False
    assert second_hub.restored == {}
    assert secret_value not in persisted
    await second.close()


@pytest.mark.asyncio
async def test_consent_revocation_expires_evidence_and_startup_runs_async_batch(tmp_path):
    datahub = FakeDataHub([data_source("wind", auth="terminal", fee="account")])
    coordinator = IntegrationCoordinator(
        tmp_path / "integrations", datahub, FakeLocalIntegrations(), FakeTabbit()
    )
    coordinator.set_auto_probe_consent("data:wind", True)
    startup = coordinator.start()
    assert startup["trigger"] == "startup"
    await coordinator.wait_batch(startup["id"])
    assert coordinator.status("data")["items"][0]["runtime_callable"] is True

    coordinator.set_auto_probe_consent("data:wind", False)
    revoked = coordinator.status("data")["items"][0]
    assert revoked["authorized"] is False
    assert revoked["stale"] is True
    assert revoked["bucket"] == "user_action"
    await coordinator.close()


@pytest.mark.asyncio
async def test_concurrent_batch_write_cannot_overwrite_later_consent_revocation(
    tmp_path, monkeypatch
):
    state_root = tmp_path / "integrations"
    datahub = FakeDataHub([data_source("wind", auth="terminal", fee="account")])
    coordinator = IntegrationCoordinator(state_root, datahub, FakeLocalIntegrations(), FakeTabbit())
    coordinator.set_auto_probe_consent("data:wind", True)

    first_replace_started = threading.Event()
    allow_first_replace = threading.Event()
    revoke_started = threading.Event()
    replace_count = 0
    replace_count_lock = threading.Lock()
    real_replace = coordinator_module.os.replace

    def ordered_replace(source, target):
        nonlocal replace_count
        with replace_count_lock:
            replace_count += 1
            current = replace_count
        if current == 1:
            first_replace_started.set()
            assert allow_first_replace.wait(timeout=2)
        real_replace(source, target)

    monkeypatch.setattr(coordinator_module.os, "replace", ordered_replace)
    batch = coordinator.start_batch(
        scope="data", trigger="manual", idempotency_key="concurrent-persist"
    )
    await asyncio.wait_for(asyncio.to_thread(first_replace_started.wait, 2), timeout=3)

    async def release_batch_writer() -> None:
        await asyncio.wait_for(asyncio.to_thread(revoke_started.wait, 2), timeout=3)
        await asyncio.sleep(0.02)
        allow_first_replace.set()

    release_task = asyncio.create_task(release_batch_writer())

    def revoke() -> None:
        revoke_started.set()
        coordinator.set_auto_probe_consent("data:wind", False)

    await asyncio.wait_for(asyncio.to_thread(revoke), timeout=3)
    await release_task
    await coordinator.wait_batch(batch["id"])

    restored = IntegrationCoordinator(
        state_root,
        FakeDataHub([data_source("wind", auth="terminal", fee="account")]),
        FakeLocalIntegrations(),
        FakeTabbit(),
    )
    restored.load()
    assert restored.consents["data:wind"] is False
    await coordinator.close()
    await restored.close()


@pytest.mark.asyncio
async def test_unified_status_classifies_unimplemented_local_items_as_developer_owned(tmp_path):
    coordinator = IntegrationCoordinator(
        tmp_path / "integrations",
        FakeDataHub([data_source("cls")]),
        FakeLocalIntegrations(),
        FakeTabbit(),
    )
    batch = coordinator.start_batch(scope="all", trigger="manual", idempotency_key="all-items")
    await coordinator.wait_batch(batch["id"])
    status = coordinator.status("all")
    by_id = {item["id"]: item for item in status["items"]}

    assert status["summary"] == {
        "available": 3,
        "checking": 0,
        "user_action": 0,
        "system_fault": 0,
        "not_delivered": 1,
        "unverified": 0,
        "stale": 0,
        "not_detected": 0,
        "not_applicable": 0,
        "total": 4,
    }
    assert by_id["local:folder_sync"]["responsibility"] == "developer"
    assert by_id["local:folder_sync"]["bucket"] == "not_delivered"
    assert list(by_id["data:cls"]["stages"]) == [
        "registration",
        "authorization",
        "probe",
        "adaptation",
        "runtime",
    ]
    assert by_id["local:tabbit"]["details"]["saved_config"]["browser_enabled"] is False
    assert by_id["local:tabbit"]["details"]["applied_config"]["browser_enabled"] is True
    await coordinator.close()


@pytest.mark.asyncio
async def test_failed_local_reprobe_invalidates_old_available_snapshot(tmp_path):
    local = ToggleLocalIntegrations()
    coordinator = IntegrationCoordinator(
        tmp_path / "integrations",
        FakeDataHub([data_source("cls")]),
        local,
        FakeTabbit(),
    )
    first = coordinator.start_batch(
        scope="local", trigger="manual", idempotency_key="local-success"
    )
    await coordinator.wait_batch(first["id"])
    before = {item["id"]: item for item in coordinator.status("local")["items"]}
    assert before["local:research_web_service"]["runtime_callable"] is True

    local.fail = True
    second = coordinator.start_batch(
        scope="local", trigger="manual", idempotency_key="local-failure"
    )
    failed = await coordinator.wait_batch(second["id"])
    after = {item["id"]: item for item in coordinator.status("local")["items"]}

    assert failed["status"] == "completed_with_failures"
    assert failed["items"]["local:research_web_service"]["status"] == "failed"
    assert after["local:research_web_service"]["runtime_callable"] is False
    assert after["local:research_web_service"]["bucket"] == "system_fault"
    assert after["local:research_web_service"]["stale"] is True
    await coordinator.close()


@pytest.mark.parametrize(
    ("tabbit_status", "bucket", "responsibility"),
    [
        ("disabled", "user_action", "user"),
        ("instance_selection_required", "user_action", "user"),
        ("browser_offline", "user_action", "user"),
        ("launcher_missing", "system_fault", "system"),
    ],
)
def test_tabbit_non_ready_statuses_have_actionable_ownership(
    tmp_path, tabbit_status, bucket, responsibility
):
    coordinator = IntegrationCoordinator(
        tmp_path / tabbit_status,
        FakeDataHub([data_source("cls")]),
        FakeLocalIntegrations(),
        FakeTabbit(),
    )
    coordinator.tabbit_snapshot = {
        "status": tabbit_status,
        "applied_config": {"browser_enabled": tabbit_status != "disabled"},
    }

    item = next(
        value for value in coordinator.status("local")["items"] if value["id"] == "local:tabbit"
    )

    assert item["bucket"] == bucket
    assert item["responsibility"] == responsibility


@pytest.mark.parametrize(
    ("error_code", "bucket", "responsibility"),
    [
        ("vendor_auth_failed", "user_action", "user"),
        ("vendor_permission_denied", "user_action", "user"),
        ("blocked_dependency", "system_fault", "system"),
        ("dependency_version_mismatch", "system_fault", "system"),
        ("vendor_rate_limited", "system_fault", "vendor"),
        ("vendor_unreachable", "system_fault", "vendor"),
    ],
)
def test_data_probe_failures_identify_the_next_responsible_party(
    tmp_path, error_code, bucket, responsibility
):
    source = data_source("tinysoft")
    source["readiness"].update(health="unavailable", failure_code=error_code)
    coordinator = IntegrationCoordinator(
        tmp_path / error_code,
        FakeDataHub([source]),
        FakeLocalIntegrations(),
        FakeTabbit(),
    )

    item = coordinator.status("data")["items"][0]

    assert item["error_code"] == error_code
    assert item["bucket"] == bucket
    assert item["responsibility"] == responsibility


@pytest.mark.asyncio
async def test_batch_persistence_failure_is_queryable_and_cleans_task(tmp_path, monkeypatch):
    coordinator = IntegrationCoordinator(
        tmp_path / "integrations",
        FakeDataHub([data_source("cls")]),
        FakeLocalIntegrations(),
        FakeTabbit(),
    )
    persist = coordinator._persist

    async def fail_persist() -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(coordinator, "_persist", fail_persist)
    batch = coordinator.start_batch(
        scope="data", trigger="manual", idempotency_key="persist-failure"
    )
    completed = await coordinator.wait_batch(batch["id"])

    assert completed["status"] == "failed"
    assert completed["error_code"] == "integration_status_persist_failed"
    assert batch["id"] not in coordinator.batch_tasks

    monkeypatch.setattr(coordinator, "_persist", persist)
    await coordinator.close()


@pytest.mark.asyncio
async def test_tabbit_status_and_persistence_deep_project_sensitive_instance_data(tmp_path):
    state_root = tmp_path / "integrations"
    coordinator = IntegrationCoordinator(
        state_root,
        FakeDataHub([data_source("cls")]),
        FakeLocalIntegrations(),
        FakeTabbit(),
    )
    batch = coordinator.start_batch(
        scope="local", trigger="manual", idempotency_key="safe-tabbit-projection"
    )
    await coordinator.wait_batch(batch["id"])

    item = next(
        value for value in coordinator.status("local")["items"] if value["id"] == "local:tabbit"
    )
    details = item["details"]
    assert details["online_instances"] == 1
    assert details["plugin_version"] == "0.3.4"
    assert details["saved_config"] == {
        "browser_enabled": False,
        "web_fetch_enabled": False,
        "instance_selected": False,
    }
    assert not {"instances", "selected_instance", "instance_id", "user_data_dir"} & details.keys()
    assert "/Users/alice" not in json.dumps(details)

    persisted = (state_root / "status.json").read_text(encoding="utf-8")
    assert "/Users/alice" not in persisted
    assert '"instances"' not in persisted
    assert '"selected_instance"' not in persisted
    await coordinator.close()

    legacy_payload = json.loads((state_root / "status.json").read_text(encoding="utf-8"))
    legacy_payload["tabbit_snapshot"] = await FakeTabbit().status()
    (state_root / "status.json").write_text(json.dumps(legacy_payload), encoding="utf-8")
    restored = IntegrationCoordinator(
        state_root,
        FakeDataHub([data_source("cls")]),
        FakeLocalIntegrations(),
        FakeTabbit(),
    )
    restored.load()
    rewritten = (state_root / "status.json").read_text(encoding="utf-8")
    assert "/Users/alice" not in rewritten
    assert '"instances"' not in rewritten
    assert '"selected_instance"' not in rewritten
    restored_item = next(
        value for value in restored.status("local")["items"] if value["id"] == "local:tabbit"
    )
    assert "/Users/alice" not in json.dumps(restored_item["details"])
    assert "instances" not in restored_item["details"]
    await restored.close()


def test_load_scrubs_legacy_tabbit_snapshot_before_datahub_restore_can_fail(tmp_path):
    state_root = tmp_path / "integrations"
    state_root.mkdir()
    legacy_snapshot = asyncio.run(FakeTabbit().status())
    (state_root / "status.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "consents": {},
                "items": {},
                "local_snapshot": None,
                "tabbit_snapshot": legacy_snapshot,
            }
        ),
        encoding="utf-8",
    )
    coordinator = IntegrationCoordinator(
        state_root,
        FailingCatalogDataHub([data_source("cls")]),
        FakeLocalIntegrations(),
        FakeTabbit(),
    )

    coordinator.load()

    rewritten = (state_root / "status.json").read_text(encoding="utf-8")
    assert "/Users/alice" not in rewritten
    assert '"instances"' not in rewritten
    assert '"selected_instance"' not in rewritten


def test_failed_tabbit_scrub_propagates_and_load_can_retry(tmp_path, monkeypatch):
    state_root = tmp_path / "integrations"
    state_root.mkdir()
    legacy_snapshot = asyncio.run(FakeTabbit().status())
    (state_root / "status.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "consents": {},
                "items": {},
                "local_snapshot": None,
                "tabbit_snapshot": legacy_snapshot,
            }
        ),
        encoding="utf-8",
    )
    coordinator = IntegrationCoordinator(
        state_root,
        FakeDataHub([data_source("cls")]),
        FakeLocalIntegrations(),
        FakeTabbit(),
    )
    persist = coordinator._persist_sync

    def fail_persist() -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(coordinator, "_persist_sync", fail_persist)
    with pytest.raises(RuntimeError, match="sanitize persisted integration status"):
        coordinator.load()

    monkeypatch.setattr(coordinator, "_persist_sync", persist)
    coordinator.load()
    rewritten = (state_root / "status.json").read_text(encoding="utf-8")
    assert "/Users/alice" not in rewritten


@pytest.mark.asyncio
async def test_probe_timeout_is_safe_and_close_cancels_active_batch(tmp_path):
    timed_out = IntegrationCoordinator(
        tmp_path / "timed-out",
        FakeDataHub([data_source("cls")], delay=0.05),
        FakeLocalIntegrations(),
        FakeTabbit(),
        probe_timeout_seconds=0.01,
    )
    batch = timed_out.start_batch(scope="data", trigger="manual", idempotency_key="timeout-batch")
    completed = await timed_out.wait_batch(batch["id"])
    assert completed["status"] == "completed"
    assert completed["items"]["data:cls"]["error_code"] == "probe_timeout"
    await timed_out.close()

    cancelled = IntegrationCoordinator(
        tmp_path / "cancelled",
        FakeDataHub([data_source("cls")], delay=0.2),
        FakeLocalIntegrations(),
        FakeTabbit(),
    )
    active = cancelled.start_batch(scope="data", trigger="manual", idempotency_key="cancel-batch")
    await asyncio.sleep(0)
    await cancelled.close()
    assert cancelled.batch(active["id"])["status"] == "cancelled"


def test_integration_api_exposes_status_batches_and_consent(tmp_path):
    coordinator = IntegrationCoordinator(
        tmp_path / "integrations",
        FakeDataHub([data_source("cls")]),
        FakeLocalIntegrations(),
        FakeTabbit(),
    )
    app = FastAPI()
    app.include_router(router)
    app.state.research = SimpleNamespace(integrations=coordinator)

    with TestClient(app) as client:
        status = client.get("/api/research/integrations/status?scope=data")
        assert status.status_code == 200

        missing_action = client.post(
            "/api/research/integrations/probe-batches",
            headers={"Idempotency-Key": "integration-api-a"},
            json={"scope": "data"},
        )
        assert missing_action.status_code == 403
        assert missing_action.json()["detail"]["code"] == "integration_user_action_required"

        cross_origin = client.post(
            "/api/research/integrations/probe-batches",
            headers={
                "Idempotency-Key": "integration-api-a",
                "Origin": "https://evil.example",
                "X-Research-User-Action": "?1",
            },
            json={"scope": "data"},
        )
        assert cross_origin.status_code == 403

        accepted = client.post(
            "/api/research/integrations/probe-batches",
            headers={
                "Idempotency-Key": "integration-api-a",
                "Origin": "http://testserver",
                "X-Research-User-Action": "?1",
            },
            json={"scope": "data"},
        )
        assert accepted.status_code == 202
        batch_id = accepted.json()["id"]
        for _ in range(100):
            current = client.get(f"/api/research/integrations/probe-batches/{batch_id}")
            if current.json()["status"] == "completed":
                break
        assert current.json()["status"] == "completed"
        consent = client.put(
            "/api/research/integrations/data%3Acls/auto-probe-consent",
            headers={
                "Origin": "http://testserver",
                "X-Research-User-Action": "?1",
            },
            json={"consent": True},
        )
        assert consent.status_code == 200
        assert consent.json()["consent"] is True

    asyncio.run(coordinator.close())


@pytest.mark.asyncio
async def test_office_auto_real_manager_serial_dedup_refresh_restart_and_owner(tmp_path):
    from app.research_web.local_integrations import DetectionEnvironment, LocalIntegrationManager

    apps = tmp_path / "Applications"
    apps.mkdir()
    for name in ("Excel", "Word", "PowerPoint"):
        (apps / f"Microsoft {name}.app").mkdir()
    env = DetectionEnvironment(
        system="Darwin",
        home=tmp_path,
        application_roots=(apps,),
        office_addin_roots=(),
        module_available=lambda _name: True,
        registry_app_exists=lambda _name: False,
        environment_variables={},
    )
    calls = []
    active = 0
    maximum = 0

    def verifier(target):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        calls.append(target)
        active -= 1
        return {"outcome": "failed"} if target == "word" else office_success(target)

    manager = LocalIntegrationManager(
        tmp_path / "local",
        environment=env,
        verifier=verifier,
        context_fingerprint=lambda target: target,
    )
    hub = FakeDataHub([])
    coordinator = IntegrationCoordinator(tmp_path / "integrations", hub, manager, FakeTabbit())
    first = coordinator.start_batch(scope="local", trigger="startup", idempotency_key="disabled")
    await coordinator.wait_batch(first["id"])
    assert calls == []
    for identifier in coordinator_module.OFFICE_AUTO_TARGETS:
        coordinator.set_auto_probe_consent(identifier, True)
    batch = coordinator.start_batch(
        scope="local", trigger="office_consent", idempotency_key="enable"
    )
    await coordinator.wait_batch(batch["id"])
    assert calls == ["excel", "word", "powerpoint"]
    assert maximum == 1
    for index in range(3):
        coordinator.status("local")
        refresh = coordinator.start_batch(
            scope="local", trigger="manual", idempotency_key=f"refresh-{index}"
        )
        await coordinator.wait_batch(refresh["id"])
    assert calls == ["excel", "word", "powerpoint"]
    assert hub.calls == []
    await coordinator.close()
    await manager.close()
    restored_manager = LocalIntegrationManager(
        tmp_path / "local",
        environment=env,
        verifier=verifier,
        context_fingerprint=lambda target: target,
    )
    restored = IntegrationCoordinator(
        tmp_path / "integrations", hub, restored_manager, FakeTabbit()
    )
    startup = restored.start()
    await restored.wait_batch(startup["id"])
    assert calls == ["excel", "word", "powerpoint"]
    assert restored.consents["local:word_app"] is True
    for identifier in coordinator_module.OFFICE_AUTO_TARGETS:
        restored.set_auto_probe_consent(identifier, False)
    startup = restored.start_batch(scope="local", trigger="startup", idempotency_key="off")
    await restored.wait_batch(startup["id"])
    assert calls == ["excel", "word", "powerpoint"]
    copied = tmp_path / "other" / "status.json"
    copied.parent.mkdir()
    copied.write_bytes(restored.state_path.read_bytes())
    foreign = IntegrationCoordinator(copied.parent, hub, restored_manager, FakeTabbit())
    foreign.load()
    assert not any(key.startswith("local:") for key in foreign.consents)
    await restored.close()
    await restored_manager.close()


@pytest.mark.asyncio
async def test_office_auto_close_cancels_only_owned_task_and_does_not_launch_next(tmp_path):
    from app.research_web.local_integrations import DetectionEnvironment, LocalIntegrationManager

    apps = tmp_path / "Applications"
    apps.mkdir()
    for name in ("Excel", "Word", "PowerPoint"):
        (apps / f"Microsoft {name}.app").mkdir()
    env = DetectionEnvironment(
        system="Darwin",
        home=tmp_path,
        application_roots=(apps,),
        office_addin_roots=(),
        module_available=lambda _name: True,
        registry_app_exists=lambda _name: False,
        environment_variables={},
    )
    entered, release = threading.Event(), threading.Event()
    calls = []

    def verifier(target):
        calls.append(target)
        entered.set()
        release.wait(2)
        return office_success(target)

    manager = LocalIntegrationManager(
        tmp_path / "local",
        environment=env,
        verifier=verifier,
        context_fingerprint=lambda target: target,
    )
    coordinator = IntegrationCoordinator(
        tmp_path / "integrations", FakeDataHub([]), manager, FakeTabbit()
    )
    for identifier in coordinator_module.OFFICE_AUTO_TARGETS:
        coordinator.set_auto_probe_consent(identifier, True)
    batch = coordinator.start_batch(
        scope="local", trigger="office_consent", idempotency_key="close"
    )
    assert await asyncio.to_thread(entered.wait, 2)
    for identifier in coordinator_module.OFFICE_AUTO_TARGETS:
        coordinator.set_auto_probe_consent(identifier, False)
    release.set()
    await coordinator.wait_batch(batch["id"])
    assert calls == ["excel"]
    await coordinator.close()
    await manager.close()


def test_office_failed_enable_persistence_rolls_back_permission(tmp_path, monkeypatch):
    coordinator = IntegrationCoordinator(
        tmp_path, FakeDataHub([]), FakeLocalIntegrations(), FakeTabbit()
    )
    coordinator.load()

    def fail():
        raise OSError("storage unavailable")

    monkeypatch.setattr(coordinator, "_persist_sync", fail)
    with pytest.raises(OSError):
        coordinator.set_auto_probe_consent("local:word_app", True)
    assert coordinator.consents.get("local:word_app") is not True
    for identifier in (
        "local:wind_terminal",
        "local:wind_excel_addin",
        "local:excel_automation_bridge",
        "local:anything",
    ):
        with pytest.raises(ValueError):
            coordinator.set_auto_probe_consent(identifier, True)


@pytest.mark.asyncio
async def test_office_waits_again_when_another_task_starts_and_finishes_batch_item(tmp_path):
    class BusyLocal:
        state_root = tmp_path / "local"

        def __init__(self):
            self.verification_tasks = {}
            self.calls = []
            first = asyncio.create_task(asyncio.sleep(0))
            self.verification_tasks["first"] = first

            def replace(_task):
                self.verification_tasks["second"] = asyncio.create_task(asyncio.sleep(0.01))

            first.add_done_callback(replace)

        def automatic_verification_state(self, _target):
            return {
                "eligible": True,
                "fingerprint": "same",
                "evidence_current": False,
                "busy": any(not task.done() for task in self.verification_tasks.values()),
            }

        def start_verification(self, target, _key):
            assert not any(not task.done() for task in self.verification_tasks.values())
            self.calls.append(target)
            self.verification_tasks["own"] = asyncio.create_task(asyncio.sleep(0))
            return {"id": "own"}

        def verification(self, _identifier):
            return {"status": "completed", "outcome": "available"}

        def snapshot(self):
            return {"items": []}

    local = BusyLocal()
    coordinator = IntegrationCoordinator(
        tmp_path / "integrations", FakeDataHub([]), local, FakeTabbit()
    )
    coordinator.set_auto_probe_consent("local:word_app", True)
    batch = {"id": "busy-chain", "items": {}}
    await coordinator._verify_consented_office(batch)
    assert local.calls == ["word"]
    assert batch["items"]["local:word_app"]["status"] == "completed"


@pytest.mark.asyncio
async def test_office_enable_after_local_stage_consumes_in_the_existing_all_batch(tmp_path):
    from app.research_web.local_integrations import DetectionEnvironment, LocalIntegrationManager

    apps = tmp_path / "Applications"
    apps.mkdir()
    (apps / "Microsoft Word.app").mkdir()
    env = DetectionEnvironment(
        system="Darwin",
        home=tmp_path,
        application_roots=(apps,),
        office_addin_roots=(),
        module_available=lambda _name: True,
        registry_app_exists=lambda _name: False,
        environment_variables={},
    )
    calls = []

    def verifier(target):
        calls.append(target)
        return office_success(target)

    manager = LocalIntegrationManager(
        tmp_path / "local",
        environment=env,
        verifier=verifier,
        context_fingerprint=lambda target: target,
    )
    coordinator = IntegrationCoordinator(
        tmp_path / "integrations",
        FakeDataHub([data_source("cls")], delay=0.2),
        manager,
        FakeTabbit(),
    )
    existing = coordinator.start_batch(scope="all", trigger="manual", idempotency_key="slow-all")
    for _ in range(100):
        if manager._latest is not None:
            break
        await asyncio.sleep(0.001)
    assert manager._latest is not None
    assert coordinator.batch(existing["id"])["status"] == "checking"
    coordinator.set_auto_probe_consent("local:word_app", True)
    accepted = coordinator.start_batch(
        scope="local", trigger="office_consent", idempotency_key="late-enable"
    )
    assert accepted["id"] == existing["id"]
    await coordinator.wait_batch(existing["id"])
    assert calls == ["word"]
    await coordinator.close()
    await manager.close()


def test_local_only_restore_never_reads_data_catalog_or_credentials(tmp_path):
    calls = []

    class SensitiveHub(FakeDataHub):
        def catalog(self):
            calls.append("catalog")
            raise ValueError("data discovery not allowed here")

        def connection_center(self):
            calls.append("credentials")
            raise ValueError("credential metadata not allowed here")

    initial = IntegrationCoordinator(
        tmp_path, FakeDataHub([]), FakeLocalIntegrations(), FakeTabbit()
    )
    initial._persist_sync()
    restored = IntegrationCoordinator(
        tmp_path, SensitiveHub([]), FakeLocalIntegrations(), FakeTabbit()
    )
    restored.status("local")
    assert calls == []
    restored.set_auto_probe_consent("local:word_app", True)
    assert calls == []
