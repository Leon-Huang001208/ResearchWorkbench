"""HTTP-facing service boundaries using isolated synthetic records and sources."""

import unittest
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app.research_web.event_studies.contracts import SOURCE_CONTRACT_DIGEST
from app.research_web.event_studies.service import implementation_digest
from app.research_web.market_scoring import ScoreService
from app.research_web.market_scoring.contracts import ScoreContext
from app.research_web.market_scoring.engine import digest, stamp
from app.research_web.market_scoring.profiles import PROFILE_VERSION
from app.research_web.store import StoreError
from tests.research_web.test_market_scoring import (
    CUTOFF,
    axes_for,
    evidence_receipts,
    overlay_context,
    proxy_for,
)
from tests.research_web.test_market_scoring import validation as engine_validation


def validation(*args, **kwargs):
    """Service fixtures represent a report from the currently frozen compiler."""
    return {**engine_validation(*args, **kwargs), "implementation_digest": implementation_digest()}


class FakeRecords:
    def __init__(self):
        self.records, self.keys = {}, {}
        self.counter = 0

    def cached(self, scope, key, intent):
        old = self.keys.get((scope, key))
        if old is None:
            return None
        if old[0] != digest(intent):
            raise StoreError("冲突", "event_idempotency_conflict", 409)
        return deepcopy(old[1])

    def revision_recorded_at(self, kind, identifier, revision):
        record = self.get(kind, identifier)
        if record["revision"] != revision:
            raise StoreError("版本变化", "event_revision_conflict", 409)
        return "2026-08-01T00:00:00+00:00"

    def batch(self, operations, key, *, intent=None, scope=None):
        scope = scope or operations[0]["kind"]
        intent = operations if intent is None else intent
        cached = self.cached(scope, key, intent)
        if cached:
            return cached
        results = []
        for operation in operations:
            self.counter += 1
            record = {
                "id": f"{self.counter:032x}",
                "revision": 1,
                "payload": deepcopy(operation["payload"]),
            }
            self.records[(operation["kind"], record["id"])] = record
            results.append(record)
        self.keys[(scope, key)] = (digest(intent), deepcopy(results))
        return results

    def create(self, kind, payload, idempotency_key):
        return self.batch([{"kind": kind, "payload": payload}], idempotency_key)[0]

    def get(self, kind, identifier):
        if (kind, identifier) not in self.records:
            raise StoreError("不存在", "event_record_not_found", 404)
        return deepcopy(self.records[(kind, identifier)])

    def list(self, kind, *, limit=50, cursor=None):
        return {
            "items": [
                deepcopy(item)
                for (stored_kind, _), item in self.records.items()
                if stored_kind == kind
            ][:limit],
            "next_cursor": None,
        }


class FakeEvents:
    def __init__(self):
        self.records = FakeRecords()
        self.broken = False

    def read_evidence(self, reference):
        if self.broken or reference != {"id": "a" * 32, "sha256": "b" * 64}:
            raise StoreError("原件变化", "event_evidence_changed", 409)
        return {"bytes": b"synthetic-source", "manifest": {"source": "eastmoney"}}


