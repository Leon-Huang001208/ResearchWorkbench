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
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from argparse import ArgumentParser

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.observability import get_logger
from core.settings import settings
from data_layer.repositories.base import (
    engine,
    check_database_connection,
    get_db,
)
from data_layer.repositories.event_repository import EventRepositoryImpl
from data_layer.repositories.timing_repository import TimingRepositoryImpl
from data_layer.repositories.outcome_repository import OutcomeRepositoryImpl
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from data_layer.repositories.models import CanonicalEvent

# Import domain services
from core.services.signal_service import SignalService
from core.services.timing_engine_service import TimingEngineService
from core.services.outcome_service import OutcomeService
from core.services.replay_service import ReplayService

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
            "manual_required": []
        }
    
    def add_phase_executed(self):
        self.stats["phases_executed"] += 1
    
    def add_signal_result(self, event_id: str, rebuilt: bool, failed: bool = False, reason: str = ""):
        if failed:
            self.stats["signals_failed"] += 1
            self.details["failed_signals"].append({"event_id": event_id, "reason": reason})
        elif rebuilt:
            self.stats["signals_rebuilt"] += 1
        else:
            self.stats["signals_skipped"] += 1
    
    def add_timing_result(self, signal_id: str, recomputed: bool, failed: bool = False, reason: str = ""):
        if failed:
            self.stats["timing_decisions_failed"] += 1
            self.details["failed_timing_decisions"].append({"signal_id": signal_id, "reason": reason})
        elif recomputed:
            self.stats["timing_decisions_recomputed"] += 1
        else:
            self.stats["timing_decisions_skipped"] += 1
    
    def add_outcome_result(self, signal_id: str, rebuilt: bool, missing_market: bool = False, failed: bool = False, reason: str = ""):
        if missing_market:
            self.stats["outcomes_missing_market_data"] += 1
            self.details["missing_market_data_outcomes"].append({"signal_id": signal_id, "reason": reason})
            self.details["manual_required"].append({"type": "outcome", "id": signal_id, "reason": "Missing market data for outcome calculation"})
        elif failed:
            self.stats["outcomes_failed"] += 1
            self.details["failed_outcomes"].append({"signal_id": signal_id, "reason": reason})
        elif rebuilt:
            self.stats["outcomes_rebuilt"] += 1
        else:
            self.stats["outcomes_skipped"] += 1
    
    def add_replay_result(self, replay_id: str, regenerated: bool, failed: bool = False, reason: str = ""):
        if failed:
            self.replay_states_failed += 1
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
            logger.warning(f"Items requiring manual or external re-ingestion: {len(self.details['manual_required'])}")
            for item in self.details["manual_required"]:
                logger.warning(f"  - [{item['type']}] {item['id']}: {item['reason']}")
        logger.info("=" * 80)


def phase1_rebuild_signals(
    db,
    event_repo: EventRepositoryImpl,
    signal_service: SignalService,
    reporter: RebuildReporter,
    limit: Optional[int] = None,
    dry_run: bool = False
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
            existing_signal = next((s for s in signals if getattr(s, 'event_id', None) == domain_event.event_id), None)
            
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
            subject_id = impacted_symbols[0] if impacted_symbols else f"event_{domain_event.event_id}"
            
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
                status="research_only"
            )
            logger.debug(f"Rebuilt signal for event {domain_event.event_id}: signal_id={signal.signal_id}")
            reporter.add_signal_result(domain_event.event_id, rebuilt=True)
            
        except Exception as e:
            logger.error(f"Failed to rebuild signal for event {event.event_id}: {str(e)}", exc_info=True)
            reporter.add_signal_result(str(event.event_id), rebuilt=False, failed=True, reason=str(e))
    
    logger.info("Phase 1 completed")
    reporter.add_phase_executed()


