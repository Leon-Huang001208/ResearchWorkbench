# Module: scripts

The optional `backup_fd_clone.mjs` / `backup_fd_clone.py` primitive only copies
from an already-open source FD into a private directory FD on supported Darwin
systems. The fixed standard-library helper accepts no arbitrary command; Node
rechecks full bytes, identities and privacy before reporting success. It neither
falls back nor removes data. The backup caller retains path/race guards, capacity
admission, fsck and actual restore. No existing backup call site is switched by
this first checkpoint; unsupported/error/unknown and platform limits are explicit
in the [task report](../../.ai/reports/test_report_backup_cow_admission_20261030.md).

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

### `scripts/run_ci_pytest_partitions.py`

Purpose:
- Schedules the two preselected Python pytest scopes in the existing Research Web Checks job as two independent processes.
- Collects the scope's actual node IDs, deterministically partitions them with a disjoint complete union, and has both workers verify that their collection matches the parent manifest before execution.
- Keeps each worker's basetemp, pytest cache, JUnit XML, result record, and stdout/stderr log under an owner-checked private task temp root. The scheduler holds both worker Popen objects and validates their PID, UID, root inode, worker index, schema, plan digest, exact execution IDs, and exact JUnit `rwb_nodeid` mapping before reporting PASS. Collection errors, missing/changed nodes, test failures, worker errors, malformed results, and interruption fail closed; skips remain in JUnit.
- Limits failure `errorClass` to the same fixed built-in/`PartitionError`/`UnknownError` enumeration used by the artifact stager. Unknown identifier-shaped pytest messages become `null`; unknown exception objects become `UnknownError`, so a private failure body or custom class name cannot become public taxonomy.
- Does not change selected test paths/configuration, add jobs/runners/dependencies, or infer that the 45-minute GitHub timeout will pass. The exact candidate CI duration is still measured remotely.

`tests/unit/test_ci_pytest_partitions.py` exercises partition integrity, independent worker evidence, visible skip/failure, collection failure, and interruption behavior.

### `scripts/stage_ci_pytest_evidence.py`

Purpose:
- Reads only the fixed Research Web Checks task roots and evidence filenames through owner-checked directory descriptors and `O_NOFOLLOW` file opens.
- Rejects symlink, hardlink, non-regular, replaced, cross-device, or wrong-owner inputs. It verifies source inode/size/timestamps before staging and checks the parent directory identities again before returning.
- Produces a fresh `artifacts/research-web-checks/` directory with sanitized JUnit nodeID properties, manifests, PID/status summaries, and redacted summary logs. For failed workers, it may include only the runner's fixed-schema `phase`, fixed-enumeration exception class (or `null`), and stable error code; arbitrary identifier-shaped classes are rejected. Raw result errors, JUnit output bodies, environment, and worker stdout remain unstaged.
- Fails if staging paths already exist, if the output tree is replaced, or if sanitized evidence exceeds the 100 MiB per-run cap.

`tests/unit/test_ci_pytest_evidence_staging.py` exercises ordinary staging, external symlinks, hardlinks, root symlinks, parent-directory replacement, raw schema-v3 taxonomy rejection, and a real worker failure whose private custom exception name must not reach the artifact.

### `scripts/setup_web.py`

Optional Hot installation consumes only `services/hot/package-lock.json` using the
selected product Node/npm and `npm ci --omit=dev --ignore-scripts --no-audit --no-fund`.
Missing locks or a failed install retain explicit failure; this step neither starts
PostgreSQL nor creates model authorization. It runs inside the existing installation
scope before publishing the manifest. Hot's one-shot report module uses the same
installed Web Python dependencies; schema upgrades remain an explicit stopped Hot setup.

`scripts/build_research_web_api_atlas.mjs` includes the signed-reader periodic report
download in the current API inventory. Regeneration binds the source/map inputs;
generated HTML is navigation evidence, not acceptance of a live report or platform.

Internal `_NativePortOptions` describes only the existing explicit port keywords. Type casts reuse
validated facts; they do not create defaults, broaden accepted input, or change installer errors.

