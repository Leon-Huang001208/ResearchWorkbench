"""Real Dossier reads across simulated historical managed-prefix relocation.

Only the historical interpreter location is simulated. Source ownership, private
snapshot/raw IO, Catalog publication and read authorization are the real Host.
"""

import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import isolated_keyring  # noqa: F401
from test_pack_execution_host import admitted
from test_workbench_operations import NativeFixture

from app.research_web.capabilities import pack_dependencies, pack_resources
from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store, StoreError


@pytest.fixture
def history(tmp_path, monkeypatch):
    actual = pack_dependencies.runtime_identity()
    old = copy.deepcopy(actual)
    prefix = Path(old["environment"])
    historical = tmp_path / "old-managed-prefix"
    old["environment"] = str(historical)
    for dependency in old["dependencies"]:
        dependency["origin"] = str(historical / Path(dependency["origin"]).relative_to(prefix))
    if Path(old["python"]).is_relative_to(prefix):
        old["python"] = str(historical / Path(old["python"]).relative_to(prefix))
    with monkeypatch.context() as startup:
        startup.setattr(pack_dependencies, "runtime_identity", lambda: copy.deepcopy(old))
        startup.setattr(pack_resources, "runtime_identity", lambda: copy.deepcopy(old))
        service = ResearchService(NativeFixture(), Store(tmp_path / "account"))
        client = TestClient(create_app(service))
        client.__enter__()
        service.connected = {"mux", "host"}
        values = admitted((client, service), monkeypatch)
    try:
        before = copy.deepcopy(service.store.data)
        service.capabilities = CapabilityCatalog(service.store.root)
        yield (*values, before)
    finally:
        client.__exit__(None, None, None)


def read_selected(service, sid):
    handoff = service.store.data["handoffs"][service.store.session(sid)["scenario_handoff_id"]]
    did = handoff["copied"][0]["dataset_id"]
    return service.dossiers._resolve(sid, {"type": "dataset", "id": did})


