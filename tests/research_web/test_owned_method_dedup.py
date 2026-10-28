"""Owned C2 consumes actual public atom bytes, never fabricated pack identity."""

import copy
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import test_owned_method_execution as fixtures

from app.research_web.capabilities.pack_resources import canonical
from app.research_web.sandbox import SandboxConfig, run_script
from app.research_web.scenario_handoffs import resolve_reference
from app.research_web.scenario_method_dedup import build_artifact, cutoff_instant
from app.research_web.scenario_method_sources import quality_issues, source_context
from app.research_web.scenarios.packs import execute_atom_bundle
from app.research_web.skills._shared.source_actions import inspect_news_sources
from app.research_web.store import StoreError

api = fixtures.api


def test_cutoff_requires_explicit_timezone_and_matching_shanghai_day():
    assert cutoff_instant(None, "2026-10-28") is None
    assert cutoff_instant("2026-10-27T16:01:00Z", "2026-10-28").hour == 16
    for value in ("2026-10-28", "2026-10-28T12:00:00", "2026-10-28T22:00:00Z"):
        with pytest.raises(StoreError, match="截止"):
            cutoff_instant(value, "2026-10-28")


@pytest.mark.parametrize("cid", ["owned-news-evidence", "owned-research-prep"])
def test_real_source_c2_bundle_native_consumption_and_host_recompute(api, monkeypatch, cid):
    client, service, sid, context, descriptor, headers, _source = fixtures.prepared(
        api, monkeypatch, cid, cutoff=True
    )
    projected, bodies, _ = source_context(service, sid, cid, context)
    artifact = json.loads(bodies[projected["dedup_artifact"]["path"]])
    direct = execute_atom_bundle(
        "deduplicate_source_versions", artifact["records"], artifact["parameters"]
    )
    assert artifact["receipt"] == direct.receipt
    assert artifact["full_result"].encode() == direct.full_result.canonical_json
    assert artifact["method_version"] == "1.1.0"
    scope, _ = fixtures.start(client, sid, descriptor, headers)
    root = service.store.root
    result = run_script(
        SandboxConfig(root, Path(sys.executable)),
        root / "sessions" / sid,
        scope["code"],
        read_paths=scope["read_paths"],
        input_policy=scope["input_policy"],
        file_bindings=scope["file_bindings"],
        output_root=scope["output_root"],
    )
    assert result.status == "completed", (result.stderr, result.error)
    completion = {
        "kind": "owned-method",
        "session_id": sid,
        "execution_id": scope["binding"]["execution_id"],
        "call_id": "actual-owned-method",
        "result": asdict(result),
    }
    saved = client.post(
        "/api/research/internal/data/pack-completion", json=completion, headers=headers
    )
    assert saved.status_code == 200, saved.text
    ledger = json.loads(
        (root / "sessions" / sid / scope["output_root"] / "ledger.json").read_bytes()
    )
    assert ledger["deduplication"]["execution"] == "host-c2-preprocess-native-consumed"
    assert "source_version_dedup_not_run" not in {gap["code"] for gap in ledger["missing"]}
    assert "source_role_unknown" in {gap["code"] for gap in ledger["missing"]}
    receipt, _ = service._task_capabilities(sid)
    assert quality_issues(service, sid, receipt) == ["method_source_incomplete:" + cid]


def test_real_projection_keeps_future_unsupported_and_native_schema_gaps(api, monkeypatch):
    client, service, sid, context, descriptor, headers, source = fixtures.prepared(
        api, monkeypatch, cutoff=True
    )
    metadata, _, raw = resolve_reference(
        service, source[0], {"type": "source", "id": source[1]}, target_sid=sid
    )
    values = context["scenario"]["inputs"]
    unsupported = copy.deepcopy(metadata)
    unsupported["reference"] = {"type": "file", "id": "unmapped-note"}
    artifact = build_artifact(
        service,
        sid,
        "owned-news-evidence",
        values,
        [(metadata, raw), (metadata, raw), (unsupported, raw)],
    )
    assert len(artifact["source_set"]) == 2
    assert len(artifact["records"]["source-version"]) == 1
    assert "source_capture_mapping_unsupported" in {
        gap["code"] for gap in artifact["projection_gaps"]
    }
    earlier = (datetime.fromisoformat(metadata["acquired_at"]) - timedelta(seconds=1)).isoformat()
    future = build_artifact(
        service, sid, "owned-news-evidence", {**values, "cutoff_at": earlier}, [(metadata, raw)]
    )
    assert not future["records"]["source-version"]
    assert "source_observed_after_cutoff" in {gap["code"] for gap in future["projection_gaps"]}
    projected, _, _ = source_context(service, sid, "owned-news-evidence", context)
    fixtures.start(client, sid, descriptor, headers)
    root = service.store.directory(sid)
    original = (root / projected["dedup_artifact"]["path"]).read_bytes()
    for field, replacement in (
        ("method_version", "0.0.0"),
        ("source_set", []),
        ("input_sha256", "0" * 64),
    ):
        changed = json.loads(original)
        changed[field] = replacement
        changed_raw = canonical(changed)
        (root / projected["dedup_artifact"]["path"]).write_bytes(changed_raw)
        forged = {
            **projected,
            "dedup_artifact": {
                **projected["dedup_artifact"],
                "sha256": hashlib.sha256(changed_raw).hexdigest(),
            },
        }
        with pytest.raises(ValueError, match="method_dedup_artifact_invalid"):
            inspect_news_sources(root, forged)
    (root / projected["dedup_artifact"]["path"]).write_bytes(original)
