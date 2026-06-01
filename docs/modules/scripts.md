# Module: scripts

## Responsibility

`scripts` provides operational scripts, database bootstrap, backup/restore, smoke tests, and development governance checks.

---

## Design Rules

- Scripts should be self-documenting
- Provide --help for all scripts
- Make destructive operations explicit
- Add dry-run mode when feasible
- Add or update tests when script behavior changes

---

## Files

### `scripts/generate_py_file_index.py`

Purpose:
- Generates Python file index documentation
- Parses source files for classes, functions, imports
- Outputs to docs/generated/py_file_index.md

Update this section when:
- Parsing logic changes
- Output format changes
- Included directories change

### `scripts/check_task_completion.py`

Purpose:
- Verifies source changes have corresponding tests/docs/reports
- Checks git diff and untracked files for changes (via shared `core/utils/git.py`)
- Ensures CHANGELOG is updated

Update this section when:
- Check logic changes
- Required file patterns change
- Failure criteria change

### `scripts/check_doc_sync.py`

Purpose:
- Verifies source changes have corresponding documentation updates
- Maps source directories to required docs
- Ensures generated index is updated
- Detects changes via shared `core/utils/git.py` (includes untracked files)

Update this section when:
- DOC_RULES mapping changes
- Check logic changes
- Required docs change

### `scripts/backfill_missing_llm_extraction.py`

Purpose:
- Finds documents in `document_v1` missing corresponding LLM extraction results in `canonical_event`.
- Enqueues them into the ingestion queue via `CrawlOrchestrator._enqueue_items()` so KnowledgePipeline can perform LLM extraction.
- Supports `--dry-run` preview and `--batch` for batch size control.
- Related: `services/crawl_orchestrator.py`, `ingestion/knowledge_pipeline.py`.

Update this section when:
- Backfill query logic changes
- Enqueue batching behavior changes

---

### `scripts/cleanup_dedup_orphans.py`

Purpose:
- Cleans orphan entries from file-based CLS crawler dedup state (`DeduplicationStore`)
- Queries `document_v1` for valid `source_doc_id`s, removes any dedup entries without matching DB rows
- Prevents permanent crawl skip when documents are deleted from DB but dedup file retains IDs
- Supports `--dry-run` preview

Update this section when:
- Dedup state file paths change
- Cleanup logic changes

---

### `scripts/backfill_pdf_artifacts.py`

Purpose:
- Scans `data/crawlers/zq/pdfs/` for existing PDF files not yet registered in `pdf_artifact_v1`
- Computes SHA-256 hash for each file, creates `PDFArtifactV1DB` records with `parse_status='pending'`
- Skip files already registered (hash-based dedup)
- Registered PDFs are automatically picked up by `CrawlScheduler` → `PDFConversionService` within 5 minutes
- Supports `--dry-run` preview

Update this section when:
- PDF root directory changes
- Registration fields change

---

### `scripts/seed_factor_data.py`

Purpose:

- Seeds factor data pipeline from market data (AKShare) or Wind WSD
- **Phase 1**: Ingests `stock_master` + `stock_daily_bar` via AKShare (with rate limiting, retry, checkpoint) or Wind WSD (single-call full time series per stock)
- **Phase 2**: Registers 10 factor definitions (momentum, reversal, liquidity, risk), computes factor values per trading day, runs evaluation cycle via `FactorComputationService`
- **Phase 3**: Ingests financial data via AKShare, registers 8 financial factor definitions (VALUE/QUALITY/GROWTH/RISK), computes quarterly factor values
- Supports `--skip-ingest`, `--stock-count`, `--symbols`, `--source`, `--delay`, `--max-retries`, `--resume`, `--date-start`, `--date-end`, `--skip-financials`, `--no-akshare-direct` CLI options

Key features:

- **双数据源**: `--source akshare` (默认)、`--source wind` (Wind Excel 插件 WSD)、`--source auto` (Wind 优先，不可用时自动降级 AKShare)
- **限流处理**: AKShare 请求间延迟 (`--delay`, 默认 2s)、指数退避重试 (`--max-retries`, 默认 3 次)、限流关键词检测 (频率/rate limit/429/throttle)
- **断点续传**: JSON checkpoint 每 10 只保存 (`--resume` 恢复), Wind/auto 模式自动生成 checkpoint
- **Wind WSD 集成**: `ingest_daily_bars_from_wind()` 单次 WSD 调用获取完整时间序列 (比 AKShare 逐只请求更高效)
- `_fetch_akshare_hist_with_retry()`: 带指数退避重试的 AKShare stock_zh_a_hist 封装
- `_normalize_akshare_hist()`: AKShare DataFrame → stock_daily_bar dict 转换
- `_wsd_to_daily_bars()`: Wind WSD list[list] → stock_daily_bar dict 转换
- `_is_wind_available()`: Wind 终端可用性检测
- `_save_checkpoint()` / `_load_checkpoint()`: JSON 断点持久化/恢复

Update this section when:

- Factor definitions change
- Factor computation formula changes
- Data source fallback behavior changes
- Rate limiting or retry strategy changes
- Checkpoint/resume mechanism changes
- New `--source` or data ingestion methods are added

---

### `scripts/debug_wind_formulas.py`

Purpose:
- Debug tool for Wind Excel formulas
- Tests individual Wind formulas against a given stock code and date
- Reports which formulas return data and which fail
- Useful for verifying formula availability on Mac Wind

Update this section when:
- New debug commands are added
- Formula test patterns change

---

### `scripts/seed_stock_master_static.py`

Purpose:
- Seeds the `stock_master` table with static A-share stock data
- Provides a fallback when AKShare is unavailable for stock list bootstrap
- Includes hardcoded stock codes and names for common A-shares

Update this section when:
- Seed data is updated
- Stock list is expanded

---

### Other `scripts/*.py`

Purpose:
- Database bootstrap and migration
- Backup and restore operations
- Smoke tests and verification
- Data import and export
- Operational utilities

Update this section when:
- New scripts are added
- Script behavior changes
- Operational workflow changes
- Backup/restore behavior changes

---

## Required Tests

- Script behavior tests when feasible
- Dry-run mode tests
- Error path tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/scripts.md`
- `docs/REFERENCE.md` (when user-facing)
- `docs/backup_restore.md` (when backup/restore changes)
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`