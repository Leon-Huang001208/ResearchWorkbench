"""Real private snapshots, archives and warehouse proofs; no vendor acceptance."""

import json
from copy import deepcopy
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.datahub.snapshots import Snapshots
from app.research_web.datahub.warehouse import WarehouseBinding, WarehouseBridge
from app.research_web.event_host_inputs import EventInputHost
from app.research_web.event_timeline import TimelineService
from app.research_web.market_scoring import ScoreService
from app.research_web.market_scoring.native_inputs import SCHEMAS, load_native
from app.research_web.market_scoring.profiles import profile_for
from app.research_web.market_store import (
    Batch,
    DatasetIdentity,
    Fact,
    InMemoryMarketStore,
    MarketStoreService,
    RawOriginal,
    StoreScope,
)
from app.research_web.store import Store, StoreError
from tests.research_web.test_market_scoring import (
    CUTOFF,
    axes_for,
    proxy_for,
)


class PermissionHub:
    """Only source-permission state is isolated; data/proof parsing is real."""

    def __init__(self):
        self.allowed, self.configuration, self.warehouse = True, "a" * 64, None
        self.authorizations = 0

    def source_configuration_digest(self, source):
        return self.configuration

    def catalog_source(self, source):
        return {"readiness": {"allowed": self.allowed}}

    def _authorize_query(self, *args, **kwargs):
        self.authorizations += 1
        if not self.allowed or kwargs.get("authorization_fingerprint") != self.configuration:
            raise StoreError("source revoked", "data_cache_authorization_changed", 409)


def host(tmp_path):
    research = SimpleNamespace(store=Store(tmp_path / "owner"), datahub=PermissionHub())
    research.event_timeline = TimelineService(research)
    research.event_inputs = EventInputHost(research)
    research.market_scores = ScoreService(research)
    research._market_scoring_source_verifier = research.event_inputs.source_verifier
    research.resolve_market_scoring_context = research.event_inputs.resolve_market_scoring_context
    research.resolve_market_overlay_context = research.event_inputs.resolve_market_overlay_context
    return research


def publish(research, kind, rows, *, canonical=False, fields=None):
    query = BusinessQuery(
        capability="fund_data",
        source="wind",
        parameters={
            "dataset": kind,
            "code": "SSE",
            "start_date": "2026-10-01",
            "end_date": "2026-10-01",
        },
        **({"purpose": "backtest", "as_of": "2026-10-02T00:00:00+00:00"} if canonical else {}),
    )
    fields = fields or {}
    result = Result(
        rows=deepcopy(rows),
        raw=[json.dumps(rows).encode()],
        provider_id="wind",
        source_url="https://synthetic.test/native",
        status="complete",
        pagination_complete=True,
        fields=fields,
        metadata={
            "event_input_schema": SCHEMAS[kind],
            "historical_eligible": True,
            "pit_verified": True,
        },
    )
    if canonical:
        service = MarketStoreService(InMemoryMarketStore(), lambda *_: research.datahub.allowed)
        scope = StoreScope("native-unit-owner", "private", "wind", research.datahub.configuration)
        dataset = DatasetIdentity(
            "fund_data",
            "SSE-native",
            "CN",
            "daily",
            "native_contract",
            "none",
            "reviewed-native-v1",
            "b" * 64,
            (kind,),
        )
        original = RawOriginal(json.dumps(rows, sort_keys=True).encode())
        known = datetime(2026, 10, 1, 7, 2, tzinfo=UTC)
        facts = tuple(
            Fact(
                kind,
                date(2026, 10, 1),
                "daily",
                json.dumps(row),
                known,
                datetime.now(UTC),
                "native-unit-v1",
                original.sha256,
                (("row", str(i)),),
            )
            for i, row in enumerate(rows)
        )
        service.commit_batch("native-unit-owner", scope, dataset, Batch(facts, (original,)))
        binding = WarehouseBinding(
            "native-unit-owner",
            scope,
            dataset,
            (date(2026, 10, 1),),
            lambda *_: None,
            render=lambda batch: [fact.value for fact in batch.facts],
            field_metadata=fields,
            source_metadata=lambda _: {"event_input_schema": SCHEMAS[kind]},
        )
        research.datahub.warehouse = WarehouseBridge(service, lambda *_: binding)
        result = research.datahub.warehouse.read(query, "wind", research.datahub.configuration)
    sid = research.store.create("claw", "合成原生事实")["id"]
    manifest = Snapshots(research.store).publish(
        sid,
        query,
        result,
        request_query=query,
        authorization_fingerprint=research.datahub.configuration,
    )
    return {"session_id": sid, "dataset_id": manifest["dataset_id"]}


