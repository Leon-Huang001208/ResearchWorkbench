"""Fifteen-year real archive/warehouse path without duplicated per-day histories."""

import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.snapshots import Snapshots
from app.research_web.datahub.warehouse import WarehouseBinding, WarehouseBridge
from app.research_web.event_studies.contracts import rule_contract
from app.research_web.event_studies.service import StudyService
from app.research_web.market_scoring.applicability import applicability_for
from app.research_web.market_scoring.engine import compute_score, digest
from app.research_web.market_scoring.matrix import FORMAT
from app.research_web.market_scoring.native_inputs import SCHEMAS
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
from app.research_web.store import StoreError
from tests.research_web.test_market_scoring import proxy_for
from tests.research_web.test_market_scoring_native_inputs import host
from tests.research_web.test_market_scoring_native_temporal import canonical_source


def matrix_source(
    research, years=15, *, late_last=False, delayed_publication_index=None, delayed_value=None
):
    profile = profile_for("SSE")
    columns = {
        axis: {
            "metric": definition["metric"],
            "unit": definition["unit"],
            "scope": definition["scope"],
            "scope_id": "SSE" if definition["scope"] == "index" else "CN",
        }
        for axis, definition in profile["axes"].items()
    }
    start, stop = date(2010, 1, 1), date(2010 + years, 1, 1)
    days = [
        start + timedelta(days=i)
        for i in range((stop - start).days)
        if (start + timedelta(days=i)).weekday() < 5
    ]
    values = []
    for i, day in enumerate(days):
        values.append(
            {
                "as_of": f"{day}T16:00:00+08:00",
                "observed_at": f"{day}T15:00:00+08:00",
                "values": {
                    "trend": i % 80 / 10,
                    "breadth": 0.6,
                    "sentiment": 0.1,
                    "funds": i % 100 - 50,
                    "valuation": 10 + i % 50 / 10,
                    "risk": 2 + i % 10 / 10,
                },
            }
        )
    if delayed_publication_index is not None:
        delayed = values[delayed_publication_index]
        delayed["known_at"] = delayed["as_of"]
        delayed["published_at"] = (
            datetime.fromisoformat(delayed["as_of"]) + timedelta(days=10)
        ).isoformat()
        if delayed_value is not None:
            delayed["values"]["trend"] = delayed_value
    raw = RawOriginal(
        json.dumps(
            {
                "factor_bundle": {
                    "format": FORMAT,
                    "index_id": "SSE",
                    "profile_version": profile["version"],
                    "columns": columns,
                    "rows": values,
                }
            },
            separators=(",", ":"),
        ).encode()
    )
    backend = InMemoryMarketStore()
    service = MarketStoreService(backend, lambda *_: research.datahub.allowed)
    scope = StoreScope("matrix-owner", "private", "wind", research.datahub.configuration)
    metric_axis = {definition["metric"]: axis for axis, definition in profile["axes"].items()}
    dataset = DatasetIdentity(
        "fund_data",
        "SSE-native-matrix",
        "CN",
        "daily",
        "per-metric-native-v1",
        "none",
        "reviewed-native-matrix-v1",
        "b" * 64,
        tuple(metric_axis),
    )
    facts = []
    for row, day in zip(values, days):
        for metric, axis in metric_axis.items():
            known = datetime.combine(day, datetime.min.time(), UTC) + timedelta(hours=7, minutes=2)
            if late_last and day == days[-1] and axis == "funds":
                known += timedelta(days=1)
            facts.append(
                Fact(
                    metric,
                    day,
                    "daily",
                    json.dumps(row["values"][axis]),
                    known,
                    datetime.now(UTC),
                    "matrix-" + day.isoformat(),
                    raw.sha256,
                    tuple(
                        sorted(
                            (
                                field,
                                datetime.fromisoformat(row[field])
                                .astimezone(UTC)
                                .isoformat()
                                .replace("+00:00", "Z"),
                            )
                            for field in ("known_at", "published_at")
                            if field in row
                        )
                    ),
                )
            )
    service.commit_batch("matrix-owner", scope, dataset, Batch(tuple(facts), (raw,)))

    def render(batch):
        grouped = {}
        for fact in batch.facts:
            day = fact.business_date.isoformat()
            row = grouped.setdefault(
                day,
                {
                    "as_of": f"{day}T16:00:00+08:00",
                    "observed_at": f"{day}T15:00:00+08:00",
                    "values": {},
                },
            )
            row["values"][metric_axis[fact.metric]] = fact.value
            for field, moment in fact.dimensions:
                row[field] = moment
        return [
            {
                "factor_bundle": {
                    "format": FORMAT,
                    "index_id": "SSE",
                    "profile_version": profile["version"],
                    "columns": columns,
                    "rows": [grouped[day] for day in sorted(grouped)],
                }
            }
        ]

    fields = {
        definition["metric"]: {"unit": definition["unit"]}
        for definition in profile["axes"].values()
    }
    binding = WarehouseBinding(
        "matrix-owner",
        scope,
        dataset,
        tuple(days),
        lambda *_: None,
        render=render,
        field_metadata=fields,
        source_metadata=lambda _: {"event_input_schema": SCHEMAS["factor_inputs"]},
    )
    research.datahub.warehouse = WarehouseBridge(service, lambda *_: binding)
    query = BusinessQuery(
        capability="fund_data",
        source="wind",
        purpose="backtest",
        as_of=f"{stop}T00:00:00+00:00",
        parameters={
            "dataset": "factor_inputs",
            "code": "SSE",
            "start_date": str(days[0]),
            "end_date": str(days[-1]),
        },
    )
    result = research.datahub.warehouse.read(query, "wind", research.datahub.configuration)
    sid = research.store.create("claw", "十五年合成矩阵")["id"]
    manifest = Snapshots(research.store).publish(
        sid,
        query,
        result,
        request_query=query,
        authorization_fingerprint=research.datahub.configuration,
    )
    return {"session_id": sid, "dataset_id": manifest["dataset_id"]}, values


