# AlphaFoundry Development Map

This file maps AlphaFoundry subsystems to source files, tests, and required documentation updates.

## Current Web research implementation (2026-09-02)

Research Web now lives in `app/research_web/`, with entrypoint `app.research_web.main:app` and `/api/research/`.
Read [Research Web](research-web.md) and [UI contract](research-web-ui.md) first for this product.
The legacy subsystems below remain historical implementations, not dependencies to add to this new chain.
Tests: `tests/research_web/` (use `--confcutdir=tests/research_web`) and `tests/javascript/research_web*.test.mjs`.
DSH owns the execution loop, skills, subagents and transcript; no second orchestration/fact database.

Claude must read this file before changing code.

---

## 1. App API System

Subsystem:

```text
app/api
```

Responsibilities:

- Expose AlphaFoundry capabilities through FastAPI.
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

- Provide command-line access to AlphaFoundry workflows.
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