def factor_rows():
    axes = axes_for()
    fields = {
        definition["metric"]: {"unit": definition["unit"]}
        for definition in profile_for("SSE")["axes"].values()
    }
    return [
        {
            "factor_bundle": {
                "index_id": "SSE",
                "profile_version": "market-six-axis-v1",
                "as_of": CUTOFF,
                "axes": axes,
            }
        }
    ], fields


def test_actual_canonical_warehouse_proof_produces_rederived_factor_receipts(tmp_path):
    research = host(tmp_path)
    rows, fields = factor_rows()
    source = publish(research, "factor_inputs", rows, canonical=True, fields=fields)
    native = load_native(research, source)
    assert native.formal_digest is not None
    record = research.event_inputs.register_native(
        "factor_inputs", source, "SSE", "native-factors-01"
    )
    bundle = record["payload"]["bundle"]
    assert set(bundle["source_receipts"]) == set(profile_for("SSE")["axes"])
    assert all(
        receipt["pit_receipt"].startswith("canonical-warehouse:")
        for receipt in bundle["source_receipts"].values()
    )
    assert (
        research.event_inputs.register_native("factor_inputs", source, "SSE", "native-factors-01")
        == record
    )
    choice = research.event_inputs.choices()["inputs"][0]
    assert choice["id"] == record["id"] and "axes" not in choice and "history" not in choice


def test_provider_pit_flags_cannot_backdate_actual_first_observation(tmp_path):
    research = host(tmp_path)
    rows, fields = factor_rows()
    source = publish(research, "factor_inputs", rows, fields=fields)
    native = load_native(research, source)
    assert native.formal_digest is None
    record = research.event_inputs.register_native(
        "factor_inputs", source, "SSE", "native-late-factors"
    )
    assert record["payload"]["bundle"]["source_receipts"] == {}
    for observation in record["payload"]["bundle"]["axes"].values():
        assert datetime.fromisoformat(observation["known_at"]) >= native.captured_at


def test_current_authority_revocation_and_configuration_change_refuse_receipts(tmp_path):
    research = host(tmp_path)
    rows, fields = factor_rows()
    source = publish(research, "factor_inputs", rows, canonical=True, fields=fields)
    record = research.event_inputs.register_native(
        "factor_inputs", source, "SSE", "native-granted-factors"
    )
    observation = record["payload"]["bundle"]["axes"]["trend"]
    original = research.event_timeline.read_evidence(observation["source_ref"])
    research.datahub.allowed = False
    with pytest.raises(StoreError):
        research.event_inputs.source_verifier(
            index_id="SSE", axis="trend", observation=observation, as_of=CUTOFF, original=original
        )
    research.datahub.allowed, research.datahub.configuration = True, "c" * 64
    with pytest.raises(StoreError, match="权限"):
        load_native(research, source)


def test_metadata_units_cannot_be_overridden_by_native_row_units(tmp_path):
    research = host(tmp_path)
    rows, fields = factor_rows()
    fields["market_main_net"]["unit"] = "USD"
    source = publish(research, "factor_inputs", rows, fields=fields)
    with pytest.raises(StoreError) as error:
        research.event_inputs.register_native("factor_inputs", source, "SSE", "native-wrong-units")
    assert error.value.code == "event_native_factor_declared_unit_missing"