def native_formal_study(tmp_path, *, holidays=None, create_study=True, holiday_canonical=True):
    """Real independent snapshots and canonical proofs feed the default Host.

    The synthetic source router delegates to actual WarehouseBridge instances;
    it neither supplies a StudyBundle nor overrides any qualification gate.
    """
    research = host(tmp_path)
    routes = {}

    def query_key(query):
        return json.dumps(query.model_dump(mode="json"), sort_keys=True)

    def remember(source):
        manifest = Snapshots(research.store).detail(source["session_id"], source["dataset_id"])
        key = query_key(BusinessQuery.model_validate(manifest["query"]))
        assert key not in routes
        routes[key] = research.datahub.warehouse
        return source

    factors, matrix = matrix_source(research, years=2)
    remember(factors)
    days = [row["as_of"][:10] for row in matrix]
    sessions = [
        {
            "day": day,
            "opens": f"{day}T09:30:00+08:00",
            "closes": f"{day}T15:00:00+08:00",
            "half_day": False,
            "known_at": "2009-01-01T00:00:00+00:00",
            "announcement_version_ref": "native-calendar-v1",
        }
        for day in days
    ]
    calendar = remember(
        canonical_source(
            research,
            "calendar",
            [
                {
                    "metric": "calendar",
                    "day": "2009-01-01",
                    "known": "2009-01-01T00:00:00+00:00",
                    "version": "native-calendar-v1",
                    "value": {
                        "sessions": sessions,
                        "holidays": (holidays or []) if holiday_canonical else [],
                    },
                }
            ],
            lambda batch: [
                {
                    "calendar": {
                        "exchange": "XSHG",
                        "timezone": "Asia/Shanghai",
                        "version": "native-v1",
                        "source_ref": "native-calendar-v1",
                        "known_at": "2009-01-01T00:00:00+00:00",
                        "sessions": batch.facts[0].value["sessions"],
                    },
                    "holidays": (
                        batch.facts[0].value["holidays"] if holiday_canonical else (holidays or [])
                    ),
                }
            ],
        )
    )
    proxy = proxy_for().model_dump(mode="json")
    proxy_source = remember(
        canonical_source(
            research,
            "proxy",
            [
                {
                    "metric": "proxy",
                    "day": proxy["listed_on"],
                    "known": proxy["known_at"],
                    "version": "native-proxy-v1",
                    "value": proxy,
                },
                {
                    "metric": "proxy",
                    "day": proxy["rules"][0]["from_date"],
                    "known": proxy["rules"][0]["known_at"],
                    "version": "native-rule-v1",
                    "value": proxy["rules"][0],
                },
            ],
            lambda batch: [
                {
                    "proxy": next(
                        f.value for f in batch.facts if f.source_version == "native-proxy-v1"
                    ),
                    "identity_announcement_version_ref": "native-proxy-v1",
                    "rule_announcement_version_refs": {
                        proxy["rules"][0]["from_date"]: "native-rule-v1"
                    },
                }
            ],
        )
    )

    def prices(role):
        # The index has its own longer coverage, so its canonical request and
        # original cannot be confused with the tradable proxy's request.
        selected = ["2009-12-31", *days] if role == "index" else days
        metrics = (
            ("open", "close")
            if role == "index"
            else ("open", "close", "split", "dividend", "suspended")
        )
        entries = []
        for i, day in enumerate(selected):
            values = {
                "open": 100 + i / 100,
                "close": 100 + (i + 1) / 100,
                "split": 1,
                "dividend": 0,
                "suspended": False,
            }
            for metric in metrics:
                entries.append(
                    {
                        "metric": metric,
                        "day": day,
                        "known": f"{day}T{'15:00' if metric == 'close' else '09:00'}:00+08:00",
                        "version": f"native-{role}-{day}",
                        "value": values[metric],
                    }
                )
        unit = "index_points" if role == "index" else "CNY/share"

        def render(batch):
            rows = {}
            for fact in batch.facts:
                day = fact.business_date.isoformat()
                row = rows.setdefault(
                    day,
                    {
                        "day": day,
                        "index_id": "SSE",
                        "role": role,
                        "asset": "000001.SH" if role == "index" else proxy["symbol"],
                        "unit": unit,
                    },
                )
                row[fact.metric] = fact.value
            return [rows[day] for day in sorted(rows)]

        return remember(
            canonical_source(
                research,
                "prices",
                entries,
                render,
                fields={metric: {"unit": unit} for metric in ("open", "close")},
            )
        )

    index_prices, proxy_prices = prices("index"), prices("proxy")
    research.datahub.warehouse = SimpleNamespace(
        read=lambda query, provider, configuration: routes[query_key(query)].read(
            query, provider, configuration
        )
    )

    def register(kind, source, **kwargs):
        record = research.event_inputs.register_native(
            kind, source, "SSE", "formal-native-" + kind + "-" + source["dataset_id"], **kwargs
        )
        return {"id": record["id"], "revision": record["revision"]}

    calendar_ref = register("calendar", calendar)
    proxy_ref = register("proxy", proxy_source)
    factor_ref = register("factor_inputs", factors, links={"proxy_ref": proxy_ref})
    proxy_prices_ref = register("prices", proxy_prices)
    index_ref = register("prices", index_prices)
    linked = research.event_inputs.link_bundle(
        index_ref,
        {
            "index_calendar_ref": calendar_ref,
            "proxy_calendar_ref": calendar_ref,
            "proxy_ref": proxy_ref,
            "factor_inputs_ref": factor_ref,
            "proxy_prices_ref": proxy_prices_ref,
        },
        "formal-native-links",
    )
    bundle_ref = {"id": linked["id"], "revision": linked["revision"]}
    research.resolve_event_study_bundle = research.event_inputs.resolve_event_study_bundle
    studies = StudyService(research)
    study = (
        studies.create(
            {
                "title": "Actual native resolver",
                "index_id": "SSE",
                "profile_version": profile_for("SSE")["version"],
                "bundle_ref": bundle_ref,
                "role": "base_score",
                "hypothesis": "native-six-axis-signal",
            },
            "formal-native-study",
        )
        if create_study
        else None
    )
    return research, studies, study, bundle_ref, factor_ref


