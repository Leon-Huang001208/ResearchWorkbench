"""Lazy block admission, freshness and immutable history contracts."""

import asyncio
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest

from app.research_web.asset_routes import BlockLoadRequest, ObservationRequest
from app.research_web.asset_workspace import AssetWorkspace, AssetWorkspaceError
from app.research_web.store import Store, StoreError


@pytest.mark.asyncio
@pytest.mark.parametrize("end_date", [None, "2026-10-21"])
async def test_new_lazy_time_series_blocks_have_explicit_sixty_day_ranges(tmp_path, end_date):
    store = Store(tmp_path)
    sid = store.create("fingpt", "lazy range fixture")["id"]
    calls = []

    async def query(_sid, _call, request):
        calls.append(request)
        return {"status": "empty", "row_count": 0}

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid,
            asset="603986.SH",
            asset_type="stock",
            source="tinysoft",
            sections=["overview"],
            end_date=end_date,
        ),
        "create-range-fixture",
    )
    await asyncio.gather(*workspace.tasks.values())
    for block in ["activity", "margin", "events"]:
        await workspace.load_block(created["id"], block, BlockLoadRequest(), f"load-range-{block}")
        await asyncio.gather(*workspace.tasks.values())
        parameters = calls[-1].parameters
        assert (
            date.fromisoformat(parameters["end_date"])
            - date.fromisoformat(parameters["start_date"])
        ).days == 59
        if end_date:
            assert parameters["start_date"] == "2026-08-23" and parameters["end_date"] == end_date
        actual = workspace.observation(created["id"])["blocks"][block]["requested_range"]
        assert actual == {key: parameters[key] for key in ["start_date", "end_date"]}
    await workspace.close()


@pytest.mark.asyncio
async def test_recorded_event_request_range_does_not_change_when_the_clock_moves(
    tmp_path, monkeypatch
):
    import app.research_web.asset_workspace as module

    store = Store(tmp_path)
    sid = store.create("fingpt", "captured range fixture")["id"]

    async def query(*args):
        return {"status": "empty", "row_count": 0}

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid, asset="603986.SH", asset_type="stock", sections=["events"]
        ),
        "create-event-range",
    )
    await asyncio.gather(*workspace.tasks.values())
    before = workspace.observation(created["id"])["blocks"]["events"]["requested_range"]
    monkeypatch.setattr(
        module,
        "_recent_range",
        lambda *args: {"start_date": "2025-01-01", "end_date": "2025-03-01"},
    )
    assert workspace.observation(created["id"])["blocks"]["events"]["requested_range"] == before
    await workspace.close()


@pytest.mark.asyncio
async def test_vendor_failure_reason_is_not_hidden_behind_human_limitations(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "failure reason fixture")["id"]

    async def query(*args):
        return {
            "status": "failed",
            "row_count": 0,
            "limitations": ["公开聚合库，单位按来源。", "vendor_unreachable"],
        }

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid, asset="603986.SH", asset_type="stock", sections=["overview"]
        ),
        "create-failure-reason",
    )
    await asyncio.gather(*workspace.tasks.values())
    assert (
        workspace.observation(created["id"])["blocks"]["overview"]["failure_code"]
        == "vendor_unreachable"
    )
    await workspace.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("active_runner", ["initial", "legacy-refresh"])
