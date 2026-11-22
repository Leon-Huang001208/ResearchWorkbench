"""Real account Store/ResearchService/HTTP contracts; external work is fail-on-call."""

import asyncio
import base64
import copy
import hashlib
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.research_web import watchlist_import as imports
from app.research_web.asset_workspace import AssetWorkspace
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store, StoreError
from tests.research_web.test_asset_workspace import (  # noqa: F401
    NativeFixture,
    isolated_host_credentials,
)

HEADER = "asset,asset_type,name\n"
SAMPLE = HEADER + "600519.SH,stock,贵州茅台\n000001.SZ,stock,同名\n430001.BJ,stock,北交😀\n"


def body(text=SAMPLE, **updates):
    raw = text.encode("utf-8") if isinstance(text, str) else text
    return {
        "schema_version": 1,
        "file_base64": base64.b64encode(raw).decode(),
        "file_sha256": hashlib.sha256(raw).hexdigest(),
        "selections": {},
        "skipped_rows": [],
        **updates,
    }


def install_catalog(workspace, *, now=None, rows=None):
    rows = rows or [
        {
            "asset": "600519.SH",
            "code": "600519",
            "name": "贵州茅台",
            "exchange": "SH",
            "asset_type": "stock",
        },
        {
            "asset": "000001.SZ",
            "code": "000001",
            "name": "同名",
            "exchange": "SZ",
            "asset_type": "stock",
        },
        {
            "asset": "430001.BJ",
            "code": "430001",
            "name": "北交😀",
            "exchange": "BJ",
            "asset_type": "stock",
        },
        {
            "asset": "000001.SH",
            "code": "000001",
            "name": "同名",
            "exchange": "SH",
            "asset_type": "stock",
        },
    ]
    directory = workspace.directory
    directory.fingerprint = lambda: "authorized-fixture"
    directory._persist(
        {
            "items": rows,
            "provider": "tinysoft",
            "total_count": len(rows),
            "fingerprint": "authorized-fixture",
            "loaded_at": now or directory.clock(),
            "as_of": "2026-10-28",
        }
    )


@pytest.fixture
def host(tmp_path, monkeypatch):
    service = ResearchService(NativeFixture(), Store(tmp_path / "account-a"))
    calls = []

    def deny(*_args, **_kwargs):
        calls.append("external")
        pytest.fail("watchlist import called provider/model/secret/SDK")

    for obj, names in [
        (service.datahub, ["asset_directory", "query"]),
        (service.datahub.connections, ["read_source_secret"]),
        (service.client, ["history"]),
    ]:
        for name in names:
            monkeypatch.setattr(obj, name, deny)
    monkeypatch.setattr(service.asset_workspace.directory, "loader", deny)
    original_rpc = service.client.rpc

    async def guarded_rpc(method, payload):
        if method in {"session.send", "session.create", "tool.call", "model.generate"}:
            deny()
        return await original_rpc(method, payload)

    monkeypatch.setattr(service.client, "rpc", guarded_rpc)
    install_catalog(service.asset_workspace)
    app = create_app(service)
    app.state.research = service
    client = TestClient(app)
    target = service.asset_workspace.create_watchlist("保留原自选😀", 15)
    yield client, service, target
    client.close()
    asyncio.run(service.close())
    assert calls == []


def preview(host, payload=None):
    client, _, target = host
    result = client.post(
        f"/api/research/watchlists/{target['id']}/imports/preview", json=payload or body()
    )
    assert result.status_code == 200, result.text
    return result.json()


def confirm(host, frozen, key="import-test-key", **updates):
    client, _, target = host
    return client.post(
        f"/api/research/watchlists/{target['id']}/imports/{frozen['import_id']}/confirm",
        json={
            "schema_version": 1,
            "preview_digest": frozen["preview_digest"],
            "confirmed": True,
            **updates,
        },
        headers={"Idempotency-Key": key},
    )