def test_certified_relocation_reads_original_and_copied_snapshot_without_state_writes(history):
    client, service, sid, context, _descriptor, _headers, before = history
    assert service.capabilities.row("research-pack-event-review")["version"] == 2
    metadata, raw = read_selected(service, sid)
    assert metadata["source_session_id"] == sid and b"68.2" in raw
    assert service.store.data == before
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "do not resend"},
        headers={"Idempotency-Key": "old-version-must-not-send"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "version_conflict"
    assert (
        service.store.data["handoffs"][service.store.session(sid)["scenario_handoff_id"]][
            "scenario_context"
        ]
        == context
    )


@pytest.mark.parametrize(
    "denial",
    [
        "disabled",
        "source_revoked",
        "forged_certificate",
        "conflicting_refs",
        "no_receipt_disabled",
        "extra_field_certificate",
        "mixed_refs",
        "dependency_changed",
        "raw_changed",
    ],
)
def test_current_denials_remain_denied_on_source_only_history_read(history, denial):
    _client, service, sid, context, _descriptor, _headers, _before = history
    if denial in {"disabled", "no_receipt_disabled"}:
        if denial == "no_receipt_disabled":
            service.store.session(sid).pop("delivery_key", None)
        service.capabilities.transition("research-pack-event-review", "disable")
    elif denial == "source_revoked":
        service.store.session(context["references"][0]["source_session_id"])["source_scope"] = [
            "web"
        ]
    elif denial in {"forged_certificate", "extra_field_certificate"}:
        certificates = service.capabilities.data["pack_read_equivalences"]
        key = next(
            key
            for key, value in certificates.items()
            if value["capability_id"] == "research-pack-event-review"
        )
        if denial == "forged_certificate":
            certificates[key]["owner_binding"] = "0" * 64
        else:
            certificates[key]["approved"] = True
    elif denial in {"conflicting_refs", "mixed_refs"}:
        receipt, _ = service._task_capabilities(sid)
        changed = copy.deepcopy(receipt["scenario_required_capabilities"][0])
        if denial == "conflicting_refs":
            changed["version"] = 2
        else:
            changed = service.capabilities.selection("company-research")
        receipt["native_capabilities"] = [changed]
    elif denial == "dependency_changed":
        active = service.capabilities.row("research-pack-event-review")["versions"]["2"]
        file = next(item for item in active["files"] if item["path"] == "references/runtime.json")
        file["sha256"] = "0" * 64
    else:
        source = context["references"][0]
        manifest = service.datahub.snapshots.detail(
            source["source_session_id"], source["reference"]["id"]
        )
        (service.store.root / manifest["raw_files"][0]["path"]).write_bytes(b"changed original")
    with pytest.raises(StoreError):
        read_selected(service, sid)


def test_frozen_context_without_receipt_is_authority_and_warehouse_cannot_borrow_read_mode(history):
    from app.research_web.capabilities.models import CapabilityError
    from app.research_web.datahub.contracts import BusinessQuery

    _client, service, sid, context, _descriptor, _headers, _before = history
    receipt, _ = service._task_capabilities(sid)
    reference = context["references"][0]
    manifest = service.datahub.snapshots.detail(
        reference["source_session_id"], reference["reference"]["id"]
    )
    query = BusinessQuery.model_validate(manifest["query"])
    # The original three-argument execution/query callback still rejects old refs.
    resolution = service.datahub._authorize_query(
        reference["source_session_id"],
        query,
        provider=manifest["provider"],
        cached=True,
        authorization_fingerprint=manifest["authorization_fingerprint"],
        storage_read=True,
    )
    with pytest.raises(CapabilityError) as strict:
        service._data_query_admission(sid, query, resolution)
    assert strict.value.code == "linked_version_conflict"
    service.store.session(sid).pop("delivery_key", None)
    assert b"68.2" in read_selected(service, sid)[1]
    assert receipt["research_contract"]["execution_context"]["scenario_id"] == "pack-event-review"


def test_legacy_three_argument_callback_and_adapter_exception_never_downgrade(history, monkeypatch):
    client, service, _sid, context, _descriptor, _headers, _before = history
    reference = context["references"][0]
    target = client.post("/api/research/sessions", json={}).json()["id"]
    calls = []
    with monkeypatch.context() as legacy:
        legacy.setattr(service, "_admit_dossier_snapshot_read", None)
        legacy.setattr(service, "_data_query_admission", lambda *args: calls.append(args))
        service.dossiers._resolve(
            reference["source_session_id"], reference["reference"], target_sid=target
        )
    assert len(calls) == 1 and len(calls[0]) == 3

    def fail(*_args, **_kwargs):
        raise TypeError("adapter failure must propagate")

    monkeypatch.setattr(service, "_admit_dossier_snapshot_read", fail)
    with pytest.raises(TypeError, match="must propagate"):
        service.dossiers._resolve(
            reference["source_session_id"], reference["reference"], target_sid=target
        )


def test_disabled_during_raw_read_cannot_use_preflight_equivalence(history, monkeypatch):
    _client, service, sid, _context, _descriptor, _headers, _before = history
    original = service.dossiers._verify_raw
    changed = []

    def revoke(*args, **kwargs):
        original(*args, **kwargs)
        if not changed:
            changed.append(True)
            service.capabilities.transition("research-pack-event-review", "disable")

    monkeypatch.setattr(service.dossiers, "_verify_raw", revoke)
    with pytest.raises(StoreError):
        read_selected(service, sid)
    assert changed


def test_forged_owner_with_correct_self_digest_is_not_a_server_certificate(history):
    from app.research_web.capabilities.pack_equivalence import digest

    _client, service, sid, _context, _descriptor, _headers, _before = history
    entries = service.capabilities.data["pack_read_equivalences"]
    key = next(
        key
        for key, value in entries.items()
        if value["capability_id"] == "research-pack-event-review"
    )
    value = entries.pop(key)
    value["owner_binding"] = "0" * 64
    value.pop("digest")
    value["digest"] = digest(value)
    entries[value["digest"]] = value
    with pytest.raises(StoreError):
        read_selected(service, sid)


@pytest.mark.parametrize("when", ["before", "during_raw"])
def test_runtime_freeze_blocks_internal_history_before_and_during_read(history, monkeypatch, when):
    _client, service, sid, _context, _descriptor, _headers, _before = history
    if when == "before":
        service.plugin_runtime_frozen = True
    else:
        original = service.dossiers._verify_raw

        def freeze(*args, **kwargs):
            original(*args, **kwargs)
            service.plugin_runtime_frozen = True

        monkeypatch.setattr(service.dossiers, "_verify_raw", freeze)
    with pytest.raises(StoreError) as error:
        read_selected(service, sid)
    assert error.value.code == "plugin_runtime_frozen"


def test_runtime_freeze_is_checked_by_read_adapter_and_legacy_callback(history):
    from app.research_web.datahub.contracts import BusinessQuery

    _client, service, sid, context, _descriptor, _headers, _before = history
    reference = context["references"][0]
    source_sid, did = reference["source_session_id"], reference["reference"]["id"]
    manifest = service.datahub.snapshots.detail(source_sid, did)
    query = BusinessQuery.model_validate(manifest["query"])
    resolution = service.datahub._authorize_query(
        source_sid,
        query,
        provider=manifest["provider"],
        cached=True,
        authorization_fingerprint=manifest["authorization_fingerprint"],
        storage_read=True,
    )
    service.plugin_runtime_frozen = True
    with pytest.raises(StoreError) as legacy:
        service._data_query_admission(sid, query, resolution)
    assert legacy.value.code == "plugin_runtime_frozen"
    with pytest.raises(StoreError) as adapter:
        service._admit_dossier_snapshot_read(
            sid,
            query,
            resolution,
            source_sid=source_sid,
            dataset_id=did,
            manifest_sha256=manifest["manifest_sha256"],
        )
    assert adapter.value.code == "plugin_runtime_frozen"
