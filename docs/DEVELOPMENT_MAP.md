# Research Workbench Development Map

This file maps Research Workbench subsystems to source files, tests, and required documentation updates.

## Current Web research implementation (2026-09-04)

Research Web now lives in `app/research_web/`, with entrypoint `app.research_web.main:app` and `/api/research/`.
Read the canonical [Research Web architecture](architecture/research-web/README.md),
[implementation notes](research-web.md) and [UI contract](research-web-ui.md) first for this product.
The machine-readable [architecture map](architecture/research-web/architecture-map.json) connects
current source modules, Markdown, diagrams and tests. Local acceptance is recorded separately from structural consistency.
The legacy subsystems below remain historical implementations, not dependencies to add to this new chain.
Tests: `tests/research_web/` (use `--confcutdir=tests/research_web`) and `tests/javascript/research_web*.test.mjs`.
DSH owns the execution loop, skills, subagents and transcript; no second orchestration/fact database.
Tabbit integration lives in `app/research_web/tabbit.py`, `app/research_web/runtime/tabbit-adapter.mjs`,
`app/research_web/launch_runtime.py`, `ui/composer.mjs`, `ui/settings.mjs` and the pinned
`vendor/dsh-tabbit/0.3.4/` archive. Read [the Tabbit contract](research-web-tabbit.md) before changing
its staging, loopback API, claim/token lifecycle or UI. Regression coverage is in
`tests/research_web/test_tabbit.py`, `test_runtime_launch.py`, `test_api.py`, `test_protocol.py`,
`tests/javascript/research_web_tabbit_adapter.test.mjs`, `research_web_tabbit_ui.test.mjs`,
`research_web_guard.test.mjs` and `research_web_settings_ui.test.mjs`.
Windows staging regressions must cover UTF-8 text, POSIX tar member names, closed-handle atomic
replacement, forward-slash adapter serialization, DSH auth-file identity, DataHub snapshot publication,
safe downloads and read-only purge; CI remains simulator-only until real browser smoke.
The product topbar keeps healthy runtime state silent and exposes only actionable configuration or
availability states; page-scoped refresh controls remain owned by their existing modules.
Settings uses five mutually exclusive hash subpages rendered by `ui/settings.mjs`; `ui/app.mjs` retains
control of catalog loads, form submissions and errors. Remote DataHub sources and local platform
integrations are filtered before rendering. The data subpage is a category-first workbench implemented
by `ui/connections.mjs` and `ui/appearance.css`: 21 remote sources remain discoverable through three
group tabs, global search and status filtering, while the selected source reuses the existing configuration
form inside a closable detail drawer. Its DOM contracts are covered by
`tests/javascript/research_web_connections_ui.test.mjs`; responsive interaction and overflow are covered by
`tests/e2e/research_web_connections_workbench.mjs` at 1440×1000, 768×1024 and 390×844.
The local subpage is a separate diagnosis console in `ui/connections.mjs`. It reads
`app/research_web/local_integrations/` through dedicated catalog and idempotent probe endpoints, and shows
discovery, authorization, verification and callable as four independent facts for every item. Its top
summary contains only local-service health, available items and actionable items; `不适用` is not actionable.
The DataHub connection endpoints and remote data-source workbench contract remain unchanged.
DataHub catalog, brand-neutral business tools, broker, Provider, probe and snapshot contracts live in `app/research_web/datahub/`, `app/research_web/launch_runtime.py`, `app/research_web/runtime/public-data.mjs` and [DataHub](research-web-datahub.md). `catalog.py` is the no-network source of truth for the 15-capability / 22-source UI. `datahub/connections.py` owns per-source local non-secret configuration, OS keyring boundaries and the explicitly confirmed legacy-environment migration; `providers_mysql.py` owns MySQL privilege checks, exact schema identifiers and bounded single-table reads. The Settings UI reads the safe `/data/connections` projection and generic source-configuration endpoints. Runtime start/restart materializes only tools whose capability has `callable_source_count > 0`. The legacy connector map below does not make a Research Web provider callable.