def test_success_preserves_old_items_all_other_business_and_once_save(host, monkeypatch):
    client, service, target = host
    workspace = service.asset_workspace
    old = workspace.add_watchlist_item(
        target["id"], {"asset": "999999.SH", "asset_type": "stock", "name": "旧名"}
    )
    other = workspace.create_watchlist("其他列表", None)
    for key in ["sessions", "data_queries", "asset_alerts", "model_profiles"]:
        service.store.data.setdefault(key, {})["unchanged-fixture"] = {"value": key}
    service.store.save()
    before = copy.deepcopy(service.store.data)
    frozen = preview(host, body("\ufeff" + SAMPLE.replace("\n", "\r\n")))
    assert service.store.data["watchlists"] == before["watchlists"]
    assert [r["proposed_action"] for r in frozen["rows"]] == ["add"] * 3
    saves = []
    save = service.store.save
    monkeypatch.setattr(service.store, "save", lambda: (saves.append(1), save())[-1])
    response = confirm(host, frozen)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert len(saves) == 1 and receipt["added_count"] == 3
    current = client.get("/api/research/watchlists").json()["items"]
    items = next(w for w in current if w["id"] == target["id"])["items"]
    assert [i["asset"] for i in items] == ["999999.SH", "600519.SH", "000001.SZ", "430001.BJ"]
    assert items[0] == old and target["polling_minutes"] == 15
    assert service.store.data["watchlists"][other["id"]] == before["watchlists"][other["id"]]
    assert {
        k: v for k, v in service.store.data.items() if k not in {"watchlists", imports.NAMESPACE}
    } == {k: v for k, v in before.items() if k != "watchlists"}
    assert imports.digest(before["watchlists"][target["id"]]) == receipt["before_digest"]
    committed = service.store.data[imports.NAMESPACE]["previews"][frozen["import_id"]]
    assert "rows" not in committed and "贵州茅台" not in json.dumps(committed, ensure_ascii=False)


def test_selection_unsupported_duplicates_and_explicit_skip(host):
    _, service, target = host
    service.asset_workspace.add_watchlist_item(
        target["id"], {"asset": "600519.SH", "asset_type": "stock", "name": "原名"}
    )
    payload = body(
        HEADER
        + "000001,stock,\n同名,stock,\n600519.SH,stock,贵州茅台\n000001.SZ,stock,同名\n510300.SH,etf,ETF\n行业,industry,行业\n404040.SZ,stock,未知\n"
    )
    first = preview(host, payload)
    assert [r["status"] for r in first["rows"]] == [
        "ambiguous",
        "ambiguous",
        "ready",
        "ready",
        "unsupported_identity_catalog",
        "unsupported_identity_catalog",
        "unresolved",
    ]
    assert confirm(host, first).status_code == 409
    bad = dict(payload, selections={"1": "430001.BJ"})
    assert (
        host[0]
        .post(f"/api/research/watchlists/{target['id']}/imports/preview", json=bad)
        .status_code
        == 422
    )
    frozen = preview(
        host, dict(payload, selections={"1": "000001.SZ", "2": "000001.SH"}, skipped_rows=[5, 6, 7])
    )
    assert [r["proposed_action"] for r in frozen["rows"]] == [
        "add",
        "add",
        "skip_existing",
        "skip_file_duplicate",
        "skip_explicit",
        "skip_explicit",
        "skip_explicit",
    ]
    assert confirm(host, first).status_code == 409
    assert confirm(host, frozen).json()["added_count"] == 2
    assert len(service.store.data["watchlists"][target["id"]]["items"]) == 3


def test_name_mismatch_and_same_name_never_merge(host):
    frozen = preview(
        host, body(HEADER + "600519.SH,stock,别名\n000001.SZ,stock,同名\n000001.SH,stock,同名\n")
    )
    assert frozen["rows"][0]["status"] == "needs_selection"
    fixed = preview(
        host,
        body(
            HEADER + "600519.SH,stock,别名\n000001.SZ,stock,同名\n000001.SH,stock,同名\n",
            selections={"1": "600519.SH"},
        ),
    )
    assert confirm(host, fixed).json()["added_count"] == 3


