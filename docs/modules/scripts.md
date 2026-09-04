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
- Node-executed `.js` scripts use ESM imports so they remain runnable under the root package's `"type": "module"` scope

---

## Files

## Desktop launch and packaging

### `scripts/desktop/backend_launcher.py`

Purpose:

- Starts the desktop FastAPI backend, workers, and crawl scheduler on the loopback-only desktop listener (`127.0.0.1` or `localhost`).
- Resolves the source root in development and `sys._MEIPASS` in a PyInstaller one-file bundle before starting the backend or child workers.
- Creates or migrates the per-user desktop `.env`, requires PostgreSQL + pgvector rather than silently creating a SQLite database, keeps user secrets out of launcher diagnostics, and refuses to terminate an unknown process that already owns the selected port.
- When `RESEARCH_PREVIEW=1` is set by the branch-preview launcher, verifies desktop readiness but does not start duplicate knowledge-worker or crawler watchdogs.

### `scripts/desktop/run_preview.js`

Purpose:

- Starts the current Git worktree in a separate Tauri development instance, using a temporary Tauri configuration with a dedicated loopback port (default `8766`).
- Reuses an available Tauri CLI from another Research Workbench worktree when the current worktree has no `node_modules`, so previewing does not require copying project dependencies.
- Uses temporary runtime data by default; `--use-stable-data` explicitly reuses the user's desktop configuration for full-workbench acceptance while the preview environment disables startup mutation and background work.

### `scripts/desktop/build_sidecar.py`

Purpose:

- Packages `backend_launcher.py`, application modules, frontend assets, built-in industry graphs, report templates, and report projects into the self-contained Tauri sidecar.
- Produces platform-specific sidecar names for Tauri; the frozen launcher resolves its bundled project root from PyInstaller resources.

### `scripts/desktop/sidecar_launcher.py`

Purpose:

- Provides a development shim that requires an explicit, existing project root instead of falling back to a developer-specific filesystem path.

Update this section when:

- Desktop launcher configuration, branch-preview behavior, bundled resources, worker startup, or platform path behavior changes.

---

### `scripts/generate_py_file_index.py`

Purpose:
- Generates Python file index documentation
- Parses source files for classes, functions, imports
- Outputs to docs/generated/py_file_index.md
- Scans the following directories (INCLUDE_DIRS): `app/`, `connectors/`, `core/`, `data_layer/`, `knowledge_layer/`, `reasoning/`, `cognitive_agents/`, `timing_engine/`, `signal_lab/`, `memory_learning/`, `reporting/`, `services/`, `storage/`, `ingestion/`, `cron_jobs/`, `scripts/`, `workers/`

Update this section when:
- Parsing logic changes
- Output format changes
- Included directories change

### `scripts/migrate_lsh_theme_data.py`

Purpose:

- Discover the reviewed LSH theme CSV set and route rows only through installed Pack manifests.
- Default to `--dry-run`; `--apply` is explicit and uses the configured database transaction.
- Emit accepted, quarantined, rejected, duplicate and applied counts plus per-file SHA-256 hashes and resumable checkpoints.
- `--resume-from` accepts only a checkpoint whose source hash still matches; a changed file must restart and cannot silently continue at an old row number.
- Preserve all mapped measures from wide rows as separate Observations. Identity collisions with different values are quarantined as `identity_conflict`, never counted as harmless duplicates or overwritten.
- Keep strategy, trading, fund approval, `score_hint` and `driver-summary` inputs frozen/rejected rather than migrating them into facts.

Update this section when:

- LSH discovery, mapping, identity, resume, report or commit semantics change.

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
- Detects source changes with NUL-delimited Git output (includes individual untracked files)

Research Web uses the repository-owned `scripts/check_research_architecture.mjs` core,
also invoked by `.agents/project-constraints.mjs` and the existing Project Constraints CI.
`check_doc_sync.py` accepts `--project`, `--base` and repeated `--changed-file`, using
NUL-delimited Git output to include individual untracked files and failing closed on Git errors.
The shared core checks all eight required diagrams, current API/source/test references,
canonical links, byte hashes, showcase 9/9 receipts, four viewport containment receipts,
and explicit same-hash human screenshot reviews. Source changes require mapped Markdown
and an `architecture-review` marker in the review record; unknown Research Web source fails.
No global Archify installation or network is required. JSONL diagnostics are written under
`logs/research-architecture-check.jsonl`; Python also uses the project logging facility.
Invalid top-level maps and unsupported HTTP declaration syntax fail closed; literal positional
and `path=` keyword routes are checked. Generated artifact/receipt paths use fixed canonical
filenames. CI checks Git's exit status before consuming NUL-delimited changed filenames.
Full CLI/security/update contracts and fixture tests are documented in
[Research Web documentation gate](../research-web-documentation.md).

Update this section when:
- DOC_RULES mapping changes
- Check logic changes
- Required docs change

### `scripts/desktop/backend_launcher.py`