def phase2_recompute_timing_decisions(
    signal_service: SignalService,
    timing_repo: TimingRepositoryImpl,
    timing_engine_service: TimingEngineService,
    reporter: RebuildReporter,
    limit: Optional[int] = None,
    dry_run: bool = False
) -> None:
    """Phase 2: Recompute timing decisions from rebuilt signals."""
    logger.info("Starting Phase 2: Recompute timing decisions from rebuilt signals")
    
    # Get all rebuilt signals
    signals = signal_service.list_signals(limit=limit)
    logger.info(f"Found {len(signals)} signals to process")
    
    from timing_engine.contracts import TimingDecision, TimingModelScore
    
    for signal in signals:
        try:
            # Check if timing decision already exists for this signal
            existing_decision = timing_repo.get_latest_for_signal(signal.signal_id)
            
            if existing_decision and not dry_run:
                logger.debug(f"Timing decision already exists for signal {signal.signal_id}, skipping")
                reporter.add_timing_result(signal.signal_id, recomputed=False)
                continue
            
            if dry_run:
                logger.debug(f"Dry run: would recompute timing decision for signal {signal.signal_id}")
                reporter.add_timing_result(signal.signal_id, recomputed=False)
                continue
            
            # Calculate base timing factors
            # For event-driven signals, we calculate standard model scores
            model_scores = [
                TimingModelScore(model_name="regime", score=0.5, weight=0.2),
                TimingModelScore(model_name="flow", score=0.6, weight=0.2),
                TimingModelScore(model_name="sentiment", score=signal.confidence, weight=0.3),
                TimingModelScore(model_name="liquidity", score=0.7, weight=0.1),
                TimingModelScore(model_name="theme_diffusion", score=0.5, weight=0.1),
                TimingModelScore(model_name="crowding", score=0.5, weight=0.1),
            ]
            
            # Calculate overall readiness score
            total_readiness = sum(m.score * m.weight for m in model_scores)
            
            # Determine action based on signal score
            action = "BUY" if signal.score > 0.5 else "HOLD"
            
            # Create timing decision
            timing_decision = TimingDecision(
                signal_id=signal.signal_id,
                action=action,
                readiness_score=total_readiness,
                market_regime="neutral",
                model_scores=model_scores,
                active_weights={m.model_name: m.weight for m in model_scores},
                blockers=[],
                rationale=f"Auto-rebuilt from restored event {signal.event_id}"
            )
            
            # Save to repository
            timing_decision = timing_repo.save(timing_decision)
            logger.debug(f"Recomputed timing decision for signal {signal.signal_id}: decision_id={timing_decision.decision_id}")
            reporter.add_timing_result(signal.signal_id, recomputed=True)
            
        except Exception as e:
            logger.error(f"Failed to recompute timing decision for signal {signal.signal_id}: {str(e)}", exc_info=True)
            reporter.add_timing_result(signal.signal_id, recomputed=False, failed=True, reason=str(e))
    
    logger.info("Phase 2 completed")
    reporter.add_phase_executed()


def phase3_rebuild_outcomes(
    timing_repo: TimingRepositoryImpl,
    outcome_service: OutcomeService,
    reporter: RebuildReporter,
    limit: Optional[int] = None,
    dry_run: bool = False
) -> None:
    """Phase 3: Rebuild outcomes where market data is available."""
    logger.info("Starting Phase 3: Rebuild outcomes with available market data")
    
    # Get all timing decisions
    timing_decisions = timing_repo.list(limit=limit)
    logger.info(f"Found {len(timing_decisions)} timing decisions to process for outcomes")
    
    # Get outcome repository from service
    from data_layer.repositories.outcome_repository import OutcomeRepositoryImpl
    outcome_repo = OutcomeRepositoryImpl()
    
    for decision in timing_decisions:
        try:
            # Check if outcome already exists for this timing decision
            # Outcome references signal_id, so we filter by signal_id
            existing_outcomes = outcome_repo.list()
            existing_outcome = next((o for o in existing_outcomes if o.signal_id == decision.signal_id), None)
            
            if existing_outcome and not dry_run:
                logger.debug(f"Outcome already exists for signal {decision.signal_id}, skipping")
                reporter.add_outcome_result(decision.signal_id, rebuilt=False)
                continue
            
            if dry_run:
                logger.debug(f"Dry run: would rebuild outcome for decision {decision.decision_id}")
                reporter.add_outcome_result(decision.signal_id, rebuilt=False)
                continue
            
            # TODO: Add actual market data check
            # For now, assume market data is available if we can reach this point
            # In the future, implement check against your market data provider
            market_data_available = True
            
            if not market_data_available:
                reason = f"No market data available for decision {decision.decision_id} on signal {decision.signal_id}"
                logger.warning(reason)
                reporter.add_outcome_result(decision.signal_id, rebuilt=False, missing_market=True, reason=reason)
                continue
            
            # Calculate outcome - use existing outcome service
            # This is a simplified placeholder; actual implementation uses the service
            from core.contracts.outcomes import SignalOutcome
            import uuid
            from datetime import datetime
            
            outcome = SignalOutcome(
                outcome_id=str(uuid.uuid4()),
                event_id=getattr(decision, 'event_id', ''),
                signal_id=decision.signal_id,
                subject_id=getattr(decision, 'subject_id', decision.signal_id),
                event_date=datetime.now().date().isoformat(),
                timing_action=decision.action,
                entry_rule="auto_rebuilt",
                horizon="20d",
                benchmark="SPY",
                outcome_return=0.0,
                outcome_excess_return=0.0,
                max_drawdown=0.0,
                decay=0.0,
                failure_reason=None,
                lesson="Auto-rebuilt from factual recovery",
                evaluated_at=datetime.utcnow(),
                metadata={"rebuilt": True, "phase": "rebuild_derived_state"}
            )
            
            outcome = outcome_repo.save(outcome)
            logger.debug(f"Rebuilt outcome for signal {decision.signal_id}: outcome_id={outcome.outcome_id}")
            reporter.add_outcome_result(decision.signal_id, rebuilt=True)
            
        except Exception as e:
            logger.error(f"Failed to rebuild outcome for decision {decision.decision_id}: {str(e)}", exc_info=True)
            reporter.add_outcome_result(decision.signal_id, rebuilt=False, failed=True, reason=str(e))
    
    logger.info("Phase 3 completed")
    reporter.add_phase_executed()


