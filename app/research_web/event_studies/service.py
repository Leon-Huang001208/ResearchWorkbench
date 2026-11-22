"""Host-owned evidence resolution, immutable trials and one-use validation batches."""

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock

from core.observability import get_logger

from ..store import StoreError
from .backtest import replay
from .calendars import (
    CALENDAR_RULES,
    FAMILIES,
    calendar_knowledge_gaps,
    calendar_windows,
    event_windows,
)
from .contracts import (
    POLICY,
    SOURCE_CONTRACT_DIGEST,
    STRATEGY_PROTOCOL,
    Calendar,
    Proxy,
    StudyError,
    StudySpec,
    execution_contract,
    proxy_identity,
    rule_contract,
    stamp,
)
from .events import availability_floor, forecast_window_gaps, project_event
from .prediction import fingerprint, prepare_prediction, validate_prediction_family
from .registry import INDICES
from .research import (
    independent_episodes,
    matched_controls,
    observed_calendar,
    summaries,
    window_returns,
)
from .validation import assess, bootstrap_family, chronological_split

log = get_logger(__name__)
IMPLEMENTATION_ROOT = Path(__file__).parents[1]


def implementation_sources():
    """Bound the real deterministic research and default Host compilation code."""
    paths = [
        *IMPLEMENTATION_ROOT.joinpath("event_studies").glob("*.py"),
        *IMPLEMENTATION_ROOT.joinpath("market_scoring").glob("*.py"),
        IMPLEMENTATION_ROOT / "event_host_inputs.py",
        IMPLEMENTATION_ROOT / "event_datahub_bridge.py",
    ]
    return tuple(sorted(path.relative_to(IMPLEMENTATION_ROOT).as_posix() for path in paths))