@pytest.mark.parametrize(
    "text,code",
    [
        (b"\xff\xfe\x00", "csv_invalid"),
        (HEADER + "600519.SH,stock,=cmd\n", "formula_rejected"),
        (HEADER + '600519.SH,stock,"合法\n换行"\n', "field_invalid"),
        (HEADER + "600519.SH,stock,空\x00\n", "field_invalid"),
        (HEADER + '600519.SH,stock,"未闭合\n', "csv_invalid"),
        ("asset,asset_type,name,extra\na,b,c,d\n", "header_invalid"),
        (HEADER + "600519.SH,stock,名,额外\n", "columns_invalid"),
        (HEADER, "empty"),
        (HEADER + "600519.SH,stock," + "长" * 121 + "\n", "field_invalid"),
    ],
)
def test_invalid_csv_no_side_effect(host, text, code):
    client, service, target = host
    before = copy.deepcopy(service.store.data)
    response = client.post(
        f"/api/research/watchlists/{target['id']}/imports/preview", json=body(text)
    )
    assert response.status_code == 422 and response.json()["error"]["code"].endswith(code)
    assert service.store.data == before


def test_strict_json_hash_decisions_and_file_budgets(host):
    client, service, target = host
    endpoint = f"/api/research/watchlists/{target['id']}/imports/preview"
    for update in [
        {"owner": "b"},
        {"root": "/tmp"},
        {"schema_version": True},
        {"schema_version": "1"},
        {"file_sha256": "0" * 64},
        {"file_base64": "###"},
        {"skipped_rows": [True]},
        {"skipped_rows": [2, 2]},
        {"selections": {"999": "600519.SH"}},
    ]:
        assert client.post(endpoint, json=body(**update)).status_code == 422
    assert client.post(endpoint, json=body(b"x" * (imports.MAX_FILE_BYTES + 1))).status_code in {
        413,
        422,
    }
    assert client.post(endpoint, json=body(HEADER + "600519.SH,stock,\n" * 1001)).status_code == 413
    frozen = preview(host)
    for update in [
        {"owner": "b"},
        {"schema_version": True},
        {"confirmed": 1},
        {"confirmed": False},
    ]:
        assert confirm(host, frozen, **update).status_code == 422
    assert confirm(host, frozen, key="short").status_code == 422
    assert confirm(host, frozen, preview_digest="0" * 64).status_code == 409
    assert service.store.data["watchlists"][target["id"]]["items"] == []


@pytest.mark.parametrize(
    "change", ["missing", "broken", "revoked", "stale", "fingerprint", "content"]
)
def test_catalog_change_blocks_whole_commit_without_refresh(host, change):
    _, service, target = host
    workspace = service.asset_workspace
    frozen = preview(host)
    path = workspace.directory.root / "index.json"
    if change == "missing":
        path.unlink()
    elif change == "broken":
        path.write_text("{broken")
    elif change == "revoked":

        def revoked():
            raise StoreError("revoked")

        workspace.directory.fingerprint = revoked
    elif change == "stale":
        workspace.directory.clock = lambda: frozen["created_at"] + 25 * 3600
    elif change == "fingerprint":
        workspace.directory.fingerprint = lambda: "other-fingerprint"
    else:
        record = json.loads(path.read_text())
        record["items"][0]["name"] = "修改"
        workspace.directory._persist(record)
    assert confirm(host, frozen).status_code == 409
    assert service.store.data["watchlists"][target["id"]]["items"] == []
    assert workspace.directory.task is None
    unavailable = preview(host)
    assert (
        not unavailable["can_confirm"]
        if change != "content"
        else unavailable["rows"][0]["status"] == "needs_selection"
    )


def test_target_and_metadata_mutation_ttl_and_corrupt_manifest(host):
    _, service, target = host
    frozen = preview(host)
    service.asset_workspace.add_watchlist_item(
        target["id"], {"asset": "999999.SH", "asset_type": "stock", "name": "介入"}
    )
    assert confirm(host, frozen).json()["error"]["code"] == "watchlist_import_target_changed"
    frozen = preview(host)
    service.store.data["watchlists"][target["id"]]["polling_minutes"] = 60
    assert confirm(host, frozen).status_code == 409
    frozen = preview(host)
    service.asset_workspace.watchlist_imports.clock = lambda: frozen["expires_at"]
    assert confirm(host, frozen).json()["error"]["code"] == "watchlist_import_preview_expired"
    service.asset_workspace.watchlist_imports.clock = lambda: frozen["created_at"]
    service.store.data[imports.NAMESPACE]["previews"][frozen["import_id"]]["rows"][0][
        "selected"
    ] = "000001.SZ"
    assert confirm(host, frozen).json()["error"]["code"] == "watchlist_import_preview_corrupt"


