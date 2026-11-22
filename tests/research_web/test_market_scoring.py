"""Synthetic evidence tests do not certify any real market's predictive score."""

import unittest
from copy import deepcopy
from datetime import UTC, datetime, timedelta

from app.research_web.market_scoring.applicability import applicability_for
from app.research_web.market_scoring.contracts import OverlayContext, scoring_identity
from app.research_web.market_scoring.engine import (
    compute_score,
    digest,
    study_signals,
)
from app.research_web.market_scoring.profiles import (
    AXES,
    PROFILE_VERSION,
    VALIDATION_POLICY,
    profile_for,
)

CUTOFF = "2026-10-01T16:00:00+08:00"


def proxy_for(index_id="SSE"):
    from app.research_web.event_studies.contracts import Proxy
    from app.research_web.event_studies.registry import INDICES

    definition = INDICES[index_id]
    return Proxy.model_validate(
        {
            "symbol": f"SYNTHETIC-{index_id}",
            "index_id": index_id,
            "market": definition["market"],
            "currency": definition["currency"],
            "exchange": definition["exchange"],
            "source_ref": "synthetic-identity",
            "known_at": "1990-01-01T00:00:00+00:00",
            "listed_on": "1991-01-01",
            "exact_tracking": True,
            "price_basis": "unadjusted",
            "rules": [
                {
                    "from_date": "1990-01-01",
                    "until_date": "2099-12-31",
                    "lot": 1,
                    "settlement_sessions": 0,
                    "tax_buy_bps": 0,
                    "tax_sell_bps": 0,
                    "source_ref": "synthetic-rules",
                    "known_at": "1990-01-01T00:00:00+00:00",
                }
            ],
        }
    )


def identity_for(role="base_score", family=None, direction=None, rule=None):
    return scoring_identity(
        "SSE", proxy_for(), role=role, family=family, direction=direction, rule=rule
    )


def overlay_context(report, as_of=CUTOFF, *, event_known_at="2026-08-01T00:00:00+00:00"):
    from app.research_web.event_studies.contracts import Calendar

    start = datetime(2026, 9, 1, 9, 30, tzinfo=UTC)
    sessions = []
    for offset in range(91):
        moment = start + timedelta(days=offset)
        if moment.weekday() < 5:
            day = moment.date().isoformat()
            sessions.append(
                {
                    "day": day,
                    "opens": f"{day}T09:30:00+08:00",
                    "closes": f"{day}T15:00:00+08:00",
                    "known_at": "2026-08-01T00:00:00+00:00",
                    "announcement_version_ref": "synthetic-announcement-v1",
                }
            )
    calendar = Calendar.model_validate(
        {
            "exchange": "XSHG",
            "timezone": "Asia/Shanghai",
            "version": "synthetic-calendar-v1",
            "source_ref": "synthetic-calendar",
            "known_at": "2026-09-01T00:00:00+00:00",
            "sessions": sessions,
        }
    )
    return OverlayContext(
        index_id="SSE",
        as_of=as_of,
        calendar=calendar,
        events=(
            {
                "id": "f" * 32,
                "revision": 1,
                "start": "2026-10-08",
                "end": "2026-10-09",
                "known_at": event_known_at,
            },
        ),
        holidays=(),
        source_refs=({"id": "a" * 32, "sha256": "b" * 64},),
        source_version="synthetic-calendar-v1",
        qualification_receipts=("synthetic-announcement-proof",),
    )


def applicability_for_report(report, as_of=CUTOFF):
    return applicability_for(overlay_context(report, as_of), report, report, "SSE", as_of)


