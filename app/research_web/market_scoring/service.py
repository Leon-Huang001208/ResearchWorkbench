"""Account-scoped score runs resolve immutable Host evidence, never browser scores."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import UTC, datetime

from core.observability import get_logger

from ..store import StoreError
from .applicability import applicability_for
from .contracts import FactorPoint, OverlayContext, ScoreContext, context_identity
from .engine import compute_score, digest, stamp
from .native_inputs import registered_event_projection
from .profiles import AXES, INDICES, PROFILE_VERSION, profile_for, profiles

log = get_logger(__name__)


def _error(code, status=422):
    log.warning("market_scoring_rejected", code=code)
    raise StoreError("评分证据缺失、失效或不符合冻结合同", code, status)


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        _error("market_score_reference_invalid")
    return value


class ScoreService:
    def __init__(self, research):
        self.research = research

    @property
    def records(self):
        return self.research.event_timeline.records

    def profiles(self):
        return {"version": PROFILE_VERSION, "items": profiles(), "production_enabled": False}

    def register_inputs(self, bundle, *, idempotency_key):
        """Trusted Host ingestion only: no HTTP endpoint exposes this operation.

        Source bytes referenced by the bundle must already be in the private
        archive. Registration preserves input; it never grants PIT permission.
        """
        if (
            not isinstance(bundle, dict)
            or bundle.get("index_id") not in INDICES
            or bundle.get("profile_version") != PROFILE_VERSION
        ):
            _error("market_score_bundle_invalid")
        bundle = deepcopy(bundle)
        bundle["profile_sha256"] = digest(profile_for(bundle["index_id"]))
        series = bundle.get("series", [bundle])
        if not isinstance(series, list) or not 1 <= len(series) <= 20000:
            _error("market_score_series_invalid")
        for row in series:
            if not isinstance(row, dict) or not isinstance(row.get("axes"), dict):
                _error("market_score_bundle_invalid")
            row["source_receipts"] = self._source_receipts(
                bundle["index_id"], row.get("as_of"), row["axes"]
            )
        try:
            encoded = json.dumps(
                bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        except (ValueError, TypeError) as exc:
            raise StoreError("评分输入不能安全序列化", "market_score_bundle_invalid", 422) from exc
        if len(encoded) > 8 * 1024 * 1024:
            _error("market_score_bundle_oversized")
        # The append-only record seals the aggregate. Each source's original
        # bytes remain in the immutable archive referenced by its observation.
        return self.records.create(
            "factor_inputs",
            {
                "index_id": bundle["index_id"],
                "profile_version": PROFILE_VERSION,
                "bundle": bundle,
                "bundle_sha256": digest(bundle),
            },
            idempotency_key,
        )

    def _bundle(self, identifier, index_id):
        record = self.records.get("factor_inputs", _identifier(identifier))
        payload = record["payload"]
        if payload.get("index_id") != index_id or payload.get("profile_version") != PROFILE_VERSION:
            _error("market_score_input_binding_invalid", 409)
        try:
            bundle = payload.get("bundle")
            if (
                not isinstance(bundle, dict)
                or digest(bundle) != payload.get("bundle_sha256")
                or bundle.get("index_id") != index_id
                or bundle.get("profile_version") != PROFILE_VERSION
                or bundle.get("profile_sha256") != digest(profile_for(index_id))
            ):
                _error("market_score_bundle_changed", 409)
        except (TypeError, ValueError) as exc:
            raise StoreError("评分原件不可读取", "market_score_bundle_invalid", 409) from exc
        return bundle, payload["bundle_sha256"]

    def _source_receipts(self, index_id, as_of, axes):
        """Re-run current authorization and exact value derivation on every read."""
        verifier = getattr(self.research, "_market_scoring_source_verifier", None)
        receipts = {}
        for axis in AXES:
            observation = axes.get(axis)
            if not isinstance(observation, dict) or not callable(verifier):
                continue
            try:
                original = self.research.event_timeline.read_evidence(observation.get("source_ref"))
                if original["manifest"].get("source") != observation.get("provider"):
                    continue
                receipt = verifier(
                    index_id=index_id,
                    axis=axis,
                    observation=deepcopy(observation),
                    as_of=as_of,
                    original=original,
                )
                if isinstance(receipt, dict):
                    receipts[axis] = receipt
            except (StoreError, OSError, ValueError, TypeError) as exc:
                log.warning(
                    "market_score_source_unavailable", axis=axis, error_type=type(exc).__name__
                )
        return receipts

    def _validation(self, identifier):
        if identifier is None:
            return None
        record = self.records.get("study_run", _identifier(identifier))
        payload = record["payload"]
        report = payload.get("validation")
        try:
            if not isinstance(report, dict) or digest(report) != payload.get("report_digest"):
                _error("market_score_validation_changed", 409)
        except (TypeError, ValueError) as exc:
            raise StoreError(
                "评分验证报告不可读取", "market_score_validation_invalid", 409
            ) from exc
        if report.get("status") == "VALIDATED":
            # Resolve lazily: the Host study producer also consumes this service.
            from ..event_studies.service import implementation_digest

            try:
                current_implementation = implementation_digest()
            except (OSError, ValueError) as exc:
                log.warning(
                    "market_score_implementation_unavailable", error_type=type(exc).__name__
                )
                raise StoreError(
                    "评分实现暂不可核验", "market_score_validation_implementation_unavailable", 409
                ) from exc
            if report.get("implementation_digest") != current_implementation:
                _error("market_score_validation_implementation_changed", 409)
        return report

    def _context(self, index_id, as_of, bundle):
        resolver = getattr(self.research, "resolve_market_scoring_context", None)
        if not callable(resolver):
            return None
        try:
            context = resolver(index_id=index_id, as_of=as_of, inputs=deepcopy(bundle))
            if not isinstance(context, ScoreContext):
                return None
            for reference in context.source_refs:
                self.research.event_timeline.read_evidence(reference)
            context_identity(context, index_id, as_of)
            return context
        except (StoreError, ValueError, OSError, TypeError) as exc:
            log.warning("market_score_context_unavailable", error_type=type(exc).__name__)
            return None

    def _overlay(self, report, index_id, as_of, score_context):
        resolver = getattr(self.research, "resolve_market_overlay_context", None)
        if (
            not callable(resolver)
            or score_context is None
            or not isinstance(report, dict)
            or report.get("status") != "VALIDATED"
        ):
            return None, None
        try:
            study = self.records.get("study", _identifier(report.get("study_id")))
            spec = study["payload"]["spec"]
            context = resolver(
                study_id=study["id"],
                spec=deepcopy(spec),
                report=deepcopy(report),
                index_id=index_id,
                as_of=as_of,
            )
            if not isinstance(context, OverlayContext):
                return None, None
            for reference in context.source_refs:
                self.research.event_timeline.read_evidence(reference)
            if report.get("role") == "event_overlay":
                for event in context.events:
                    current = self.records.get("event", _identifier(event.get("id")))
                    payload = current["payload"]
                    if (
                        current["revision"] != event.get("revision")
                        or payload.get("admission") != "confirmed"
                        or payload.get("lifecycle") in {"cancelled", "scenario"}
                        or payload.get("date_precision") not in {"day", "minute"}
                        or payload.get("category") != spec.get("family")
                        or profile_for(index_id)["market"] not in payload.get("markets", [])
                    ):
                        raise ValueError("overlay_current_event_version_invalid")
                    projected = registered_event_projection(
                        self.research.event_timeline, current, index_id
                    )
                    if projected is None or any(
                        event.get(key) != projected.get(key)
                        for key in ("id", "revision", "start", "end", "known_at")
                    ):
                        raise ValueError("overlay_current_event_facts_changed")
                    for reference in payload.get("evidence_refs", []):
                        self.research.event_timeline.read_evidence(reference)
            proof = applicability_for(context, report, spec, index_id, as_of)
            identity = context_identity(
                score_context,
                index_id,
                as_of,
                role=report.get("role"),
                family=report.get("family"),
                direction=report.get("direction"),
                rule=report.get("rule"),
            )
            return identity, proof
        except (StoreError, ValueError, OSError, TypeError, KeyError) as exc:
            log.warning("market_overlay_context_unavailable", error_type=type(exc).__name__)
            return None, None

    @staticmethod
    def _public_result(result):
        # Research evidence is not the separate production activation receipt.
        return {
            **result,
            "research_score": result["total_score"],
            "total_score": None,
            "effective_score": None,
            "formal_score_enabled": False,
            "production_enabled": False,
            "activation_status": "NOT_ACTIVATED",
        }

    def _compute(self, body):
        allowed = {
            "index_id",
            "as_of",
            "inputs_id",
            "validation_id",
            "overlay_ids",
            "idempotency_key",
        }
        if not isinstance(body, dict) or set(body) - allowed or body.get("index_id") not in INDICES:
            _error("market_score_request_invalid")
        index_id, as_of = body["index_id"], body.get("as_of")
        try:
            cutoff = stamp(as_of)
        except (TypeError, ValueError) as exc:
            raise StoreError("评分时间必须包含时区", "market_score_time_invalid", 422) from exc
        if cutoff > datetime.now(UTC):
            _error("market_score_future_cutoff")
        bundle, evidence_sha256 = self._bundle(body.get("inputs_id"), index_id)
        if bundle.get("format") == "factor-matrix-ref-v1":
            resolver = getattr(self.research, "resolve_market_factor_point", None)
            resolved = (
                resolver(index_id=index_id, as_of=as_of, inputs=deepcopy(bundle))
                if callable(resolver)
                else None
            )
            if (
                not isinstance(resolved, FactorPoint)
                or resolved.index_id != index_id
                or stamp(resolved.as_of) != cutoff
                or resolved.inputs_sha256 != evidence_sha256
            ):
                _error("market_score_matrix_resolver_required", 409)
            axes, source_receipts = resolved.axes, resolved.source_receipts
        else:
            series = bundle.get("series", [bundle])
            if not isinstance(series, list) or len(series) > 20000:
                _error("market_score_series_invalid")
            matches = [row for row in series if isinstance(row, dict) and row.get("as_of") == as_of]
            if len(matches) != 1 or not isinstance(matches[0].get("axes"), dict):
                _error("market_score_cutoff_not_frozen", 409)
            axes = matches[0]["axes"]
            source_receipts = self._source_receipts(index_id, as_of, axes)
        overlay_ids = body.get("overlay_ids", [])
        if not isinstance(overlay_ids, list) or len(overlay_ids) > 200:
            _error("market_score_overlays_invalid")
        report = self._validation(body.get("validation_id"))
        overlays = [self._validation(identifier) for identifier in overlay_ids]
        for overlay in overlays:
            try:
                expired = stamp(overlay.get("expires_at")) <= datetime.now(UTC)
            except (AttributeError, ValueError):
                expired = True
            if expired and isinstance(overlay, dict):
                overlay["status"] = "VALIDATION_EXPIRED"
        score_context = self._context(index_id, as_of, bundle)
        identity = (
            context_identity(score_context, index_id, as_of) if score_context is not None else None
        )
        overlay_identities, applicability = {}, {}
        for overlay in overlays:
            overlay_identity, proof = self._overlay(overlay, index_id, as_of, score_context)
            overlay_identities[digest(overlay)] = overlay_identity
            applicability[digest(overlay)] = proof
        try:
            result = compute_score(
                index_id,
                as_of,
                axes,
                source_receipts=source_receipts,
                validation=report,
                overlays=overlays,
                evidence_sha256=evidence_sha256,
                validation_identity=identity,
                overlay_identities=overlay_identities,
                applicability=applicability,
            )
        except (ValueError, TypeError) as exc:
            raise StoreError("评分输入不符合冻结规则", "market_score_input_invalid", 422) from exc
        # An expired report cannot be resurrected by requesting a past cutoff.
        now = datetime.now(UTC)
        if report is not None:
            try:
                expired = stamp(report.get("expires_at")) <= now
            except (TypeError, ValueError):
                expired = True
            if expired:
                result.update(
                    total_score=None,
                    base_score=None,
                    overlay_delta=0,
                    formal_score_enabled=False,
                    status="VALIDATION_REQUIRED",
                )
                result["validation_reasons"].append("validation_expired_now")
        return self._public_result(result)

    def run_initial_if_qualified(self, body):
        """Try a current registered input without admitting a provider or enabling production."""
        result = self._compute(body)
        if not any(
            axis.get("status") == "QUALIFIED" and axis.get("score") is not None
            for axis in result.get("axes", {}).values()
        ):
            return None
        return self.create(body)

    def create(self, body):
        if not isinstance(body, dict):
            _error("market_score_request_invalid")
        request = {key: value for key, value in body.items() if key != "idempotency_key"}
        cached = self.records.cached("market-score-create", body.get("idempotency_key"), request)
        if cached:
            return self.get(cached[0]["id"])
        result = self._compute(body)
        record = self.records.batch(
            [
                {
                    "kind": "score",
                    "payload": {
                        "request": request,
                        "result": result,
                        "computed_at": datetime.now(UTC).isoformat(),
                    },
                }
            ],
            body.get("idempotency_key"),
            intent=request,
            scope="market-score-create",
        )[0]
        log.info("market_score_run_saved", index_id=body["index_id"], status=result["status"])
        return {**record, "current_eligibility": result}

    def get(self, identifier):
        record = self.records.get("score", _identifier(identifier))
        try:
            current = self._compute(record["payload"]["request"])
        except StoreError as exc:
            current = {
                "status": "DATA_INELIGIBLE",
                "total_score": None,
                "effective_score": None,
                "formal_score_enabled": False,
                "production_enabled": False,
                "reasons": [exc.code],
            }
        return {**record, "current_eligibility": current}

    def list(self, *, limit=50, cursor=None):
        result = self.records.list("score", limit=limit, cursor=cursor)
        return {**result, "historical_only": True, "production_enabled": False}

    def preview(self, index_id="SSE", as_of=None):
        if index_id not in INDICES:
            _error("market_score_index_unknown")
        as_of = as_of or datetime.now(UTC).isoformat()
        try:
            result = compute_score(index_id, as_of, {})
        except (TypeError, ValueError) as exc:
            raise StoreError("评分时间必须包含时区", "market_score_time_invalid", 422) from exc
        return self._public_result(result)