async def test_failed_lazy_admission_does_not_detach_active_block(
    tmp_path, monkeypatch, active_runner
):
    store = Store(tmp_path)
    sid = store.create("fingpt", "concurrent rollback fixture")["id"]
    blocked = [active_runner == "initial"]
    entered = asyncio.Event()
    release = asyncio.Event()

    async def query(_sid, _call, request):
        if blocked[0] and request.capability == "market_snapshot":
            entered.set()
            await release.wait()
        return {"status": "complete", "dataset_id": "valid-overview", "row_count": 1}

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid, asset="603986.SH", asset_type="stock", sections=["overview"]
        ),
        "create-fixture",
    )
    if active_runner == "legacy-refresh":
        await asyncio.gather(*workspace.tasks.values())
        blocked[0] = True
        await workspace.refresh_block(created["id"], "overview", "legacy-refresh")
    await entered.wait()
    row = store.data["asset_observations"][created["id"]]
    blocks = row["blocks"]
    active = blocks["overview"]
    request = row["request"]
    sources = request["section_sources"]
    ranges = request["section_ranges"]
    keys = row.setdefault("refresh_keys", {})
    existing = {"status": "complete", "dataset": {"dataset_id": "prior-financials"}}
    blocks["financials"] = existing
    previous = deepcopy(row)
    original_save = store.save

    def failing_save():
        raise OSError("isolated admission failure")

    monkeypatch.setattr(store, "save", failing_save)
    try:
        for block, body in [
            ("financials", BlockLoadRequest(source="wind", refresh=True)),
            (
                "activity",
                BlockLoadRequest(source="wind", start_date="2026-10-01", end_date="2026-10-21"),
            ),
            ("overview", BlockLoadRequest()),
        ]:
            with pytest.raises(StoreError) as caught:
                await workspace.load_block(created["id"], block, body, f"failed-{block}")
            assert caught.value.status == 503
            assert row == previous
            assert row["blocks"] is blocks and blocks["overview"] is active
            assert blocks["financials"] is existing
            assert row["request"] is request
            assert request["section_sources"] is sources and request["section_ranges"] is ranges
            assert row["refresh_keys"] is keys
    finally:
        monkeypatch.setattr(store, "save", original_save)
        release.set()
        await asyncio.gather(*workspace.tasks.values())
        await workspace.close()
    assert row["status"] == "complete"
    assert row["blocks"]["overview"]["status"] == "complete"
    assert row["blocks"]["overview"]["dataset"]["dataset_id"] == "valid-overview"
    assert not workspace.tasks


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [BlockLoadRequest(), BlockLoadRequest(source="wind")])
async def test_cache_and_source_change_save_failure_preserves_prior_snapshot_and_request(
    tmp_path, monkeypatch, body
):
    store = Store(tmp_path)
    sid = store.create("fingpt", "save rollback fixture")["id"]
    calls = []

    async def query(_sid, _call, request):
        calls.append(request)
        return {"status": "complete", "row_count": 1, "dataset_id": "preserved"}

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid,
            asset="603986.SH",
            asset_type="stock",
            source="tinysoft",
            sections=["overview"],
        ),
        "create-fixture",
    )
    await asyncio.gather(*workspace.tasks.values())
    row = store.data["asset_observations"][created["id"]]
    previous = deepcopy(row)
    original_save = store.save

    def failing_save():
        raise OSError("isolated admission failure")

    monkeypatch.setattr(store, "save", failing_save)
    with pytest.raises(StoreError) as caught:
        await workspace.load_block(created["id"], "overview", body, "save-must-fail")
    monkeypatch.setattr(store, "save", original_save)
    assert caught.value.status == 503
    assert row == previous and len(calls) == 1
    assert not workspace.tasks
    await workspace.close()


@pytest.mark.asyncio
async def test_frozen_history_success_reserves_key_before_replaying_changed_conditions(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "frozen history receipt fixture")["id"]

    async def query(*args):
        return {"status": "empty", "row_count": 0}

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid, asset="603986.SH", asset_type="stock", sections=["overview"]
        ),
        "create-fixture",
    )
    await asyncio.gather(*workspace.tasks.values())
    row = store.data["asset_observations"][created["id"]]
    frozen = {
        "status": "complete",
        "dataset": {"dataset_id": "immutable", "asset_history": {"canonical_version": "v1"}},
    }
    row["blocks"]["history"] = deepcopy(frozen)
    await workspace.load_block(created["id"], "history", BlockLoadRequest(), "frozen-cache-key")
    assert next(iter(row["refresh_keys"].values()))["load_signature"]
    with pytest.raises(AssetWorkspaceError, match="同一加载标识") as caught:
        await workspace.load_block(
            created["id"], "history", BlockLoadRequest(refresh=True), "frozen-cache-key"
        )
    assert caught.value.status == 409 and row["blocks"]["history"] == frozen
    await workspace.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("expired", [False, True])