Purpose:
- Starts the FastAPI desktop backend and its knowledge-worker and crawl-scheduler watchdogs.
- Resolves the shared project/resource root with `RESEARCH_PROJECT_ROOT` first, then PyInstaller's `sys._MEIPASS` for frozen one-file sidecars, and finally the source-tree fallback.
- Passes that resolved root as the backend cwd and to watchdog child environments, so frozen processes load bundled resources from the same self-contained directory.

Update this section when:
- Desktop root-resolution precedence changes.
- Sidecar, watchdog, or worker startup behavior changes.

---

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
- Type boundaries: financial rows and forward-return inputs normalize pandas/DB scalar values through explicit optional float/date conversion before arithmetic, keeping recovery/seed flows compatible with strict mypy checks.

Update this section when:

- Factor definitions change
- Factor computation formula changes
- Data source fallback behavior changes
- Rate limiting or retry strategy changes
- Checkpoint/resume mechanism changes
- New `--source` or data ingestion methods are added

---

### `scripts/update_huaan_chart_workbook_excel.py`

Purpose:

- Uses Microsoft Excel via `xlwings` to update `report_projects/华安ETF周报/data/周报图表.xlsx`.
- Rebinds gold and crude-oil chart series to the left-side Wind data ranges.
- Removes duplicate right-side copied data ranges from the workbook sheets.
- Saves a backup under `report_projects/华安ETF周报/data/backups/` before writing.

Operational notes:

- Requires a local Excel/xlwings environment.
- The script intentionally uses Excel rather than ZIP-level XLSX mutation because Excel is stricter about chart XML and relationship consistency.
- It logs workbook open/save and chart-series updates through `core.observability`.

Update this section when:

- Huaan workbook sheet names, chart source ranges, or backup behavior changes.
- Excel automation behavior or dependencies change.

---

### `scripts/run_official_index_structure_ingestion.py`

Purpose:

- Runs CSI/CNI official constituent ingestion into `index_component_snapshot`.
- Defaults to CSI `000300/000905/000852` and CNI `399001/399006`.
- Supports `--provider CSI|CNI|all` and repeated `--index-code`.
- Supports `--discover-active --max-count N` to read active index codes from official provider catalogs; `--max-count 0` removes the cap.
- Uses `services.official_index_structure_ingestion`, which temporarily clears proxy environment variables around AKShare official downloads.

Update this section when:

- Default index universe changes.
- Provider options change.
- Official ingestion output or error handling changes.

---

### `scripts/run_wind_index_structure_probe.py`

Purpose:

- Builds and optionally primes the fixed Wind Excel probe workbook for index/ETF structure fields.
- Supports hidden Excel calculation with `--prime`, cached result output with `--read`, and database persistence with `--persist`.
- `--skip-build` reads an existing workbook cache without overwriting freshly calculated values.

Update this section when:

- Probe workbook sheets or formula catalog changes.
- CLI options change.
- Persistence mapping changes.

---

### `scripts/switch_huaan_word_template_to_native_charts.py`

Purpose:

- Updates `report_projects/华安ETF周报/templates/report_template.docx` so selected chart placeholders become native Word chart drawings.
- Copies chart XML from `report_projects/华安ETF周报/data/周报图表.xlsx` where configured.
- Updates DOCX relationships and content types, then writes a backup under `report_projects/华安ETF周报/templates/backups/`.

Operational notes:

- This script mutates the DOCX package structure and should be run only after the workbook chart XML is known good.
- It logs backup and relationship replacement details through `core.observability`.

Update this section when:

- Huaan Word template media targets, chart relationship ids, chart XML parts, or backup behavior changes.
- DOCX chart replacement semantics change.

---

### `scripts/desktop/`

Purpose:

- `run_backend.js` is the ESM Tauri development bridge: it derives its directory from `import.meta.url`, delegates to `run_backend.cmd` on Windows and `run_backend.sh` on macOS/Linux, and forwards process arguments and exit status.
- `build_sidecar.py` packages `backend_launcher.py` as the self-contained PyInstaller sidecar, collecting backend submodules, third-party package data, and required project assets, including `data/industry_graphs/`.
- `backend_launcher.py` creates an editable per-user `.env` for frozen builds; an absent or unusable `DATABASE_URL` leaves the application in setup-required mode instead of creating a SQLite fallback.

Update this section when:

- Desktop launch routing, ESM compatibility, sidecar packaging inputs, or frozen-build defaults change.

---

### Other `scripts/*.py`

Purpose:
- Database bootstrap and migration
- Backup and restore operations
- Smoke tests and verification
- Data import and export
- Operational utilities

Typing notes:
- Backup/restore scripts narrow subprocess commands and pipe handles before use.
- Recovery scripts coerce ORM `Column`-typed fields such as document ids, content hashes, and signal ids into runtime strings at service/reporting boundaries.
- Derived-state rebuild scripts must construct `TimingModelScore` with complete contract fields and keep active weights outside the score object.

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