class ScoreServiceTests(unittest.TestCase):
    def setUp(self):
        self.allowed = True
        self.host = SimpleNamespace(event_timeline=FakeEvents())
        self.host._market_scoring_source_verifier = self.verify_source
        self.host.resolve_market_scoring_context = self.context
        self.service = ScoreService(self.host)
        self.bundle = {
            "index_id": "SSE",
            "profile_version": PROFILE_VERSION,
            "as_of": CUTOFF,
            "axes": axes_for(),
        }

    def verify_source(self, *, axis, observation, **kwargs):
        return evidence_receipts({axis: observation})[axis] if self.allowed else None

    def context(self, *, index_id, as_of, inputs):
        return ScoreContext(
            index_id=index_id,
            as_of=as_of,
            proxy=proxy_for(index_id),
            source_contract_digest=SOURCE_CONTRACT_DIGEST,
            source_refs=({"id": "a" * 32, "sha256": "b" * 64},),
            qualification_receipts=("synthetic-proxy-source-proof",),
        )

    def register(self):
        return self.service.register_inputs(
            self.bundle, idempotency_key="input-" + digest(self.bundle["as_of"])[:24]
        )

    def move_inputs_to(self, days):
        self.bundle = {
            "index_id": "SSE",
            "profile_version": PROFILE_VERSION,
            "as_of": (stamp(CUTOFF) + timedelta(days=days)).isoformat(),
            "axes": axes_for(),
        }
        for observation in self.bundle["axes"].values():
            for key in ("as_of", "published_at", "known_at", "valid_until"):
                observation[key] = (stamp(observation[key]) + timedelta(days=days)).isoformat()
            for row in observation["history"]:
                for key in ("as_of", "known_at"):
                    row[key] = (stamp(row[key]) + timedelta(days=days)).isoformat()

    def request(self, *, qualified=True):
        inputs = self.register()
        report = validation(
            evidence_sha256=inputs["payload"]["bundle_sha256"],
            expires_at="2099-01-01T00:00:00+00:00",
        )
        study = self.host.event_timeline.records.create(
            "study_run", {"validation": report, "report_digest": digest(report)}, "study-report-one"
        )
        return {
            "index_id": "SSE",
            "as_of": CUTOFF,
            "inputs_id": inputs["id"],
            "validation_id": study["id"] if qualified else None,
            "overlay_ids": [],
            "idempotency_key": "score-request-one",
        }

    def test_safe_preview_never_needs_existing_data(self):
        result = self.service.preview("SP500")
        self.assertIsNone(result["total_score"])
        self.assertFalse(result["production_enabled"])
        self.assertEqual(result["status"], "DATA_INELIGIBLE")
        self.assertEqual(self.service.list()["items"], [])

    def test_internal_inputs_registration_is_idempotent(self):
        first, second = self.register(), self.register()
        self.assertEqual(first, second)
        self.assertEqual(len(self.host.event_timeline.records.list("factor_inputs")["items"]), 1)

    def test_research_validation_does_not_activate_production(self):
        run = self.service.create(self.request())
        result = run["payload"]["result"]
        self.assertIsNotNone(result["research_score"])
        self.assertIsNone(result["total_score"])
        self.assertIsNone(result["effective_score"])
        self.assertFalse(result["formal_score_enabled"])
        self.assertFalse(result["production_enabled"])

    def test_current_implementation_certificate_is_accepted_by_service(self):
        request = self.request()
        report = self.service._validation(request["validation_id"])
        self.assertEqual(report["implementation_digest"], implementation_digest())
        self.assertIsNotNone(self.service.create(request)["payload"]["result"]["research_score"])

    def test_other_implementation_certificate_is_rejected_even_with_valid_report_hash(self):
        request = self.request()
        stored = self.host.event_timeline.records.records[("study_run", request["validation_id"])]
        stored["payload"]["validation"]["implementation_digest"] = "f" * 64
        stored["payload"]["report_digest"] = digest(stored["payload"]["validation"])
        with self.assertRaises(StoreError) as caught:
            self.service.create(request)
        self.assertEqual(caught.exception.code, "market_score_validation_implementation_changed")

    def test_missing_implementation_certificate_is_rejected(self):
        request = self.request()
        stored = self.host.event_timeline.records.records[("study_run", request["validation_id"])]
        stored["payload"]["validation"].pop("implementation_digest")
        stored["payload"]["report_digest"] = digest(stored["payload"]["validation"])
        with self.assertRaises(StoreError) as caught:
            self.service.create(request)
        self.assertEqual(caught.exception.code, "market_score_validation_implementation_changed")

    def test_changed_compiler_revokes_current_eligibility_of_saved_score(self):
        run = self.service.create(self.request())
        with patch(
            "app.research_web.event_studies.service.implementation_digest", return_value="f" * 64
        ):
            current = self.service.get(run["id"])["current_eligibility"]
        self.assertEqual(current["status"], "DATA_INELIGIBLE")
        self.assertIsNone(current.get("research_score"))
        self.assertIn("market_score_validation_implementation_changed", current["reasons"])

    def test_idempotent_replay_keeps_result_and_rechecks_revocation(self):
        request = self.request()
        first = self.service.create(request)
        self.allowed = False
        replay = self.service.create(request)
        self.assertEqual(first["id"], replay["id"])
        self.assertEqual(first["payload"], replay["payload"])
        self.assertEqual(replay["current_eligibility"]["status"], "DATA_INELIGIBLE")
        self.assertIsNone(replay["current_eligibility"]["candidate_score"])

    def test_new_intent_same_key_is_conflict(self):
        request = self.request()
        self.service.create(request)
        with self.assertRaises(StoreError) as error:
            self.service.create({**request, "index_id": "CSI300"})
        self.assertEqual(error.exception.status, 409)

    def test_browser_cannot_supply_scores_or_permission_flags(self):
        request = self.request()
        for key in ("axes", "total_score", "approved", "pit_verified", "owner", "validation"):
            with self.assertRaises(StoreError):
                self.service.create({**request, key: True})

    def test_client_embedded_receipts_are_overwritten(self):
        self.bundle["source_receipts"] = evidence_receipts(self.bundle["axes"])
        del self.host._market_scoring_source_verifier
        inputs = self.register()
        self.assertEqual(inputs["payload"]["bundle"]["source_receipts"], {})

    def test_frozen_input_changes_are_detected(self):
        request = self.request()
        stored = self.host.event_timeline.records.records[("factor_inputs", request["inputs_id"])]
        stored["payload"]["bundle"]["axes"]["funds"]["value"] += 1
        with self.assertRaises(StoreError) as error:
            self.service.create(request)
        self.assertEqual(error.exception.code, "market_score_bundle_changed")

    def test_raw_source_changes_revoke_current_result(self):
        run = self.service.create(self.request())
        self.host.event_timeline.broken = True
        current = self.service.get(run["id"])["current_eligibility"]
        self.assertIsNone(current["research_score"])
        self.assertEqual(current["status"], "DATA_INELIGIBLE")

    def test_validation_report_hash_cannot_be_replaced(self):
        request = self.request()
        stored = self.host.event_timeline.records.records[("study_run", request["validation_id"])]
        stored["payload"]["validation"]["evidence_sha256"] = "f" * 64
        with self.assertRaises(StoreError) as error:
            self.service.create(request)
        self.assertEqual(error.exception.code, "market_score_validation_changed")

    def test_old_cutoff_cannot_resurrect_expired_validation(self):
        request = self.request()
        stored = self.host.event_timeline.records.records[("study_run", request["validation_id"])]
        report = {**stored["payload"]["validation"], "expires_at": "2026-10-02T00:00:00+00:00"}
        stored["payload"] = {"validation": report, "report_digest": digest(report)}
        result = self.service.create(request)["payload"]["result"]
        self.assertIsNone(result["research_score"])
        self.assertIn("validation_expired_now", result["validation_reasons"])

    def test_other_account_cannot_read_inputs_or_runs(self):
        request = self.request()
        other = ScoreService(SimpleNamespace(event_timeline=FakeEvents()))
        with self.assertRaises(StoreError) as error:
            other.create(request)
        self.assertEqual(error.exception.status, 404)

    def test_yesterday_validation_accepts_today_and_tomorrow_independent_inputs(self):
        first_request = self.request()
        first = self.service.create(first_request)["payload"]["result"]
        self.assertIsNotNone(first["research_score"])
        prior_digest = first["evidence_sha256"]
        for days in (1, 2):
            self.move_inputs_to(days)
            inputs = self.register()
            request = {
                **first_request,
                "inputs_id": inputs["id"],
                "as_of": self.bundle["as_of"],
                "idempotency_key": f"next-day-score-{days}",
            }
            current = self.service.create(request)["payload"]["result"]
            self.assertIsNotNone(current["research_score"])
            self.assertNotEqual(current["evidence_sha256"], prior_digest)

    def test_proxy_change_does_not_reuse_old_validation(self):
        request = self.request()
        old = self.host.resolve_market_scoring_context
        self.host.resolve_market_scoring_context = lambda **kwargs: replace(
            old(**kwargs), proxy=proxy_for().model_copy(update={"symbol": "SYNTHETIC-OTHER"})
        )
        result = self.service.create(request)["payload"]["result"]
        self.assertIsNone(result["research_score"])
        self.assertIn("current_proxy_identity_mismatch", result["validation_reasons"])

    def test_calendar_overlay_rechecks_active_window(self):
        request = self.request()
        for family, rule, expected in (
            ("month_end", "month_end_1", 0),
            ("month_start", "month_start_5", 1),
        ):
            report = validation(
                role="calendar_overlay",
                family=family,
                direction=1,
                rule=rule,
                expires_at="2099-01-01T00:00:00+00:00",
            )
            study = self.host.event_timeline.records.create(
                "study", {"spec": deepcopy(report)}, "overlay-study-" + family
            )
            report["study_id"] = study["id"]
            run = self.host.event_timeline.records.create(
                "study_run",
                {"validation": report, "report_digest": digest(report)},
                "overlay-run-" + family,
            )
            self.host.resolve_market_overlay_context = lambda **kwargs: overlay_context(
                kwargs["report"], kwargs["as_of"]
            )
            result = self.service.create(
                {
                    **request,
                    "overlay_ids": [run["id"]],
                    "idempotency_key": "calendar-score-" + family,
                }
            )["payload"]["result"]
            self.assertEqual(result["overlay_delta"], expected)

    def test_current_event_version_and_known_window_bound_activity(self):
        request = self.request()
        event = self.host.event_timeline.records.create(
            "event",
            {
                "category": "macro",
                "markets": ["CN"],
                "occurrence_start": "2026-10-08",
                "occurrence_end": "2026-10-09",
                "source_published_at": "2026-08-01T00:00:00+00:00",
                "admission": "confirmed",
                "lifecycle": "announced",
                "date_precision": "day",
            },
            "future-event-one",
        )
        report = validation(
            role="event_overlay",
            family="macro",
            direction=1,
            expires_at="2099-01-01T00:00:00+00:00",
        )
        study = self.host.event_timeline.records.create(
            "study", {"spec": deepcopy(report)}, "event-overlay-study"
        )
        report["study_id"] = study["id"]
        run = self.host.event_timeline.records.create(
            "study_run",
            {"validation": report, "report_digest": digest(report)},
            "event-overlay-run",
        )

        def resolve(**kwargs):
            context = overlay_context(kwargs["report"], kwargs["as_of"])
            return replace(context, events=({**context.events[0], "id": event["id"]},))

        self.host.resolve_market_overlay_context = resolve
        active = self.service.create(
            {**request, "overlay_ids": [run["id"]], "idempotency_key": "event-active-score"}
        )["payload"]["result"]
        self.assertEqual(active["overlay_delta"], 1)
        self.move_inputs_to(6)
        inputs = self.register()
        ended = self.service.create(
            {
                **request,
                "inputs_id": inputs["id"],
                "as_of": self.bundle["as_of"],
                "overlay_ids": [run["id"]],
                "idempotency_key": "event-ended-score",
            }
        )["payload"]["result"]
        self.assertEqual(ended["overlay_delta"], 0)
        self.host.event_timeline.records.records[("event", event["id"])]["revision"] += 1
        changed = self.service.create(
            {**request, "overlay_ids": [run["id"]], "idempotency_key": "event-revised-score"}
        )["payload"]["result"]
        self.assertEqual(changed["overlay_delta"], 0)


if __name__ == "__main__":
    unittest.main()
