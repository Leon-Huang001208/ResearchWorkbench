"""Actual study producer -> scorer interop in an explicitly synthetic market.

No gate is mocked and no production/provider qualification is asserted.
"""

import unittest
from collections import deque
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from statistics import pstdev
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.research_web.event_studies.contracts import Calendar, Proxy, Session
from app.research_web.event_studies.service import StudyBundle, StudyService
from app.research_web.market_scoring.applicability import applicability_for
from app.research_web.market_scoring.contracts import OverlayContext, scoring_identity
from app.research_web.market_scoring.engine import compute_score, digest, study_signals
from app.research_web.market_scoring.profiles import PROFILE_VERSION, profile_for
from tests.research_web.test_event_studies_service import Records
from tests.research_web.test_market_scoring import CUTOFF, axes_for, evidence_receipts


def compiled_toy_inputs(rows, days):
    """Stream actual six-axis compilation, with no custom target-weight callback.

    This toy world's public calendar determines its observed breadth/sentiment
    and fund-flow cycle. Momentum/volatility use only already closed toy bars;
    every normalization history contains only earlier observations.
    """
    profile = profile_for("SSE")
    history = {axis: deque(maxlen=300) for axis in profile["axes"]}
    changes, signals, receipts, input_hashes = [], {}, {}, []
    for i, row in enumerate(rows):
        close = float(row["close"])
        changes.append(close / float(row["open"]) - 1)
        following_is_month_end = i + 1 < len(days) and (
            i + 2 == len(days) or days[i + 2].month != days[i + 1].month
        )
        public_calendar_cycle = (i + 1) % 7 == 0 or following_is_month_end
        values = {
            "trend": (close / float(rows[i - 20]["close"]) - 1) * 100 if i >= 20 else 0.0,
            "risk": pstdev(changes[-20:]) * 100 if i else 0.0,
            "breadth": 0.9 if public_calendar_cycle else 0.1,
            "sentiment": 0.8 if public_calendar_cycle else -0.8,
            "funds": 1000.0 if public_calendar_cycle else -1000.0,
            "valuation": 20.0,
        }
        axes = {}
        for axis, definition in profile["axes"].items():
            axes[axis] = {
                "metric": definition["metric"],
                "unit": definition["unit"],
                "provider": definition["providers"][0],
                "scope": definition["scope"],
                "scope_id": "SSE" if definition["scope"] == "index" else "CN",
                "value": values[axis],
                "as_of": row["known_at"],
                "published_at": row["known_at"],
                "known_at": row["known_at"],
                "valid_until": (
                    datetime.fromisoformat(row["known_at"]) + timedelta(days=1)
                ).isoformat(),
                "source_ref": {"id": "a" * 32, "sha256": "b" * 64},
                "history": (
                    list(history[axis]) if definition["normalization"] == "past_percentile" else []
                ),
            }
        if days[i] >= date(1995, 1, 1):
            at = row["known_at"]
            compiled = study_signals(
                "SSE",
                {
                    "index_id": "SSE",
                    "series": [
                        {"as_of": at, "axes": axes, "source_receipts": evidence_receipts(axes)}
                    ],
                },
            )[0]
            if compiled["score"] is None:
                raise AssertionError(f"synthetic six-axis inputs did not qualify on {days[i]}")
            day = row["day"]
            signals[day] = str(Decimal(str(compiled["score"])) / 100)
            receipts[day] = {"known_at": at, "source_ref": compiled["evidence_sha256"]}
            input_hashes.append(compiled["evidence_sha256"])
        for axis, definition in profile["axes"].items():
            history[axis].append(
                {
                    "as_of": row["known_at"],
                    "known_at": row["known_at"],
                    "unit": definition["unit"],
                    "value": values[axis],
                }
            )
    return signals, receipts, digest(input_hashes)


