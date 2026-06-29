# Index Structure Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the database foundation for CSI, CNI, HSI, and WIND index constituents, stock-to-index membership lookup, index-linked ETFs, and ETF daily scale/flow metrics.

**Architecture:** Extend the existing SQLAlchemy market data models and `MarketDataRepository` instead of introducing a separate persistence stack. Keep Wind and official-site crawlers as source adapters that write normalized rows into provider-aware tables.

**Tech Stack:** Python 3.11, SQLAlchemy ORM, Alembic migrations, SQLite unit tests, PostgreSQL-compatible unique constraints.

---

### Task 1: Repository Tests

**Files:**
- Modify: `tests/unit/data_layer/repositories/test_market_data_repository.py`

- [x] Add failing tests for index providers, index master rows, component snapshots, stock membership lookup, ETF links, and ETF daily metrics.
- [x] Run `pytest tests/unit/data_layer/repositories/test_market_data_repository.py -q` and confirm the new methods/models are missing.

### Task 2: ORM Models And Migration

**Files:**
- Modify: `data_layer/repositories/models.py`
- Create: `storage/migrations/versions/011_add_index_structure_tables.py`

- [x] Add `IndexProviderDB`, `IndexMasterDB`, `IndexComponentSnapshotDB`, `ETFMasterDB`, `IndexETFLinkDB`, and `ETFDailyMetricDB`.
- [x] Add unique constraints matching repository upsert keys.
- [x] Add Alembic migration for the new tables and migrate legacy `index_component` data into `index_component_snapshot` when possible.

### Task 3: Repository Methods

**Files:**
- Modify: `data_layer/repositories/market_data_repository.py`

- [x] Add upsert methods for all new tables.
- [x] Update `upsert_index_components` to write `index_component_snapshot`.
- [x] Add `get_index_components`, `get_stock_index_memberships`, `get_index_etfs`, and `get_etf_daily_metrics`.
- [x] Keep SQLite fallback and PostgreSQL `on_conflict_do_update` behavior aligned.

### Task 4: Documentation

**Files:**
- Modify: `docs/DATA_STORAGE.md`
- Modify: `docs/modules/data_layer_repositories.md`
- Modify: `docs/FILE_GUIDE.md`
- Modify: `docs/CHANGELOG.md`

- [x] Document the new market structure tables and repository responsibilities.
- [x] Document that Excel/Wind workbooks are ingestion/diagnostic surfaces, while PostgreSQL is the long-term fact store.

### Task 5: Verification

**Files:**
- Read-only verification.

- [x] Run `pytest tests/unit/data_layer/repositories/test_market_data_repository.py -q`.
- [x] Run a focused syntax import check for `data_layer.repositories.models` and `data_layer.repositories.market_data_repository`.

### Task 6: Wind Probe And Official-Source Backfill

**Files:**
- Create: `services/wind_index_structure_probe.py`
- Create: `services/wind_index_structure_ingestion.py`
- Create: `services/official_index_structure_ingestion.py`
- Create: `scripts/run_wind_index_structure_probe.py`
- Create: `scripts/run_official_index_structure_ingestion.py`
- Create: `tests/unit/test_wind_index_structure_probe.py`
- Create: `tests/unit/test_wind_index_structure_ingestion.py`
- Create: `tests/unit/test_official_index_structure_ingestion.py`

- [x] Build a fixed Wind Excel probe workbook for index/ETF structure fields, with hidden Excel priming and cache reads.
- [x] Persist verified Wind ETF tracking-index, NAV, share, and AUM fields into the structure tables.
- [x] Add CSI/CNI official constituent ingestion through AKShare's CSIndex/CNIndex official-download wrappers.
- [x] Add CSI/CNI official catalog discovery for active index-code batches.
- [x] Add daily market-data scheduler job for official index structure ingestion.
- [x] Temporarily remove stale proxy environment variables around AKShare official downloads.
- [x] Run live Wind probe for sample CSI/CNI/HSI/WIND indices and ETF products; persist successful ETF rows.
- [x] Run live CSI/CNI official constituent ingestion for CSI `000300/000905/000852` and CNI `399001/399006`.
- [x] Run live active-catalog limited ingestion with `--discover-active --max-count 2`.
- [x] Verify `CSI:000300` components and `600519.SH` index membership from the structure database.