def test_default_native_resolver_binds_signal_original_and_reaches_formal_evaluate(tmp_path):
    research, studies, study, bundle_ref, factor_ref = native_formal_study(tmp_path)
    bundle = research.event_inputs.resolve_event_study_bundle(bundle_ref)
    assert bundle.data_gaps == ()
    batch = studies.seal([study["id"]], "native-formal-seal")
    report = studies.evaluate(batch["id"], "native-formal-evaluate")["items"][0]["payload"][
        "validation"
    ]
    assert "signal_not_known_before_execution" not in report["reasons"]
    assert report["metrics"]["normal"] is not None
    assert report["metrics"]["stress"] is not None
    factor = research.event_timeline.records.get(
        "factor_inputs", factor_ref["id"], revision=factor_ref["revision"]
    )["payload"]
    for receipt in bundle.signal_receipts.values():
        assert receipt["source_ref"] == {
            "kind": "factor_inputs",
            **factor_ref,
            "sha256": factor["bundle_sha256"],
            "archive_ref": factor.get("evidence_ref") or factor["bundle"]["matrix_evidence_ref"],
        }


def test_formal_evaluate_still_rejects_native_signal_without_source_reference(tmp_path):
    research, studies, study, _, _ = native_formal_study(tmp_path)
    actual_resolve = research.event_inputs.resolve_event_study_bundle

    def stripped(ref, **kwargs):
        bundle = actual_resolve(ref, **kwargs)
        for receipt in bundle.signal_receipts.values():
            receipt.pop("source_ref", None)
        return bundle

    research.resolve_event_study_bundle = stripped
    batch = studies.seal([study["id"]], "native-missing-reference-seal")
    report = studies.evaluate(batch["id"], "native-missing-reference-evaluate")["items"][0][
        "payload"
    ]["validation"]
    assert report["status"] == "DATA_INELIGIBLE"
    assert "signal_not_known_before_execution" in report["reasons"]
    assert report["metrics"]["normal"] is None