async def test_explicit_source_changes_existing_fresh_or_expired_block(tmp_path, expired):
    store = Store(tmp_path)
    sid = store.create("fingpt", "source identity fixture")["id"]
    calls = []

    async def query(_sid, _call, request):
        calls.append(request.source)
        return {
            "status": "complete",
            "row_count": 1,
            "dataset_id": f"dataset-{len(calls)}",
            "provider": request.source,
        }

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid,
            asset="603986.SH",
            asset_type="stock",
            source="tinysoft",
            sections=["overview"],
        ),
        "create-fixture",
    )
    await asyncio.gather(*workspace.tasks.values())
    if expired:
        store.data["asset_observations"][created["id"]]["blocks"]["overview"]["loaded_at"] = 0
    await workspace.load_block(
        created["id"], "overview", BlockLoadRequest(source="wind"), "change-source"
    )
    await asyncio.gather(*workspace.tasks.values())
    result = workspace.observation(created["id"])
    assert calls == ["tinysoft", "wind"]
    assert result["blocks"]["overview"]["requested_source"] == "wind"
    assert result["blocks"]["overview"]["dataset"]["provider"] == "wind"
    assert result["request_parameters"]["section_sources"]["overview"] == "wind"
    await workspace.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed",
    [{"source": "wind"}, {"start_date": "2026-09-01", "end_date": "2026-10-21"}, {"refresh": True}],
)
async def test_fresh_cache_key_cannot_be_reused_with_changed_conditions(tmp_path, changed):
    store = Store(tmp_path)
    sid = store.create("fingpt", "cache admission fixture")["id"]
    calls = []

    async def query(_sid, _call, request):
        calls.append(request)
        return {"status": "complete", "row_count": 1, "dataset_id": "cached"}

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid, asset="603986.SH", asset_type="stock", sections=["activity"]
        ),
        "create-fixture",
    )
    await asyncio.gather(*workspace.tasks.values())
    await workspace.load_block(created["id"], "activity", BlockLoadRequest(), "fresh-cache-key")
    assert len(calls) == 1
    try:
        with pytest.raises(AssetWorkspaceError) as caught:
            await workspace.load_block(
                created["id"], "activity", BlockLoadRequest(**changed), "fresh-cache-key"
            )
        assert caught.value.status == 409 and len(calls) == 1
    finally:
        await asyncio.gather(*workspace.tasks.values())
        await workspace.close()


@pytest.mark.asyncio
async def test_legacy_refresh_and_lazy_load_share_one_runner_lock(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "shared runner fixture")["id"]
    blocked = [False]
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def query(_sid, _call, request):
        calls.append(request.capability)
        if blocked[0] and request.capability == "market_snapshot":
            entered.set()
            await release.wait()
        return {"status": "empty", "row_count": 0}

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid, asset="603986.SH", asset_type="stock", sections=["overview"]
        ),
        "create-fixture",
    )
    await asyncio.gather(*workspace.tasks.values())
    calls.clear()
    blocked[0] = True
    await workspace.refresh_block(created["id"], "overview", "legacy-refresh")
    await entered.wait()
    await workspace.load_block(created["id"], "financials", BlockLoadRequest(), "lazy-financials")
    try:
        for _ in range(3):
            await asyncio.sleep(0)
        assert calls == ["market_snapshot"]
    finally:
        release.set()
        await asyncio.gather(*workspace.tasks.values())
        await workspace.close()
    assert calls == ["market_snapshot", "financials"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changed", "key"),
    [
        ({"source": "wind"}, "different-source"),
        ({"start_date": "2026-09-01"}, "different-range"),
        ({"source": "wind"}, "initial-activity"),
        ({"start_date": "2026-09-01"}, "initial-activity"),
    ],
)
async def test_loading_block_condition_conflicts_are_409_and_keep_valid_task(
    tmp_path, monkeypatch, changed, key
):
    store = Store(tmp_path)
    sid = store.create("fingpt", "loading isolation fixture")["id"]
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def query(_sid, _call, request):
        if request.capability == "market_activity":
            calls.append(request)
            entered.set()
            await release.wait()
        return {"status": "empty", "row_count": 0}

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid, asset="603986.SH", asset_type="stock", sections=["overview"]
        ),
        "create-fixture",
    )
    await asyncio.gather(*workspace.tasks.values())
    body = BlockLoadRequest(source="auto", start_date="2026-10-01", end_date="2026-10-21")
    await workspace.load_block(created["id"], "activity", body, "initial-activity")
    await entered.wait()
    try:
        if key == "different-source":
            original_save = store.save

            def failing_save():
                raise OSError("isolated persistence failure")

            monkeypatch.setattr(store, "save", failing_save)
            with pytest.raises(StoreError) as failed:
                await workspace.load_block(created["id"], "activity", body, "failed-coalesce")
            assert failed.value.status == 503
            monkeypatch.setattr(store, "save", original_save)
        same = await workspace.load_block(created["id"], "activity", body, "same-conditions")
        assert same["blocks"]["activity"]["status"] == "loading" and len(calls) == 1
        with pytest.raises(AssetWorkspaceError) as caught:
            await workspace.load_block(
                created["id"], "activity", BlockLoadRequest(**{**body.model_dump(), **changed}), key
            )
        assert caught.value.status == 409
        current = workspace.observation(created["id"])
        assert current["blocks"]["activity"]["status"] == "loading"
        assert current["blocks"]["activity"]["requested_source"] == "auto"
        assert current["blocks"]["activity"]["requested_range"] == {
            "start_date": "2026-10-01",
            "end_date": "2026-10-21",
        }
        assert len(calls) == 1
    finally:
        release.set()
        await asyncio.gather(*workspace.tasks.values())
        await workspace.close()


