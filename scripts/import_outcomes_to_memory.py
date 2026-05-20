#!/usr/bin/env python3
"""Import existing outcomes to memory learning module."""
import json
import sys
import uuid
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from data_layer.repositories.base import SessionLocal
from memory_learning.contracts import MarketEpisode
from memory_learning.journal import LearningJournal

print("=" * 60)
print("Importing Outcomes to Memory Learning Module")
print("=" * 60)


journal = LearningJournal()

db = SessionLocal()
try:
    # Get existing outcomes
    result = db.execute(text("SELECT * FROM signal_outcome ORDER BY created_at DESC LIMIT 20"))
    outcomes = [dict(row._mapping) for row in result]

    print(f"\nFound {len(outcomes)} outcomes to import")

    imported_count = 0
    for outcome in outcomes:
        try:
            # Parse metadata
            metadata = {}
            if outcome.get("metadata"):
                try:
                    metadata = json.loads(outcome["metadata"])
                except Exception:
                    pass

            # Create market episode
            episode = MarketEpisode(
                episode_id=str(uuid.uuid4()),
                event_id=outcome.get("event_id", ""),
                event_type=outcome.get("event_type", metadata.get("event_type", "unknown")),
                market_regime="unknown",
                initial_reaction="unknown",
                outcome_horizon=outcome.get("horizon", "20d"),
                outcome_return=float(outcome["outcome_return"])
                if outcome["outcome_return"] is not None
                else 0.0,
                outcome_excess_return=float(outcome["outcome_excess_return"])
                if outcome["outcome_excess_return"] is not None
                else 0.0,
                timing_action=outcome.get("timing_action", "enter"),
                signal_id=outcome.get("signal_id"),
                timing_decision_id=None,
                failed_reason=outcome.get("failure_reason"),
                lesson=outcome.get("lesson"),
                evidence_refs=[outcome.get("event_id")] if outcome.get("event_id") else [],
                metadata=metadata,
            )

            journal.record_episode(episode)
            imported_count += 1
            print(
                f"  ✓ Imported episode for {episode.event_type}: return={episode.outcome_return:.2%}, excess={episode.outcome_excess_return:.2%}"
            )

        except Exception as e:
            print(f"  ✗ Failed to import: {e}")

    print(f"\n✓ Imported {imported_count}/{len(outcomes)} episodes")

    # Show summary
    if imported_count > 0:
        print("\nEvent type summary:")
        event_types = set(e.event_type for e in journal.list_episodes())
        for event_type in sorted(event_types):
            summary = journal.summarize_event_type(event_type)
            print(
                f"  - {event_type}: {summary['sample_size']} samples, "
                f"{summary['win_rate']:.1%} win rate, "
                f"{summary['average_excess_return']:.2%} avg excess return"
            )

finally:
    db.close()

print("\n" + "=" * 60)
print("Import completed!")
print("=" * 60)