def native_holiday_spec():
    spec = {
        "role": "calendar_overlay",
        "family": "holiday",
        "direction": 1,
        "rule": "holiday_pre_1",
        "index_id": "SSE",
        "horizon": 20,
        "profile_version": profile_for("SSE")["version"],
    }
    rules = digest(
        rule_contract(
            spec["role"], spec["profile_version"], spec["family"], spec["direction"], spec["rule"]
        )
    )
    return spec, {**spec, "rules_digest": rules, "signal_rule_sha256": rules}


def native_holiday(known="2009-01-01T00:00:00+00:00"):
    value = {
        "id": "native-weekend-holiday",
        "start": "2010-01-09",
        "end": "2010-01-10",
        "announcement_version_ref": "native-calendar-v1",
    }
    if known is not None:
        value["known_at"] = known
    return value


def test_actual_native_holiday_projects_identically_into_history_and_current_window(tmp_path):
    research, _, _, ref, _ = native_formal_study(tmp_path, holidays=[native_holiday()])
    bundle = research.event_inputs.resolve_event_study_bundle(ref)
    spec, report = native_holiday_spec()
    as_of = "2010-01-07T16:00:00+08:00"
    context = research.event_inputs.resolve_market_overlay_context(
        study_id="synthetic", spec=spec, report=report, index_id="SSE", as_of=as_of
    )
    assert list(context.holidays) == bundle.holidays
    assert len(context.holidays) == 1
    proof = applicability_for(context, report, spec, "SSE", as_of)
    assert proof.window_start == "2010-01-07T15:00:00+08:00"
    assert proof.window_end == "2010-01-08T15:00:00+08:00"


@pytest.mark.parametrize("known", [None, "2010-01-08T16:00:00+08:00"])
def test_native_holiday_unknown_or_late_knowledge_is_explicit_gap(tmp_path, known):
    research, _, _, _, _ = native_formal_study(
        tmp_path, holidays=[native_holiday(known)], create_study=False
    )
    spec, report = native_holiday_spec()
    with pytest.raises(StoreError, match="原生输入") as caught:
        research.event_inputs.resolve_market_overlay_context(
            study_id="synthetic",
            spec=spec,
            report=report,
            index_id="SSE",
            as_of="2010-01-07T16:00:00+08:00",
        )
    assert caught.value.code in {
        "event_native_holiday_knowledge_missing",
        "event_native_holiday_not_known_by_cutoff",
    }


