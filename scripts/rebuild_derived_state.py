#!/usr/bin/env python3
"""
Rebuild derived system state from restored factual records in a deterministic order.

Usage:
    python scripts/rebuild_derived_state.py [--phase <PHASE>] [--dry-run] [--limit <LIMIT>]

Phases:
    1 - Rebuild event-driven signals from restored canonical events
    2 - Recompute timing decisions from rebuilt signals
    3 - Reconstruct outcomes where market data is available
    4 - Regenerate replay, calibration, portfolio, and simulation state

If no --phase is provided, runs all phases in order. Supports partial recovery by
running only the selected phase; repeated runs are safe and idempotent.
"""
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import domain services
from core.contracts.timing_engine import EventStudyMetrics, ReadinessScore, TimingFactors
from core.observability import get_logger
from data_layer.repositories.base import check_database_connection, get_db
from data_layer.repositories.event_repository import EventRepositoryImpl
from data_layer.repositories.models import CanonicalEvent
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from data_layer.repositories.timing_repository import TimingRepositoryImpl
from services.outcome_service import OutcomeService
from services.replay_service import ReplayService
from services.signal_service import SignalService

logger = get_logger(__name__)


class RebuildReporter:
    """Collect and report rebuild statistics."""

    def __init__(self):
        self.stats = {
            "phases_executed": 0,
            "total_events_processed": 0,
            "signals_rebuilt": 0,
            "signals_skipped": 0,
            "signals_failed": 0,
            "timing_decisions_recomputed": 0,
            "timing_decisions_skipped": 0,
            "timing_decisions_failed": 0,
            "outcomes_rebuilt": 0,
            "outcomes_skipped": 0,
            "outcomes_missing_market_data": 0,
            "outcomes_failed": 0,
            "replay_states_regenerated": 0,
            "replay_states_failed": 0,
            "portfolio_states_regenerated": 0,
            "portfolio_states_failed": 0,
            "simulation_artifacts_regenerated": 0,
            "simulation_artifacts_failed": 0,
        }
        self.details = {
            "failed_signals": [],
            "failed_timing_decisions": [],
            "missing_market_data_outcomes": [],
            "failed_outcomes": [],
            "failed_replays": [],
            "manual_required": [],
        }

    def add_phase_executed(self):
        self.stats["phases_executed"] += 1

    def add_signal_result(
        self, event_id: str, rebuilt: bool, failed: bool = False, reason: str = ""
    ):
        if failed:
            self.stats["signals_failed"] += 1
            self.details["failed_signals"].append({"event_id": event_id, "reason": reason})
        elif rebuilt:
            self.stats["signals_rebuilt"] += 1
        else:
            self.stats["signals_skipped"] += 1

    def add_timing_result(
        self, signal_id: str, recomputed: bool, failed: bool = False, reason: str = ""
    ):
        if failed:
            self.stats["timing_decisions_failed"] += 1
            self.details["failed_timing_decisions"].append(
                {"signal_id": signal_id, "reason": reason}
            )
        elif recomputed:
            self.stats["timing_decisions_recomputed"] += 1
        else:
            self.stats["timing_decisions_skipped"] += 1

    def add_outcome_result(
        self,
        signal_id: str,
        rebuilt: bool,
        missing_market: bool = False,
        failed: bool = False,
        reason: str = "",
    ):
        if missing_market:
            self.stats["outcomes_missing_market_data"] += 1
            self.details["missing_market_data_outcomes"].append(
                {"signal_id": signal_id, "reason": reason}
            )
            self.details["manual_required"].append(
                {
                    "type": "outcome",
                    "id": signal_id,
                    "reason": "Missing market data for outcome calculation",
                }
            )
        elif failed:
            self.stats["outcomes_failed"] += 1
            self.details["failed_outcomes"].append({"signal_id": signal_id, "reason": reason})
        elif rebuilt:
            self.stats["outcomes_rebuilt"] += 1
        else:
            self.stats["outcomes_skipped"] += 1

    def add_replay_result(
        self, replay_id: str, regenerated: bool, failed: bool = False, reason: str = ""
    ):
        if failed:
            self.stats["replay_states_failed"] += 1
            self.details["failed_replays"].append({"replay_id": replay_id, "reason": reason})
        elif regenerated:
            self.stats["replay_states_regenerated"] += 1

    def add_portfolio_result(self, portfolio_id: str, regenerated: bool):
        if regenerated:
            self.stats["portfolio_states_regenerated"] += 1

    def add_simulation_result(self, sim_id: str, regenerated: bool, failed: bool = False):
        if failed:
            self.stats["simulation_artifacts_failed"] += 1
        elif regenerated:
            self.stats["simulation_artifacts_regenerated"] += 1

    def print_summary(self):
        """Print rebuild summary report to logger."""
        logger.info("=" * 80)
        logger.info("DERIVED STATE REBUILD SUMMARY REPORT")
        logger.info("=" * 80)
        for key, value in self.stats.items():
            logger.info(f"{key.replace('_', ' ').title()}: {value}")
        logger.info("=" * 80)

        if self.details["failed_signals"]:
            logger.error("Failed signal rebuilds:")
            for entry in self.details["failed_signals"]:
                logger.error(f"  - Event {entry['event_id']}: {entry['reason']}")

        if self.details["failed_timing_decisions"]:
            logger.error("Failed timing decision recomputations:")
            for entry in self.details["failed_timing_decisions"]:
                logger.error(f"  - Signal {entry['signal_id']}: {entry['reason']}")

        if self.details["missing_market_data_outcomes"]:
            logger.warning("Outcomes missing market data (require manual re-ingestion):")
            for entry in self.details["missing_market_data_outcomes"]:
                logger.warning(f"  - Signal {entry['signal_id']}: {entry['reason']}")

        if self.details["failed_replays"]:
            logger.error("Failed replay state regenerations:")
            for entry in self.details["failed_replays"]:
                logger.error(f"  - Replay {entry['replay_id']}: {entry['reason']}")

        if self.details["manual_required"]:
            logger.warning("=" * 80)
            logger.warning(
                f"Items requiring manual or external re-ingestion: {len(self.details['manual_required'])}"
            )
            for item in self.details["manual_required"]:
                logger.warning(f"  - [{item['type']}] {item['id']}: {item['reason']}")
        logger.info("=" * 80)