`app/research_web/datahub/security.py` keeps descriptor-relative, no-follow IO on POSIX and a Windows-only path fallback for private control files, receipts and immutable snapshots. The fallback validates canonical containment, reparse points, regular-file identity, hard-link count and size, and closes file handles before atomic replacement. `client.py` applies the same Windows identity boundary to the DSH auth record; `store.py` applies it to downloads and restores owner-write permission only inside product-owned trees during purge. Native `windows-2022` CI must start the full loopback service before local-integration support is considered verified.
`app/research_web/runtime_auth.py` is the shared DSH authentication-record reader for `client.py` and `service_manager.py`. It bounds content, rejects aliases and identity replacement on every platform, applies POSIX mode checks only on POSIX, and is exercised by the same native Windows service smoke test.
`app/research_web/service_manager.py` applies the same platform distinction to its private data, state and log directories: type, symlink and Windows reparse checks remain universal, while group/other mode checks remain POSIX-only.

Research Web 的内置能力元数据由 `app/research_web/capabilities/seeds.py` 声明；能力包源码位于
`app/research_web/skills/<slug>/`。当前主分支的六个既有 Skill 加五个专用 Skill 共 11 项，四个
Workflow 保持原有执行边界。`app/research_web/skills/_shared/evidence-protocol.md` 是专用 Skill 的共享证据
协议源码，构建时复制到每个包的 `references/` 并进入不可变版本哈希；它本身不进入发现目录。
研报增量能力另含 `scripts/validate_digest.py` 和 `scripts/render_knowledge_graph.py`，在既有研究沙箱
内运行并复用 `research_helpers.read_pdf`，不得调用宿主进程。检查、种子、导出与会话快照覆盖在
`tests/research_web/test_capabilities*.py` 和 `tests/research_web/test_sell_side_report_skill.py`；
分类、详情、选择、搜索及无路由卡片覆盖在
`tests/javascript/research_web_capabilities_ui.test.mjs`；该测试从项目 Python 环境中的真实
`CapabilityCatalog.list(kind="skill")` 获取目录，不维护第二份内置元数据。契约文档见
[能力包与版本](research-web-capabilities.md)及
[架构能力管理](architecture/research-web/07-capabilities.md)。

能力工作区 v0 的聚合与可访问快览位于 `app/research_web/ui/capability-workspace.mjs`，由
`app.mjs` 组合 capabilities、tools、report-workflows、data catalog 与 connections 的现有安全投影。
`core.mjs` 将 `kind=skill|tool|workflow|data` 解析为四个主分区，再按类型归一
`view=library|mine|plans|connections`；无 kind 的旧计划/连接链接分别映射到 Workflow/Tool，
既有 kind 深链继续有效。该层不持久化
第二份能力数据，也不执行研究。筛选、路由、真实状态和 dialog DOM 契约继续由
`tests/javascript/research_web_capabilities_ui.test.mjs` 与 `research_web_appearance.test.mjs` 覆盖。

Legacy market-home fact writers share `data_layer/repositories/market_home_invalidation.py` for UTC normalization and transaction-coupled invalidation outbox writes. `services/market_home_invalidation.py` owns scheduler/materializer coordination only. Boundary logging for legacy research execution lives in `services/agent_team_service.py`, `services/research_graph.py`, `services/research_orchestration_service.py` and `services/research_templates.py`; exceptions remain visible to callers after structured logging.

Claude must read this file before changing code.

---

## 1. App API System

Subsystem:

```text
app/api
```

Responsibilities:

- Expose Research Workbench capabilities through FastAPI.
- Provide endpoints for dashboard, ingest, search, scenarios, signal lab, monitoring, governance, reports, and memory.
- Keep API routes thin and delegate business logic to `services`.

Main files:

```text
app/api/main.py
app/api/models.py
app/api/routes/*.py
app/api/routes/report_projects.py
```

Related modules:

```text
services/*
core/contracts/*
```

Required tests:

- API route tests
- Request/response schema tests
- Error handling tests

Required docs:

```text
docs/modules/app_api.md
docs/REFERENCE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- New endpoint added
- Endpoint behavior changes
- Request/response schema changes
- Route dependency changes
- Error response behavior changes
- Report project source persistence, generation, preview, or download behavior changes

---

## 2. App CLI System

Subsystem:

```text
app/cli
```

Responsibilities:

- Provide command-line access to Research Workbench workflows.
- Wrap service calls into user-facing commands.

Main files:

```text
app/cli/main.py
app/cli/commands/*.py
```

Required tests:

- CLI invocation tests
- Command output tests
- Error case tests

Required docs:

```text
docs/modules/app_cli.md
docs/REFERENCE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- New command added
- Command argument changes
- Command output changes
- CLI behavior changes

---

## 3. App Web System

Subsystem:

```text
app/web
```

Responsibilities:

- Web workbench UI.
- Research dashboard.
- Candidate board.
- Learning center.
- Search and workflow surfaces.
- System center and configuration workbench: the two views share one navigation track; configuration edits retain secret masking and environment-lock boundaries.

Main files:

```text
app/web/**
```

Required tests:

- UI/browser verification with Playwright MCP
- API integration verification where applicable

Required docs:

```text
docs/modules/app_web.md
docs/ARCHITECTURE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- Page added
- Layout changed
- User interaction changed
- API dependency changed
- UI data contract changed

---

## 4. Core Contracts System

Subsystem:

```text
core/contracts
```

Responsibilities:

- Define Pydantic domain contracts.
- Standardize cross-layer data exchange.

Main files:

```text
core/contracts/*.py
```

Required tests:

- Validation tests
- Serialization/deserialization tests
- Enum behavior tests
- Required/optional field tests

Required docs:

```text
docs/modules/core_contracts.md
docs/ARCHITECTURE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- New contract added
- Field added/removed/renamed
- Validation behavior changes
- Enum changes
- Cross-layer data model changes

---

## 5. Core Services System

Subsystem:

```text
services
```

Responsibilities:

- Implement business logic.
- Orchestrate contracts, repositories, crawlers, retrieval, reasoning, timing, signal, memory, reporting, and APIs.

Main files:

```text
services/*.py
```

Required tests:

- Service unit tests
- Mocked dependency tests
- Failure path tests
- Integration tests when multiple subsystems interact

Required docs:

```text
docs/modules/core_services.md
docs/ARCHITECTURE.md when data flow or module boundary changes
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- New service added
- Service responsibility changes
- Pipeline order changes
- Cross-layer dependency changes
- Business logic changes

---

## 6. Data Source and Crawler System

Subsystem:

```text
data_layer/adapters
data_layer/crawlers
data_layer/parsers
data_layer/normalizers
```

Responsibilities:

- Collect external market, news, financial, and research data.
- Normalize source-specific outputs into internal data formats.

Main files:

```text
data_layer/adapters/*.py
data_layer/crawlers/**/*.py
data_layer/parsers/*.py
data_layer/normalizers/*.py
```

Required tests:

- Parser tests
- Normalizer tests
- Mocked crawler tests
- Field mapping tests
- Failure/retry behavior tests

Required docs:

```text
docs/modules/data_layer_crawlers.md
docs/DATA_SOURCES.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- New source added
- Existing source parsing changes
- Rate-limit behavior changes
- Retry behavior changes
- Returned fields change
- Anti-crawling strategy changes

---

## 7. Data Repositories System

Subsystem:

```text
data_layer/repositories
```

Responsibilities:

- Provide persistence and query access.
- Isolate storage access from services.

Main files:

```text
data_layer/repositories/*.py
```

Required tests:

- Repository tests
- CRUD tests
- Query behavior tests
- Transaction/error tests where applicable

Required docs:

```text
docs/modules/data_layer_repositories.md
docs/DATA_STORAGE.md when storage behavior changes
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- Repository method added
- Query behavior changes
- Persistence behavior changes
- Transaction behavior changes

---

## 8. Knowledge Layer System

Subsystem:

```text
knowledge_layer
```

Responsibilities:

- Entity resolution
- Assertion management
- Event database
- Graph projection
- Retrieval

Main files:

```text
knowledge_layer/**/*.py
```

Required tests:

- Entity resolution tests
- Assertion tests
- Event retrieval tests
- Graph/retrieval tests

Required docs:

```text
docs/modules/knowledge_layer.md
docs/ARCHITECTURE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- Entity resolution logic changes
- Assertion behavior changes
- Event indexing changes
- Retrieval behavior changes
- Knowledge graph behavior changes