def test_native_holiday_must_exist_in_dated_canonical_fact_not_only_rendered_calendar(tmp_path):
    research, _, _, _, _ = native_formal_study(
        tmp_path, holidays=[native_holiday()], create_study=False, holiday_canonical=False
    )
    spec, report = native_holiday_spec()
    with pytest.raises(StoreError) as caught:
        research.event_inputs.resolve_market_overlay_context(
            study_id="synthetic",
            spec=spec,
            report=report,
            index_id="SSE",
            as_of="2010-01-07T16:00:00+08:00",
        )
    assert caught.value.code == "event_native_holiday_canonical_evidence_missing"


def test_fifteen_year_archive_fits_real_budgets_and_streams_causal_base_weights(tmp_path):
    research = host(tmp_path)
    source, rows = matrix_source(research)
    registered = research.event_inputs.register_native(
        "factor_inputs", source, "SSE", "fifteen-year-matrix"
    )
    ref = {"id": registered["id"], "revision": registered["revision"]}
    assert len(json.dumps(registered).encode()) < 4096
    compiled = research.event_inputs.factor_signals(ref)
    assert compiled["input_bytes"] < 8 * 1024 * 1024
    assert compiled["formal_qualification"]
    assert len(compiled["items"]) == len(rows)
    assert all(item["score"] is None for item in compiled["items"][:252])
    assert all(item["score"] is not None for item in compiled["items"][252:])
    point = research.event_inputs.resolve_market_factor_point(
        index_id="SSE", as_of=rows[-1]["as_of"], inputs=registered["payload"]["bundle"]
    )
    expanded = compute_score("SSE", point.as_of, point.axes, source_receipts=point.source_receipts)
    assert abs(expanded["candidate_score"] - compiled["items"][-1]["score"]) < 1e-12
    assert research.event_inputs.choices()["inputs"][0]["latest_as_of"] == rows[-1]["as_of"]


def test_matrix_late_known_scalar_is_not_used_as_if_available(tmp_path):
    research = host(tmp_path)
    source, _rows = matrix_source(research, years=2, late_last=True)
    registered = research.event_inputs.register_native(
        "factor_inputs", source, "SSE", "late-known-matrix"
    )
    compiled = research.event_inputs.factor_signals(
        {"id": registered["id"], "revision": registered["revision"]}
    )
    assert compiled["items"][-2]["score"] is not None
    assert compiled["items"][-1]["score"] is None
    assert compiled["items"][-1]["status"] == "DATA_INELIGIBLE"


def test_late_publication_cannot_enter_point_or_stream_history_before_publication(tmp_path):
    outputs = []
    for label, altered in (("original", None), ("altered", 9999)):
        research = host(tmp_path / label)
        source, rows = matrix_source(
            research, years=2, delayed_publication_index=300, delayed_value=altered
        )
        registered = research.event_inputs.register_native(
            "factor_inputs", source, "SSE", "delayed-publication-matrix"
        )
        compiled = research.event_inputs.factor_signals(
            {"id": registered["id"], "revision": registered["revision"]}
        )["items"]
        assert compiled[300]["score"] is None
        for position in range(301, 306):
            resolved = research.event_inputs.resolve_market_factor_point(
                index_id="SSE",
                as_of=rows[position]["as_of"],
                inputs=registered["payload"]["bundle"],
            )
            actual = compute_score(
                "SSE", resolved.as_of, resolved.axes, source_receipts=resolved.source_receipts
            )["candidate_score"]
            assert actual == compiled[position]["score"]
            assert all(
                item["as_of"][:10] != rows[300]["observed_at"][:10]
                for item in resolved.axes["trend"]["history"]
            )
        outputs.append(compiled)
    assert [point["score"] for point in outputs[0][301:306]] == [
        point["score"] for point in outputs[1][301:306]
    ]
    assert any(
        left["score"] != right["score"]
        for left, right in zip(outputs[0][306:316], outputs[1][306:316])
    )
