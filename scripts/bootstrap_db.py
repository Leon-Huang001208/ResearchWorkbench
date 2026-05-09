#!/usr/bin/env python3
"""
Bootstrap database for AlphaFoundry: initialize schema, verify connectivity, seed minimal configuration.

Usage:
    python scripts/bootstrap_db.py

This script is idempotent and can be run multiple times safely.
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.observability import get_logger
from core.settings import settings
from data_layer.repositories.base import (
    engine,
    check_database_connection,
    ensure_schema,
    get_db,
)
from data_layer.repositories.models import AlertThresholdDB

logger = get_logger(__name__)

DEFAULT_ALERT_THRESHOLDS = [
    {
        "threshold_id": "error-rate-high",
        "name": "High error rate",
        "subsystem": "ingestion",
        "dimension": "processing",
        "metric_field": "error_rate",
        "operator": "gte",
        "value": 0.05,
        "severity": "warning",
        "cooldown_minutes": 15,
        "enabled": True,
    },
    {
        "threshold_id": "error-rate-critical",
        "name": "Critical error rate",
        "subsystem": "ingestion",
        "dimension": "processing",
        "metric_field": "error_rate",
        "operator": "gte",
        "value": 0.2,
        "severity": "critical",
        "cooldown_minutes": 5,
        "enabled": True,
    },
    {
        "threshold_id": "queue-depth-high",
        "name": "Ingestion queue depth high",
        "subsystem": "ingestion",
        "dimension": "queue",
        "metric_field": "queue_depth",
        "operator": "gte",
        "value": 100,
        "severity": "warning",
        "cooldown_minutes": 30,
        "enabled": True,
    },
    {
        "threshold_id": "p99-latency-too-high",
        "name": "P99 latency exceeds threshold",
        "subsystem": "api",
        "dimension": "performance",
        "metric_field": "p99_latency_ms",
        "operator": "gte",
        "value": 5000,
        "severity": "warning",
        "cooldown_minutes": 30,
        "enabled": True,
    },
    {
        "threshold_id": "drift-detected",
        "name": "Model data drift detected",
        "subsystem": "ml",
        "dimension": "model",
        "metric_field": "drift_score",
        "operator": "gte",
        "value": 0.7,
        "severity": "warning",
        "cooldown_minutes": 60,
        "enabled": True,
    },
]

def seed_defaults(db):
    """Seed minimal required default data (idempotent)."""
    logger.info("Seeding minimal default configuration...")
    
    # Seed alert thresholds - idempotent insert or update
    inserted = 0
    updated = 0
    
    for threshold in DEFAULT_ALERT_THRESHOLDS:
        existing = db.query(AlertThresholdDB).filter_by(threshold_id=threshold["threshold_id"]).first()
        
        if existing:
            # Update existing threshold with new defaults (safe to keep user changes? no, we just update to keep consistent)
            for key, value in threshold.items():
                setattr(existing, key, value)
            updated += 1
        else:
            new_threshold = AlertThresholdDB(**threshold)
            db.add(new_threshold)
            inserted += 1
    
    logger.info(f"Seeding complete: inserted {inserted} new thresholds, updated {updated} existing thresholds")
    
    # Add other minimal seeds here (strategy metadata, etc.) if needed in future

def verify_schema():
    """Verify that all tables are present in the database."""
    from data_layer.repositories.base import engine, Base
    from sqlalchemy import inspect

    inspector = inspect(engine)
    missing_tables = []
    
    for table_name in Base.metadata.tables.keys():
        if not inspector.has_table(table_name):
            missing_tables.append(table_name)
    
    if missing_tables:
        error_msg = f"Schema verification failed: missing tables: {', '.join(missing_tables)}"
        logger.critical(error_msg)
        raise RuntimeError(error_msg)
    
    logger.info(f"Schema verification passed: all {len(Base.metadata.tables)} tables are present")

def main():
    """Main bootstrap flow."""
    try:
        logger.info("Starting AlphaFoundry database bootstrap...")
        logger.info(f"Environment: {settings.APP_ENV}, Database: {engine.dialect.name}")
        
        # Step 1: Verify connectivity
        check_database_connection()
        logger.info("✅ Database connectivity verified")
        
        # Step 2: Initialize schema (create all tables, add missing columns for SQLite)
        ensure_schema()
        logger.info("✅ Schema initialization complete")
        
        # Step 3: Verify schema
        verify_schema()
        logger.info("✅ Schema verification passed")
        
        # Step 4: Seed minimal defaults (idempotent)
        db_gen = get_db()
        db = next(db_gen)
        try:
            seed_defaults(db)
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass
        
        logger.info("✅ All defaults seeded")
        logger.info("🚀 Database bootstrap completed successfully!")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"❌ Database bootstrap failed: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