---

## 9. Reasoning System

Subsystem:

```text
reasoning
```

Responsibilities:

- Evidence chain management
- Scenario analysis
- Skeptic validation
- Reasoning traces

Main files:

```text
reasoning/**/*.py
```

Required tests:

- Reasoning logic tests
- Scenario output tests
- Validation/skeptic tests
- Trace consistency tests

Required docs:

```text
docs/modules/reasoning.md
docs/ARCHITECTURE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- Scenario logic changes
- Evidence chain behavior changes
- Skeptic validation changes
- Trace model changes

---

## 10. Cognitive Agents System

Subsystem:

```text
cognitive_agents
```

Responsibilities:

- Cognitive agent contracts
- Blackboard write/read behavior
- Multi-perspective reasoning inputs

Main files:

```text
cognitive_agents/*.py
```

Required tests:

- Blackboard tests
- Agent contract tests
- Multi-agent input/output tests

Required docs:

```text
docs/modules/cognitive_agents.md
docs/ARCHITECTURE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- Agent contract changes
- Blackboard schema changes
- New agent type added
- Agent workflow changes

---

## 11. Timing Engine System

Subsystem:

```text
timing_engine
```

Responsibilities:

- Market timing models
- Regime, flow, sentiment, diffusion, crowding, liquidity, expectation-gap signals
- Meta timing assessment

Main files:

```text
timing_engine/*.py
core/contracts/timing_engine.py
```

Required tests:

- Deterministic scoring tests
- Edge case tests
- Invalid input tests
- Blocking/readiness tests

Required docs:

```text
docs/modules/timing_engine.md
docs/ARCHITECTURE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- Timing factor changes
- Readiness score changes
- Blocking logic changes
- Meta timing behavior changes

---

## 12. Signal Lab System

Subsystem:

```text
signal_lab
```

Responsibilities:

- Feature engineering
- Label engineering
- Signal scoring
- Event study and backtesting

Main files:

```text
signal_lab/features/*.py
signal_lab/labels/*.py
signal_lab/scoring/*.py
signal_lab/backtests/*.py
```

Required tests:

- Feature calculation tests
- Label generation tests
- Scoring tests
- Backtest correctness tests
- Edge case tests

Required docs:

```text
docs/modules/signal_lab.md
docs/ARCHITECTURE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- New feature added
- Label definition changes
- Scoring logic changes
- Backtest metric changes
- Risk/portfolio behavior changes

---

## 13. Memory and Learning System

Subsystem:

```text
memory_learning
```

Responsibilities:

- Outcome memory
- Failure memory
- Learning journal
- Feedback loop

Main files:

```text
memory_learning/*.py
services/failure_memory_service.py
services/outcome_journal_service.py
```

Required tests:

- Memory write/read tests
- Similarity retrieval tests
- Failure classification tests
- Weekly review tests

Required docs:

```text
docs/modules/memory_learning.md
docs/ARCHITECTURE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- Memory schema changes
- Failure classification changes
- Outcome feedback behavior changes
- Learning loop changes

---

## 14. Reporting System

Subsystem:

```text
reporting
```

Responsibilities:

- Report composition
- Templates
- Markdown/Word projections
- Research outputs

Main files:

```text
reporting/**/*.py
services/report_generator.py
reporting/projects/*.py
report_projects/*/project.yaml
report_projects/*/config/*.yaml
report_projects/*/config/*.md
```

Required tests:

- Report generation tests
- Template rendering tests
- Output format tests
- Report project API/source persistence tests
- Chart generation and DOCX embedding tests
- Frontend template workbench tests when Web UI behavior changes

Required docs:

```text
docs/modules/reporting.md
docs/REFERENCE.md when user-facing output changes
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- New report type added
- Template changes
- Output format changes
- Report section changes
- Report project folder schema changes
- Word placeholder, section config, prompt template, chart embedding, preview, or run-log behavior changes

---

## 15. Storage System

Subsystem:

```text
storage
```

Responsibilities:

- Database schema
- Alembic migrations
- Storage conventions

Main files:

```text
storage/**/*.py
storage/migrations/**
alembic.ini
```

Required tests:

- Migration tests where feasible
- Schema compatibility tests
- Repository integration tests

Required docs:

```text
docs/modules/storage.md
docs/DATA_STORAGE.md
docs/ARCHITECTURE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- Schema changes
- Migration added
- Storage layout changes
- Backup/restore implications

---

## 16. Structured Ingestion System

Subsystem:

```text
ingestion
```

Responsibilities:

- Structured event ingestion
- Input normalization
- Event conversion into internal representation

Main files:

```text
ingestion/**/*.py
```

Required tests:

- Ingestion input tests
- Conversion tests
- Invalid input tests

Required docs:

```text
docs/modules/ingestion.md
docs/DATA_SOURCES.md
docs/ARCHITECTURE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- New ingestion type
- Event conversion changes
- Input schema changes
- Validation behavior changes