def test_actual_native_proxy_context_and_reference_only_linking(tmp_path):
    research = host(tmp_path)
    source = publish(
        research, "proxy", [{"proxy": proxy_for().model_dump(mode="json")}], canonical=True
    )
    proxy = research.event_inputs.register_native("proxy", source, "SSE", "native-proxy-one")
    context = research.event_inputs.resolve_market_scoring_context(
        index_id="SSE",
        as_of=CUTOFF,
        inputs={"proxy_ref": {"id": proxy["id"], "revision": proxy["revision"]}},
    )
    assert context.proxy.known_at == datetime(2026, 10, 1, 7, 2, tzinfo=UTC)
    prices_source = publish(
        research,
        "prices",
        [
            {
                "day": "2026-10-01",
                "index_id": "SSE",
                "role": "index",
                "asset": "000001.SH",
                "unit": "index_points",
                "open": "100",
                "close": "101",
            },
            {
                "day": "2026-10-02",
                "index_id": "SSE",
                "role": "index",
                "asset": "000001.SH",
                "unit": "index_points",
                "open": "101",
                "close": "102",
            },
        ],
        fields={"open": {"unit": "index_points"}, "close": {"unit": "index_points"}},
    )
    prices = research.event_inputs.register_native(
        "prices", prices_source, "SSE", "native-index-one"
    )
    linked = research.event_inputs.link_bundle(
        {"id": prices["id"], "revision": 1},
        {"proxy_ref": {"id": proxy["id"], "revision": 1}},
        "native-link-one",
    )
    assert linked["revision"] == 2
    assert (
        "proxy_ref"
        not in research.event_timeline.records.get("prices", prices["id"], revision=1)["payload"]
    )


def test_reconciliation_marker_blocks_all_qualification_without_public_override(tmp_path):
    research = host(tmp_path)
    rows, fields = factor_rows()
    source = publish(research, "factor_inputs", rows, canonical=True, fields=fields)
    record = research.event_inputs.register_native(
        "factor_inputs", source, "SSE", "native-before-restore"
    )
    observation = record["payload"]["bundle"]["axes"]["trend"]
    research.event_timeline.records.mark_reconciliation_required()
    with pytest.raises(StoreError) as error:
        research.event_inputs.source_verifier(
            index_id="SSE",
            axis="trend",
            observation=observation,
            as_of=CUTOFF,
            original=research.event_timeline.read_evidence(observation["source_ref"]),
        )
    assert error.value.code == "qualification_reconciliation_required"
    assert load_native(research, source).formal_digest is None


def test_tampered_registered_original_or_other_owner_cannot_resolve(tmp_path):
    research = host(tmp_path / "first")
    source = publish(
        research, "proxy", [{"proxy": proxy_for().model_dump(mode="json")}], canonical=True
    )
    record = research.event_inputs.register_native("proxy", source, "SSE", "native-proxy-tamper")
    other = host(tmp_path / "second")
    with pytest.raises(StoreError):
        other.event_inputs.resolve_market_scoring_context(
            index_id="SSE", as_of=CUTOFF, inputs={"proxy_ref": {"id": record["id"], "revision": 1}}
        )
    reference = record["payload"]["evidence_ref"]
    target = research.store.root / "event_timeline" / "evidence" / reference["id"] / "raw.bin"
    target.write_bytes(b"changed")
    with pytest.raises(StoreError):
        research.event_inputs.resolve_market_scoring_context(
            index_id="SSE", as_of=CUTOFF, inputs={"proxy_ref": {"id": record["id"], "revision": 1}}
        )


def test_malformed_native_fact_is_stable_error_and_original_is_retained(tmp_path):
    research = host(tmp_path)
    source = publish(research, "proxy", [{"proxy": {"known_at": "missing-timezone"}}])
    with pytest.raises(StoreError) as error:
        research.event_inputs.register_native("proxy", source, "SSE", "native-invalid-proxy")
    assert error.value.status in {409, 422}
    assert list((research.store.root / "event_timeline" / "evidence").glob("*/raw.bin"))