def qualified_synthetic_studies(*, legacy=False):
    """Predeclared toy scenarios, never searched using their final holdout results."""
    zone = ZoneInfo("Asia/Shanghai")
    day, days = date(1995, 1, 1) if legacy else date(1993, 1, 1), []
    while day <= date(2026, 9, 30):
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    sessions = [
        Session(
            day=d,
            opens=datetime.combine(d, time(9, 30), zone),
            closes=datetime.combine(d, time(15), zone),
            known_at="1994-01-01T00:00:00Z",
            announcement_version_ref="synthetic-full-calendar-announcement",
        )
        for d in days
    ]
    calendar = Calendar(
        exchange="XSHG",
        timezone="Asia/Shanghai",
        version="synthetic-v1",
        source_ref="synthetic-calendar",
        known_at="2026-10-01T00:00:00Z",
        sessions=sessions,
    )
    proxy = Proxy(
        symbol="SYNTHETIC-SSE-PROXY",
        index_id="SSE",
        market="CN",
        currency="CNY",
        exchange="XSHG",
        source_ref="synthetic-proxy",
        known_at="1994-01-01T00:00:00Z",
        listed_on="1990-01-01",
        exact_tracking=True,
        price_basis="unadjusted",
        rules=[
            {
                "from_date": "1990-01-01",
                "until_date": "2099-12-31",
                "lot": 1,
                "settlement_sessions": 0,
                "sell_after_sessions": 1,
                "tax_buy_bps": "0",
                "tax_sell_bps": "0",
                "source_ref": "synthetic-rules",
                "known_at": "1994-01-01T00:00:00Z",
            }
        ],
    )
    positive = [
        i % 7 == 0 or i == len(days) - 1 or days[i + 1].month != d.month for i, d in enumerate(days)
    ]
    price, rows, signals, receipts = Decimal(100), [], {}, {}
    for i, session in enumerate(sessions):
        monthly = i == len(days) - 1 or days[i + 1].month != days[i].month
        if legacy:
            change = (
                Decimal(".03") if monthly else Decimal(".01") if positive[i] else Decimal("-.003")
            )
        else:
            # A negative month-end shock is known only as a calendar hypothesis;
            # the actual -1 point rule must survive costs, drawdown and Sharpe.
            change = (
                Decimal("-.02") if monthly else Decimal(".0245") if i % 7 == 0 else Decimal("-.003")
            )
        close = (price * (1 + change)).quantize(Decimal(".00000001"))
        rows.append(
            {
                "day": session.day.isoformat(),
                "open": str(price),
                "close": str(close),
                "execution_known_at": session.opens.isoformat(),
                "known_at": session.closes.isoformat(),
                "actions_known_at": session.opens.isoformat(),
                "dividend": "0",
                "split": "1",
                "historical_eligible": True,
                "source_ref": "synthetic-historical-price-receipt",
            }
        )
        if legacy:
            signals[session.day.isoformat()] = (
                ".5" if i + 1 < len(positive) and positive[i + 1] else ".1"
            )
            receipts[session.day.isoformat()] = {
                "known_at": session.closes.isoformat(),
                "source_ref": "legacy-callback-weights",
            }
        price = close
    evidence_digest = "c" * 64
    if not legacy:
        signals, receipts, evidence_digest = compiled_toy_inputs(rows, days)
        included = [i for i, day in enumerate(days) if day >= date(1995, 1, 1)]
        sessions, rows = [sessions[i] for i in included], [rows[i] for i in included]
        calendar = calendar.model_copy(update={"sessions": sessions})
    bundle = StudyBundle(
        index_id="SSE",
        rows=rows,
        data_digest="b" * 64,
        calendar=calendar,
        proxy=proxy,
        index_rows=deepcopy(rows),
        index_calendar=calendar,
        index_data_digest="e" * 64,
        index_qualification_receipts=("synthetic-independent-index-history",),
        signals=signals,
        base_signals=signals,
        evidence_sha256=evidence_digest,
        qualification_receipts=("synthetic-pit-and-six-axis-receipt",),
        signal_receipts=receipts,
        data_gaps=(),
        calendar_basis="synthetic_verified_sessions",
    )
    records = Records()
    source = records.create("prices", {"source": "synthetic-host-adapter"}, "synthetic-source")
    research = SimpleNamespace(
        event_timeline=SimpleNamespace(records=records),
        resolve_event_study_bundle=lambda ref: bundle,
        _event_study_clock=lambda: datetime(2026, 10, 1, tzinfo=ZoneInfo("UTC")),
    )
    service = StudyService(research)
    common = {
        "title": "Synthetic interop",
        "index_id": "SSE",
        "profile_version": PROFILE_VERSION,
        "bundle_ref": {"id": source["id"], "revision": 1},
        "family_id": "synthetic-interop",
    }
    base = service.create(
        {**common, "role": "base_score", "hypothesis": "six-axis-score-weight"}, "synthetic-base"
    )
    overlay = service.create(
        {
            **common,
            "role": "calendar_overlay",
            "family": "month_end",
            "direction": 1 if legacy else -1,
            "rule": "month_end_1",
            "hypothesis": (
                "positive-month-end-one-session" if legacy else "negative-month-end-one-session"
            ),
        },
        "synthetic-overlay",
    )
    batch = service.seal([base["id"], overlay["id"]], "synthetic-seal")
    results = service.evaluate(batch["id"], "synthetic-evaluate")["items"]
    return (
        service,
        bundle,
        {row["payload"]["validation"]["role"]: row["payload"]["validation"] for row in results},
    )


