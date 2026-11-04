"""Actual frozen routes reject write-capable contexts before any reconciliation."""

import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
import test_workbench_operations as fixtures
from test_api import isolated_keyring  # noqa: F401

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result

api = fixtures.api
STRICT = {"X-RWB-Frozen-Read": "v1"}


def frozen(api):
    _client, service = api
    sid = service.store.create("fingpt", "synthetic readonly")["id"]
    path = service.store.directory(sid) / "inputs" / "source.txt"
    path.write_text("synthetic frozen source", encoding="utf-8")
    fid = "a" * 24
    service.store.session(sid)["files"][fid] = "inputs/source.txt"
    service.store.save()
    query = BusinessQuery(
        capability="financials", source="akshare", parameters={"asset": "600600.SH"}
    )
    data = service.datahub.snapshots.publish(
        sid,
        query,
        Result(rows=[{"value": 1}], raw=[b"synthetic"], status="snapshot"),
        request_query=query,
        authorization_fingerprint=service.datahub.source_configuration_digest("akshare"),
    )
    return sid, fid, data["dataset_id"], path


def forbid(monkeypatch, service):
    def failed(*args, **kwargs):
        raise AssertionError("business write or lineage resolution attempted")

    for obj, name in (
        (service.store, "save"),
        (service.store, "create"),
        (service.store, "files"),
        (service, "detail"),
        (service, "capability_readiness"),
        (service.client, "rpc"),
        (service.discovery, "trusted_context"),
        (service.datahub, "query"),
    ):
        monkeypatch.setattr(obj, name, failed)
    monkeypatch.setattr("app.research_web.scenario_handoffs.resolve_reference", failed)
    monkeypatch.setattr("app.research_web.scenario_handoffs.verify_material", failed)


def test_actual_backend_frozen_reads_preserve_index_and_sources(api, monkeypatch):
    client, service = api
    sid, fid, did, source = frozen(api)
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in service.store.root.rglob("*")
        if p.is_file()
    }
    forbid(monkeypatch, service)
    probe = client.get("/api/research/data/catalog", headers={"X-RWB-Frozen-Read": "probe-v1"})
    assert probe.json() == {"frozen_read_protocol": "v1"}
    paths = [
        f"/sessions/{sid}/files/{fid}/download",
        f"/sessions/{sid}/datasets/{did}",
        f"/sessions/{sid}/datasets/{did}/rows",
        f"/sessions/{sid}/datasets/{did}/files/manifest.json",
        f"/sessions/{sid}/datasets/{did}/files/rows.json",
    ]
    for path in paths:
        response = client.get("/api/research" + path, headers=STRICT)
        assert response.status_code == 200, response.text
        assert response.headers["x-rwb-frozen-read"] == "v1"
    after = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in service.store.root.rglob("*")
        if p.is_file()
    }
    assert before == after
    assert source.read_text() == "synthetic frozen source"


def test_actual_backend_rejects_all_handoffs_and_deleted_before_lineage(api, monkeypatch):
    client, service = api
    sid, fid, did, _ = frozen(api)
    row = service.store.session(sid)
    forbid(monkeypatch, service)
    for key, value in [
        ("purpose", "discovery_research"),
        ("scenario_handoff_id", "unknown"),
        ("evidence_handoff_id", "unknown"),
        ("discovery_handoff_id", "unknown"),
        ("deleted_at", 1),
    ]:
        row[key] = value
        for path in [
            f"/sessions/{sid}/files/{fid}/download",
            f"/sessions/{sid}/datasets/{did}/files/rows.json",
        ]:
            result = client.get("/api/research" + path, headers=STRICT)
            assert result.status_code == 409
        del row[key]
    service.store.data["handoffs"]["legacy"] = {"session_id": sid}
    assert (
        client.get(f"/api/research/sessions/{sid}/datasets/{did}", headers=STRICT).status_code
        == 409
    )


def test_actual_backend_rejects_output_binary_before_open_normal_compatible(api, monkeypatch):
    client, service = api
    sid, fid, _, _ = frozen(api)
    assert client.get(f"/api/research/sessions/{sid}/files/{fid}/download").status_code == 200
    forbid(monkeypatch, service)

    def failed(*args):
        raise AssertionError("must reject before file open")

    monkeypatch.setattr(service.store, "open_file", failed)
    for relative in [
        "outputs/report.md",
        "outputs/report-versions/old.md",
        "inputs/image.png",
        "inputs/doc.pdf",
        "unknown.txt",
    ]:
        service.store.session(sid)["files"][fid] = relative
        result = client.get(f"/api/research/sessions/{sid}/files/{fid}/download", headers=STRICT)
        assert result.status_code == 409