def test_old_dirty_target_type_conflict_and_no_changes(host):
    _, service, target = host
    old = service.asset_workspace.add_watchlist_item(
        target["id"], {"asset": "600519.SH", "asset_type": "etf", "name": "错误旧项"}
    )
    frozen = preview(host, body(HEADER + "600519.SH,stock,贵州茅台\n"))
    assert frozen["rows"][0]["status"] == "target_integrity_conflict"
    assert confirm(host, frozen).status_code == 409
    frozen = preview(host, body(HEADER + "600519.SH,stock,贵州茅台\n", skipped_rows=[1]))
    assert confirm(host, frozen).json()["status"] == "no_changes"
    assert service.store.data["watchlists"][target["id"]]["items"] == [old]
    service.store.data["watchlists"][target["id"]]["items"].append(copy.deepcopy(old))
    assert (
        preview(host, body(HEADER + "600519.SH,stock,贵州茅台\n"))["rows"][0]["status"]
        == "target_integrity_conflict"
    )


def test_concurrent_keys_previews_and_restarts_preserve_receipt(host):
    _, service, target = host
    workspace = service.asset_workspace
    frozen = preview(host)
    data = {"schema_version": 1, "preview_digest": frozen["preview_digest"], "confirmed": True}
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(
            pool.map(
                lambda _: workspace.confirm_watchlist_import(
                    target["id"], frozen["import_id"], data, "same-key-concurrent"
                ),
                range(4),
            )
        )
    assert all(r == receipts[0] for r in receipts) and receipts[0]["added_count"] == 3
    assert confirm(host, frozen, "different-key-same-preview").json() == receipts[0]
    assert confirm(host, frozen, "same-key-concurrent", preview_digest="0" * 64).status_code == 409
    # A complete index backup and a fresh process-equivalent Store reader recover both sides.
    backup = service.store.root.parent / "backup-index.json"
    shutil.copy2(service.store.index, backup)
    restarted = AssetWorkspace(SimpleNamespace(store=Store(service.store.root)))
    install_catalog(restarted)
    replay = restarted.confirm_watchlist_import(
        target["id"], frozen["import_id"], data, "same-key-concurrent"
    )
    assert replay == receipts[0]
    restored_root = service.store.root.parent / "restored-account"
    restored_root.mkdir()
    shutil.copy2(backup, restored_root / "index.json")
    # Backup restored at another root is another owner scope and cannot replay a token.
    restored = AssetWorkspace(SimpleNamespace(store=Store(restored_root)))
    install_catalog(restored)
    with pytest.raises(StoreError):
        restored.confirm_watchlist_import(
            target["id"], frozen["import_id"], data, "same-key-concurrent"
        )
    shutil.copy2(backup, service.store.index)
    assert service.store.index.stat().st_mode & 0o777 == backup.stat().st_mode & 0o777
    assert service.store.index.read_bytes() == backup.read_bytes()
    assert (
        Store(service.store.root).data["watchlists"][target["id"]]["items"]
        == restarted.store.data["watchlists"][target["id"]]["items"]
    )


def test_two_previews_same_target_only_one_succeeds(host):
    _, service, target = host
    first = preview(host)
    second = preview(host, body(SAMPLE + "600519.SH,stock,贵州茅台\n"))

    def run(pair):
        frozen, key = pair
        try:
            return service.asset_workspace.confirm_watchlist_import(
                target["id"],
                frozen["import_id"],
                {
                    "schema_version": 1,
                    "preview_digest": frozen["preview_digest"],
                    "confirmed": True,
                },
                key,
            )["status"]
        except StoreError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(run, [(first, "first-preview-key"), (second, "second-preview-key")])
        )
    assert sorted(results) == ["committed", "watchlist_import_target_changed"]
    assert len(service.store.data["watchlists"][target["id"]]["items"]) == 3


