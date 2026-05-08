# Backup, Restore, and Migration Discipline

This document describes the operational hygiene for persistent data in AlphaFoundry, covering automated backup, restore procedures, restore drills, and schema migration discipline.

## Table of Contents

1. [Backup Procedures](#backup-procedures)
2. [Restore Procedures](#restore-procedures)
3. [Restore Drill Checklist](#restore-drill-checklist)
4. [Schema Migration Discipline](#schema-migration-discipline)
5. [Data Storage Responsibility Matrix](#data-storage-responsibility-matrix)

---

## Backup Procedures

AlphaFoundry provides automated backup scripts supporting both PostgreSQL (primary) and SQLite (development).

### Automated Backup (PostgreSQL Production)

```bash
# Basic usage (reads DATABASE_URL from .env, stores backups in ./backups, keeps 30 days of backups)
./scripts/backup_db.py

# Custom output directory and retention
./scripts/backup_db.py --output-dir /path/to/backups --retention 90
```

#### Retention Guidance

- Production: keep **30-90 days** of daily backups
- Staging: keep **7-14 days** of daily backups
- Development: keep **3 days** of daily backups (or disable automatic backups)

Backup files are automatically compressed with gzip to save space.

### Backup for SQLite

If you're using SQLite in development:

```bash
./scripts/backup_db.py --sqlite-path ./data/alphafoundry.db
```

Or if your DATABASE_URL is already configured for SQLite:

```bash
./scripts/backup_db.py
```

---

## Restore Procedures

### Full PostgreSQL Restore

To restore from a backup:

```bash
# Create and restore to fresh database
./scripts/restore_db.py /path/to/backups/backup_20250101_000000.sql.gz --create-db --drop-existing
```

Options:
- `--drop-existing`: Drop the existing database before restore (use with caution!)
- `--create-db`: Create the database if it doesn't exist
- `--database-url`: Override the DATABASE_URL from .env

### Local Testing Restore

You can test restore locally by restoring to a different database:

```bash
# Set up a test database in PostgreSQL
createdb alphafoundry_test

# Restore the backup to the test database
./scripts/restore_db.py ./backups/backup_<timestamp>.sql.gz --database-url postgresql://user:password@localhost:5432/alphafoundry_test
```

### SQLite Restore

```bash
./scripts/restore_db.py /path/to/backup.sql.gz --sqlite-path ./data/alphafoundry.db
```

---

## Restore Drill Checklist

Perform a restore drill **quarterly** to validate backups and ensure the team can recover from data loss.

### Pre-Drill

- [ ] Identify a recent backup to restore from
- [ ] Provision a clean test environment (separate database from production/staging)
- [ ] Ensure all team members who might need to perform recovery have access to the backup storage

### Drill Steps

1. [ ] Create a new empty database
2. [ ] Run the restore command per [Restore Procedures](#restore-procedures)
3. [ ] Wait for restore to complete
4. [ ] Check the restore logs for any errors or warnings
5. [ ] Start the application connected to the restored database
6. [ ] Run application health checks
7. [ ] Verify key metrics:
   - [ ] Number of records in major tables matches expectations
   - [ ] Embeddings are intact
   - [ ] Document metadata is correct
   - [ ] User authentication works
   - [ ] Ingestion pipelines can run against the restored database
8. [ ] Document the time taken to complete full recovery
9. [ ] Identify any gaps or issues

### Post-Drill

- [ ] Document the results in the session notes
- [ ] Fix any issues found during the drill
- [ ] Update this checklist if any steps are missing

**Success Criteria**: Full restore completes without errors and the application is fully operational within 30 minutes.

---

## Schema Migration Discipline

AlphaFoundry uses **Alembic** for SQLAlchemy schema migrations.

### Workflow for Schema Changes

1. **Make changes to your SQLAlchemy models** in the codebase
2. **Generate an automatic migration revision**:
   ```bash
   alembic revision --autogenerate -m "Description of the change"
   ```
3. **Review the generated migration**:
   - Check that all changes are captured
   - Verify that data migrations are correct (autogenerate doesn't always get data changes right)
   - Edit the migration file if needed
4. **Test the migration locally**:
   ```bash
   alembic upgrade head
   # Run any tests for your changes
   alembic downgrade -1  # Test rollback
   ```
5. **Commit the migration file** to version control
   - Migrations must be reviewed along with the model changes
6. **Apply to production**:
   ```bash
   alembic upgrade head
   ```

### Key Rules

- **Never modify existing migration files** after they've been merged to main branch. If you need to fix something, create a new migration.
- **Always test both upgrade and downgrade** locally before deploying.
- **Data migrations** must be done carefully:
  - Backward compatible changes are preferred when possible
  - Large table changes should be done during low-traffic periods
- **Review migrations** just like any other code changes - at least one approval required.

### Initializing Alembic

If you're setting up a new environment:

```bash
# Initialize alembic (already done for this project)
alembic init alembic
```

Update `alembic.ini` to set your sqlalchemy URL, or use the `.env` based configuration we have (we use env DATABASE_URL from the project).

---

## Data Storage Responsibility Matrix

This table clarifies what type of data belongs where:

| Data Category | PostgreSQL | Object Storage | Derived Rebuildable | Notes |
|---------------|------------|----------------|----------------------|-------|
| Document metadata (title, author, date, source) | ✅ | | | Relational data for querying |
| Document chunk embeddings | ✅ | | | indexed with pgvector |
| User accounts, credentials, settings | ✅ | | | Core relational data |
| Raw original documents (PDF, DOCX, images) | | ✅ | | Large binary files |
| Processed text extractions | | ✅ | | Stored as text/json files |
| Cached LLM responses | | | ✅ | Can be reconstructed from source |
| Derived signal scores, rankings | | | ✅ | Can be rebuilt from raw data and code |
| Ingestion pipeline state/checkpoints | | ✅ | | Intermediate artifacts |
| Application logs | | ✅ (or external logging) | | Log files rotated automatically |

### Definitions

- **PostgreSQL**: Structured relational data, queryable, transactional. Must fit within reasonable database size (~10s of GBs).
- **Object Storage**: Large unstructured files, binary blobs, immutable artifacts.
- **Derived Rebuildable**: Data that can be completely reconstructed from the source data stored in PostgreSQL + object storage using existing code. It's acceptable to store these for performance, but we don't need to back them up as they can be rebuilt.

---

## Troubleshooting

- **pg_dump/psql connection errors**: Check your DATABASE_URL, PGPASSWORD, and that PostgreSQL is running and accessible from the machine you're running the backup/restore on.
- **Migration errors**: Always check Alembic docs and make sure you're on the correct migration head. If you get stuck, you can compare the current schema to the models and generate a new migration to bring it into sync.
- **Restore is slow**: For large databases, consider using pg_dump custom format and parallel restore for faster restores. Our current script uses plain SQL for maximum compatibility, but you can modify it for your needs.