@pytest.mark.asyncio
async def test_coalesced_key_cannot_change_conditions_after_the_valid_task_completes(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "coalesced receipt fixture")["id"]
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def query(_sid, _call, request):
        if request.capability == "market_activity":
            calls.append(request)
            entered.set()
            await release.wait()
        return {"status": "empty", "row_count": 0}

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid, asset="603986.SH", asset_type="stock", sections=["overview"]
        ),
        "create-fixture",
    )
    await asyncio.gather(*workspace.tasks.values())
    body = BlockLoadRequest(source="auto", start_date="2026-10-01", end_date="2026-10-21")
    await workspace.load_block(created["id"], "activity", body, "initial-activity")
    await entered.wait()
    await workspace.load_block(created["id"], "activity", body, "coalesced-activity")
    release.set()
    await asyncio.gather(*workspace.tasks.values())
    try:
        with pytest.raises(AssetWorkspaceError) as caught:
            await workspace.load_block(
                created["id"],
                "activity",
                BlockLoadRequest(
                    source="wind", refresh=True, start_date="2026-09-01", end_date="2026-10-21"
                ),
                "coalesced-activity",
            )
        assert caught.value.status == 409
        assert len(calls) == 1
    finally:
        await asyncio.gather(*workspace.tasks.values())
        await workspace.close()


@pytest.mark.asyncio
async def test_legacy_missing_blocks_load_once_preserve_history_and_fresh_cache(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "asset fixture")["id"]
    calls = []

    async def query(_sid, _call, request):
        calls.append(request)
        await asyncio.sleep(0)
        return {
            "status": "complete",
            "dataset_id": f"dataset-{len(calls)}",
            "row_count": 1,
            "provider": request.source,
            "sample": [{"value": 1}],
        }

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid,
            asset="603986.SH",
            asset_type="stock",
            source="wind",
            sections=["overview", "history"],
        ),
        "create-fixture",
    )
    await asyncio.gather(*workspace.tasks.values())
    calls.clear()
    history = dict(store.data["asset_observations"][created["id"]]["blocks"]["history"])
    first = await workspace.load_block(
        created["id"], "financials", BlockLoadRequest(), "load-financials"
    )
    await workspace.load_block(created["id"], "financials", BlockLoadRequest(), "duplicate-load")
    assert first["blocks"]["financials"]["status"] == "loading"
    await asyncio.gather(*workspace.tasks.values())
    assert len(calls) == 1 and calls[0].source == "auto"
    await workspace.load_block(created["id"], "financials", BlockLoadRequest(), "fresh-cache-key")
    assert len(calls) == 1
    await workspace.load_block(
        created["id"], "financials", BlockLoadRequest(refresh=True), "explicit-refresh"
    )
    await asyncio.gather(*workspace.tasks.values())
    assert len(calls) == 2
    assert store.data["asset_observations"][created["id"]]["blocks"]["history"] == history
    await workspace.close()


@pytest.mark.asyncio
async def test_initial_and_lazy_blocks_are_serialized_and_restart_keeps_both_owners(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "asset fixture")["id"]
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def query(_sid, _call, request):
        calls.append(request.capability)
        if len(calls) == 1:
            entered.set()
            await release.wait()
        return {"status": "empty", "row_count": 0}

    service = SimpleNamespace(
        store=store, datahub=SimpleNamespace(query=query), notify=lambda: None
    )
    workspace = AssetWorkspace(service)
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid, asset="603986.SH", asset_type="stock", sections=["overview"]
        ),
        "create-fixture",
    )
    # Admit before the initial coroutine starts: it must not absorb/duplicate the new block.
    await workspace.load_block(created["id"], "financials", BlockLoadRequest(), "load-financials")
    await entered.wait()
    assert calls == ["market_snapshot"]
    reopened = AssetWorkspace(service)
    assert reopened.observation(created["id"])["blocks"]["financials"]["status"] == "loading"
    release.set()
    await asyncio.gather(*workspace.tasks.values())
    assert calls == ["market_snapshot", "financials"]
    await workspace.close()
    await reopened.close()


