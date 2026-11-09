"""Re-open account DataHub facts and the canonical warehouse proof, never flags."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from core.observability import get_logger

from ..datahub.contracts import BusinessQuery
from ..datahub.security import directory, read_file
from ..datahub.snapshots import Snapshots
from ..market_store.models import FrozenSnapshot, parse_batch
from ..store import StoreError

log = get_logger(__name__)
SCHEMAS = {
    "calendar": "rwb-event-calendar-v1",
    "proxy": "rwb-event-proxy-v1",
    "factor_inputs": "rwb-event-factors-v1",
    "prices": "rwb-event-prices-v1",
}


def reject(code):
    log.warning("event_native_input_rejected", code=code)
    raise StoreError("原生输入缺少可核验的来源、时点、单位或权限", code, 409)


@dataclass(frozen=True)
class NativeInput:
    manifest: dict
    raw: bytes
    rows: list
    reference: dict
    configuration: str
    captured_at: datetime
    formal_digest: str | None = None
    availability: dict = field(default_factory=dict)
    proofs: tuple = ()
    canonical_dataset: dict = field(default_factory=dict)

    def floor(self, day=None, metric=None, version=None, fallback_metric=None):
        if not self.formal_digest:
            return self.captured_at
        if version is None and day is not None and (day, metric) in self.availability:
            return self.availability[day, metric]
        facts = [fact for fact in self.proofs if fact.metric == metric]
        if version is not None:
            facts = [fact for fact in facts if fact.source_version == version]
            exact = [fact for fact in facts if fact.business_date.isoformat() == day]
            facts = exact or facts
        elif day is not None:
            exact = [fact for fact in facts if fact.business_date.isoformat() == day]
            # One explicit whole-object publication may establish calendar or
            # proxy knowledge now, but never a batch-wide latest timestamp.
            facts = exact or (
                facts
                if len(facts) == 1 and metric in {"calendar", "proxy", "factor_inputs"}
                else []
            )
        elif len(facts) != 1:
            facts = []
        if not facts or any(fact.available_at is None for fact in facts):
            if fallback_metric is not None and fallback_metric != metric:
                return self.floor(day, fallback_metric, version)
            reject("event_native_canonical_availability_missing")
        return max(fact.available_at for fact in facts)


def _warehouse_proof(research, manifest, query, configuration, snapshots, source):
    """Provider-native snapshots cannot pass by declaring historical/PIT fields."""
    warehouse = getattr(research.datahub, "warehouse", None)
    if warehouse is None or query is None or query.purpose != "backtest" or query.as_of is None:
        return None, {}, (), {}
    files = manifest.get("raw_files", [])
    if len(files) != 1 or not re.fullmatch(r"raw-[0-9]{4}\.bin", str(files[0].get("name", ""))):
        return None, {}, (), {}
    try:
        with directory(
            research.store.root,
            (*snapshots._private(source["session_id"]), source["dataset_id"]),
            private=True,
        ) as folder:
            raw = read_file(folder, files[0]["name"], private=True, limit=16 * 1024 * 1024)
        if hashlib.sha256(raw).hexdigest() != files[0].get("sha256"):
            reject("event_native_warehouse_original_changed")
        frozen = FrozenSnapshot.load(raw)
        document = json.loads(frozen.payload)
        if (
            document.get("dataset", {}).get("factor_contract") in {"unverified", "unknown"}
            or document.get("dataset", {}).get("frequency") == "provider-native"
        ):
            return None, {}, (), {}
        if (
            document.get("pit_complete") is not True
            or document["scope"]["source"] != manifest["provider"]
            or document["scope"]["config_digest"] != configuration
        ):
            return None, {}, (), {}
        # This invokes the existing source-specific warehouse admission. In
        # particular SnapshotBinding still rejects purpose=backtest outright.
        current = warehouse.read(query, manifest["provider"], configuration)
        if (
            current is None
            or current.metadata.get("warehouse_snapshot_sha256") != frozen.digest
            or not current.raw
        ):
            return None, {}, (), {}
        if current.fields != manifest.get("fields") or current.metadata.get(
            "event_input_schema"
        ) != manifest.get("provider_metadata", {}).get("event_input_schema"):
            reject("event_native_warehouse_field_contract_changed")
        if json.dumps(current.rows, sort_keys=True, default=str) != json.dumps(
            json.loads(snapshots.read(source["session_id"], source["dataset_id"], "rows.json")),
            sort_keys=True,
            default=str,
        ):
            reject("event_native_warehouse_render_changed")
        if FrozenSnapshot.load(current.raw[0]).digest != frozen.digest:
            reject("event_native_warehouse_view_changed")
        facts = parse_batch(document["batch"]).facts
        availability = {}
        for fact in facts:
            if fact.available_at is None:
                return None, {}, (), {}
            key = (fact.business_date.isoformat(), fact.metric)
            availability[key] = max(availability.get(key, fact.available_at), fact.available_at)
        return frozen.digest, availability, tuple(facts), document["dataset"]
    except StoreError:
        raise
    except (ValueError, TypeError, KeyError, OSError) as exc:
        log.warning("event_native_warehouse_unqualified", error_type=type(exc).__name__)
        return None, {}, (), {}


def load_native(research, source, *, expected_manifest_sha256=None):
    """Read actual private/public twins and recheck current source admission."""
    if (
        not isinstance(source, dict)
        or set(source) - {"session_id", "dataset_id", "index_id"}
        or not all(isinstance(source.get(key), str) for key in ("session_id", "dataset_id"))
    ):
        reject("event_native_snapshot_reference_invalid")
    snapshots = Snapshots(research.store)
    manifest = snapshots.detail(source["session_id"], source["dataset_id"])
    if (
        expected_manifest_sha256 is not None
        and manifest.get("manifest_sha256") != expected_manifest_sha256
    ):
        reject("event_native_source_manifest_changed")
    provider = manifest.get("provider")
    if not isinstance(provider, str):
        reject("event_native_provider_missing")
    if not isinstance(manifest.get("fields", {}), dict) or not isinstance(
        manifest.get("provider_metadata", {}), dict
    ):
        reject("event_native_field_metadata_invalid")
    if (
        manifest.get("status") not in {"complete", "snapshot"}
        or manifest.get("pagination_complete") is not True
    ):
        reject("event_native_source_incomplete")
    configuration = research.datahub.source_configuration_digest(provider)
    saved = manifest.get("authorization_fingerprint")
    if saved is not None and saved != configuration:
        reject("event_native_source_authorization_changed")
    try:
        query = BusinessQuery.model_validate(manifest.get("query"))
    except ValueError:
        query = None
    if query is not None and saved is not None:
        research.datahub._authorize_query(
            source["session_id"],
            query,
            provider=provider,
            cached=True,
            authorization_fingerprint=saved,
        )
    else:
        readiness = research.datahub.catalog_source(provider).get("readiness", {})
        if readiness.get("allowed") is not True:
            reject("event_native_source_not_allowed")
    raw = snapshots.read(source["session_id"], source["dataset_id"], "rows.json")
    try:
        rows = json.loads(raw)
        captured = datetime.fromisoformat(manifest["retrieved_at"])
        if (
            captured.tzinfo is None
            or captured.utcoffset() is None
            or not isinstance(rows, list)
            or not 1 <= len(rows) <= 20000
            or len(raw) > 8 * 1024 * 1024
        ):
            raise ValueError
    except (ValueError, TypeError, KeyError) as exc:
        raise StoreError("原生快照不符合有界合同", "event_native_rows_invalid", 422) from exc
    reconciliation = research.event_timeline.records.qualification_status()["required"]
    formal, availability, proofs, dataset = (
        (None, {}, (), {})
        if reconciliation
        else _warehouse_proof(research, manifest, query, configuration, snapshots, source)
    )
    if research.datahub.source_configuration_digest(provider) != configuration:
        reject("event_native_source_authorization_changed")
    return NativeInput(
        manifest,
        raw,
        rows,
        dict(source),
        configuration,
        captured,
        formal,
        availability,
        proofs,
        dataset,
    )


def registered_event_projection(events, record, index_id):
    """One shared exact-revision clock for historical and current overlays."""
    from ..event_studies.events import availability_floor, project_event

    observed = []
    for reference in record["payload"].get("evidence_refs", []):
        observed.append(events.read_evidence(reference)["manifest"].get("first_observed"))
    floor = availability_floor(
        events.records.revision_recorded_at("event", record["id"], record["revision"]), observed
    )
    return project_event(
        record["payload"],
        index_id,
        identifier=record["id"],
        revision=record["revision"],
        known_floor=floor,
    )