@pytest.mark.parametrize("fault", ["json", "fsync", "replace"])
def test_save_fault_rolls_back_memory_and_disk_then_retry(host, monkeypatch, fault):
    _, service, _target = host
    frozen = preview(host)
    disk = service.store.index.read_bytes()
    memory = copy.deepcopy(service.store.data)

    def fail(*args, **kwargs):
        raise OSError("injected-before-replace")

    with monkeypatch.context() as patch:
        if fault == "json":
            patch.setattr(json, "dump", fail)
        else:
            patch.setattr(os, fault, fail)
        response = confirm(host, frozen)
    assert response.status_code == 503 and service.store.index.read_bytes() == disk
    assert service.store.data == memory
    assert confirm(host, frozen).json()["added_count"] == 3


def test_response_lost_after_replace_reads_original_receipt(host):
    _, service, target = host
    frozen = preview(host)
    original = service.asset_workspace.confirm_watchlist_import

    def lost():
        original(
            target["id"],
            frozen["import_id"],
            {"preview_digest": frozen["preview_digest"]},
            "response-lost-key",
        )
        raise ConnectionError("response lost after successful save")

    with pytest.raises(ConnectionError):
        lost()
    restarted = AssetWorkspace(SimpleNamespace(store=Store(service.store.root)))
    install_catalog(restarted)
    receipt = restarted.confirm_watchlist_import(
        target["id"],
        frozen["import_id"],
        {"preview_digest": frozen["preview_digest"]},
        "response-lost-key",
    )
    assert receipt["added_item_ids"] == [
        item["id"] for item in restarted.store.data["watchlists"][target["id"]]["items"]
    ]
    assert receipt["added_count"] == 3


def test_namespace_budget_retains_committed_receipts(host, monkeypatch):
    _, service, _ = host
    frozen = preview(host)
    receipt = confirm(host, frozen).json()
    engine = service.asset_workspace.watchlist_imports
    monkeypatch.setattr(imports, "MAX_ACTIVE_PREVIEWS", 1)
    active = preview(host, body(HEADER + "600519.SH,stock,\n"))
    rejected = host[0].post(
        f"/api/research/watchlists/{host[2]['id']}/imports/preview",
        json=body(HEADER + "000001.SZ,stock,\n"),
    )
    assert rejected.status_code == 429
    engine.clock = lambda: active["expires_at"] + 1
    preview(host, body(HEADER + "000001.SZ,stock,\n"))
    assert (
        service.store.data[imports.NAMESPACE]["previews"][frozen["import_id"]]["receipt"] == receipt
    )
    before = copy.deepcopy(service.store.data)
    monkeypatch.setattr(imports, "MAX_NAMESPACE_BYTES", 10)
    rejected = host[0].post(
        f"/api/research/watchlists/{host[2]['id']}/imports/preview",
        json=body(HEADER + "000001.SZ,stock,\n"),
    )
    assert rejected.status_code == 413 and service.store.data == before


def test_real_tenant_backend_rejects_direct_and_cross_account(host, tmp_path, monkeypatch):
    _client, service, target = host
    frozen = preview(host)
    second = ResearchService(NativeFixture(), Store(tmp_path / "account-b"))
    install_catalog(second.asset_workspace)
    app = create_app(second)
    app.state.research = second
    try:
        with TestClient(app) as other:
            monkeypatch.setenv("RWB_TENANT_MODE", "1")
            monkeypatch.setattr(
                "app.research_web.tenant_policy._gateway_key", lambda: "b-gateway-fixture"
            )
            endpoint = (
                f"/api/research/watchlists/{target['id']}/imports/{frozen['import_id']}/confirm"
            )
            payload = {
                "schema_version": 1,
                "preview_digest": frozen["preview_digest"],
                "confirmed": True,
            }
            assert (
                other.post(
                    endpoint, json=payload, headers={"Idempotency-Key": "cross-account-key"}
                ).status_code
                == 403
            )
            assert (
                other.post(
                    endpoint,
                    json=payload,
                    headers={
                        "Idempotency-Key": "cross-account-key",
                        "X-RWB-Tenant-Gateway-Key": "b-gateway-fixture",
                    },
                ).status_code
                == 404
            )
            assert (
                other.post(
                    endpoint,
                    json={**payload, "owner": "a"},
                    headers={
                        "Idempotency-Key": "cross-account-key",
                        "X-RWB-Tenant-Gateway-Key": "b-gateway-fixture",
                    },
                ).status_code
                == 422
            )
            assert second.store.data["watchlists"] == {}
    finally:
        asyncio.run(second.close())
    assert service.store.data["watchlists"][target["id"]]["items"] == []