def axes_for(index_id="SSE"):
    profile = profile_for(index_id)
    result = {}
    for axis, definition in profile["axes"].items():
        result[axis] = {
            "metric": definition["metric"],
            "unit": definition["unit"],
            "provider": definition["providers"][0],
            "scope": definition["scope"],
            "scope_id": index_id if definition["scope"] == "index" else profile["market"],
            "value": (
                0.6
                if axis == "breadth"
                else 0.2 if definition["metric"] == "confirmed_limit_balance" else 50.0
            ),
            "as_of": "2026-10-01T15:00:00+08:00",
            "published_at": "2026-10-01T15:01:00+08:00",
            "known_at": "2026-10-01T15:02:00+08:00",
            "valid_until": "2026-10-02T16:00:00+08:00",
            "source_ref": {"id": "a" * 32, "sha256": "b" * 64},
            "history": [
                {
                    "as_of": (datetime(2026, 9, 30, tzinfo=UTC) - timedelta(days=i)).isoformat(),
                    "known_at": (
                        datetime(2026, 9, 30, 1, tzinfo=UTC) - timedelta(days=i)
                    ).isoformat(),
                    "value": float(i),
                    "unit": definition["unit"],
                }
                for i in range(300)
            ],
        }
    return result


def evidence_receipts(axes):
    return {
        axis: {
            "status": "qualified",
            "source_ref": item["source_ref"],
            "observation_sha256": digest(item),
            "authorization_revision": "synthetic-grant-v1",
            "pit_receipt": "synthetic-pit-v1",
            "scope_id": item["scope_id"],
        }
        for axis, item in axes.items()
    }


def validation(evidence_sha256="c" * 64, **changes):
    role = changes.get("role", "base_score")
    family = changes.get("family")
    direction = changes.get("direction")
    rule = changes.get(
        "rule",
        (
            "event_pre_5"
            if role == "event_overlay"
            else "month_end_1" if role == "calendar_overlay" else None
        ),
    )
    identity = identity_for(role, family, direction, rule)
    return {
        **identity,
        "status": "VALIDATED",
        "role": "base_score",
        "index_id": "SSE",
        "horizon": 20,
        "profile_version": PROFILE_VERSION,
        "evidence_sha256": evidence_sha256,
        "training_holdout_evidence_sha256": evidence_sha256,
        "family": family,
        "direction": direction,
        "rule": rule,
        "rules_digest": identity["signal_rule_sha256"],
        "valid_from": "2026-09-30T00:00:00+00:00",
        "expires_at": "2026-11-01T00:00:00+00:00",
        "policy_version": VALIDATION_POLICY,
        "study_id": "d" * 32,
        "holdout_id": "e" * 32,
        **changes,
    }