Native public auto-start reexecutes the same script/arguments in the exact marked checkout venv before
creating the product root. The actual manager creates the root under its real lifecycle lease, completes
DSH/build-lock/manifest, and starts through the verified same-lease entry. Outer-home UID/0700 preparation
reuses the existing boundary; Native no-start/check-only do not gain Native creation authority. Old roots/replacements
and observer/lease changes remain refused; no global package or public flag is added.

Docker no-start selection may retain only a missing-product-root observation under the controller's own
outer real lifecycle lease with a pinned private parent, absent Native records/endpoints and no containers.
It publishes the original image/mode metadata without product-root, controls, PID or endpoint creation;
the observation ends with the call and cannot authorize a later start. Standard first start independently
rechecks absence, performs real private mkdir and pins its root inode/descriptor in that same transaction.
Allocation authority expires before up; existing roots/containers never gain the fresh exception. Exact
attempt recovery under the original lease/root/parent/listener/CAS facts retains the initial error with
stable recovery diagnostics, never deletes user data or serializes a witness.

Docker selection publication retains the manifest writer's held-FD identity. A later failure restores
the previous receipt only while both the published bytes and inode still match; same-content inode
replacement fails closed with `docker_install_summary_recovery_unverified` and is not overwritten.

Purpose:

- Implements the shared macOS/Windows Web bootstrap used by `setup-web.sh` and `setup-web.cmd`; `--runtime` defaults
  to Native, while Docker uses the same pinned Web/DSH contract and a separate accepted-image manifest.
- On Native, creates only an installer-owned checkout `.venv`, consumes `requirements/web.lock` with hashes, installs the
  root package without dependencies, and verifies the vendored `cjpy==0.5.2` wheel and transport dependencies.
- Clones, checks out and builds the pinned DSH commit with its declared pnpm version; a user-private Corepack shim
  keeps nested DSH build commands independent from global pnpm. The first successful build records a path-specific
  closure attestation that Doctor rechecks on later runs. Clone, checkout, and dirty-worktree verification share
  command-level long-path and line-ending settings, so the same pinned source can be materialized and verified on
  Windows without machine-level Git settings. Windows also uses `core.symlinks=false` for all three operations, so
  Git's regular-file representation of repository symlinks is accepted consistently without weakening checks for
  other tracked changes.
- Rejects unsupported Python/Node versions, unknown managed directories, links/reparse points, mismatched hashes,
  dirty or wrong DSH sources, and incomplete builds. `--repair` is limited to directories bearing this installer's
  ownership marker.
- On Docker, builds an independent candidate tag and checks its immutable image ID and lock/Compose/runtime contract
  before publishing the private accepted-image manifest. Default start waits for both DSH and Web health; `--no-start`
  records only an accepted build. A different old container image requires explicit `--repair`, which rechecks stopped
  ownership before a non-force removal; failed candidates preserve the prior accepted image and data.
  Windows Docker fails closed while credential-directory ACL preparation cannot be proved.
- macOS public setup accepts `--web-port`, and Native additionally `--runtime-port`; explicit occupied ports fail.
  `--no-start` does not allocate ports or alter control origins. A starting Docker candidate keeps its origin
  transaction under the shared lifecycle lease until manifest/mode publication; exact cleanup and endpoint CAS
  restoration preserve the previous accepted installation on failure. Trusted portless temporary guests may
  fill missing controls with the existing creators, but do not mount credentials or change existing tokens.
- Passes application secrets to neither pip nor Node/Git build commands. Git may retain the host's proxy settings;
  pip and Corepack/Node keep only HTTP(S) proxy protocols across upper- and lower-case variables. Filtering records
  only a bounded count, never a proxy value, and does not mutate the host environment. macOS discovers libc++ headers through `xcrun`, and Windows
  retains only the standard system paths needed for `node-gyp`/MSBuild to discover and run an already installed
  Visual Studio C++ toolchain.

Update this section when:

- The Web prerequisite range, Python lock, CJPY bundle/checkout byte policy, DSH identity/build/Corepack shim,
  ownership marker, safe environment or public setup flags change.