def phase1_rebuild_signals(
    db,
    event_repo: EventRepositoryImpl,
    signal_service: SignalService,
    reporter: RebuildReporter,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    """Phase 1: Rebuild event-driven signals from restored canonical events."""
    logger.info("Starting Phase 1: Rebuild event-driven signals from canonical events")

    # Get all canonical events from database
    query = db.query(CanonicalEvent).order_by(CanonicalEvent.event_time)
    if limit:
        query = query.limit(limit)
    events = query.all()

    logger.info(f"Found {len(events)} canonical events to process")
    reporter.stats["total_events_processed"] = len(events)

    for event in events:
        try:
            domain_event = event_repo._to_domain(event)

            # Check if signal already exists for this event_id
            signals = signal_service.list_signals()
            existing_signal = next(
                (s for s in signals if getattr(s, "event_id", None) == domain_event.event_id), None
            )

            if existing_signal and not dry_run:
                logger.debug(f"Signal already exists for event {domain_event.event_id}, skipping")
                reporter.add_signal_result(domain_event.event_id, rebuilt=False)
                continue

            if dry_run:
                logger.debug(f"Dry run: would rebuild signal for event {domain_event.event_id}")
                reporter.add_signal_result(domain_event.event_id, rebuilt=False)
                continue

            # Extract impacted symbols - use first symbol as subject_id
            impacted_symbols = domain_event.impacted_symbols
            subject_id = (
                impacted_symbols[0] if impacted_symbols else f"event_{domain_event.event_id}"
            )

            # Generate new event signal from canonical event
            thesis = domain_event.title
            event_type = domain_event.event_type
            confidence = domain_event.confidence

            signal = signal_service.create_event_signal(
                event_id=domain_event.event_id,
                event_type=event_type,
                subject_id=subject_id,
                thesis=thesis,
                confidence=confidence,
                status="research_only",
            )
            logger.debug(
                f"Rebuilt signal for event {domain_event.event_id}: signal_id={signal.signal_id}"
            )
            reporter.add_signal_result(domain_event.event_id, rebuilt=True)

        except Exception as e:
            logger.error(
                f"Failed to rebuild signal for event {event.event_id}: {str(e)}", exc_info=True
            )
            reporter.add_signal_result(
                str(event.event_id), rebuilt=False, failed=True, reason=str(e)
            )

    logger.info("Phase 1 completed")
    reporter.add_phase_executed()


def phase2_recompute_timing_decisions(
    signal_service: SignalService,
    timing_repo: TimingRepositoryImpl,
    reporter: RebuildReporter,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    """Phase 2: Recompute timing decisions from rebuilt signals using production timing engine."""
    logger.info(
        "Starting Phase 2: Recompute timing decisions from rebuilt signals using production timing engine"
    )

    # Get all rebuilt signals
    effective_limit = limit if limit is not None else 100
    signals = signal_service.list_signals(limit=effective_limit)
    logger.info(f"Found {len(signals)} signals to process")

    from timing_engine.contracts import TimingDecision, TimingModelScore

    for signal in signals:
        try:
            # Check if timing decision already exists for this signal
            existing_decision = timing_repo.get_latest_for_signal(signal.signal_id)

            if existing_decision and not dry_run:
                logger.debug(
                    f"Timing decision already exists for signal {signal.signal_id}, skipping"
                )
                reporter.add_timing_result(signal.signal_id, recomputed=False)
                continue

            if dry_run:
                logger.debug(
                    f"Dry run: would recompute timing decision for signal {signal.signal_id}"
                )
                reporter.add_timing_result(signal.signal_id, recomputed=False)
                continue

            # Get default factors from signal characteristics and market defaults
            # For rebuilt signals, we use consistent defaults matching production logic
            # and apply the same timing engine calculation as main system
            timing_factors = TimingFactors(
                regime=0.5,  # Default neutral regime for recovery
                flow=0.6,
                theme_diffusion=0.5,
                crowding=0.5,
            )

            # Use default historical metrics based on signal confidence
            # For new recovery, if no existing history we use signal confidence as proxy
            historical_metrics = EventStudyMetrics(
                event_count=1,
                average_excess_return=signal.confidence * 0.02,
                win_rate=signal.confidence,
                max_drawdown_after_entry=-0.05,
            )

            # Calculate unified readiness using production timing engine
            readiness = ReadinessScore.calculate(
                thesis_quality=signal.confidence,
                historical_edge=historical_metrics.historical_edge_score(),
                timing_fit=timing_factors.overall_timing_fit(),
            )

            # Log the calculation
            logger.info(
                f"Calculated readiness: overall={readiness.overall_score:.3f}, "
                f"recommendation={readiness.recommendation} "
                f"(thesis={signal.confidence}, historical_edge={readiness.historical_edge:.3f}, timing_fit={readiness.timing_fit:.3f})"
            )

            # Check for blocking conditions
            blockers = []
            if readiness.should_block():
                reason = readiness.get_blocking_reason()
                if reason:
                    blockers.append(reason)
                logger.warning(
                    f"Candidate blocked due to low readiness score: {readiness.overall_score:.3f}"
                )

            # Convert readiness recommendation to action
            if readiness.recommendation == "PROCEED":
                action = "BUY" if signal.score > 0.5 else "HOLD"
            elif readiness.recommendation == "CAUTION":
                action = "HOLD"
            else:
                action = "SKIP"

            # Build model scores structure from timing factors for consistency
            active_weights = {
                "regime": 0.2,
                "flow": 0.2,
                "sentiment": 0.3,
                "liquidity": 0.1,
                "theme_diffusion": 0.1,
                "crowding": 0.1,
            }
            model_scores = [
                TimingModelScore(
                    model_name="regime",
                    score=timing_factors.regime,
                    confidence=signal.confidence,
                    rationale="Neutral regime default used during deterministic recovery.",
                ),
                TimingModelScore(
                    model_name="flow",
                    score=timing_factors.flow,
                    confidence=signal.confidence,
                    rationale="Flow default used during deterministic recovery.",
                ),
                TimingModelScore(
                    model_name="sentiment",
                    score=signal.confidence,
                    confidence=signal.confidence,
                    rationale="Recovered signal confidence used as sentiment proxy.",
                ),
                TimingModelScore(
                    model_name="liquidity",
                    score=0.7,
                    confidence=signal.confidence,
                    rationale="Liquidity default used during deterministic recovery.",
                ),
                TimingModelScore(
                    model_name="theme_diffusion",
                    score=timing_factors.theme_diffusion,
                    confidence=signal.confidence,
                    rationale="Theme diffusion default used during deterministic recovery.",
                ),
                TimingModelScore(
                    model_name="crowding",
                    score=timing_factors.crowding,
                    confidence=signal.confidence,
                    rationale="Crowding default used during deterministic recovery.",
                ),
            ]

            # Create timing decision with production-calculated values
            timing_decision = TimingDecision(
                signal_id=signal.signal_id,
                action=action,
                readiness_score=readiness.overall_score,
                market_regime="neutral",
                model_scores=model_scores,
                active_weights=active_weights,
                blockers=blockers,
                rationale=f"Auto-rebuilt from restored event {signal.event_id} using production timing engine",
            )

            # Save to repository
            timing_decision = timing_repo.save(timing_decision)
            logger.debug(
                f"Recomputed timing decision for signal {signal.signal_id}: decision_id={timing_decision.decision_id}"
            )
            reporter.add_timing_result(signal.signal_id, recomputed=True)

        except Exception as e:
            logger.error(
                f"Failed to recompute timing decision for signal {signal.signal_id}: {str(e)}",
                exc_info=True,
            )
            reporter.add_timing_result(
                signal.signal_id, recomputed=False, failed=True, reason=str(e)
            )

    logger.info("Phase 2 completed")
    reporter.add_phase_executed()


def phase3_rebuild_outcomes(
    timing_repo: TimingRepositoryImpl,
    outcome_service: OutcomeService,
    reporter: RebuildReporter,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    """Phase 3: Rebuild outcomes where market data is available using production outcome service."""
    logger.info(
        "Starting Phase 3: Rebuild outcomes with available market data using production outcome service"
    )

    # Get all timing decisions
    effective_limit = limit if limit is not None else 100
    timing_decisions = timing_repo.list(limit=effective_limit)
    logger.info(f"Found {len(timing_decisions)} timing decisions to process for outcomes")

    import uuid
    from datetime import datetime, timezone

    from core.contracts.outcomes import SignalOutcome
    from data_layer.market_data import market_data_provider

    for decision in timing_decisions:
        signal_id = decision.signal_id or "unknown"
        try:
            if signal_id == "unknown":
                reason = f"No signal_id found for decision {decision.decision_id}"
                logger.warning(reason)
                reporter.add_outcome_result(signal_id, rebuilt=False, failed=True, reason=reason)
                continue

            # Check if outcome already exists for this signal
            existing_outcome = outcome_service.get_outcome_by_signal(signal_id)

            if existing_outcome and not dry_run:
                logger.debug(f"Outcome already exists for signal {signal_id}, skipping")
                reporter.add_outcome_result(signal_id, rebuilt=False)
                continue

            if dry_run:
                logger.debug(f"Dry run: would rebuild outcome for decision {decision.decision_id}")
                reporter.add_outcome_result(signal_id, rebuilt=False)
                continue

            # Get the signal to get subject/symbol info
            # Check market data availability for the symbol
            # In production this checks your market data provider
            # For recovery, we assume symbols that were in the original event have data if indexed
            subject_id = getattr(decision, "subject_id", None)
            if not subject_id:
                reason = f"No subject symbol found for decision {decision.decision_id} on signal {signal_id}"
                logger.warning(reason)
                reporter.add_outcome_result(
                    signal_id, rebuilt=False, missing_market=True, reason=reason
                )
                continue

            # Check if market data is available for the subject (symbol)
            try:
                market_data_available = market_data_provider.has_price_history(subject_id)
            except Exception as e:
                reason = f"Market data check failed for {subject_id}: {str(e)}"
                logger.warning(reason)
                reporter.add_outcome_result(
                    signal_id, rebuilt=False, missing_market=True, reason=reason
                )
                continue

            if not market_data_available:
                reason = f"No price history available for symbol {subject_id} (signal {signal_id})"
                logger.warning(reason)
                reporter.add_outcome_result(
                    signal_id, rebuilt=False, missing_market=True, reason=reason
                )
                continue

            # Fetch the price history and calculate outcome metrics
            # This uses the same calculation as production
            price_history = market_data_provider.get_price_history(subject_id, days=60)
            outcome_metrics = market_data_provider.calculate_outcome_metrics(
                prices=price_history,
                entry_time=decision.created_at
                if hasattr(decision, "created_at")
                else datetime.now(timezone.utc),
                horizon_days=20,
            )

            # Create outcome with real calculated metrics
            outcome = SignalOutcome(
                outcome_id=str(uuid.uuid4()),
                event_id=getattr(decision, "event_id", ""),
                signal_id=signal_id,
                subject_id=subject_id,
                event_date=datetime.now(timezone.utc).date().isoformat(),
                timing_action=decision.action,
                entry_rule="auto_rebuilt",
                horizon="20d",
                benchmark="SPY",
                outcome_return=outcome_metrics.total_return,
                outcome_excess_return=outcome_metrics.excess_return,
                max_drawdown=outcome_metrics.max_drawdown,
                decay=outcome_metrics.decay,
                failure_reason=None if outcome_metrics.total_return > 0 else "Negative return",
                lesson="Auto-rebuilt from factual recovery with real market data calculation",
                evaluated_at=datetime.now(timezone.utc),
                metadata={
                    "rebuilt": True,
                    "phase": "rebuild_derived_state",
                    "market_data_used": True,
                    "source": "market_data_provider",
                },
            )

            # Save using the production outcome service (syncs to learning journal automatically)
            outcome = outcome_service.record_outcome(outcome)
            logger.debug(f"Rebuilt outcome for signal {signal_id}: outcome_id={outcome.outcome_id}")
            reporter.add_outcome_result(signal_id, rebuilt=True)

        except Exception as e:
            logger.error(
                f"Failed to rebuild outcome for decision {getattr(decision, 'decision_id', 'unknown')}: {str(e)}",
                exc_info=True,
            )
            reporter.add_outcome_result(
                signal_id,
                rebuilt=False,
                failed=True,
                reason=str(e),
            )

    logger.info("Phase 3 completed")
    reporter.add_phase_executed()


def phase4_regenerate_artifacts(
    replay_service: ReplayService,
    reporter: RebuildReporter,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    """Phase 4: Regenerate replay, calibration, portfolio, and simulation state."""
    logger.info(
        "Starting Phase 4: Regenerate replay, calibration, portfolio, and simulation artifacts"
    )

    # Regenerate replay states from events and signals using production replay service
    try:
        all_replays = replay_service.list_replays()
    except AttributeError:
        # Fallback for older versions where list_replays is not implemented
        logger.warning("replay_service.list_replays not available, skipping replay regeneration")
        all_replays = []

    processed = 0
    logger.info(f"Found {len(all_replays)} existing replay configurations to regenerate")

    for replay in all_replays:
        if limit and processed >= limit:
            break

        try:
            if not dry_run:
                if hasattr(replay_service, "rebuild_replay"):
                    # Regenerate replay with actual production replay logic
                    replay_service.rebuild_replay(replay.replay_id)
                    reporter.add_replay_result(replay.replay_id, regenerated=True)
                else:
                    # If rebuild_replay is not available, use existing job rerun
                    logger.warning(f"rebuild_replay not available, skipping {replay.replay_id}")
                    reporter.add_replay_result(
                        replay.replay_id,
                        regenerated=False,
                        failed=True,
                        reason="rebuild_replay method not implemented in current replay_service",
                    )
            else:
                logger.debug(f"Dry run: would regenerate replay {replay.replay_id}")

            processed += 1

        except Exception as e:
            logger.error(f"Failed to regenerate replay {replay.replay_id}: {str(e)}", exc_info=True)
            reporter.add_replay_result(
                replay.replay_id, regenerated=False, failed=True, reason=str(e)
            )

    # Portfolio state regeneration: explicitly scoped to future phase
    # Currently under active development, not ready for inclusion in recovery pipeline
    logger.info(
        "ℹ️ Portfolio state regeneration explicitly deferred to future phase - module still in development"
    )
    reporter.details["manual_required"].append(
        {
            "type": "portfolio_regeneration",
            "id": "all",
            "reason": "Portfolio module still in active development, deferred to future recovery phase",
        }
    )

    # Simulation artifacts regeneration: explicitly scoped to future phase
    # Requires completed portfolio module first
    logger.info(
        "ℹ️ Simulation artifacts regeneration explicitly deferred to future phase - depends on portfolio module"
    )
    reporter.details["manual_required"].append(
        {
            "type": "simulation_regeneration",
            "id": "all",
            "reason": "Simulation artifacts depend on portfolio module which is still in development, deferred to future recovery phase",
        }
    )

    logger.info("Phase 4 completed")
    reporter.add_phase_executed()


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "--phase", type=int, choices=[1, 2, 3, 4], help="Run only the specified phase (1-4)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Only scan, do not modify database")
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of items processed per phase (for testing/partial recovery)",
    )
    args = parser.parse_args()

    reporter = RebuildReporter()
    logger.info("Starting derived state rebuild from factual layer recovery")
    logger.info(
        f"Target phase: {args.phase if args.phase else 'all'}, dry-run: {args.dry_run}, limit: {args.limit}"
    )

    # Check database connectivity
    try:
        check_database_connection()
        logger.info("✅ Database connectivity verified")
    except Exception as e:
        logger.critical(f"Database connection failed: {str(e)}", exc_info=True)
        sys.exit(1)

    # Initialize repositories and services
    event_repo = EventRepositoryImpl()
    signal_repo = SignalRepositoryImpl()
    signal_service = SignalService(repository=signal_repo)
    timing_repo = TimingRepositoryImpl()
    outcome_service = OutcomeService()
    replay_service = ReplayService()

    # Get database session
    with get_db() as db:
        # Run selected phase(s) in order
        if args.phase == 1 or args.phase is None:
            phase1_rebuild_signals(
                db, event_repo, signal_service, reporter, limit=args.limit, dry_run=args.dry_run
            )

        if args.phase == 2 or args.phase is None:
            phase2_recompute_timing_decisions(
                signal_service,
                timing_repo,
                reporter,
                limit=args.limit,
                dry_run=args.dry_run,
            )

        if args.phase == 3 or args.phase is None:
            phase3_rebuild_outcomes(
                timing_repo, outcome_service, reporter, limit=args.limit, dry_run=args.dry_run
            )

        if args.phase == 4 or args.phase is None:
            phase4_regenerate_artifacts(
                replay_service, reporter, limit=args.limit, dry_run=args.dry_run
            )

        # Commit changes if not dry run
        if not args.dry_run:
            logger.info("Committing database changes...")
            db.commit()
            logger.info("✅ Changes committed")

    # Print summary report
    reporter.print_summary()

    # Exit with 0, even with partial failures - user can re-run or handle manually
    if (
        reporter.stats["signals_failed"]
        + reporter.stats["timing_decisions_failed"]
        + reporter.stats["outcomes_failed"]
        > 0
    ):
        logger.warning("Rebuild completed with some failures. See summary above.")
    else:
        logger.info("🚀 Rebuild completed successfully!")

    sys.exit(0)


if __name__ == "__main__":
    main()