class MarketScoringTests(unittest.TestCase):
    def compute(self, axes=None, **kw):
        observations = axes_for() if axes is None else axes
        overlays = kw.get("overlays", [])
        kw.setdefault("validation_identity", identity_for())
        kw.setdefault(
            "overlay_identities",
            {
                digest(report): identity_for(
                    report["role"], report["family"], report["direction"], report["rule"]
                )
                for report in overlays
            },
        )
        kw.setdefault(
            "applicability",
            {digest(report): applicability_for_report(report) for report in overlays},
        )
        return compute_score(
            "SSE",
            CUTOFF,
            observations,
            evidence_sha256="c" * 64,
            source_receipts=evidence_receipts(observations),
            **kw,
        )

    def test_all_nine_profiles_have_six_fixed_axes(self):
        for index in (
            "SSE",
            "CSI300",
            "CHINEXT",
            "SP500",
            "NASDAQ",
            "DJI",
            "HSI",
            "HSCEI",
            "HSTECH",
        ):
            profile = profile_for(index)
            self.assertEqual(set(profile["axes"]), set(AXES))
            self.assertEqual(profile["horizon"], 20)
            self.assertEqual(profile["version"], PROFILE_VERSION)
        with self.assertRaises(ValueError):
            profile_for("UNKNOWN")

    def test_foreign_sentiment_does_not_use_china_limits(self):
        for index in ("SP500", "HSI"):
            profile = profile_for(index)
            self.assertEqual(profile["axes"]["sentiment"]["metric"], "put_call_volume_ratio")
            self.assertNotEqual(profile["axes"]["funds"]["metric"], "turnover")

    def test_synthetic_six_axis_candidate_requires_separate_validation(self):
        result = self.compute()
        self.assertIsNotNone(result["candidate_score"])
        self.assertIsNone(result["total_score"])
        self.assertFalse(result["formal_score_enabled"])
        self.assertEqual(result["status"], "VALIDATION_REQUIRED")

    def test_validated_score_is_equal_weight(self):
        result = self.compute(validation=validation())
        expected = sum(axis["score"] for axis in result["axes"].values()) / 6
        self.assertAlmostEqual(result["base_score"], expected)
        self.assertEqual(result["total_score"], expected)
        self.assertTrue(result["formal_score_enabled"])
        self.assertIsNone(result["allocation"])

    def test_missing_axis_never_reweights_or_fills(self):
        axes = axes_for()
        del axes["funds"]
        result = self.compute(axes, validation=validation())
        self.assertIsNone(result["candidate_score"])
        self.assertIsNone(result["total_score"])
        self.assertEqual(result["axes"]["funds"]["status"], "DATA_INELIGIBLE")

    def test_raw_approval_booleans_cannot_admit(self):
        axes = axes_for()
        for axis in axes.values():
            axis["pit_verified"] = True
            axis["approved"] = True
        result = compute_score("SSE", CUTOFF, axes, validation=validation())
        self.assertIsNone(result["total_score"])
        self.assertEqual(result["status"], "DATA_INELIGIBLE")

    def test_receipt_hash_mismatch_revokes_candidate(self):
        axes = axes_for()
        receipts = evidence_receipts(axes)
        axes["funds"]["value"] = 9999
        result = compute_score(
            "SSE", CUTOFF, axes, source_receipts=receipts, validation=validation()
        )
        self.assertIsNone(result["total_score"])
        self.assertIn("observation_receipt_mismatch", result["axes"]["funds"]["reasons"])

    def test_future_current_and_expired_sources_rejected(self):
        for key, value in (
            ("known_at", "2026-10-02T01:00:00+00:00"),
            ("valid_until", "2026-09-30T01:00:00+00:00"),
        ):
            axes = axes_for()
            axes["trend"][key] = value
            self.assertIsNone(self.compute(axes)["candidate_score"])

    def test_same_date_history_or_future_known_rows_cannot_raise_rank(self):
        axes = axes_for()
        result = self.compute(axes)
        axes["trend"]["history"].extend(
            [
                {
                    "value": -100000,
                    "unit": "percent",
                    "as_of": "2026-10-01T02:00:00+00:00",
                    "known_at": "2026-10-01T03:00:00+00:00",
                },
                {
                    "value": -100000,
                    "unit": "percent",
                    "as_of": "2025-01-01T00:00:00+00:00",
                    "known_at": "2026-10-03T00:00:00+00:00",
                },
            ]
        )
        changed = self.compute(axes)
        self.assertEqual(result["axes"]["trend"]["score"], changed["axes"]["trend"]["score"])

    def test_duplicate_conflicting_history_is_not_silently_selected(self):
        axes = axes_for()
        axes["trend"]["history"].append({**axes["trend"]["history"][0], "value": 99999})
        result = self.compute(axes)
        self.assertIsNone(result["candidate_score"])

    def test_unrecognized_metric_and_provider_fail_closed(self):
        for key, value in (("metric", "turnover"), ("provider", "random_blog"), ("unit", "USD")):
            axes = axes_for()
            axes["funds"][key] = value
            self.assertIsNone(self.compute(axes)["candidate_score"])

    def test_validation_must_bind_horizon_version_input_and_time(self):
        for change in (
            {"horizon": 5},
            {"profile_version": "future"},
            {"policy_version": "unreviewed"},
            {"training_holdout_evidence_sha256": "f" * 64},
            {"profile_sha256": "f" * 64},
            {"proxy_identity_sha256": "f" * 64},
            {"execution_rule_sha256": "f" * 64},
            {"signal_rule_sha256": "f" * 64},
            {"expires_at": "2025-01-01T00:00:00+00:00"},
            {"index_id": "HSI"},
            {"status": "VALIDATION_FAILED"},
            {"holdout_id": None},
        ):
            result = self.compute(validation=validation(**change))
            self.assertIsNone(result["total_score"])

    def test_training_audit_digest_does_not_equal_new_live_input_digest(self):
        result = self.compute(validation=validation(evidence_sha256="f" * 64))
        self.assertIsNotNone(result["total_score"])
        self.assertEqual(result["evidence_sha256"], "c" * 64)

    def test_overlay_needs_reconstructed_window_not_active_bool(self):
        report = validation(role="event_overlay", family="macro", direction=1)
        result = self.compute(
            validation=validation(),
            overlays=[report],
            applicability={digest(report): {"active": True}},
        )
        self.assertEqual(result["overlay_delta"], 0)
        self.assertIn("overlay_applicability_required", result["rejected_overlays"][0]["reasons"])

    def test_calendar_overlay_is_inactive_outside_its_rule_window(self):
        report = validation(
            role="calendar_overlay", family="month_end", direction=1, rule="month_end_1"
        )
        result = self.compute(validation=validation(), overlays=[report])
        self.assertEqual(result["overlay_delta"], 0)
        self.assertIn("overlay_outside_active_window", result["rejected_overlays"][0]["reasons"])

    def test_announced_calendar_window_can_be_active_before_end(self):
        report = validation(
            role="calendar_overlay", family="month_start", direction=1, rule="month_start_5"
        )
        self.assertEqual(
            self.compute(validation=validation(), overlays=[report])["overlay_delta"], 1
        )

    def test_future_event_not_yet_known_cannot_activate_its_window(self):
        report = validation(role="event_overlay", family="macro", direction=1)
        context = overlay_context(report, event_known_at="2026-10-02T00:00:00+00:00")
        proof = applicability_for(context, report, report, "SSE", CUTOFF)
        result = self.compute(
            validation=validation(), overlays=[report], applicability={digest(report): proof}
        )
        self.assertEqual(result["overlay_delta"], 0)

    def test_overlay_family_is_counted_once_and_total_capped(self):
        overlays = [
            validation(role="event_overlay", family=family, direction=1)
            for family in (
                "macro",
                "policy",
                "geopolitics",
                "war",
                "sports",
                "disaster",
                "unexpected",
                "other",
            )
        ]
        overlays.append(deepcopy(overlays[0]))
        result = self.compute(validation=validation(), overlays=overlays)
        self.assertEqual(result["overlay_delta"], 5)
        self.assertEqual(len(result["active_families"]), 8)
        self.assertLessEqual(result["total_score"], 100)

    def test_conflicting_or_unvalidated_family_has_no_contribution(self):
        overlays = [
            validation(role="event_overlay", family="macro", direction=1),
            validation(role="event_overlay", family="macro", direction=-1),
            validation(
                role="event_overlay", family="war", direction=1, status="INSUFFICIENT_SAMPLE"
            ),
        ]
        self.assertEqual(
            self.compute(validation=validation(), overlays=overlays)["overlay_delta"], 0
        )

    def test_overlay_cannot_supply_absent_base(self):
        result = self.compute(
            overlays=[validation(role="event_overlay", family="macro", direction=1)]
        )
        self.assertIsNone(result["total_score"])
        self.assertEqual(result["overlay_delta"], 0)

    def test_study_series_is_explicitly_candidate_only_and_sorted(self):
        axes = axes_for()
        payload = {
            "index_id": "SSE",
            "series": [{"as_of": CUTOFF, "axes": axes, "source_receipts": evidence_receipts(axes)}],
        }
        result = study_signals("SSE", payload)
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0]["score"])
        self.assertTrue(result[0]["candidate_only"])

    def test_bool_nan_and_naive_timestamp_refused(self):
        for value in (True,):
            axes = axes_for()
            axes["funds"]["value"] = value
            self.assertIsNone(self.compute(axes)["candidate_score"])
        for value in (float("nan"), float("inf")):
            axes = axes_for()
            axes["funds"]["value"] = value
            with self.assertRaises(ValueError):
                self.compute(axes)
        with self.assertRaises(ValueError):
            compute_score("SSE", "2026-10-01", axes_for(), validation=validation())


if __name__ == "__main__":
    unittest.main()