def test_probe_does_not_read_business_catalog(api, monkeypatch):
    client, service = api

    def failed():
        raise AssertionError("catalog business read")

    monkeypatch.setattr(service.datahub, "catalog", failed)
    response = client.get("/api/research/data/catalog", headers={"X-RWB-Frozen-Read": "probe-v1"})
    assert response.status_code == 200
    assert response.headers["X-RWB-Frozen-Read"] == "v1"


@pytest.mark.asyncio
async def test_actual_runtime_readonly_lookup_never_starts_or_mutates(tmp_path, monkeypatch):
    from app.research_web.multiuser.runtime import (
        Backend,
        RuntimeConfig,
        RuntimeErrorSafe,
        RuntimePool,
        _Instance,
    )

    pool = RuntimePool(
        RuntimeConfig(
            tmp_path / "server",
            tmp_path,
            tmp_path,
            "/synthetic/python",
            "/synthetic/node",
            max_instances=1,
        )
    )
    user = str(uuid4())
    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        raise AssertionError("readonly lookup must never start business lifecycle")

    for name in ("_start", "_spawn", "backend_for", "restore_discovery_tracks"):
        monkeypatch.setattr(pool, name, forbidden)

    def hashes():
        return {
            str(p.relative_to(pool.config.root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in pool.config.root.rglob("*")
            if p.is_file()
        }

    try:
        before = hashes()
        with pytest.raises(RuntimeErrorSafe, match="runtime_not_running"):
            await pool.backend_for_readonly(user)
        assert before == hashes() and not pool._instances
        state = pool.config.root / "users" / user / "state"
        state.mkdir(mode=0o700, parents=True)
        generation = "a" * 32
        child = SimpleNamespace(pid=101, poll=lambda: None)
        web = SimpleNamespace(pid=102, poll=lambda: None)
        backend = Backend("http://127.0.0.1:19999", "synthetic-key", generation, child.pid)
        entry = _Instance(user, state, backend, [child, web], generation)
        pool._instances[user] = entry
        pool._record(entry, create=True)
        before = hashes()
        assert await pool.backend_for_readonly(user) == backend
        assert before == hashes()
        with pytest.raises(RuntimeErrorSafe, match="runtime_capacity_exceeded"):
            await pool.backend_for_readonly(str(uuid4()))
        pool._plugin_frozen.add(user)
        with pytest.raises(RuntimeErrorSafe, match="runtime_restart_deferred"):
            await pool.backend_for_readonly(user)
        pool._plugin_frozen.clear()
        child.poll = lambda: 1
        with pytest.raises(RuntimeErrorSafe, match="runtime_process_exited"):
            await pool.backend_for_readonly(user)
        child.poll = lambda: None
        owner = json.loads((state / "owner.json").read_bytes())
        owner["user"] = str(uuid4())
        (state / "owner.json").write_text(json.dumps(owner))
        with pytest.raises(RuntimeErrorSafe, match="runtime_instance_unverified"):
            await pool.backend_for_readonly(user)
        pool._closing = True
        with pytest.raises(RuntimeErrorSafe, match="runtime_pool_closed"):
            await pool.backend_for_readonly(user)
        assert forbidden_calls == []
    finally:
        pool._plugin_frozen.clear()
        pool._instances.clear()
        await pool.close()


@pytest.mark.asyncio
async def test_attached_readonly_routes_primary_and_private_without_fallback(tmp_path):
    from app.research_web.multiuser.resident_binding import AttachedPool
    from app.research_web.multiuser.runtime import Backend, RuntimeErrorSafe

    primary, private_id = str(uuid4()), str(uuid4())
    calls = []

    def verify():
        calls.append("verify")
        return {"ready": True}

    def forbidden(*args):
        raise AssertionError("must not use starting lookup")

    async def private_lookup(user):
        calls.append(user)
        return Backend("http://127.0.0.1:19998", "synthetic-private")

    private = SimpleNamespace(backend_for=forbidden, backend_for_readonly=private_lookup)
    accounts = SimpleNamespace(
        get_user=lambda _: SimpleNamespace(id=primary, role="admin", enabled=True)
    )
    binding = SimpleNamespace(
        primary_user_id=primary, project=tmp_path, web_port=19999, verify=verify
    )
    pool = AttachedPool(accounts, private, binding, "synthetic")
    assert await pool.backend_for_readonly(primary) == Backend("http://127.0.0.1:19999", "")
    assert (await pool.backend_for_readonly(private_id)).key == "synthetic-private"
    assert calls == ["verify", private_id]
    del private.backend_for_readonly
    with pytest.raises(RuntimeErrorSafe, match="readonly_runtime_lookup_required"):
        await pool.backend_for_readonly(private_id)

    def unavailable():
        raise RuntimeErrorSafe("legacy_instance_unverified")

    binding.verify = unavailable
    with pytest.raises(RuntimeErrorSafe, match="legacy_instance_unverified"):
        await pool.backend_for_readonly(primary)