def test_offline_snapshot_detached_complete_and_candidate_budget(host):
    _, service, _ = host
    directory = service.asset_workspace.directory
    online_record = {"sentinel": ["unchanged"]}
    directory.record = online_record
    snapshot = directory.offline_snapshot()
    assert len(snapshot["items"]) == 4 and directory.record is online_record
    snapshot["items"][0]["name"] = "caller mutation"
    assert directory.offline_snapshot()["items"][0]["name"] != "caller mutation"
    rows = [
        {
            "asset": f"{n:06}.SZ",
            "code": f"{n:06}",
            "name": "同名",
            "exchange": "SZ",
            "asset_type": "stock",
        }
        for n in range(60)
    ]
    install_catalog(service.asset_workspace, rows=rows)
    frozen = preview(host, body(HEADER + "同名,stock,\n"))
    row = frozen["rows"][0]
    assert (
        len(row["candidates"]) == 50
        and row["candidate_count"] == 60
        and row["candidates_truncated"]
    )
    assert not frozen["can_confirm"]


def test_quote_comma_and_leading_zero_match_only_explicit_identity(host):
    _, service, _ = host
    rows = [
        {
            "asset": "000002.SZ",
            "code": "000002",
            "name": "中文,😀",
            "exchange": "SZ",
            "asset_type": "stock",
        }
    ]
    install_catalog(service.asset_workspace, rows=rows)
    frozen = preview(host, body(HEADER + '000002.SZ,stock,"中文,😀"\n'))
    assert frozen["rows"][0]["input"]["name"] == "中文,😀"
    assert confirm(host, frozen).json()["added_count"] == 1


def test_old_single_item_and_confirm_share_the_actual_host_lock(host):
    _, service, target = host
    workspace = service.asset_workspace
    frozen = preview(host)

    def original_writer():
        return workspace.add_watchlist_item(
            target["id"], {"asset": "888888.SH", "asset_type": "stock", "name": "旧入口"}
        )

    def import_writer():
        try:
            return workspace.confirm_watchlist_import(
                target["id"],
                frozen["import_id"],
                {"preview_digest": frozen["preview_digest"]},
                "original-writer-key",
            )["status"]
        except StoreError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        old_future = pool.submit(original_writer)
        new_future = pool.submit(import_writer)
        old_item, status = old_future.result(), new_future.result()
    items = service.store.data["watchlists"][target["id"]]["items"]
    assert old_item in items
    assert status in {"committed", "watchlist_import_target_changed"}
    assert len(items) == (4 if status == "committed" else 1)


def test_previews_and_old_item_faults_preserve_reference_and_saved_index(host, monkeypatch):
    _, service, target = host
    old = service.store.data["watchlists"][target["id"]]
    disk = service.store.index.read_bytes()

    def fail():
        raise TypeError("json serialization failure")

    with monkeypatch.context() as patch:
        patch.setattr(service.store, "save", fail)
        with pytest.raises(StoreError, match="persist_failed"):
            service.asset_workspace.preview_watchlist_import(target["id"], body())
        assert imports.NAMESPACE not in service.store.data
        with pytest.raises(TypeError):
            service.asset_workspace.add_watchlist_item(
                target["id"], {"asset": "600519.SH", "asset_type": "stock", "name": "旧入口"}
            )
    assert service.store.data["watchlists"][target["id"]] is old
    assert service.store.index.read_bytes() == disk