def implementation_digest():
    """Re-read path-bound source hashes before opening any sealed holdout."""
    try:
        sources = [
            [relative, hashlib.sha256((IMPLEMENTATION_ROOT / relative).read_bytes()).hexdigest()]
            for relative in implementation_sources()
        ]
    except OSError as exc:
        log.warning("event_study_implementation_unavailable", error_type=type(exc).__name__)
        raise StudyError("implementation_source_unavailable") from exc
    return hashlib.sha256(
        json.dumps(
            {"format": "event-study-implementation-v2", "sources": sources},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class StudyBundle:
    """Only a trusted Host adapter may construct a qualified bundle.

    Browser JSON is resolved through the unqualified archive branch instead.
    Qualification requires independently verified historical facts and receipts.
    """

    index_id: str
    rows: list[dict]
    data_digest: str
    calendar: Calendar | None = None
    proxy: Proxy | None = None
    signals: dict = field(default_factory=dict)
    base_signals: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    holidays: list[dict] = field(default_factory=list)
    evidence_sha256: str = ""
    qualification_receipts: tuple[str, ...] = ()
    index_rows: list[dict] = field(default_factory=list)
    index_calendar: Calendar | None = None
    index_calendar_basis: str | None = None
    index_data_digest: str = ""
    index_qualification_receipts: tuple[str, ...] = ()
    signal_receipts: dict = field(default_factory=dict)
    data_gaps: tuple[str, ...] = ("historical_point_in_time_not_verified",)
    calendar_basis: str = "unverified_sessions"


class StudyService:
    def __init__(self, research):
        self.research = research
        self._activity_lock = RLock()
        self._active_count = 0

    @property
    def active(self):
        with self._activity_lock:
            return self._active_count > 0

    @contextmanager
    def activity(self):
        """A request cancellation never retires a still-draining worker thread."""
        with self._activity_lock:
            self._active_count += 1
        try:
            yield
        finally:
            with self._activity_lock:
                self._active_count -= 1

    @property
    def events(self):
        events = getattr(self.research, "event_timeline", None)
        if events is None:
            raise StoreError("事件存储尚未就绪", "event_store_unavailable", 503)
        return events

    @property
    def records(self):
        return self.events.records

    def catalog(self):
        return {
            "indices": [{"id": key, **value} for key, value in INDICES.items()],
            "policy_version": POLICY,
            "horizon": 20,
            "overlay_cap": 5,
            "calendar_windows": [1, 5, 10],
            "period_windows": [1, 5],
            "base_commission_bps": 10,
            "base_slippage_bps": 10,
            "families": FAMILIES,
            "source_policy": "public_free_only",
            "browser_arrays_grant_admission": False,
        }

    def list(self, limit=100, cursor=None):
        result = self.records.list("study", limit=limit, cursor=cursor)
        source_catalog = getattr(self.research, "available_event_sources", None)
        sources = source_catalog().get("items", []) if source_catalog else []
        return {
            **result,
            **self.catalog(),
            "bundles": self.records.list("prices", limit=100)["items"],
            "freezes": self.records.list("freeze", limit=100)["items"],
            "source_choices": sources,
            "validation_batches": [
                {
                    "id": row["id"],
                    "revision": row["revision"],
                    "label": "；".join(
                        f"{index} {span[0]}—{span[1]}"
                        for index, span in sorted(row["payload"].get("indices", {}).items())
                    )
                    + " · "
                    + "、".join(
                        item["spec"]["title"] for item in row["payload"].get("studies", [])[:3]
                    ),
                    "state": row["payload"].get("state"),
                }
                for row in self.records.list("validation_batch", limit=100)["items"]
                if row["payload"].get("state") == "sealed"
            ],
        }

    def get(self, identity):
        return self.records.get("study", identity)

    def run(self, identity):
        return self.records.get("study_run", identity)

    def runs(self, study_id, *, cursor=None):
        self.get(study_id)  # Owner/identity check happens in the server store.
        page = self.records.list("study_run", limit=20, cursor=cursor)
        items = []
        for record in page["items"]:
            payload = record["payload"]
            if payload.get("study_id") == study_id:
                summary = {
                    key: payload[key]
                    for key in (
                        "study_id",
                        "validation",
                        "report_digest",
                        "data_digest",
                        "calendar_basis",
                        "holdout_status",
                        "summary",
                    )
                    if key in payload
                }
                items.append(
                    {"id": record["id"], "revision": record["revision"], "payload": summary}
                )
        return {"items": items, "next_cursor": page.get("next_cursor")}

    def export(self, run_id, format="json"):
        record = self.run(run_id)
        payload = record["payload"]
        if format == "json":
            return (
                json.dumps(
                    record,
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode(),
                "application/json",
            )
        if format != "csv":
            raise StudyError("study_export_format_invalid")
        from ..datahub.snapshots import csv_bytes

        spec = payload.get("spec", {})
        common = {
            "run_id": run_id,
            "study_id": payload["study_id"],
            "index_id": spec.get("index_id"),
            "family": spec.get("family"),
            "direction": spec.get("direction"),
            "validation_status": payload["validation"]["status"],
            "source": payload.get("source", {}),
            "data_digest": payload.get("data_digest"),
            "calendar_basis": payload.get("calendar_basis"),
            "limitations": payload.get("limitations", []),
        }
        rows = [{**common, **window} for window in payload.get("windows", [])]
        return (
            csv_bytes(
                rows or [{**common, "rule": spec.get("rule"), "validation": payload["validation"]}]
            ),
            "text/csv; charset=utf-8",
        )

    def _source_summary(self, spec):
        reference = spec.bundle_ref
        payload = self.records.get("prices", reference["id"], revision=reference["revision"])[
            "payload"
        ]
        summary = {"bundle_ref": reference}
        for name in (
            "evidence_ref",
            "original_ref",
            "calendar_ref",
            "proxy_ref",
            "factor_inputs_ref",
        ):
            if isinstance(payload.get(name), dict):
                summary[name] = {
                    key: value
                    for key, value in payload[name].items()
                    if key in {"id", "revision", "sha256", "manifest_sha256"}
                }
        if isinstance(payload.get("source_snapshot"), dict):
            summary["datahub"] = {
                key: value
                for key, value in payload["source_snapshot"].items()
                if key in {"session_id", "dataset_id", "index_id"}
            }
        for name in ("source_manifest_sha256", "source_kind", "calendar_basis"):
            if name in payload:
                summary[name] = payload[name]
        return summary

    def create(self, raw, key):
        spec = StudySpec.model_validate(raw)
        # Resolving references before persistence rejects other-account/missing evidence.
        self._resolve(spec)
        payload = {
            "spec": spec.model_dump(mode="json"),
            "state": "registered",
            "policy_version": POLICY,
        }
        result = self.records.batch(
            [
                {"kind": "study", "payload": payload},
                {
                    "kind": "trial",
                    "payload": {
                        "hypothesis": spec.hypothesis,
                        "status": "registered",
                        "spec_digest": digest(payload["spec"]),
                    },
                },
            ],
            key,
            intent=payload,
            scope="study-create",
        )[0]
        log.info("event_study_registered", role=spec.role, index=spec.index_id)
        return result

    def _archive(self, record):
        ref = record["payload"].get("evidence_ref")
        if not isinstance(ref, dict):
            raise StudyError("immutable_source_evidence_missing")
        evidence = self.events.read_evidence(ref)
        try:
            data = json.loads(evidence["bytes"])
        except (ValueError, TypeError, UnicodeError, KeyError):
            raise StudyError("source_evidence_invalid") from None
        if not isinstance(data, dict):
            raise StudyError("source_evidence_invalid")
        return data, ref["sha256"]

    def _frozen_events(self, spec):
        if spec.frozen_event_ref is None:
            return []
        ref = spec.frozen_event_ref
        frozen = self.records.get("freeze", ref["id"], revision=ref["revision"])["payload"]
        observed_times = {}

        def archive_observed(evidence):
            key = (evidence.get("id"), evidence.get("sha256"), evidence.get("manifest_sha256"))
            if key not in observed_times:
                manifest = self.events.read_evidence(evidence).get("manifest", {})
                observed_times[key] = manifest.get("first_observed")
            return observed_times[key]

        for evidence in frozen.get("evidence_refs", []):
            archive_observed(evidence)
        result = []
        for event_ref in frozen.get("event_refs", []):
            event = self.records.get("event", event_ref["id"], revision=event_ref["revision"])[
                "payload"
            ]
            if event.get("admission") != "confirmed":
                raise StudyError("event_not_confirmed")
            category = "calendar" if spec.role == "calendar_overlay" else spec.family
            if event.get("category") != category:
                continue
            getter = getattr(self.records, "revision_recorded_at", None)
            recorded = getter("event", event_ref["id"], event_ref["revision"]) if getter else None
            floor = availability_floor(
                recorded,
                [archive_observed(evidence) for evidence in event.get("evidence_refs", [])],
            )
            projected = project_event(
                event,
                spec.index_id,
                identifier=event_ref["id"],
                revision=event_ref["revision"],
                known_floor=floor,
            )
            if projected is None:
                raise StudyError("event_daily_window_ineligible")
            result.append(projected)
        if not result:
            raise StudyError("frozen_event_sample_empty")
        return result

    def _resolve(self, spec):
        resolver = getattr(self.research, "resolve_event_study_bundle", None)
        if resolver is not None:
            bundle = resolver(spec.bundle_ref)
            if not isinstance(bundle, StudyBundle) or bundle.index_id != spec.index_id:
                raise StudyError("trusted_study_bundle_invalid")
            if not bundle.data_gaps and (
                not bundle.qualification_receipts or bundle.calendar is None or bundle.proxy is None
            ):
                raise StudyError("historical_qualification_receipt_missing")
            if spec.role == "event_overlay":
                frozen = self._frozen_events(spec)
                bundle = replace(bundle, events=frozen)
            elif (
                spec.role == "calendar_overlay"
                and spec.family == "holiday"
                and spec.frozen_event_ref
            ):
                frozen = self._frozen_events(spec)
                bundle = replace(bundle, holidays=[*bundle.holidays, *frozen])
            return bundle
        ref = spec.bundle_ref
        source = self.records.get("prices", ref["id"], revision=ref["revision"])
        data, sha = self._archive(source)
        if data.get("index_id") != spec.index_id or not isinstance(data.get("rows"), list):
            raise StudyError("source_index_mismatch")
        rows = data["rows"]
        if (
            not rows
            or len(rows) > 20000
            or any(
                not isinstance(r, dict) or not isinstance(r.get("day"), str) or "close" not in r
                for r in rows
            )
        ):
            raise StudyError("source_prices_invalid")
        if [r["day"] for r in rows] != sorted({r["day"] for r in rows}):
            raise StudyError("source_prices_invalid")
        chronological_split([r["day"] for r in rows])
        cal = None
        holidays = []
        calendar_ref = source["payload"].get("calendar_ref")
        if calendar_ref:
            record = self.records.get(
                "calendar", calendar_ref["id"], revision=calendar_ref["revision"]
            )
            calendar_data, _ = self._archive(record)
            holidays = calendar_data.pop("holidays", [])
            cal = Calendar.model_validate(calendar_data)
        frozen_events = self._frozen_events(spec)
        if spec.role == "calendar_overlay" and spec.family == "holiday":
            holidays += frozen_events
        return StudyBundle(
            index_id=spec.index_id,
            rows=rows,
            data_digest=sha,
            calendar=cal,
            index_rows=rows,
            index_calendar=cal,
            index_data_digest=sha,
            holidays=holidays,
            events=frozen_events,
            calendar_basis=(
                source["payload"].get("calendar_basis", "source_declared_sessions_unverified")
                if cal
                else "observed_price_dates_only"
            ),
            data_gaps=(
                "historical_point_in_time_not_verified",
                "tradable_proxy_not_qualified",
                "factor_history_not_qualified",
            ),
        )

    def analyze(self, study_id, key):
        item = self.get(study_id)
        spec = StudySpec.model_validate(item["payload"]["spec"])
        bundle = self._resolve(spec)
        index_rows = self._index_rows(bundle)
        index_digest = self._index_digest(bundle)
        index_calendar = self._index_calendar(bundle)
        if not index_rows or not index_digest:
            raise StudyError("index_evidence_missing")
        split = chronological_split([r["day"] for r in index_rows])
        # Looking at historical statistics consumes their future eligibility as an
        # untouched test range. New disjoint future data remains admissible.
        self.records.claim_study_ranges(
            [
                {
                    "scope": spec.index_id,
                    "start": index_rows[0]["day"],
                    "end": index_rows[-1]["day"],
                    "phase": "viewed",
                    "batch_id": f"view:{study_id}",
                }
            ],
            f"study-view:{study_id}:{index_digest}",
        )
        windows = self._windows(spec, bundle)
        returns = window_returns(windows, index_rows)
        controls = matched_controls(windows, index_rows)
        limitations = (
            list(bundle.data_gaps)
            + self._endpoint_gaps(spec, bundle)
            + (["calendar_evidence_missing"] if index_calendar is None else [])
        )
        qualification = self._qualification_status()
        if qualification["required"]:
            limitations.append(qualification["code"])
        validation = self._report(
            spec,
            bundle,
            study_id,
            "DATA_INELIGIBLE" if limitations else "INSUFFICIENT_SAMPLE",
            limitations,
        )
        payload = {
            "study_id": study_id,
            "spec": spec.model_dump(mode="json"),
            "windows": returns,
            "summary": summaries(returns),
            "controls": controls,
            "validation": validation,
            "report_digest": digest(validation),
            "data_digest": index_digest,
            "proxy_data_digest": bundle.data_digest if bundle.proxy else None,
            "holdout_status": "historical_range_viewed_not_untouched",
            "calendar_basis": self._index_calendar_basis(bundle),
            "split_counts": {k: len(v) for k, v in split.items() if isinstance(v, list)},
        }
        payload.update(source=self._source_summary(spec), limitations=limitations)
        ledger = []
        rules = (
            {spec.rule}
            if spec.rule
            else set(FAMILIES[spec.family]) if spec.family else set(CALENDAR_RULES)
        )
        rules.update(row["rule"] for row in returns)
        for rule in sorted(rules):
            rows = [row for row in returns if row["rule"] == rule]
            ledger.append(
                {
                    "kind": "trial",
                    "payload": {
                        "study_id": study_id,
                        "rule": rule,
                        "spec_digest": digest(spec.model_dump(mode="json")),
                        "data_digest": index_digest,
                        "status": (
                            "descriptive_complete"
                            if rows and all(row["status"] == "complete" for row in rows)
                            else "missing_or_insufficient_data"
                        ),
                        "window_count": len(rows),
                        "purpose": "descriptive_not_formal_validation",
                    },
                }
            )
        saved = self.records.batch(
            [{"kind": "study_run", "payload": payload}] + ledger,
            key,
            intent={
                "study_id": study_id,
                "data_digest": index_digest,
                "proxy_data_digest": bundle.data_digest if bundle.proxy else None,
            },
            scope="study-analysis",
        )
        result = saved[0]
        log.info("event_study_described", index=spec.index_id, windows=len(returns))
        return result

    def _report(self, spec, bundle, study_id, status, reasons):
        from ..market_scoring.profiles import profile_for

        # A certificate cannot be backdated to the data cutoff. The store caches
        # completed request receipts; retries return their original timestamps.
        clock = getattr(self.research, "_event_study_clock", None)
        now = stamp(clock()) if clock is not None else datetime.now(UTC)
        available = [rows[-1]["day"] for rows in (bundle.rows, self._index_rows(bundle)) if rows]
        if not available:
            raise StudyError("index_evidence_missing")
        cutoff_day = max(available)
        earliest = datetime.fromisoformat(cutoff_day).replace(tzinfo=UTC) + timedelta(days=1)
        now = max(now, earliest)
        return {
            "status": status,
            "role": spec.role,
            "index_id": spec.index_id,
            "horizon": spec.horizon,
            "profile_version": spec.profile_version,
            "evidence_sha256": bundle.evidence_sha256
            or self._index_digest(bundle)
            or bundle.data_digest,
            "training_holdout_evidence_sha256": bundle.evidence_sha256
            or self._index_digest(bundle)
            or bundle.data_digest,
            "profile_sha256": digest(profile_for(spec.index_id)),
            "strategy_protocol": STRATEGY_PROTOCOL,
            "source_contract_digest": SOURCE_CONTRACT_DIGEST,
            "signal_rule_sha256": digest(
                rule_contract(
                    spec.role, spec.profile_version, spec.family, spec.direction, spec.rule
                )
            ),
            "execution_rule_sha256": digest(execution_contract()),
            "proxy_identity_sha256": digest(proxy_identity(bundle.proxy)) if bundle.proxy else None,
            "study_id": study_id,
            "policy_version": POLICY,
            "reasons": reasons,
            "family": spec.family,
            "direction": spec.direction,
            "rule": spec.rule,
            "rules_digest": digest(
                rule_contract(
                    spec.role, spec.profile_version, spec.family, spec.direction, spec.rule
                )
            ),
            "implementation_digest": implementation_digest(),
            "valid_from": now.isoformat(),
            "expires_at": (now + timedelta(days=365)).isoformat(),
        }

    def seal(self, study_ids, key):
        self._qualification_guard()
        if not study_ids or len(study_ids) > 100 or len(set(study_ids)) != len(study_ids):
            raise StudyError("validation_family_invalid")
        studies, indices = [], {}
        for identity in sorted(study_ids):
            item = self.get(identity)
            spec = StudySpec.model_validate(item["payload"]["spec"])
            if spec.role != "base_score" and spec.rule is None:
                raise StudyError("formal_overlay_requires_exact_registered_rule")
            if spec.rule == "reopening_gap":
                raise StudyError("reopening_gap_requires_pre_closure_execution")
            bundle = self._resolve(spec)
            endpoint_gaps = self._endpoint_gaps(spec, bundle)
            if endpoint_gaps:
                raise StudyError(endpoint_gaps[0])
            split = chronological_split([r["day"] for r in bundle.rows])
            index_rows = self._index_rows(bundle)
            index_split = (
                chronological_split([r["day"] for r in index_rows]) if index_rows else None
            )
            if not split["holdout"]:
                raise StudyError("holdout_empty")
            studies.append(
                {
                    "id": identity,
                    "revision": item["revision"],
                    "spec": spec.model_dump(mode="json"),
                    "data_digest": bundle.data_digest,
                    "split": split,
                    "index_split": index_split,
                    "index_inputs_sha256": self._index_inputs_digest(bundle),
                }
            )
            index_days = (
                index_split["holdout"]
                if index_split and index_split["holdout"]
                else split["holdout"]
            )
            current = (
                min(split["holdout"][0], index_days[0]),
                max(split["holdout"][-1], index_days[-1]),
            )
            if spec.index_id in indices and indices[spec.index_id] != current:
                raise StudyError("family_holdout_range_mismatch")
            indices[spec.index_id] = current
        families = {s["spec"]["family_id"] for s in studies}
        if len(families) != 1:
            raise StudyError("validation_family_mismatch")
        registered = self.records.list("study", limit=100)
        if registered.get("next_cursor"):
            raise StudyError("validation_family_exceeds_budget")
        required = {
            s["id"]
            for s in registered["items"]
            if s["payload"]["spec"].get("family_id", "event-calendar-v1") in families
        }
        if required != set(study_ids):
            raise StudyError("registered_trials_omitted_from_family")
        payload = {
            "studies": studies,
            "indices": indices,
            "policy_version": POLICY,
            "implementation_digest": implementation_digest(),
            "state": "pending_seal",
        }
        result = self.records.create("validation_batch", payload, key)
        current = self.records.get("validation_batch", result["id"])
        if current["payload"].get("state") == "sealed":
            return current
        self.records.claim_study_ranges(
            [
                {
                    "scope": index,
                    "start": span[0],
                    "end": span[1],
                    "phase": "sealed",
                    "batch_id": result["id"],
                }
                for index, span in sorted(indices.items())
            ],
            f"study-seal:{result['id']}",
        )
        result = self.records.update(
            "validation_batch",
            result["id"],
            {**payload, "state": "sealed"},
            current["revision"],
            f"study-seal-complete:{result['id']}",
            guard=self._qualification_guard,
        )
        log.info("event_study_family_sealed", trials=len(studies))
        return result

    def evaluate(self, batch_id, key):
        self._qualification_guard()
        batch = self.records.get("validation_batch", batch_id)["payload"]
        if batch.get("state") != "sealed":
            raise StudyError("validation_batch_not_sealed")
        if batch.get("implementation_digest") != implementation_digest():
            raise StudyError("sealed_implementation_changed")
        previous = [
            r
            for r in self.records.list("study_run", limit=100)["items"]
            if r["payload"].get("batch_id") == batch_id
        ]
        if previous:
            if len(previous) == len(batch["studies"]) and all(
                r["payload"].get("request_digest") == digest(key) for r in previous
            ):
                return {"items": previous}
            raise StudyError("holdout_result_reconciliation_required")
        # A fixed opening key plus persistent one-shot claim prevents unknown
        # computation/crash results being automatically retried.
        self.records.claim_study_ranges(
            [
                {
                    "scope": index,
                    "start": span[0],
                    "end": span[1],
                    "phase": "opened",
                    "batch_id": batch_id,
                }
                for index, span in sorted(batch["indices"].items())
            ],
            f"study-open:{batch_id}:{key}",
        )
        self.records.claim_once("holdout", f"compute:{batch_id}", {"request_digest": digest(key)})
        trials, bundles, specifications, predictions, index_bindings = {}, {}, {}, {}, {}
        for frozen in batch["studies"]:
            identity = frozen["id"]
            spec = StudySpec.model_validate(frozen["spec"])
            bundle = self._resolve(spec)
            if bundle.data_digest != frozen["data_digest"]:
                raise StudyError("sealed_evidence_changed")
            if frozen.get("index_inputs_sha256") != self._index_inputs_digest(bundle):
                raise StudyError("sealed_index_evidence_changed")
            specifications[identity], bundles[identity] = spec, bundle
            holdout = frozen["split"]["holdout"]
            episodes = (
                independent_episodes(self._windows(spec, bundle))
                if spec.role != "base_score"
                else []
            )
            episodes = [e for e in episodes if holdout[0] <= e["start"] <= e["end"] <= holdout[-1]]
            trial = {
                "days": holdout,
                "data_gaps": list(bundle.data_gaps) + self._endpoint_gaps(spec, bundle),
                "event": spec.role != "base_score",
                "event_episodes": episodes,
            }
            if spec.rule == "reopening_gap":
                trial["data_gaps"].append("reopening_gap_requires_pre_closure_execution")
            if spec.role == "event_overlay" and any(
                not event.get("known_at") for event in bundle.events
            ):
                trial["data_gaps"].append("event_public_knowledge_time_missing")
            if spec.role != "base_score":
                index_days = frozen["index_split"]["holdout"] if frozen.get("index_split") else []
                prediction = {
                    "pairs": [],
                    "missing": [],
                    "days": index_days,
                    "data_gaps": self._index_history_gaps(bundle),
                }
                if not prediction["data_gaps"]:
                    try:
                        prediction.update(
                            prepare_prediction(
                                bundle.index_rows,
                                self._windows(spec, bundle),
                                index_days,
                                spec.direction,
                                exclusion_windows=self._exclusions(bundle),
                                calendar=bundle.index_calendar,
                                events=bundle.events,
                                deterministic_calendar=spec.role == "calendar_overlay",
                            )
                        )
                    except StudyError as exc:
                        prediction["data_gaps"].append(exc.code)
                predictions[identity] = prediction
                index_bindings[identity] = {
                    "index_id": spec.index_id,
                    "family": spec.family,
                    "rule": spec.rule,
                    "direction": spec.direction,
                    "profile_version": spec.profile_version,
                    "profile_sha256": digest(self._profile(spec.index_id)),
                    "signal_rule_sha256": digest(
                        rule_contract(
                            spec.role, spec.profile_version, spec.family, spec.direction, spec.rule
                        )
                    ),
                    "index_data_digest": bundle.index_data_digest,
                    "index_inputs_sha256": frozen["index_inputs_sha256"],
                    "source_receipts_sha256": digest(bundle.index_qualification_receipts),
                    "holdout_id": batch_id,
                    "study_id": identity,
                    "horizon": 20,
                    "split_policy": POLICY,
                    "holdout_start": index_days[0] if index_days else None,
                    "holdout_end": index_days[-1] if index_days else None,
                }
            if spec.role != "base_score" and bundle.calendar is not None:
                trial["data_gaps"].extend(self._calendar_knowledge_gaps(spec, bundle, holdout))
            if not bundle.signal_receipts:
                trial["data_gaps"].append("signal_point_in_time_receipts_missing")
            if not trial["data_gaps"]:
                try:
                    selected = set(holdout)
                    cal = bundle.calendar.model_copy(
                        update={
                            "sessions": [
                                s for s in bundle.calendar.sessions if s.day.isoformat() in selected
                            ]
                        }
                    )
                    prices = [r for r in bundle.rows if r["day"] in selected]
                    strategy = {d: w for d, w in bundle.signals.items() if d in selected}
                    comparator = (
                        {d: "1" for d in holdout}
                        if spec.role == "base_score"
                        else {d: w for d, w in bundle.base_signals.items() if d in selected}
                    )
                    if not strategy or not comparator:
                        raise StudyError("qualified_score_signals_missing")
                    if spec.role != "base_score":
                        from decimal import Decimal

                        windows = self._windows(spec, bundle)
                        event_knowledge = (
                            {event["id"]: stamp(event["known_at"]) for event in bundle.events}
                            if spec.role == "event_overlay"
                            else {}
                        )
                        active = {
                            d
                            for d in holdout
                            if any(
                                w["start"] <= d < w["end"]
                                and (
                                    spec.role != "event_overlay"
                                    or event_knowledge[w["episode"]]
                                    <= stamp(bundle.signal_receipts.get(d, {}).get("known_at"))
                                )
                                for w in windows
                            )
                        }
                        # The registered family/rule/direction compiles the actual
                        # strategy. A callback cannot provide an unrelated winner.
                        strategy = {
                            d: str(
                                max(
                                    Decimal(0),
                                    min(
                                        Decimal(1),
                                        Decimal(str(w))
                                        + (Decimal(spec.direction) / 100 if d in active else 0),
                                    ),
                                )
                            )
                            for d, w in comparator.items()
                        }
                    for i, session in enumerate(cal.sessions[:-1]):
                        day = session.day.isoformat()
                        if day in strategy:
                            receipt = bundle.signal_receipts.get(day, {})
                            if (
                                not receipt.get("source_ref")
                                or stamp(receipt.get("known_at")) >= cal.sessions[i + 1].opens
                            ):
                                raise StudyError("signal_not_known_before_execution")
                    if spec.role != "base_score" and any(
                        abs(float(strategy[d]) - float(comparator.get(d, strategy[d])))
                        > 0.0500000001
                        for d in strategy
                    ):
                        raise StudyError("overlay_contribution_exceeds_five_points")
                    for tag, multiplier in (("normal", 1), ("stress", 2)):
                        a = replay(cal, bundle.proxy, prices, strategy, cost_multiplier=multiplier)
                        b = replay(
                            cal, bundle.proxy, prices, comparator, cost_multiplier=multiplier
                        )
                        trial[tag] = {"strategy": a["metrics"], "comparator": b["metrics"]}
                except StudyError as exc:
                    trial["data_gaps"].append(exc.code)
            trials[identity] = trial
        candidates = {
            key: {
                "days": t["days"],
                "strategy": t["normal"]["strategy"]["daily_returns"],
                "comparator": t["normal"]["comparator"]["daily_returns"],
            }
            for key, t in trials.items()
            if not t["data_gaps"]
        }
        episode_keys = {}
        # One event episode is shared across all markets in the frozen family.
        for trial in trials.values():
            for episode in trial["event_episodes"]:
                for day in trial["days"]:
                    if episode["start"] <= day <= episode["end"]:
                        episode_keys[day] = f"episode:{episode['id']}"
        bootstraps = bootstrap_family(candidates, episode_keys=episode_keys) if candidates else {}
        for identity, result in bootstraps.items():
            trials[identity]["bootstrap"] = result
        decisions = assess(trials)
        index_decisions = (
            validate_prediction_family(predictions, sorted(predictions)) if predictions else {}
        )
        outputs = []
        for identity, decision in decisions.items():
            independent_receipt = None
            if identity in index_decisions:
                independent_receipt = {**index_decisions[identity], **index_bindings[identity]}
                independent_receipt["receipt_sha256"] = fingerprint(independent_receipt)
                if independent_receipt["status"] != "VALIDATED":
                    severity = {
                        "VALIDATED": 0,
                        "VALIDATION_FAILED": 1,
                        "INSUFFICIENT_SAMPLE": 2,
                        "DATA_INELIGIBLE": 3,
                    }
                    if severity[independent_receipt["status"]] > severity[decision["status"]]:
                        decision["status"] = independent_receipt["status"]
                    decision["reasons"] += [
                        f"index_prediction:{reason}" for reason in independent_receipt["reasons"]
                    ]
            report = self._report(
                specifications[identity],
                bundles[identity],
                identity,
                decision["status"],
                decision["reasons"],
            )
            report.update(
                {
                    "holdout_id": batch_id,
                    "metrics": {k: trials[identity].get(k) for k in ("normal", "stress")},
                    **decision,
                }
            )
            if independent_receipt is not None:
                reference = {"id": independent_receipt["receipt_sha256"][:32], "revision": 1}
                outputs.append(
                    {"kind": "admission", "new_id": reference["id"], "payload": independent_receipt}
                )
                report.update(index_prediction=independent_receipt, index_prediction_ref=reference)
            outputs.append(
                {
                    "kind": "study_run",
                    "payload": {
                        "study_id": identity,
                        "validation": report,
                        "report_digest": digest(report),
                        "batch_id": batch_id,
                        "data_digest": bundles[identity].data_digest,
                        "spec": specifications[identity].model_dump(mode="json"),
                        "source": self._source_summary(specifications[identity]),
                        "calendar_basis": bundles[identity].calendar_basis,
                        "limitations": list(bundles[identity].data_gaps),
                        "request_digest": digest(key),
                    },
                }
            )
        results = self.records.batch(outputs, key, guard=self._qualification_guard)
        log.info("event_study_holdout_evaluated", trials=len(outputs))
        return {
            "items": [
                result
                for operation, result in zip(outputs, results)
                if operation["kind"] == "study_run"
            ]
        }

    def preflight(self, study_id):
        item = self.get(study_id)
        spec = StudySpec.model_validate(item["payload"]["spec"])
        bundle = self._resolve(spec)
        index_rows = self._index_rows(bundle)
        gaps = (
            list(bundle.data_gaps)
            + self._endpoint_gaps(spec, bundle)
            + self._forecast_gaps(spec, bundle)
        )
        qualification = self._qualification_status()
        if qualification["required"]:
            gaps.append(qualification["code"])
        if spec.rule == "reopening_gap":
            gaps.append("reopening_gap_requires_pre_closure_execution")
        if self._index_calendar(bundle) is None:
            gaps.append("calendar_evidence_missing")
        if not index_rows or not self._index_digest(bundle):
            gaps.append("index_evidence_missing")
        if bundle.proxy is None:
            gaps.append("tradable_proxy_missing")
        if spec.role != "base_score":
            gaps.extend(self._index_history_gaps(bundle))
        return {
            "study_id": study_id,
            "status": "DATA_INELIGIBLE" if gaps else "ready_for_sealed_validation",
            "reasons": sorted(set(gaps)),
            "historical_rows": len(index_rows),
            "coverage_start": index_rows[0]["day"] if index_rows else None,
            "coverage_end": index_rows[-1]["day"] if index_rows else None,
            "split": chronological_split([r["day"] for r in index_rows]),
            "calendar_basis": self._index_calendar_basis(bundle),
            "proxy_coverage": {
                "historical_rows": len(bundle.rows) if bundle.proxy else 0,
                "coverage_start": bundle.rows[0]["day"] if bundle.proxy and bundle.rows else None,
                "coverage_end": bundle.rows[-1]["day"] if bundle.proxy and bundle.rows else None,
            },
        }

    def _windows(self, spec, bundle):
        cal = self._index_calendar(bundle) or observed_calendar(self._index_rows(bundle))
        windows = (
            event_windows(cal, bundle.events)
            if spec.role == "event_overlay"
            else calendar_windows(cal, bundle.holidays if isinstance(cal, Calendar) else [])
        )
        if spec.family is not None:
            allowed = {spec.rule} if spec.rule else set(FAMILIES[spec.family])
            windows = [row for row in windows if row["rule"] in allowed]
        return windows

    def _calendar_knowledge_gaps(self, spec, bundle, holdout):
        """Execution sessions are ex-post facts; forecasting boundaries need announcements."""
        cal = self._index_calendar(bundle)
        if cal is None:
            return ["index_calendar_evidence_missing"]
        for window in self._windows(spec, bundle):
            if not holdout[0] <= window["start"] <= window["end"] <= holdout[-1]:
                continue
            known_by = bundle.signal_receipts.get(window["start"], {}).get("known_at")
            gaps = calendar_knowledge_gaps(cal, window, known_by)
            if gaps:
                return gaps
        return []

    def _index_rows(self, bundle):
        # Proxy bars are never silently relabelled as independent index returns.
        return bundle.index_rows or (bundle.rows if bundle.proxy is None else [])

    def _index_calendar(self, bundle):
        return bundle.index_calendar or (bundle.calendar if bundle.proxy is None else None)

    def _index_digest(self, bundle):
        return bundle.index_data_digest or (bundle.data_digest if bundle.proxy is None else "")

    def _index_calendar_basis(self, bundle):
        if self._index_calendar(bundle) is None:
            return "observed_price_dates_only"
        return bundle.index_calendar_basis or (
            bundle.calendar_basis if bundle.proxy is None else "index_sessions_unverified"
        )

    def _index_inputs_digest(self, bundle):
        return digest(
            {
                "rows": self._index_rows(bundle),
                "data_digest": bundle.index_data_digest,
                "calendar": (
                    self._index_calendar(bundle).model_dump(mode="json")
                    if self._index_calendar(bundle)
                    else None
                ),
                "events": bundle.events,
                "holidays": bundle.holidays,
                "qualification_receipts": bundle.index_qualification_receipts,
            }
        )

    def _index_history_gaps(self, bundle):
        gaps = []
        if (
            not bundle.index_rows
            or not bundle.index_data_digest
            or not bundle.index_qualification_receipts
        ):
            gaps.append("independent_index_pit_evidence_missing")
        if bundle.index_calendar is None:
            gaps.append("independent_index_calendar_missing")
        elif bundle.index_rows and [r.get("day") for r in bundle.index_rows] != [
            s.day.isoformat() for s in bundle.index_calendar.sessions
        ]:
            gaps.append("index_price_calendar_mismatch")
        return gaps

    def _exclusions(self, bundle):
        cal = bundle.index_calendar
        return event_windows(cal, bundle.events) + [
            w
            for w in calendar_windows(cal, bundle.holidays)
            if w["rule"].startswith("holiday_") or w["rule"] == "reopening_gap"
        ]

    def _profile(self, index_id):
        from ..market_scoring.profiles import profile_for

        return profile_for(index_id)

    def _endpoint_gaps(self, spec, bundle):
        if (
            spec.role == "event_overlay"
            and spec.rule in {"event_during", "event_post_5", "event_post_10"}
            and bundle.events
            and not any(
                event.get("end_known") is not False and event.get("end") for event in bundle.events
            )
        ):
            return ["event_end_unknown_for_selected_window"]
        return []

    def _forecast_gaps(self, spec, bundle):
        if spec.role == "base_score":
            return []
        windows = self._windows(spec, bundle)
        checks = [
            forecast_window_gaps(
                self._index_calendar(bundle),
                window,
                events=bundle.events,
                deterministic_calendar=spec.role == "calendar_overlay",
            )
            for window in windows
        ]
        return (
            sorted({reason for reasons in checks for reason in reasons})
            if checks and all(checks)
            else []
        )

    def _qualification_status(self):
        checker = getattr(self.records, "qualification_status", None)
        if checker is None:
            return {"required": True, "code": "qualification_state_unavailable"}
        return checker()

    def _qualification_guard(self):
        status = self._qualification_status()
        if status["required"]:
            raise StoreError("来源资格需要先完成恢复对账", status["code"], 409)