@pytest.mark.asyncio
async def test_load_failure_keeps_previous_dataset_and_new_key_retries(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "asset fixture")["id"]
    failed = [False]

    async def query(*args):
        return (
            {"status": "failed", "limitations": ["provider_unavailable"]}
            if failed[0]
            else {"status": "complete", "dataset_id": "old-dataset", "row_count": 1}
        )

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid, asset="603986.SH", asset_type="stock", sections=["overview"]
        ),
        "create-fixture",
    )
    await asyncio.gather(*workspace.tasks.values())
    failed[0] = True
    await workspace.load_block(
        created["id"], "overview", BlockLoadRequest(refresh=True), "refresh-overview"
    )
    await asyncio.gather(*workspace.tasks.values())
    block = workspace.observation(created["id"])["blocks"]["overview"]
    assert block["status"] == "unavailable" and block["dataset"]["dataset_id"] == "old-dataset"
    failed[0] = False
    await workspace.load_block(created["id"], "overview", BlockLoadRequest(), "retry-overview")
    await asyncio.gather(*workspace.tasks.values())
    assert workspace.observation(created["id"])["blocks"]["overview"]["status"] == "complete"
    await workspace.close()


def test_search_and_load_http_validate_limits_sections_intervals_and_idempotency():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.research_web.asset_routes import router

    class Workspace:
        directory = SimpleNamespace(
            search=lambda q, limit: {"items": [], "q": q, "limit": limit, "status": "loading"}
        )

        async def load_block(self, oid, block, body, key):
            return {
                "id": oid,
                "block": block,
                "refresh": body.refresh,
                "source": body.source,
                "key": key,
            }

    app = FastAPI()
    app.include_router(router)
    app.state.research = SimpleNamespace(asset_workspace=Workspace())
    with TestClient(app) as client:
        assert client.get("/api/research/assets/search?q=gzmt").json()["limit"] == 20
        assert client.get("/api/research/assets/search?limit=51").status_code == 422
        assert client.get("/api/research/assets/search", params={"q": "x" * 81}).status_code == 422
        path = "/api/research/assets/observations/observation/blocks/events/load"
        assert (
            client.post(
                path, json={"source": "auto"}, headers={"Idempotency-Key": "load-events"}
            ).json()["block"]
            == "events"
        )
        assert client.post(path, json={}).status_code == 422
        assert (
            client.post(
                path, json={"start_date": "2026-01-01"}, headers={"Idempotency-Key": "load-events"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                path.replace("events", "macro"), json={}, headers={"Idempotency-Key": "load-macro"}
            ).status_code
            == 422
        )


@pytest.mark.asyncio
async def test_explicit_source_and_range_preserved_and_canonical_history_cannot_overwrite(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "asset fixture")["id"]
    calls = []

    async def query(_sid, _call, request):
        calls.append(request)
        return {"status": "empty", "row_count": 0}

    workspace = AssetWorkspace(
        SimpleNamespace(store=store, datahub=SimpleNamespace(query=query), notify=lambda: None)
    )
    created = await workspace.create_observation(
        ObservationRequest(
            session_id=sid,
            asset="603986.SH",
            asset_type="stock",
            sections=["activity"],
            section_sources={"activity": "wind"},
            section_ranges={"activity": {"start_date": "2026-10-01", "end_date": "2026-10-21"}},
        ),
        "create-fixture",
    )
    await asyncio.gather(*workspace.tasks.values())
    calls.clear()
    await workspace.load_block(
        created["id"], "activity", BlockLoadRequest(refresh=True), "load-activity"
    )
    await asyncio.gather(*workspace.tasks.values())
    assert calls[0].source == "wind" and calls[0].parameters["start_date"] == "2026-10-01"
    row = store.data["asset_observations"][created["id"]]
    row["blocks"]["history"] = {
        "status": "complete",
        "dataset": {"dataset_id": "frozen", "asset_history": {"canonical_version": "v1"}},
    }
    with pytest.raises(AssetWorkspaceError, match="历史任务"):
        await workspace.load_block(
            created["id"], "history", BlockLoadRequest(refresh=True), "history-blocked"
        )
    await workspace.close()