---

## 17. Cron Jobs System

Subsystem:

```text
cron_jobs
```

Responsibilities:

- Scheduled ingestion
- Scheduled signal generation
- Background automation

Main files:

```text
cron_jobs/*.py
```

Required tests:

- Scheduling logic tests
- Mocked job execution tests
- Failure handling tests

Required docs:

```text
docs/modules/cron_jobs.md
docs/ARCHITECTURE.md
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- New scheduled job
- Frequency changes
- Job dependency changes
- Failure/retry behavior changes

---

## 18. Scripts System

Subsystem:

```text
scripts
```

Responsibilities:

- Operational scripts
- Database bootstrap
- Backup/restore
- Smoke tests
- Development governance checks

Main files:

```text
scripts/*.py
```

Required tests:

- Script behavior tests where feasible
- Dry-run tests
- Error path tests

Required docs:

```text
docs/modules/scripts.md
docs/REFERENCE.md when user-facing
docs/backup_restore.md when backup/restore changes
docs/FILE_GUIDE.md
docs/CHANGELOG.md
```

Update triggers:

- New script added
- Script behavior changes
- Operational workflow changes
- Backup/restore behavior changes

## 19. Connector System

Subsystem:

```text
core/connectors
connectors
```

Responsibilities:

- Unified data source connector abstraction (`BaseConnector → DocumentConnector / MarketDataConnector`)
- Connector lifecycle: `discover → fetch → save_raw → parse → normalize → validate → persist`
- Connector registry for discovery, registration, and health management
- Concrete implementations wrap existing `data_layer/adapters/` classes (Wrapper-first strategy)

Main files:

```text
core/connectors/base.py
core/connectors/registry.py
connectors/document/cls.py
connectors/document/cninfo.py
connectors/document/cnstock.py
connectors/document/zq.py
connectors/market/akshare.py
connectors/market/wind.py
connectors/market/baostock.py
connectors/market/cjpy.py
connectors/market/csindex.py
connectors/market/szse.py
connectors/market/yahoo.py
```

Required tests:

- Base connector lifecycle tests
- Concrete connector integration tests (mock external dependencies)
- Registry registration/discovery tests
- Health check tests

Required docs:

```text
docs/modules/core_connectors.md
docs/ARCHITECTURE.md
docs/FILE_GUIDE.md
docs/DATA_SOURCES.md
docs/CHANGELOG.md
```

Update triggers:

- New connector type added
- Base class lifecycle changes
- Registry API changes
- New concrete connector implementation

---

## 20. Runtime Configuration and Worker Operations

Subsystem:

```text
core/settings
workers
```

Responsibilities:

- Generate safe first-run desktop configuration templates.
- Guard PostgreSQL-backed workers from invalid configuration and control retry logging.

Main files:

```text
core/settings/registry.py
workers/knowledge_worker.py
```

Required tests:

- Desktop configuration template tests.
- Worker database-readiness and retry/backoff tests.

Required docs:

```text
docs/ARCHITECTURE.md
docs/CHANGELOG.md
```

Update triggers:

- Desktop database template default changes.
- Worker startup, database readiness, retry, or log-volume behavior changes.
