"""Executable, account-bound adapters for archived DataHub event-study inputs.

No constructor I/O, remote calls, caller PIT flags or production activation.
Only the existing canonical warehouse can certify historical availability.
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .event_studies.contracts import SOURCE_CONTRACT_DIGEST, Calendar, Proxy, number
from .event_studies.registry import INDICES
from .event_studies.service import StudyBundle
from .market_scoring import OverlayContext, ScoreContext
from .market_scoring.contracts import FactorPoint
from .market_scoring.engine import digest, stamp, study_signals
from .market_scoring.matrix import FORMAT, REFERENCE_FORMAT, point, stream_signals, validate_matrix
from .market_scoring.native_inputs import SCHEMAS, load_native, registered_event_projection, reject
from .market_scoring.profiles import PROFILE_VERSION, profile_for
from .store import StoreError

log = get_logger(__name__)


def native_boundary(function):
    """Bound malformed supplier data without exposing its values or traceback."""

    @wraps(function)
    def invoke(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except StoreError:
            raise
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            OSError,
            ArithmeticError,
            sqlite3.Error,
        ) as exc:
            log.warning(
                "event_native_contract_invalid",
                error_type=type(exc).__name__,
                code="event_native_contract_invalid",
            )
            raise StoreError(
                "来源原件不符合原生输入合同；原件已保留供核验", "event_native_contract_invalid", 422
            ) from None

    return invoke


class EventInputHost:
    def __init__(self, research):
        self.research = research
        self._lock = threading.Lock()
        self._active = 0

    @property
    def active(self):
        with self._lock:
            return self._active > 0

    @contextmanager
    def activity(self):
        with self._lock:
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1

    @property
    def events(self):
        return self.research.event_timeline

    @property
    def records(self):
        return self.events.records

    def _qualified(self):
        status = self.records.qualification_status()
        if status["required"]:
            reject(status.get("code") or "event_qualification_reconciliation_required")

    @staticmethod
    def _reference(ref):
        if (
            not isinstance(ref, dict)
            or set(ref) != {"id", "revision"}
            or type(ref.get("revision")) is not int
            or ref["revision"] < 1
        ):
            reject("event_native_record_reference_invalid")
        return ref

    def _record(self, kind, ref):
        self._reference(ref)
        record = self.records.get(kind, ref["id"], revision=ref["revision"])
        payload = record["payload"]
        evidence = self.events.read_evidence(payload.get("evidence_ref"))
        native = load_native(
            self.research,
            payload.get("source_snapshot"),
            expected_manifest_sha256=payload.get("source_manifest_sha256"),
        )
        if evidence["bytes"] != native.raw:
            # Existing index imports intentionally retain a normalized research
            # projection. Recompute it from the original private snapshot.
            from .event_datahub_bridge import normalize_rows

            value = json.loads(evidence["bytes"])
            if kind == "calendar" and payload.get("source_kind") == "provider_calendar_projection":
                expected_days = [
                    row["date"] for row in native.rows if row.get("is_trading_day") is True
                ]
                if (
                    not isinstance(value, dict)
                    or value.get("version") != native.manifest["manifest_sha256"]
                    or value.get("known_at") != native.manifest["retrieved_at"]
                    or [row.get("day") for row in value.get("sessions", [])] != expected_days
                    or value.get("exchange") != INDICES[payload["index_id"]]["exchange"]
                ):
                    reject("event_native_calendar_projection_changed")
            elif kind != "prices" or value != {
                "index_id": payload.get("index_id"),
                "rows": normalize_rows(native.raw),
            }:
                reject("event_native_registered_bytes_changed")
        return record, native, evidence

    @staticmethod
    def _node(native, kind):
        if native.manifest.get("provider_metadata", {}).get("event_input_schema") != SCHEMAS[kind]:
            reject("event_native_schema_not_declared")
        if len(native.rows) != 1 or not isinstance(native.rows[0], dict):
            reject("event_native_single_contract_required")
        key = {"calendar": "calendar", "proxy": "proxy", "factor_inputs": "factor_bundle"}.get(kind)
        value = native.rows[0].get(key)
        if not isinstance(value, dict):
            reject("event_native_contract_missing")
        return deepcopy(value)

    def _calendar(self, record, native):
        value = self._node(native, "calendar")
        # Capture is audit, not an assertion that all historical boundaries
        # became known at the final year of this batch.
        value["known_at"] = native.captured_at.isoformat()
        # Actual source session times are mandatory. No synthesized 09:30/16:00.
        value["source_ref"] = digest(record["payload"]["evidence_ref"])
        value["version"] = native.manifest["manifest_sha256"]
        for session in value.get("sessions", []):
            if not all(name in session for name in ("day", "opens", "closes", "half_day")):
                reject("event_native_session_times_missing")
            version = session.get("announcement_version_ref") or value.get(
                "announcement_version_ref"
            )
            floor = native.floor(day=session["day"], metric="calendar", version=version)
            declared = session.get("known_at") or value.get("announcement_known_at")
            session["known_at"] = (
                max(stamp(declared), floor).isoformat() if declared else floor.isoformat()
            )
            session["announcement_version_ref"] = (
                version or native.formal_digest or native.manifest["manifest_sha256"]
            )
        if value.get("announcement_version_ref") is not None:
            floor = native.floor(metric="calendar", version=value["announcement_version_ref"])
            value["announcement_known_at"] = max(
                stamp(value["announcement_known_at"]), floor
            ).isoformat()
        else:
            value["announcement_known_at"] = None
            value["announcement_version_ref"] = None
        calendar = Calendar.model_validate(value)
        index_id = record["payload"]["index_id"]
        exchanges = {"CN": {"XSHG", "XSHE"}, "US": {"XNYS", "XNAS", "ARCX"}, "HK": {"XHKG"}}
        if (
            calendar.exchange not in exchanges[INDICES[index_id]["market"]]
            or calendar.timezone != profile_for(index_id)["timezone"]
        ):
            reject("event_native_calendar_index_mismatch")
        return calendar

    def _proxy(self, record, native):
        value = self._node(native, "proxy")
        bindings = native.rows[0]
        floor = native.floor(
            day=value.get("listed_on"),
            metric="proxy",
            version=bindings.get("identity_announcement_version_ref"),
        )
        value["known_at"] = max(stamp(value.get("known_at")), floor).isoformat()
        value["source_ref"] = digest(record["payload"]["evidence_ref"])
        for rule in value.get("rules", []):
            version = bindings.get("rule_announcement_version_refs", {}).get(rule["from_date"])
            floor = native.floor(
                day=rule["from_date"],
                metric="trading_rule",
                version=version,
                fallback_metric="proxy",
            )
            rule["known_at"] = max(stamp(rule.get("known_at")), floor).isoformat()
            rule["source_ref"] = value["source_ref"]
        return Proxy.model_validate(value)

    def _native_holidays(self, record, native, *, start=None, end=None, cutoff=None):
        """Project the same archived holiday and announcement clock in both lanes."""
        values = native.rows[0].get("holidays", [])
        if not isinstance(values, list) or len(values) > 20000:
            reject("event_native_holiday_contract_invalid")
        calendar = self._node(native, "calendar")
        result = []
        for value in values:
            if not isinstance(value, dict):
                reject("event_native_holiday_contract_invalid")
            first, last = date.fromisoformat(value["start"]), date.fromisoformat(value["end"])
            if (
                first.isoformat() != value["start"]
                or last.isoformat() != value["end"]
                or last < first
                or not isinstance(value.get("id"), str)
                or not value["id"]
            ):
                reject("event_native_holiday_contract_invalid")
            if (start is not None and value["end"] < start) or (
                end is not None and value["start"] > end
            ):
                continue
            version = value.get("announcement_version_ref") or calendar.get(
                "announcement_version_ref"
            )
            declared = value.get("known_at") or calendar.get("announcement_known_at")
            if not version or not declared:
                reject("event_native_holiday_knowledge_missing")
            if native.formal_digest:
                matching = [
                    fact
                    for fact in native.proofs
                    if fact.metric == "calendar"
                    and fact.source_version == version
                    and isinstance(fact.value, dict)
                    and isinstance(fact.value.get("holidays"), list)
                    and any(digest(item) == digest(value) for item in fact.value["holidays"])
                ]
                if not matching or any(fact.available_at is None for fact in matching):
                    reject("event_native_holiday_canonical_evidence_missing")
                floor = max(fact.available_at for fact in matching)
            else:
                floor = native.captured_at
            known = max(stamp(declared), floor)
            if cutoff is not None and known > cutoff:
                reject("event_native_holiday_not_known_by_cutoff")
            result.append(
                {
                    **deepcopy(value),
                    "known_at": known.isoformat(),
                    "announcement_version_ref": version,
                    "source_ref": digest(record["payload"]["evidence_ref"]),
                }
            )
        return result

    def _factors(self, native, reference, index_id):
        value = self._node(native, "factor_inputs")
        if value.get("index_id") != index_id or value.get("profile_version") != PROFILE_VERSION:
            reject("event_native_factor_identity_mismatch")
        value.pop("proxy_ref", None)
        series = value.get("series", [value])
        if not isinstance(series, list) or not 1 <= len(series) <= 20000:
            reject("event_native_factor_series_invalid")
        for row in series:
            stamp(row.get("as_of"))
            if not isinstance(row.get("axes"), dict):
                reject("event_native_factor_axes_missing")
            for axis, observation in row["axes"].items():
                definition = profile_for(index_id)["axes"].get(axis)
                if (
                    definition is None
                    or observation.get("metric") != definition["metric"]
                    or observation.get("unit") != definition["unit"]
                ):
                    reject("event_native_factor_metric_or_unit_mismatch")
                if (
                    native.manifest.get("fields", {}).get(observation["metric"], {}).get("unit")
                    != definition["unit"]
                ):
                    reject("event_native_factor_declared_unit_missing")
                observed = stamp(observation.get("as_of"))
                floor = native.floor(
                    observed.date().isoformat(),
                    observation["metric"],
                    observation.get("availability_version_ref"),
                    fallback_metric="factor_inputs",
                )
                observation["provider"] = native.manifest["provider"]
                observation["source_ref"] = reference
                observation.pop("pit_verified", None)
                observation.pop("approved", None)
                observation["known_at"] = max(
                    stamp(observation.get("published_at", observation["as_of"])),
                    stamp(observation.get("known_at", row["as_of"])),
                    floor,
                ).isoformat()
                observation["published_at"] = max(
                    stamp(observation.get("published_at", observation["as_of"])), floor
                ).isoformat()
                observation["valid_until"] = min(
                    stamp(
                        observation.get("valid_until", (observed + timedelta(days=1)).isoformat())
                    ),
                    observed + timedelta(days=7),
                ).isoformat()
                for prior in observation.get("history", []):
                    if prior.get("unit") != definition["unit"]:
                        reject("event_native_factor_history_unit_mismatch")
                    known_floor = native.floor(
                        stamp(prior.get("as_of")).date().isoformat(),
                        observation["metric"],
                        prior.get("availability_version_ref"),
                        fallback_metric="factor_inputs",
                    )
                    prior["known_at"] = max(
                        stamp(prior.get("known_at")),
                        stamp(prior.get("published_at", prior["known_at"])),
                        known_floor,
                    ).isoformat()
            row.pop("source_receipts", None)
        return value

    @native_boundary
    def register_native(self, kind, source_snapshot, index_id, key, *, links=None):
        if kind not in {"calendar", "proxy", "factor_inputs", "prices"} or index_id not in INDICES:
            reject("event_native_kind_or_index_invalid")
        native = load_native(self.research, source_snapshot)
        if native.manifest.get("provider_metadata", {}).get("event_input_schema") != SCHEMAS[kind]:
            reject("event_native_schema_not_declared")
        links = links or {}
        allowed = {
            "calendar_ref": "calendar",
            "index_calendar_ref": "calendar",
            "proxy_ref": "proxy",
            "proxy_calendar_ref": "calendar",
            "proxy_prices_ref": "prices",
            "factor_inputs_ref": "factor_inputs",
        }
        if set(links) - set(allowed):
            reject("event_native_link_kind_invalid")
        for name, ref in links.items():
            self._reference(ref)
            self.records.get(allowed[name], ref["id"], revision=ref["revision"])
        intent = {
            "kind": kind,
            "index_id": index_id,
            "source_snapshot": source_snapshot,
            "manifest_sha256": native.manifest["manifest_sha256"],
            "links": links,
        }
        cached = self.records.cached("native-input-registration", key, intent)
        if cached:
            if kind == "factor_inputs":
                reference = cached[0]["payload"]["factor_inputs_ref"]
                return self.records.get(
                    "factor_inputs", reference["id"], revision=reference["revision"]
                )
            return cached[0]
        reference = self.events.archive_evidence(
            native.raw,
            source=native.manifest["provider"],
            url=native.manifest.get("source_url") or "",
            metadata={
                "source_snapshot": source_snapshot,
                "source_manifest_sha256": native.manifest["manifest_sha256"],
                "native_kind": kind,
            },
        )
        payload = {
            "index_id": index_id,
            "evidence_ref": reference,
            "source_snapshot": source_snapshot,
            "source_manifest_sha256": native.manifest["manifest_sha256"],
            "source_contract": SCHEMAS[kind],
            **links,
        }
        if kind == "factor_inputs":
            matrix = self._node(native, "factor_inputs")
            if matrix.get("format") == FORMAT:
                matrix = validate_matrix(native, index_id)
                value = {
                    "format": REFERENCE_FORMAT,
                    "index_id": index_id,
                    "profile_version": PROFILE_VERSION,
                    "profile_sha256": digest(profile_for(index_id)),
                    "matrix_evidence_ref": reference,
                    "source_snapshot": source_snapshot,
                    "source_manifest_sha256": native.manifest["manifest_sha256"],
                    "as_of": matrix["rows"][-1]["as_of"],
                    "coverage_start": matrix["rows"][0]["as_of"],
                    "row_count": len(matrix["rows"]),
                }
            else:
                value = self._factors(native, reference, index_id)
            if links.get("proxy_ref"):
                value["proxy_ref"] = links["proxy_ref"]
            result = (
                self.records.create(
                    "factor_inputs",
                    {
                        "index_id": index_id,
                        "profile_version": PROFILE_VERSION,
                        "bundle": value,
                        "bundle_sha256": digest(value),
                    },
                    "factor-" + digest(intent),
                )
                if value.get("format") == REFERENCE_FORMAT
                else self.research.market_scores.register_inputs(
                    value, idempotency_key="factor-" + digest(intent)
                )
            )
            # Record the durable input's native origin for future Host resolution.
            self.records.batch(
                [
                    {
                        "kind": "factor_profile",
                        "payload": {
                            **payload,
                            "factor_inputs_ref": {
                                "id": result["id"],
                                "revision": result["revision"],
                            },
                        },
                    }
                ],
                key,
                intent=intent,
                scope="native-input-registration",
            )
            return result
        if kind == "calendar":
            payload["calendar_exchange"] = self._calendar({"payload": payload}, native).exchange
        elif kind == "proxy":
            if self._proxy({"payload": payload}, native).index_id != index_id:
                reject("event_native_proxy_index_mismatch")
        elif kind == "prices":
            rows, _ = self._prices({"payload": payload}, native)
            if (
                len({row.get("asset") for row in rows}) != 1
                or len({row.get("role") for row in rows}) != 1
            ):
                reject("event_native_single_price_identity_required")
            payload.update(price_role=rows[0]["role"], symbol=rows[0]["asset"])
        result = self.records.batch(
            [{"kind": kind, "payload": payload}],
            key,
            intent=intent,
            scope="native-input-registration",
        )[0]
        log.info("event_native_input_registered", kind=kind, index_id=index_id)
        return result

    @native_boundary
    def choices(self):
        """Return bounded reference-only summaries without loading histories."""
        result = {}
        for field, kind in (
            ("inputs", "factor_inputs"),
            ("proxies", "proxy"),
            ("calendars", "calendar"),
            ("prices", "prices"),
            ("validations", "study_run"),
        ):
            with self.records.connection() as connection:
                if connection is None:
                    result[field] = []
                    continue
                rows = connection.execute(
                    "SELECT r.id,r.revision,json_extract(r.payload,'$.index_id') idx,json_extract(r.payload,'$.validation.index_id') validation_index,json_extract(r.payload,'$.title') title,json_extract(r.payload,'$.validation.role') role,json_extract(r.payload,'$.validation.status') status,json_extract(r.payload,'$.bundle.as_of') stamp,json_extract(r.payload,'$.bundle.series[#-1].as_of') last_stamp,json_extract(r.payload,'$.bundle.proxy_ref') proxy_ref,json_extract(r.payload,'$.price_role') price_role,json_extract(r.payload,'$.calendar_exchange') calendar_exchange FROM records r JOIN(SELECT id,MAX(revision) revision FROM records WHERE kind=? GROUP BY id) latest ON r.id=latest.id AND r.revision=latest.revision WHERE r.kind=? ORDER BY r.created_at DESC,r.id LIMIT 100",
                    (kind, kind),
                ).fetchall()
            items = []
            for row in rows:
                value = dict(row)
                item = {
                    "id": value["id"],
                    "revision": value["revision"],
                    "index_id": value["idx"] or value["validation_index"],
                    "label": value["title"]
                    or f"{kind} · {value['idx'] or value['validation_index'] or value['id'][:8]}",
                }
                if kind == "factor_inputs":
                    item["latest_as_of"] = value["stamp"] or value["last_stamp"]
                    if value["proxy_ref"]:
                        item["proxy_ref"] = json.loads(value["proxy_ref"])
                for name in ("role", "status", "price_role", "calendar_exchange"):
                    if value[name] is not None:
                        item[name] = value[name]
                items.append(item)
            result[field] = items
        return {
            **result,
            "qualification": self.records.qualification_status(),
            "production_enabled": False,
        }

    @native_boundary
    def link_bundle(self, bundle_ref, links, key):
        """CAS a new source-bundle revision from explicit existing native refs."""
        source, _native, _ = self._record("prices", bundle_ref)
        self._main_index(source, _native)
        payload, index_id = deepcopy(source["payload"]), source["payload"]["index_id"]
        kinds = {
            "calendar_ref": "calendar",
            "index_calendar_ref": "calendar",
            "proxy_calendar_ref": "calendar",
            "proxy_ref": "proxy",
            "proxy_prices_ref": "prices",
            "factor_inputs_ref": "factor_inputs",
        }
        if not isinstance(links, dict) or not links or set(links) - set(kinds):
            reject("event_native_link_kind_invalid")
        selected = {
            name: self.records.get(
                kinds[name], self._reference(ref)["id"], revision=ref["revision"]
            )
            for name, ref in links.items()
        }
        if any(record["payload"].get("index_id") != index_id for record in selected.values()):
            reject("event_native_link_index_mismatch")
        payload.update(links)
        proxy = None
        if payload.get("proxy_ref"):
            record, current, _ = self._record("proxy", payload["proxy_ref"])
            proxy = self._proxy(record, current)
        for name in ("calendar_ref", "index_calendar_ref", "proxy_calendar_ref"):
            if payload.get(name):
                record, current, evidence = self._record("calendar", payload[name])
                try:
                    calendar = self._calendar(record, current)
                except StoreError:
                    value = json.loads(evidence["bytes"])
                    value.pop("holidays", None)
                    calendar = Calendar.model_validate(value)
                expected = (
                    proxy.exchange
                    if name == "proxy_calendar_ref" and proxy
                    else INDICES[index_id]["exchange"]
                )
                if calendar.exchange != expected:
                    reject("event_native_link_calendar_exchange_mismatch")
        if payload.get("proxy_prices_ref"):
            record, current, _ = self._record("prices", payload["proxy_prices_ref"])
            prices, _ = self._prices(record, current)
            if proxy is None or any(
                row.get("role") != "proxy" or row.get("asset") != proxy.symbol for row in prices
            ):
                reject("event_native_link_proxy_price_identity_mismatch")
        if payload.get("factor_inputs_ref"):
            factor = self.records.get(
                "factor_inputs",
                payload["factor_inputs_ref"]["id"],
                revision=payload["factor_inputs_ref"]["revision"],
            )["payload"]
            if factor.get("index_id") != index_id or digest(factor.get("bundle")) != factor.get(
                "bundle_sha256"
            ):
                reject("event_native_link_factor_identity_mismatch")
            if (
                payload.get("proxy_ref")
                and factor["bundle"].get("proxy_ref") != payload["proxy_ref"]
            ):
                reject("event_native_link_factor_proxy_mismatch")
        return self.records.batch(
            [
                {
                    "kind": "prices",
                    "id": source["id"],
                    "expected_revision": source["revision"],
                    "payload": payload,
                }
            ],
            key,
            intent={"bundle_ref": bundle_ref, "links": links},
            scope="native-bundle-link",
        )[0]

    @native_boundary
    def source_verifier(self, *, index_id, axis, observation, as_of, original):
        """Re-derive the exact factor from source bytes and current permission."""
        self._qualified()
        metadata = original["manifest"].get("metadata", {})
        if metadata.get("native_kind") != "factor_inputs":
            reject("event_native_factor_origin_missing")
        native = load_native(
            self.research,
            metadata.get("source_snapshot"),
            expected_manifest_sha256=metadata.get("source_manifest_sha256"),
        )
        if (
            native.raw != original["bytes"]
            or native.manifest["provider"] != original["manifest"]["source"]
        ):
            reject("event_native_factor_original_changed")
        bundle = self._factors(native, observation.get("source_ref"), index_id)
        matching = [
            row for row in bundle.get("series", [bundle]) if stamp(row["as_of"]) == stamp(as_of)
        ]
        if len(matching) != 1 or digest(matching[0]["axes"].get(axis)) != digest(observation):
            reject("event_native_factor_derivation_changed")
        if stamp(observation["known_at"]) > stamp(as_of):
            reject("event_native_factor_not_known_by_cutoff")
        return {
            "status": "qualified",
            "source_ref": observation["source_ref"],
            "observation_sha256": digest(observation),
            "authorization_revision": native.configuration,
            "pit_receipt": (
                "canonical-warehouse:" + native.formal_digest
                if native.formal_digest
                else "first-observed:" + native.manifest["manifest_sha256"]
            ),
            "scope_id": observation.get("scope_id"),
            "availability_basis": (
                "canonical_warehouse"
                if native.formal_digest
                else "actual_private_snapshot_first_observed"
            ),
        }

    def _matrix(self, inputs, index_id):
        self._qualified()
        if (
            inputs.get("format") != REFERENCE_FORMAT
            or inputs.get("index_id") != index_id
            or inputs.get("profile_sha256") != digest(profile_for(index_id))
        ):
            reject("event_factor_matrix_reference_invalid")
        archived = self.events.read_evidence(inputs.get("matrix_evidence_ref"))
        native = load_native(
            self.research,
            inputs.get("source_snapshot"),
            expected_manifest_sha256=inputs.get("source_manifest_sha256"),
        )
        if (
            archived["bytes"] != native.raw
            or archived["manifest"]["source"] != native.manifest["provider"]
            or native.manifest.get("provider_metadata", {}).get("event_input_schema")
            != SCHEMAS["factor_inputs"]
            or archived["manifest"].get("metadata", {}).get("native_kind") != "factor_inputs"
        ):
            reject("event_factor_matrix_original_changed")
        validate_matrix(native, index_id)
        return native

    @native_boundary
    def resolve_market_factor_point(self, *, index_id, as_of, inputs):
        native = self._matrix(inputs, index_id)
        axes, receipts = point(native, inputs["matrix_evidence_ref"], index_id, as_of)
        if (
            self.research.datahub.source_configuration_digest(native.manifest["provider"])
            != native.configuration
        ):
            reject("event_native_source_authorization_changed")
        return FactorPoint(
            index_id=index_id,
            as_of=as_of,
            inputs_sha256=digest(inputs),
            axes=axes,
            source_receipts=receipts,
        )

    @native_boundary
    def factor_signals(self, factor_ref):
        payload = self.records.get(
            "factor_inputs", self._reference(factor_ref)["id"], revision=factor_ref["revision"]
        )["payload"]
        inputs = payload["bundle"]
        if digest(inputs) != payload.get("bundle_sha256"):
            reject("event_native_factor_bundle_changed")
        native = self._matrix(inputs, inputs["index_id"])
        result = list(stream_signals(native, inputs["matrix_evidence_ref"], inputs["index_id"]))
        if (
            self.research.datahub.source_configuration_digest(native.manifest["provider"])
            != native.configuration
        ):
            reject("event_native_source_authorization_changed")
        return {
            "items": result,
            "evidence_sha256": payload["bundle_sha256"],
            "formal_qualification": native.formal_digest,
            "input_bytes": len(native.raw),
        }

    @native_boundary
    def resolve_market_scoring_context(self, *, index_id, as_of, inputs):
        self._qualified()
        ref = inputs.get("proxy_ref")
        record, native, _ = self._record("proxy", ref)
        proxy = self._proxy(record, native)
        if proxy.index_id != index_id or proxy.known_at > stamp(as_of):
            reject("event_native_proxy_not_known_by_cutoff")
        local_day = stamp(as_of).astimezone(ZoneInfo(profile_for(index_id)["timezone"])).date()
        if not any(
            rule.from_date <= local_day <= rule.until_date and rule.known_at <= stamp(as_of)
            for rule in proxy.rules
        ):
            reject("event_native_proxy_rule_not_known_by_cutoff")
        return ScoreContext(
            index_id=index_id,
            as_of=as_of,
            proxy=proxy,
            source_contract_digest=SOURCE_CONTRACT_DIGEST,
            source_refs=(record["payload"]["evidence_ref"],),
            qualification_receipts=((native.formal_digest or native.manifest["manifest_sha256"]),),
        )

    def _prices(self, record, native):
        index_id = record["payload"].get("index_id")
        if (
            native.manifest.get("provider_metadata", {}).get("event_input_schema")
            != SCHEMAS["prices"]
        ):
            from .event_datahub_bridge import normalize_rows

            return normalize_rows(native.raw), False
        rows = []
        declarations = [
            native.manifest.get("query", {}).get("parameters", {}).get("adjustment"),
            native.manifest.get("provider_query", {}).get("adjustment"),
            native.manifest.get("provider_query", {}).get("parameters", {}).get("adjustment"),
            native.manifest.get("provider_metadata", {}).get("adjustment"),
            native.manifest.get("provider_metadata", {}).get("price_basis"),
            native.canonical_dataset.get("adjustment"),
        ]
        declared = {value for value in declarations if value is not None}
        unadjusted = bool(declared) and declared <= {"none", "unadjusted"}
        for source in native.rows:
            if (
                not isinstance(source, dict)
                or source.get("index_id") != index_id
                or source.get("role") not in {"index", "proxy"}
            ):
                reject("event_native_price_identity_or_unit_invalid")
            unit = (
                "index_points"
                if source["role"] == "index"
                else INDICES[index_id]["currency"] + "/share"
            )
            if source.get("unit") != unit or any(
                native.manifest.get("fields", {}).get(metric, {}).get("unit") != unit
                for metric in ("open", "close")
            ):
                reject("event_native_price_identity_or_unit_invalid")
            if source["role"] == "index":
                from .event_datahub_bridge import ALIASES

                if source.get("asset") not in ALIASES[index_id]:
                    reject("event_native_index_price_symbol_mismatch")
            row = {
                key: source[key]
                for key in (
                    "day",
                    "open",
                    "close",
                    "split",
                    "dividend",
                    "asset",
                    "role",
                    "suspended",
                    "trade_status",
                )
                if key in source
            }
            if not all(key in row for key in ("day", "open", "close")):
                reject("event_native_price_fields_missing")
            if number(row["open"]) <= 0 or number(row["close"]) <= 0:
                reject("event_native_price_values_invalid")
            if source["role"] == "proxy" and (
                not all(key in row for key in ("split", "dividend"))
                or number(row["split"]) <= 0
                or number(row["dividend"]) < 0
            ):
                reject("event_native_proxy_action_facts_missing")
            if source["role"] == "proxy":
                if not unadjusted:
                    reject("event_native_proxy_price_basis_unverified_or_adjusted")
                if "suspended" in source and type(source["suspended"]) is not bool:
                    reject("event_native_proxy_trade_status_unknown")
                if "trade_status" in source and source["trade_status"] not in {
                    "trading",
                    "suspended",
                }:
                    reject("event_native_proxy_trade_status_unknown")
                if "suspended" not in source and "trade_status" not in source:
                    reject("event_native_proxy_trade_status_unknown")
                suspended = source.get("suspended", source.get("trade_status") == "suspended")
                if "trade_status" in source and suspended != (
                    source["trade_status"] == "suspended"
                ):
                    reject("event_native_proxy_trade_status_conflict")
                row["suspended"] = suspended
                status_metric = "suspended" if "suspended" in source else "trade_status"
                row["trade_status_known_at"] = native.floor(row["day"], status_metric).isoformat()
            row["source_ref"] = digest(record["payload"]["evidence_ref"])
            row["price_basis"] = "unadjusted" if unadjusted else "adjusted_or_unknown"
            row["historical_eligible"] = native.formal_digest is not None and unadjusted
            row["execution_known_at"] = native.floor(row["day"], "open").isoformat()
            row["close_known_at"] = native.floor(row["day"], "close").isoformat()
            if source["role"] == "proxy":
                row["actions_known_at"] = max(
                    native.floor(row["day"], "split"), native.floor(row["day"], "dividend")
                ).isoformat()
            if source["role"] == "proxy" and stamp(row["trade_status_known_at"]) > stamp(
                row["execution_known_at"]
            ):
                reject("event_native_proxy_trade_status_late_known")
            rows.append(row)
        if not rows or [row["day"] for row in rows] != sorted({row["day"] for row in rows}):
            reject("event_native_price_dates_invalid")
        return rows, native.formal_digest is not None and unadjusted

    def _main_index(self, record, native):
        rows, qualified = self._prices(record, native)
        if (
            native.manifest.get("provider_metadata", {}).get("event_input_schema")
            == SCHEMAS["prices"]
        ):
            if any(row.get("role") != "index" for row in rows):
                reject("event_native_main_bundle_must_be_index")
        else:
            from .event_datahub_bridge import snapshot_identity

            if snapshot_identity(native.manifest) != record["payload"]["index_id"]:
                reject("event_native_main_index_identity_missing")
        return rows, qualified

    def _calendar_link(self, payload, name, gaps):
        ref = payload.get(name)
        if not ref:
            gaps.append(name + "_missing")
            return None, None, None
        record, native, evidence = self._record("calendar", ref)
        try:
            calendar = self._calendar(record, native)
        except StoreError:
            if record["payload"].get("source_kind") != "provider_calendar_projection":
                raise
            gaps.append(
                "unqualified_calendar_projection"
                if record["payload"].get("source_kind") == "provider_calendar_projection"
                else "calendar_native_session_times_unverified"
            )
            value = json.loads(evidence["bytes"])
            value.pop("holidays", None)
            calendar = Calendar.model_validate(value)
        return calendar, native, record

    @native_boundary
    def resolve_event_study_bundle(self, ref, *, spec=None):
        source, index_native, _ = self._record("prices", ref)
        payload = source["payload"]
        index_id = payload["index_id"]
        index_rows, index_qualified = self._main_index(source, index_native)
        gaps = []
        try:
            self._qualified()
        except StoreError:
            gaps.append("qualification_reconciliation_required")
        if not index_qualified:
            gaps.append("independent_index_pit_evidence_missing")
        calendar_payload = {
            **payload,
            "index_calendar_ref": payload.get("index_calendar_ref") or payload.get("calendar_ref"),
        }
        index_calendar, index_calendar_native, _ = self._calendar_link(
            calendar_payload, "index_calendar_ref", gaps
        )
        proxy, proxy_rows, proxy_calendar, proxy_native = None, [], None, None
        if payload.get("proxy_ref"):
            record, proxy_native, _ = self._record("proxy", payload["proxy_ref"])
            proxy = self._proxy(record, proxy_native)
        else:
            gaps.append("tradable_proxy_missing")
        if payload.get("proxy_prices_ref"):
            record, price_native, _ = self._record("prices", payload["proxy_prices_ref"])
            if (
                record["id"] == source["id"]
                or record["payload"]["evidence_ref"]["sha256"] == payload["evidence_ref"]["sha256"]
            ):
                reject("event_native_index_and_proxy_must_be_independent")
            proxy_rows, eligible = self._prices(record, price_native)
            if not eligible:
                gaps.append("tradable_proxy_prices_not_pit_qualified")
            if proxy is None or any(
                row.get("asset") != proxy.symbol or row.get("role") != "proxy" for row in proxy_rows
            ):
                gaps.append("tradable_proxy_price_identity_mismatch")
        else:
            gaps.append("tradable_proxy_prices_missing")
        proxy_calendar, proxy_calendar_native, proxy_calendar_record = self._calendar_link(
            payload, "proxy_calendar_ref", gaps
        )
        holidays = []
        if proxy_calendar_record is not None:
            archived = json.loads(
                self.events.read_evidence(proxy_calendar_record["payload"]["evidence_ref"])["bytes"]
            )
            holidays = archived.get("holidays", []) if isinstance(archived, dict) else []
            if (
                proxy_calendar_native
                and proxy_calendar_native.manifest.get("provider_metadata", {}).get(
                    "event_input_schema"
                )
                == SCHEMAS["calendar"]
            ):
                holidays = self._native_holidays(proxy_calendar_record, proxy_calendar_native)
        if not holidays and payload.get("calendar_ref"):
            archived = json.loads(
                self.events.read_evidence(
                    self.records.get(
                        "calendar",
                        payload["calendar_ref"]["id"],
                        revision=payload["calendar_ref"]["revision"],
                    )["payload"]["evidence_ref"]
                )["bytes"]
            )
            holidays = archived.get("holidays", []) if isinstance(archived, dict) else []
        signals, receipts, factor_digest = {}, {}, ""
        if payload.get("factor_inputs_ref"):
            factor = self.records.get(
                "factor_inputs",
                payload["factor_inputs_ref"]["id"],
                revision=payload["factor_inputs_ref"]["revision"],
            )["payload"]
            bundle = factor.get("bundle", {})
            if digest(bundle) != factor.get("bundle_sha256"):
                reject("event_native_factor_bundle_changed")
            signal_source = {
                "kind": "factor_inputs",
                **self._reference(payload["factor_inputs_ref"]),
                "sha256": factor["bundle_sha256"],
                "archive_ref": deepcopy(
                    factor.get("evidence_ref") or bundle.get("matrix_evidence_ref")
                ),
            }
            if bundle.get("format") == REFERENCE_FORMAT:
                compiled = self.factor_signals(payload["factor_inputs_ref"])
                compiled_signals = compiled["items"]
                if not compiled["formal_qualification"]:
                    gaps.append("factor_history_not_pit_qualified")
            else:
                refreshed = deepcopy(bundle)
                for row in refreshed.get("series", [refreshed]):
                    row["source_receipts"] = self.research.market_scores._source_receipts(
                        index_id, row["as_of"], row["axes"]
                    )
                compiled_signals = study_signals(index_id, refreshed)
            first_ready = next(
                (signal["as_of"] for signal in compiled_signals if signal["score"] is not None),
                None,
            )
            for signal in compiled_signals:
                if signal["score"] is None:
                    if first_ready is None or stamp(signal["as_of"]) >= stamp(first_ready):
                        gaps.append("factor_history_not_qualified")
                else:
                    day = (
                        stamp(signal["as_of"])
                        .astimezone(ZoneInfo(profile_for(index_id)["timezone"]))
                        .date()
                        .isoformat()
                    )
                    signals[day] = signal["score"] / 100
                    receipts[day] = {
                        "known_at": signal["as_of"],
                        "evidence_sha256": factor["bundle_sha256"],
                        "source_ref": deepcopy(signal_source),
                    }
            factor_digest = factor["bundle_sha256"]
        else:
            gaps.append("factor_history_missing")
        if proxy_rows and signals:
            first_ready_day = min(signals)
            proxy_rows = [row for row in proxy_rows if row["day"] >= first_ready_day]
            if proxy_calendar is not None:
                proxy_calendar = proxy_calendar.model_copy(
                    update={
                        "sessions": [
                            session
                            for session in proxy_calendar.sessions
                            if session.day.isoformat() >= first_ready_day
                        ]
                    }
                )
        if proxy_rows and set(signals) != {row["day"] for row in proxy_rows}:
            gaps.append("factor_history_calendar_coverage_incomplete")
        if any(
            value is None or value.formal_digest is None
            for value in (proxy_native, proxy_calendar_native, index_calendar_native)
        ):
            gaps.append("canonical_warehouse_historical_input_missing")
        rows = proxy_rows or index_rows
        return StudyBundle(
            index_id=index_id,
            rows=rows,
            data_digest=digest(rows),
            calendar=proxy_calendar,
            proxy=proxy,
            signals=signals,
            base_signals=signals,
            evidence_sha256=factor_digest,
            qualification_receipts=tuple(
                value.formal_digest
                for value in (proxy_native, proxy_calendar_native)
                if value and value.formal_digest
            ),
            index_rows=index_rows,
            index_calendar=index_calendar,
            index_data_digest=digest(index_rows),
            index_qualification_receipts=(
                (index_native.formal_digest,)
                if index_qualified and "qualification_reconciliation_required" not in gaps
                else ()
            ),
            signal_receipts=receipts,
            holidays=holidays,
            data_gaps=tuple(sorted(set(gaps))),
            calendar_basis=(
                "verified_native_sessions"
                if proxy_calendar_native and proxy_calendar_native.formal_digest
                else "native_or_descriptive_sessions_unqualified"
            ),
        )

    @native_boundary
    def resolve_market_overlay_context(self, *, study_id, spec, report, index_id, as_of):
        self._qualified()
        # Choose the latest explicitly registered native calendar for this
        # index; do not reuse the historical validation's calendar as current.
        candidates, cursor = [], None
        for _ in range(10):
            page = self.records.list("calendar", limit=200, cursor=cursor)
            candidates.extend(
                row
                for row in page["items"]
                if row["payload"].get("index_id") == index_id
                and row["payload"].get("source_contract") == SCHEMAS["calendar"]
            )
            cursor = page.get("next_cursor")
            if not cursor:
                break
        candidates = [
            row
            for row in candidates
            if row["payload"].get("calendar_exchange") == INDICES[index_id]["exchange"]
        ]
        if cursor or not candidates:
            reject("event_native_current_calendar_unavailable")
        record, native, _ = self._record(
            "calendar", {"id": candidates[-1]["id"], "revision": candidates[-1]["revision"]}
        )
        calendar = self._calendar(record, native)
        cutoff = stamp(as_of)
        category = spec.get("family") if spec.get("role") == "event_overlay" else "calendar"
        selected = self.events.timeline(
            start=(cutoff - timedelta(days=45)).date().isoformat(),
            end=(cutoff + timedelta(days=45)).date().isoformat(),
            market=INDICES[index_id]["market"],
            category=category,
            admission_state="confirmed",
            limit=200,
        )
        if selected.get("next_cursor"):
            reject("event_native_overlay_event_budget_exceeded")
        events, references = [], [record["payload"]["evidence_ref"]]
        for item in selected["items"]:
            value = item["payload"]
            projected = registered_event_projection(self.events, item, index_id)
            if projected is None:
                continue
            for reference in value.get("evidence_refs", []):
                self.events.read_evidence(reference)
                references.append(reference)
            events.append(projected)
        if len(references) > 200:
            reject("event_native_overlay_source_budget_exceeded")
        holidays = []
        if spec.get("role") == "calendar_overlay" and spec.get("family") == "holiday":
            if (
                native.manifest.get("provider_metadata", {}).get("event_input_schema")
                == SCHEMAS["calendar"]
            ):
                holidays = self._native_holidays(
                    record,
                    native,
                    start=(cutoff - timedelta(days=45)).date().isoformat(),
                    end=(cutoff + timedelta(days=45)).date().isoformat(),
                    cutoff=cutoff,
                )
            holidays.extend(events)
            holidays = list({(row["start"], row["end"]): row for row in holidays}.values())
            if not holidays:
                reject("event_native_holiday_evidence_unavailable")
            if len(holidays) > 200:
                reject("event_native_overlay_event_budget_exceeded")
        return OverlayContext(
            index_id=index_id,
            as_of=as_of,
            calendar=calendar,
            events=tuple(events) if spec.get("role") == "event_overlay" else (),
            holidays=tuple(holidays),
            source_refs=tuple(references),
            source_version=native.manifest["manifest_sha256"],
            qualification_receipts=(native.formal_digest or native.manifest["manifest_sha256"],),
        )
