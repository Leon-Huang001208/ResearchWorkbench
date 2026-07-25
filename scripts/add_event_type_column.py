#!/usr/bin/env python3
"""
Add event_type column to signal_outcome table directly with SQL.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from core.observability import get_logger
from data_layer.repositories.base import SessionLocal

logger = get_logger(__name__)


def add_event_type_column():
    """Add event_type column to signal_outcome table."""
    db = SessionLocal()
    try:
        # Check if column already exists
        result = db.execute(
            text(
                """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'signal_outcome' AND column_name = 'event_type'
        """
            )
        )
        if result.fetchone():
            logger.info("event_type column already exists, skipping")
            return True

        # Add column
        logger.info("Adding event_type column to signal_outcome...")
        db.execute(
            text(
                """
            ALTER TABLE signal_outcome
            ADD COLUMN IF NOT EXISTS event_type TEXT DEFAULT 'unknown'
        """
            )
        )
        db.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_signal_outcome_event_type
            ON signal_outcome(event_type)
        """
            )
        )
        db.commit()
        logger.info("✅ event_type column added successfully")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to add column: {e}", exc_info=True)
        return False
    finally:
        db.close()


def main():
    """Main function."""
    logger.info("Starting column addition...")
    success = add_event_type_column()
    if success:
        logger.info("✅ Done!")
        sys.exit(0)
    else:
        logger.error("❌ Failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