class StudyScorerInterop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service, cls.bundle, cls.reports = qualified_synthetic_studies()

    def compute(self, report):
        observations = axes_for()
        return compute_score(
            "SSE",
            CUTOFF,
            observations,
            source_receipts=evidence_receipts(observations),
            validation=report,
            evidence_sha256="c" * 64,
            validation_identity=scoring_identity("SSE", self.bundle.proxy),
        )

    def test_actual_producer_base_receipt_is_accepted(self):
        report = self.reports["base_score"]
        self.assertEqual(report["status"], "VALIDATED", report["reasons"])
        result = self.compute(report)
        self.assertIsNotNone(result["base_score"], result)

    def test_actual_calendar_receipt_freezes_family_direction_and_rule(self):
        report = self.reports["calendar_overlay"]
        self.assertEqual(report["status"], "VALIDATED", report["reasons"])
        self.assertEqual(
            (report["family"], report["direction"], report["rule"]),
            ("month_end", -1, "month_end_1"),
        )
        self.assertTrue(report["signal_rule_sha256"])
        self.assertTrue(report["proxy_identity_sha256"])
        prediction = report["index_prediction"]
        self.assertEqual(prediction["status"], "VALIDATED", prediction["reasons"])
        self.assertEqual(prediction["index_data_digest"], self.bundle.index_data_digest)
        self.assertEqual(prediction["holdout_id"], report["holdout_id"])
        stored = self.service.records.get("admission", report["index_prediction_ref"]["id"])
        self.assertEqual(stored["payload"], prediction)

    def test_mutating_producer_contract_is_rejected(self):
        for key, value in (
            ("role", "calendar_overlay"),
            ("profile_version", "unknown"),
            ("index_id", "HSI"),
            ("horizon", 5),
            ("policy_version", "unknown"),
        ):
            report = deepcopy(self.reports["base_score"])
            report[key] = value
            self.assertIsNone(self.compute(report)["base_score"], key)

    def test_actual_producer_overlay_only_applies_inside_new_verified_window(self):
        overlay = self.reports["calendar_overlay"]
        spec = self.service.get(overlay["study_id"])["payload"]["spec"]
        sessions = []
        day = date(2026, 10, 1)
        while day <= date(2026, 11, 3):
            if day.weekday() < 5:
                sessions.append(
                    Session(
                        day=day,
                        opens=datetime.combine(day, time(9, 30), ZoneInfo("Asia/Shanghai")),
                        closes=datetime.combine(day, time(15), ZoneInfo("Asia/Shanghai")),
                        known_at="2026-01-01T00:00:00Z",
                        announcement_version_ref="synthetic-next-year-calendar",
                    )
                )
            day += timedelta(days=1)
        calendar = Calendar(
            exchange="XSHG",
            timezone="Asia/Shanghai",
            version="synthetic-future-calendar",
            source_ref="synthetic-next-year-calendar",
            known_at="2026-10-01T00:00:00Z",
            sessions=sessions,
        )
        for as_of, expected in (
            ("2026-10-29T16:00:00+08:00", -1),
            ("2026-11-02T16:00:00+08:00", 0),
        ):
            context = OverlayContext(
                index_id="SSE",
                as_of=as_of,
                calendar=calendar,
                events=(),
                holidays=(),
                source_refs=({"id": "a" * 32, "sha256": "d" * 64},),
                source_version="synthetic-future-v1",
                qualification_receipts=("synthetic-schedule-receipt",),
            )
            proof = applicability_for(context, overlay, spec, "SSE", as_of)
            observations = axes_for()
            for observation in observations.values():
                observation.update(
                    as_of=as_of[:10] + "T15:00:00+08:00",
                    published_at=as_of[:10] + "T15:01:00+08:00",
                    known_at=as_of[:10] + "T15:02:00+08:00",
                    valid_until=as_of[:10] + "T23:59:59+08:00",
                )
            identity = scoring_identity(
                "SSE",
                self.bundle.proxy,
                role="calendar_overlay",
                family="month_end",
                direction=-1,
                rule="month_end_1",
            )
            result = compute_score(
                "SSE",
                as_of,
                observations,
                source_receipts=evidence_receipts(observations),
                validation=self.reports["base_score"],
                validation_identity=scoring_identity("SSE", self.bundle.proxy),
                overlays=[overlay],
                overlay_identities={digest(overlay): identity},
                applicability={digest(overlay): proof},
            )
            self.assertIsNotNone(result["base_score"])
            self.assertEqual(result["overlay_delta"], expected, result)

    def test_profitable_legacy_callback_base_does_not_certify_registered_calendar_rule(self):
        _, _, reports = qualified_synthetic_studies(legacy=True)
        base, overlay = reports["base_score"], reports["calendar_overlay"]
        self.assertEqual(base["status"], "VALIDATED")
        self.assertGreater(
            base["metrics"]["normal"]["strategy"]["cagr"],
            base["metrics"]["normal"]["comparator"]["cagr"],
        )
        self.assertEqual(overlay["index_prediction"]["status"], "VALIDATED")
        self.assertEqual(overlay["status"], "VALIDATION_FAILED")
        self.assertIn("normal_sharpe_not_improved", overlay["reasons"])
        self.assertIn("normal_drawdown_worse", overlay["reasons"])