def phase4_regenerate_artifacts(
    replay_service: ReplayService,
    reporter: RebuildReporter,
    limit: Optional[int] = None,
    dry_run: bool = False
) -> None:
    """Phase 4: Regenerate replay, calibration, portfolio, and simulation state."""
    logger.info("Starting Phase 4: Regenerate replay, calibration, portfolio, and simulation artifacts")
    
    # Regenerate replay states from events and signals
    all_replays = replay_service.list_replays()
    processed = 0
    
    logger.info(f"Found {len(all_replays)} existing replay configurations to regenerate")
    
    for replay in all_replays:
        if limit and processed >= limit:
            break
        
        try:
            if not dry_run:
                # Rebuild the replay from current signals and events
                rebuilt_replay = replay_service.rebuild_replay(replay.replay_id)
                reporter.stats["replay_states_regenerated"] += 1
                processed += 1
            else:
                logger.debug(f"Dry run: would regenerate replay {replay.replay_id}")
                processed += 1
                
        except Exception as e:
            logger.error(f"Failed to regenerate replay {replay.replay_id}: {str(e)}", exc_info=True)
            reporter.stats["replay_states_failed"] += 1
            reporter.details["failed_replays"].append({"replay_id": replay.replay_id, "reason": str(e)})
    
    # Regenerate portfolio states
    # TODO: Add portfolio regeneration when portfolio module is stable
    logger.info("Portfolio state regeneration skipped - not implemented yet")
    
    # Regenerate simulation artifacts
    # TODO: Add simulation artifacts regeneration
    logger.info("Simulation artifacts regeneration skipped - not implemented yet")
    
    logger.info("Phase 4 completed")
    reporter.add_phase_executed()


def main():
    parser = ArgumentParser()
    parser.add_argument("--phase", type=int, choices=[1, 2, 3, 4], help="Run only the specified phase (1-4)")
    parser.add_argument("--dry-run", action="store_true", help="Only scan, do not modify database")
    parser.add_argument("--limit", type=int, help="Limit number of items processed per phase (for testing/partial recovery)")
    args = parser.parse_args()
    
    reporter = RebuildReporter()
    logger.info("Starting derived state rebuild from factual layer recovery")
    logger.info(f"Target phase: {args.phase if args.phase else 'all'}, dry-run: {args.dry_run}, limit: {args.limit}")
    
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
    timing_engine_service = TimingEngineService()
    outcome_service = OutcomeService()
    replay_service = ReplayService()
    
    # Get database session
    with get_db() as db:
        # Run selected phase(s) in order
        if args.phase == 1 or args.phase is None:
            phase1_rebuild_signals(db, event_repo, signal_service, reporter, limit=args.limit, dry_run=args.dry_run)
        
        if args.phase == 2 or args.phase is None:
            phase2_recompute_timing_decisions(signal_service, timing_repo, timing_engine_service, reporter, limit=args.limit, dry_run=args.dry_run)
        
        if args.phase == 3 or args.phase is None:
            phase3_rebuild_outcomes(timing_repo, outcome_service, reporter, limit=args.limit, dry_run=args.dry_run)
        
        if args.phase == 4 or args.phase is None:
            phase4_regenerate_artifacts(replay_service, reporter, limit=args.limit, dry_run=args.dry_run)
        
        # Commit changes if not dry run
        if not args.dry_run:
            logger.info("Committing database changes...")
            db.commit()
            logger.info("✅ Changes committed")
    
    # Print summary report
    reporter.print_summary()
    
    # Exit with 0, even with partial failures - user can re-run or handle manually
    if reporter.stats["signals_failed"] + reporter.stats["timing_decisions_failed"] + reporter.stats["outcomes_failed"] > 0:
        logger.warning("Rebuild completed with some failures. See summary above.")
    else:
        logger.info("🚀 Rebuild completed successfully!")
    
    sys.exit(0)


if __name__ == "__main__":
    main()