@pytest.mark.parametrize(
    "operation", ["confirm_fail", "preview_fail", "create_fail", "confirm_success"]
)
def test_threaded_files_cannot_publish_a_staged_import(host, monkeypatch, operation):
    """Real background files/save must serialize after the batch commits or rolls back."""
    import threading

    _, service, target = host
    store, workspace = service.store, service.asset_workspace
    session = store.create("claw", "线程登记夹具")
    folder = store.directory(session["id"]) / "inputs"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "new-upload.txt").write_text("synthetic upload", encoding="utf-8")
    frozen = preview(host) if operation.startswith("confirm") else None
    before = copy.deepcopy(store.data["watchlists"])
    namespace_before = copy.deepcopy(store.data.get(imports.NAMESPACE))
    staged, release, worker_attempt, worker_done = (threading.Event() for _ in range(4))
    real_replace, real_save = os.replace, store.save
    import_thread = [None]

    def observed_save():
        # Observation only: delegate the complete real Store.save, including its lock.
        if threading.get_ident() != import_thread[0]:
            worker_attempt.set()
        return real_save()

    def replacement(source, destination, *args, **kwargs):
        if threading.get_ident() == import_thread[0] and destination == store.index:
            staged.set()
            if not release.wait(3):
                raise RuntimeError("thread barrier release timeout")
            if operation.endswith("fail"):
                raise OSError("injected import replace failure")
        return real_replace(source, destination, *args, **kwargs)

    monkeypatch.setattr(store, "save", observed_save)
    monkeypatch.setattr(os, "replace", replacement)

    def importer():
        import_thread[0] = threading.get_ident()
        try:
            if operation == "create_fail":
                return workspace.create_watchlist("失败的新列表", None)
            if operation == "preview_fail":
                return workspace.preview_watchlist_import(target["id"], body())
            return workspace.confirm_watchlist_import(
                target["id"],
                frozen["import_id"],
                {"preview_digest": frozen["preview_digest"]},
                "thread-batch-key",
            )
        except StoreError as exc:
            return exc.code

    def files_worker():
        try:
            return store.files(session["id"])
        finally:
            worker_done.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        batch = pool.submit(importer)
        try:
            assert staged.wait(3), "import must reach the real replace boundary"
            worker = pool.submit(files_worker)
            assert worker_attempt.wait(3), "background files must attempt the real save"
            assert store.session(session["id"])["files"], "non-target memory mutation is real"
            stole_publish = worker_done.wait(0.05)
        finally:
            release.set()
        result = batch.result(timeout=3)
        registered = worker.result(timeout=3)
    disk = json.loads(store.index.read_text())
    print(
        "thread_batch_evidence",
        operation,
        "stolen",
        stole_publish,
        "disk_items",
        len(disk["watchlists"][target["id"]]["items"]),
        "memory_items",
        len(store.data["watchlists"][target["id"]]["items"]),
        "disk_keys",
        len(disk.get(imports.NAMESPACE, {}).get("keys", {})),
    )
    assert not stole_publish, "background Store.files stole publication of an uncommitted batch"
    assert disk["sessions"][session["id"]]["files"] == store.session(session["id"])["files"]
    assert registered[0]["name"] == "new-upload.txt"
    if operation.endswith("fail"):
        assert store.data["watchlists"] == before and disk["watchlists"] == before
        assert store.data.get(imports.NAMESPACE) == namespace_before
        assert disk.get(imports.NAMESPACE) == namespace_before
    else:
        assert result["added_count"] == 3
        assert disk["watchlists"] == store.data["watchlists"]
        assert disk[imports.NAMESPACE] == store.data[imports.NAMESPACE]


def test_two_workspaces_share_store_cas_and_idempotency(host):
    _, service, target = host
    second = AssetWorkspace(service)
    install_catalog(second)
    assert second.watchlist_lock is service.store.write_lock
    assert service.asset_workspace.watchlist_lock is second.watchlist_lock
    frozen = preview(host)
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(
            pool.map(
                lambda workspace: workspace.confirm_watchlist_import(
                    target["id"],
                    frozen["import_id"],
                    {"preview_digest": frozen["preview_digest"]},
                    "two-workspaces-key",
                ),
                [service.asset_workspace, second],
            )
        )
    assert receipts[0] == receipts[1]
    assert len(service.store.data["watchlists"][target["id"]]["items"]) == 3


