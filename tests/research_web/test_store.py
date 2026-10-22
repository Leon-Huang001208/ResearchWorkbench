"""Ownership, idempotency and file path constraints."""

import json
from types import SimpleNamespace

import pytest

from app.research_web.asset_workspace import AssetWorkspace
from app.research_web.automation.service import AutomationService
from app.research_web.store import Store, StoreError


def _legacy_index(root):
    """The complete pre-history index, including an unrelated extension."""
    value = {
        "sessions": {},
        "receipts": {},
        "data_queries": {},
        "data_query_keys": {},
        "handoffs": {},
        "handoff_keys": {},
        "operation_audit": [],
        "asset_observations": {},
        "asset_observation_keys": {},
        "watchlists": {},
        "asset_notes": {},
        "asset_alerts": {},
        "asset_notifications": {},
        "report_projects": {},
        "report_runs": {},
        "report_schedules": {},
        "report_migrations": [],
        "automations": {},
        "automation_runs": {},
        "delivery_channels": {},
        "existing_extension": {"name": "既有业务", "zero": 0},
    }
    root.mkdir()
    path = root / "index.json"
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.asyncio
async def test_idle_startup_and_close_preserve_legacy_index_bytes(tmp_path):
    path = _legacy_index(tmp_path / "store")
    before = path.read_bytes()
    for _ in range(2):
        store = Store(path.parent)
        workspace = AssetWorkspace(SimpleNamespace(store=store))
        automation = AutomationService(store, scheduler=False)
        assert workspace.chart_preferences() == {"panels": ["volume", "macd"], "revision": 0}
        await automation.start()
        await automation.close()
        await workspace.close()
        assert path.read_bytes() == before
        assert store.data["asset_history_jobs"] == {}
        assert store.data["asset_history_keys"] == {}


@pytest.mark.parametrize("key", ["asset_history_jobs", "asset_history_keys", "chart_preferences"])
def test_existing_empty_asset_extensions_remain_present(tmp_path, key):
    path = _legacy_index(tmp_path / "store")
    before = json.loads(path.read_text())
    before[key] = (
        {"panels": ["volume", "macd"], "revision": 0} if key == "chart_preferences" else {}
    )
    path.write_text(json.dumps(before, ensure_ascii=False), encoding="utf-8")
    Store(path.parent).save()
    assert json.loads(path.read_text()) == before


def test_optional_defaults_are_independent_between_stores(tmp_path):
    one, two = Store(tmp_path / "one"), Store(tmp_path / "two")
    one.data["chart_preferences"]["panels"].clear()
    one.save()
    two.save()
    assert two.data["chart_preferences"] == {"panels": ["volume", "macd"], "revision": 0}
    assert "chart_preferences" not in json.loads(two.index.read_text())
    assert json.loads(one.index.read_text())["chart_preferences"]["panels"] == []


def test_failed_asset_extension_write_does_not_mark_defaults_persisted(tmp_path, monkeypatch):
    path = _legacy_index(tmp_path / "store")
    before = path.read_bytes()
    store = Store(path.parent)
    workspace = AssetWorkspace(SimpleNamespace(store=store))

    def reject_replace(*_args):
        raise OSError("replace rejected")

    with monkeypatch.context() as patch:
        patch.setattr("app.research_web.store.os.replace", reject_replace)
        with pytest.raises(StoreError, match="保存失败"):
            workspace.set_chart_preferences(["rsi"])
    assert workspace.chart_preferences() == {"panels": ["volume", "macd"], "revision": 0}
    assert path.read_bytes() == before
    store.save()
    assert path.read_bytes() == before
    assert not list(path.parent.glob("index-*"))


def test_asset_extensions_remain_after_successful_use_and_later_emptying(tmp_path):
    path = _legacy_index(tmp_path / "store")
    store = Store(path.parent)
    store.data["asset_history_jobs"]["history"] = {"state": "completed"}
    store.data["asset_history_keys"]["key"] = "history"
    store.save()
    store.data["asset_history_jobs"].clear()
    store.data["asset_history_keys"].clear()
    store.save()
    saved = json.loads(path.read_text())
    assert saved["asset_history_jobs"] == {}
    assert saved["asset_history_keys"] == {}
    assert "chart_preferences" not in saved


def test_malformed_zero_like_preference_is_not_discarded_as_default(tmp_path):
    path = _legacy_index(tmp_path / "store")
    store = Store(path.parent)
    store.data["chart_preferences"]["revision"] = False
    store.save()
    assert json.loads(path.read_text())["chart_preferences"]["revision"] is False


def test_index_persists_without_storing_transcripts(tmp_path):
    store = Store(tmp_path)
    session = store.create("fingpt", "新研究")
    assert Store(tmp_path).session(session["id"])["title"] == "新研究"
    assert "messages" not in store.session(session["id"])
    with pytest.raises(StoreError):
        store.session("../other")


def test_idempotency_survives_restart_and_rejects_changed_payload(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "研究")["id"]
    assert store.reserve(sid, "key", "hash")
    assert not Store(tmp_path).reserve(sid, "key", "hash")
    with pytest.raises(StoreError):
        store.reserve(sid, "key", "changed")


def test_files_never_follow_symlinks_or_cross_sessions(tmp_path):
    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "研究")["id"]
    outside = tmp_path / "secret.txt"
    outside.write_text("private")
    (store.directory(sid) / "outputs" / "leak.txt").symlink_to(outside)
    assert store.files(sid) == []
    with pytest.raises(StoreError):
        store.file_path(sid, "../../secret.txt")


def test_generated_files_have_opaque_ids_and_are_discovered(tmp_path):
    store = Store(tmp_path)
    sid = store.create("claw", "行业")["id"]
    (store.directory(sid) / "outputs" / "report.md").write_text("# Report")
    files = store.files(sid)
    assert len(files) == 1 and files[0]["name"] == "report.md"
    assert store.file_path(sid, files[0]["id"]).read_text() == "# Report"


def test_download_opens_without_following_replaced_output_symlink(tmp_path):
    store = Store(tmp_path / "store")
    sid = store.create("fingpt", "研究")["id"]
    output = store.directory(sid) / "outputs" / "report.md"
    output.write_text("report")
    fid = store.files(sid)[0]["id"]
    output.unlink()
    secret = tmp_path / "canary.md"
    secret.write_text("canary")
    output.symlink_to(secret)
    with pytest.raises(StoreError):
        store.open_file(sid, fid)
