"""Pure planning tests: no warehouse, provider, network or clock."""

import inspect
import sys
import unittest
from datetime import UTC, date, datetime, timedelta

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.planning import (
    MAX_SEGMENTS,
    Plan,
    Segment,
    merge_days,
    plan,
    plan_queries,
    plannable,
)
from app.research_web.market_store import CoverageProof


def bar_query(**overrides):
    parameters = {
        "asset": "600519.SH",
        "asset_type": "stock",
        "frequency": "daily",
        "adjustment": "none",
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
    }
    parameters.update(overrides.pop("parameters", {}))
    values = {"capability": "market_bars", "parameters": parameters}
    values.update(overrides)
    return BusinessQuery(**values)


def days(start, count):
    first = date.fromisoformat(start)
    return tuple(first + timedelta(days=offset) for offset in range(count))


def gap_lookup(missing):
    missing_set = set(missing)
    return lambda expected: tuple(day for day in expected if day in missing_set)


class PlannableTests(unittest.TestCase):
    def test_daily_stock_raw_bars_are_plannable(self):
        self.assertTrue(plannable(bar_query()))

    def test_refresh_is_never_planned(self):
        self.assertFalse(plannable(bar_query(refresh=True)))

    def test_point_in_time_is_never_planned(self):
        self.assertFalse(plannable(bar_query(as_of=datetime(2026, 1, 5, tzinfo=UTC))))

    def test_adjusted_bars_are_never_planned(self):
        self.assertFalse(plannable(bar_query(parameters={"adjustment": "qfq"})))

    def test_other_capabilities_are_never_planned(self):
        self.assertFalse(
            plannable(
                BusinessQuery(
                    capability="market_snapshot",
                    parameters={"assets": ["600519.SH"], "asset_type": "stock"},
                )
            )
        )

    def test_explicit_source_is_still_plannable(self):
        # The reviewed code restricted planning to auto/wind; planning is now
        # independent of the source so an explicit source can hit the warehouse.
        self.assertTrue(plannable(bar_query(source="akshare")))

    def test_plannable_is_the_single_source_of_truth(self):
        # ``warehouse.missing_queries`` delegates to this predicate. If someone
        # re-adds an inline condition there, the two can disagree and a
        # capability silently gains or loses planning.
        from app.research_web.datahub import warehouse

        source = inspect.getsource(warehouse.WarehouseBridge.missing_queries)
        self.assertIn("plannable(query)", source)
        self.assertNotIn('capability != "market_bars"', source)

    def test_every_plannable_capability_is_named_explicitly(self):
        from app.research_web.datahub.planning import PLANNABLE_CAPABILITIES

        self.assertEqual(PLANNABLE_CAPABILITIES, frozenset({"market_bars"}))

    def test_capabilities_without_per_date_rows_stay_direct(self):
        for capability, parameters in (
            ("market_snapshot", {"assets": ["600519.SH"], "asset_type": "stock"}),
            ("financials", {"asset": "600519.SH", "statements": ["metrics"]}),
            ("search_assets", {"query": "茅台"}),
        ):
            with self.subTest(capability=capability):
                self.assertFalse(
                    plannable(BusinessQuery(capability=capability, parameters=parameters))
                )

    def test_snapshot_backed_capabilities_do_not_use_this_planner(self):
        # The 2026-11-27 audit found financials/market_activity are warehouse
        # backed through SnapshotSeries, which never calls find_gaps. If that
        # ever changes, this assertion should be updated deliberately rather
        # than by widening PLANNABLE_CAPABILITIES and hoping.
        planner = inspect.getsource(sys.modules["app.research_web.datahub.planning"])
        self.assertIn('PLANNABLE_CAPABILITIES = frozenset({"market_bars"})', planner)

        from app.research_web.datahub import research_snapshot_store

        series = inspect.getsource(research_snapshot_store.SnapshotSeries)
        self.assertNotIn("find_gaps", series)
        self.assertNotIn("plan_queries", series)


class MergeDaysTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(merge_days(()), ())

    def test_single_day(self):
        self.assertEqual(
            merge_days((date(2026, 1, 5),)), (Segment(date(2026, 1, 5), date(2026, 1, 5)),)
        )

    def test_contiguous(self):
        self.assertEqual(
            merge_days(days("2026-01-01", 5)),
            (Segment(date(2026, 1, 1), date(2026, 1, 5)),),
        )

    def test_multiple_ranges(self):
        merged = merge_days(
            (date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 10), date(2026, 1, 11))
        )
        self.assertEqual(
            merged,
            (
                Segment(date(2026, 1, 1), date(2026, 1, 2)),
                Segment(date(2026, 1, 10), date(2026, 1, 11)),
            ),
        )

    def test_duplicates_and_unsorted_input(self):
        merged = merge_days((date(2026, 1, 2), date(2026, 1, 1), date(2026, 1, 2)))
        self.assertEqual(merged, (Segment(date(2026, 1, 1), date(2026, 1, 2)),))

    def test_fragmentation_folds_to_one_range(self):
        scattered = tuple(date(2026, 1, 1) + timedelta(days=2 * i) for i in range(MAX_SEGMENTS + 1))
        merged = merge_days(scattered)
        self.assertEqual(merged, (Segment(scattered[0], scattered[-1]),))

    def test_threshold_boundary_keeps_ranges(self):
        scattered = tuple(date(2026, 1, 1) + timedelta(days=2 * i) for i in range(MAX_SEGMENTS))
        self.assertEqual(len(merge_days(scattered)), MAX_SEGMENTS)

    def test_invalid_max_segments(self):
        with self.assertRaises(ValueError):
            merge_days((date(2026, 1, 1),), max_segments=0)


class PlanTests(unittest.TestCase):
    def test_not_plannable_returns_none(self):
        self.assertIsNone(
            plan(
                bar_query(refresh=True),
                expected_dates=days("2026-01-01", 5),
                find_gaps=gap_lookup(()),
            )
        )

    def test_empty_expected_returns_none(self):
        self.assertIsNone(plan(bar_query(), expected_dates=(), find_gaps=gap_lookup(())))

    def test_full_hit(self):
        expected = days("2026-01-01", 5)
        result = plan(bar_query(), expected_dates=expected, find_gaps=gap_lookup(()))
        self.assertIsInstance(result, Plan)
        self.assertTrue(result.complete)
        self.assertEqual(result.gaps, ())
        self.assertEqual(result.hits, (Segment(expected[0], expected[-1]),))
        self.assertEqual(result.expected_days, 5)
        self.assertEqual(result.covered_days, 5)
        self.assertEqual(result.gap_days, 0)
        self.assertFalse(result.folded)

    def test_full_gap(self):
        expected = days("2026-01-01", 4)
        result = plan(bar_query(), expected_dates=expected, find_gaps=gap_lookup(expected))
        self.assertFalse(result.complete)
        self.assertEqual(result.gaps, (Segment(expected[0], expected[-1]),))
        self.assertEqual(result.covered_days, 0)
        self.assertEqual(result.gap_days, 4)

    def test_partial_gap(self):
        expected = days("2026-01-01", 6)
        missing = (expected[1], expected[4])
        result = plan(bar_query(), expected_dates=expected, find_gaps=gap_lookup(missing))
        self.assertEqual(
            result.gaps,
            (
                Segment(expected[1], expected[1]),
                Segment(expected[4], expected[4]),
            ),
        )
        self.assertEqual(result.expected_days, result.covered_days + result.gap_days)

    def test_gap_outside_window_is_rejected(self):
        expected = days("2026-01-01", 3)
        outside = date(2026, 2, 1)
        with self.assertRaises(ValueError):
            plan(bar_query(), expected_dates=expected, find_gaps=lambda _: (outside,))

    def test_proofs_are_sorted_and_preserved(self):
        expected = days("2026-01-01", 3)
        proofs = (
            CoverageProof(date(2026, 1, 3), "nontrading", "cal-2"),
            CoverageProof(date(2026, 1, 2), "suspended", "cal-1"),
        )
        result = plan(bar_query(), expected_dates=expected, find_gaps=gap_lookup(()), proofs=proofs)
        self.assertEqual(
            [p.business_date for p in result.proofs], [date(2026, 1, 2), date(2026, 1, 3)]
        )

    def test_fragmentation_marks_folded(self):
        expected = days("2026-01-01", 2 * MAX_SEGMENTS + 1)
        result = plan(bar_query(), expected_dates=expected, find_gaps=gap_lookup(expected[::2]))
        self.assertTrue(result.folded)
        self.assertEqual(len(result.gaps), 1)

    def test_idempotent(self):
        expected = days("2026-01-01", 6)
        lookup = gap_lookup((expected[2],))
        first = plan(bar_query(), expected_dates=expected, find_gaps=lookup)
        second = plan(bar_query(), expected_dates=expected, find_gaps=lookup)
        self.assertEqual(first, second)

    def test_manifest_is_bounded_summary(self):
        expected = days("2026-01-01", 10)
        result = plan(bar_query(), expected_dates=expected, find_gaps=gap_lookup((expected[0],)))
        manifest = result.manifest()
        self.assertEqual(manifest["version"], "plan-v2")
        self.assertEqual(manifest["expected_days"], 10)
        self.assertEqual(manifest["gap_days"], 1)
        self.assertEqual(
            manifest["gap_segments"], [[expected[0].isoformat(), expected[0].isoformat()]]
        )
        self.assertNotIn("hits", manifest)