def test_import_cannot_stage_while_files_save_is_serializing(host, monkeypatch):
    import threading

    _, service, target = host
    store = service.store
    session = store.create("claw", "后台保存夹具")
    (store.directory(session["id"]) / "inputs" / "late-upload.txt").write_text(
        "synthetic", encoding="utf-8"
    )
    frozen = preview(host)
    serializing, release, import_attempt, import_done = (threading.Event() for _ in range(4))
    worker_id = [None]
    real_dump = json.dump

    def blocked_dump(*args, **kwargs):
        if threading.get_ident() == worker_id[0]:
            serializing.set()
            if not release.wait(3):
                raise RuntimeError("files serialization barrier timeout")
        return real_dump(*args, **kwargs)

    monkeypatch.setattr(json, "dump", blocked_dump)

    def files_worker():
        worker_id[0] = threading.get_ident()
        return store.files(session["id"])

    def importer():
        import_attempt.set()
        try:
            return service.asset_workspace.confirm_watchlist_import(
                target["id"],
                frozen["import_id"],
                {"preview_digest": frozen["preview_digest"]},
                "files-first-key",
            )
        finally:
            import_done.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        worker = pool.submit(files_worker)
        try:
            assert serializing.wait(3)
            batch = pool.submit(importer)
            assert import_attempt.wait(3) and not import_done.wait(0.05)
            assert store.data["watchlists"][target["id"]]["items"] == []
            assert "receipt" not in store.data[imports.NAMESPACE]["previews"][frozen["import_id"]]
        finally:
            release.set()
        assert worker.result(timeout=3)[0]["name"] == "late-upload.txt"
        assert batch.result(timeout=3)["added_count"] == 3
    disk = json.loads(store.index.read_text())
    assert disk["watchlists"] == store.data["watchlists"]
    assert disk["sessions"][session["id"]]["files"] == store.session(session["id"])["files"]


@pytest.mark.parametrize("kind", ["etf", "fund", "index", "industry", "theme"])
def test_unsupported_identity_types_are_explicit_and_skippable(host, kind):
    frozen = preview(host, body(HEADER + f"600519.SH,{kind},贵州茅台\n"))
    assert frozen["rows"][0]["status"] == "unsupported_identity_catalog"
    assert frozen["rows"][0]["candidates"] == [] and not frozen["can_confirm"]
    skipped = preview(host, body(HEADER + f"600519.SH,{kind},贵州茅台\n", skipped_rows=[1]))
    assert confirm(host, skipped).json()["status"] == "no_changes"


def test_response_loss_and_same_root_backup_recover_in_fresh_process(host):
    import subprocess
    import sys

    _, service, target = host
    frozen = preview(host)
    expected = confirm(host, frozen, "real-restart-key").json()
    session = service.store.create("claw", "响应丢失后文件登记")
    (service.store.directory(session["id"]) / "inputs" / "after.txt").write_text(
        "synthetic", encoding="utf-8"
    )
    service.store.files(session["id"])
    backup = service.store.root.parent / "complete-index-backup.json"
    shutil.copy2(service.store.index, backup)
    original_mode = service.store.index.stat().st_mode & 0o777
    script = """
import json,sys
from pathlib import Path
from types import SimpleNamespace
from app.research_web.store import Store
from app.research_web.asset_workspace import AssetWorkspace
workspace=AssetWorkspace(SimpleNamespace(store=Store(Path(sys.argv[1]))))
workspace.directory.fingerprint=lambda:'authorized-fixture'
receipt=workspace.confirm_watchlist_import(sys.argv[2],sys.argv[3],{'preview_digest':sys.argv[4]},'real-restart-key')
print(json.dumps(receipt))
"""
    for restoring in [False, True]:
        if restoring:
            shutil.copy2(backup, service.store.index)
        run = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                script,
                str(service.store.root),
                target["id"],
                frozen["import_id"],
                frozen["preview_digest"],
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert run.returncode == 0, run.stderr
        assert json.loads(run.stdout.splitlines()[-1]) == expected
        assert service.store.index.read_bytes() == backup.read_bytes()
        assert service.store.index.stat().st_mode & 0o777 == original_mode
        disk = json.loads(service.store.index.read_text())
        assert (
            disk["sessions"][session["id"]]["files"]
            == service.store.session(session["id"])["files"]
        )
        assert len(disk["watchlists"][target["id"]]["items"]) == 3