- `rwb web doctor`, clean-install CI, or the user-facing installation contract changes.

## Desktop launch and packaging

### `scripts/desktop/backend_launcher.py`

Purpose:

- Starts the desktop FastAPI backend, workers, and crawl scheduler on the loopback-only desktop listener (`127.0.0.1` or `localhost`).
- Resolves the source root in development and `sys._MEIPASS` in a PyInstaller one-file bundle before starting the backend or child workers.
- Creates or migrates the per-user desktop `.env`, requires PostgreSQL + pgvector rather than silently creating a SQLite database, keeps user secrets out of launcher diagnostics, and refuses to terminate an unknown process that already owns the selected port.
- When `RESEARCH_PREVIEW=1` is set by the branch-preview launcher, verifies desktop readiness but does not start duplicate knowledge-worker or crawler watchdogs.
- `RESEARCH_CRAWLER_AUTOSTART=0` keeps the knowledge worker available but prevents the crawl-scheduler watchdog from starting after an application restart; explicit manual scheduler starts remain available.

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
- `--check` compares the committed index with deterministic generated content without writing files
- Scans the `INCLUDE_DIRS` declared in the script; the list is code-owned and must not be copied into other current documents

Update this section when:
- Parsing logic changes
- Output format changes
- Included directories change

### Documentation governance

- `scripts/check_documentation_governance.mjs` validates that every tracked or untracked Markdown file is classified by `docs/documentation-governance.json`.
- The same check enforces one current authority per topic, current relative links and anchors, retired-command exclusions, and explicit archive banners.
- `scripts/check_doc_sync.py` composes governance, generated-index and Research Web architecture checks, then applies narrow compatibility-module owner mappings.
- Research Web architecture decisions are recorded in the changed task report under `.ai/reports/`, not appended to a permanent review log.

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
The shared core checks all ten required diagrams, current API/source/test references,
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

`scripts/git_safety.mjs`同时拥有项目受管交付与资源收尾编排：修补feature tip须证明其干净、同任务且已进入候选；合并及CI通过后调用`research_workbench_entrypoint/iteration_resources.py`与`iteration_cache.py`，复用原Docker资源清理和原Git安全备份。资源ledger/证据/回执保留在common Git私有目录，受管缓存合计20GiB，状态失败不冒充cleaned。近处回归为`iteration_closeout.test.mjs`与`test_iteration_resources.py`；无产品路由、依赖或后台定时器变更。

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
- `docs/REFERENCE.md` (only when user-facing commands change)
- `docs/backup_restore.md` (when backup/restore changes)
- `docs/CHANGELOG.md` (only for user-visible behavior)
- `docs/generated/py_file_index.md` with `--check`; regenerate only when public Python structure changed


## 2026-10-24：Git pending 收尾恢复

Git管理面新增 closeout-recover：默认预览不fetch；执行绑定预览、v2备份实际恢复、原引用审计/完整性及资源预算，追加epoch而保留原pending证明。只处理原证明/备份覆盖的特定Codex树快照消失，未知删除仍拒绝。不新增产品服务、HTTP、依赖、研究引擎或租户权限，常驻活动任务门不变。 Python revalidate只观察退休目录/剩余任务对象，并经原ManagedCaches检查20GiB合计预算，不重放目录或卷删除；实际恢复、CI和Mac安装另证，Windows/Linux原生仍交接对应设备。步骤见AGENT_WORKFLOW的pending finalization重新核验。

已正式完成的其他任务分支/worktree退休仅作为另一种独立证据接纳：唯一精确managed归属、同仓库/remote、CI与独评、最终证明和资源回执均complete、旧提交至声明tip/最终候选/主线祖先链成立；四原件字节与哈希固定到epoch。pending/未知owner、目录重现、归属不唯一仍拒绝，不递归调用他任务status或操作其资源。preview同时禁止Git隐式lazy fetch及replace映射；fsck失败输出退出码/信号与输出摘要哈希，不输出对象内容。