class PlanQueriesTests(unittest.TestCase):
    def test_complete_plan_produces_no_queries(self):
        expected = days("2026-01-01", 3)
        result = plan(bar_query(), expected_dates=expected, find_gaps=gap_lookup(()))
        self.assertEqual(plan_queries(bar_query(), result, "wind"), ())

    def test_each_gap_becomes_one_bound_query(self):
        expected = days("2026-01-01", 6)
        missing = (expected[1], expected[4], expected[5])
        result = plan(bar_query(), expected_dates=expected, find_gaps=gap_lookup(missing))
        queries = plan_queries(bar_query(), result, "wind")
        self.assertEqual(len(queries), 2)
        self.assertEqual(
            [q.parameters["start_date"] for q in queries],
            [expected[1].isoformat(), expected[4].isoformat()],
        )
        for query in queries:
            self.assertEqual(query.source, "wind")
            self.assertFalse(query.allow_fallback)

    def test_source_is_required(self):
        expected = days("2026-01-01", 2)
        result = plan(bar_query(), expected_dates=expected, find_gaps=gap_lookup(expected))
        with self.assertRaises(ValueError):
            plan_queries(bar_query(), result, "")


if __name__ == "__main__":
    unittest.main()


class TradingGapTests(unittest.TestCase):
    def test_weekend_does_not_split_adjacent_trading_days(self):
        from app.research_web.datahub.planning import merge_gaps

        expected = (date(2026, 11, 13), date(2026, 11, 16))
        self.assertEqual(merge_gaps(expected, expected), (Segment(*expected),))

    def test_covered_trading_day_splits_gaps(self):
        from app.research_web.datahub.planning import merge_gaps

        expected = (date(2026, 11, 12), date(2026, 11, 13), date(2026, 11, 16))
        self.assertEqual(
            merge_gaps(expected, (expected[0], expected[2])),
            (Segment(expected[0], expected[0]), Segment(expected[2], expected[2])),
        )


class SupplierWindowTests(unittest.TestCase):
    def test_wind_long_gap_is_split_into_inclusive_sixty_day_requests(self):
        start = date(2026, 1, 1)
        end = start + timedelta(days=129)
        planned = plan_queries(bar_query(), Plan(gaps=(Segment(start, end),)), "wind")
        self.assertEqual(len(planned), 3)
        self.assertEqual(planned[0].parameters["start_date"], start.isoformat())
        self.assertEqual(planned[-1].parameters["end_date"], end.isoformat())
        for q in planned:
            self.assertLessEqual(
                (
                    date.fromisoformat(q.parameters["end_date"])
                    - date.fromisoformat(q.parameters["start_date"])
                ).days
                + 1,
                60,
            )
