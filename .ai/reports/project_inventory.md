# AlphaFoundry Project Inventory

> **Document Version**: 1.0  
> **Audit Date**: 2026-05-10  
> **Repository Path**: /Users/leon/Desktop/Projects/AlphaFoundry

---

## Executive Summary

AlphaFoundry is a sophisticated, AI-native investment operating system built in Python. It employs a modular monolith architecture with PostgreSQL/pgvector as its primary data store. The system focuses on event-driven quantitative research and investment decision support.

### Key Statistics

| Metric | Value |
|--------|-------|
| Total Python Files | 300+ |
| Core Modules | 12 |
| API Endpoints | 28 |
| CLI Commands | 7+ |
| Database Migrations | 7+ |
| Code Lines | ~50K+ |
| Tests | ~40 |

### Architecture Type

**Modular Monolith** - All components live in a single codebase with clear module boundaries, enabling potential future extraction to microservices if needed.

---

## Directory Structure

```
AlphaFoundry/
├── app/                           # Application Layer
│   ├── api/                       # FastAPI REST API
│   │   ├── main.py                # API entry point
│   │   ├── models.py              # API request/response models
│   │   └── routes/                # API route handlers (28 endpoints)
│   ├── cli/                       # Command Line Interface
│   │   ├── main.py                # CLI entry point
│   │   └── commands/              # CLI command implementations
│   └── web/                       # Web UI (HTML templates & static assets)
│
├── core/                          # Core Layer (Foundation)
│   ├── contracts/                 # Pydantic v2 domain models (25+ modules)
│   ├── interfaces/                # Abstract interface definitions
│   ├── model_gateway/             # LLM provider abstraction
│   │   └── providers/             # Model provider implementations
│   ├── observability/             # Logging, metrics, tracing
│   ├── services/                  # Business logic services (30+ modules)
│   ├── settings/                  # Configuration management
│   └── utils/                     # Utility functions
│
├── data_layer/                    # Data Layer
│   ├── adapters/                  # Data source adapters
│   │   ├── akshare/               # AKShare adapter implementation
│   │   ├── china_stock/           # China stock data adapter
│   │   └── ifind/                 # iFind adapter
│   ├── crawlers/                  # Web crawlers & data fetchers
│   │   ├── akshare/               # AKShare crawler (market, financial, news, macro)
│   │   ├── cls/                   # 财联社 (CLS) crawler
│   │   ├── cnstock/               # 中国证券网 (CNStock) crawler
│   │   └── zq/                    # 知丘 (ZQ) crawler (research, articles, notes)
│   ├── normalizers/               # Data normalization components
│   ├── parsers/                   # Document parsers (PDF, etc.)
│   └── repositories/              # Database repository implementations
│
├── knowledge_layer/               # Knowledge Layer
│   ├── assertions/                # Fact assertion management
│   ├── entity_resolution/         # Entity normalization & disambiguation
│   ├── events/                    # Event database management
│   ├── graph_projection/          # Knowledge graph projections
│   └── retrieval/                 # Vector-based semantic retrieval (pgvector)
│
├── reasoning/                     # Reasoning Layer
│   ├── evidence/                  # Evidence chain management
│   ├── router/                    # Reasoning path routing
│   ├── scenarios/                 # Scenario analysis engine
│   ├── skeptic/                   # Skeptical verification & cross-checking
│   ├── traces/                    # Reasoning trace audit
│   ├── graph.py                   # Graph-based reasoning
│   └── state.py                   # LangGraph state management
│
├── cognitive_agents/              # Cognitive Agent Layer
│   ├── agents/                    # Agent implementations
│   │   ├── adversarial/           # Bull, Bear, Skeptic agents
│   │   ├── cognitive/             # Fundamental, Technical, Macro, etc.
│   │   ├── information/           # News, Data collection agents
│   │   └── validation/            # Alpha validation agents
│   ├── contracts.py               # Agent & Blackboard contracts
│   └── blackboard.py              # Shared cognitive blackboard
│
├── timing_engine/                 # Market Timing Layer
│   ├── models/                    # Timing model implementations
│   │   ├── regime_model.py        # Market regime detection
│   │   ├── flow_model.py          # Capital flow analysis
│   │   ├── sentiment_model.py     # Market sentiment
│   │   ├── theme_diffusion_model.py # Theme spread patterns
│   │   ├── crowding_model.py      # Crowded trade detection
│   │   ├── liquidity_model.py     # Liquidity conditions
│   │   ├── expectation_gap_model.py # Expectation vs reality
│   │   ├── alpha_decay_model.py   # Alpha decay patterns
│   │   ├── market_structure_model.py # Market structure analysis
│   │   └── registry.py            # Model registry
│   ├── contracts.py               # Timing contracts
│   └── meta.py                    # Meta Timing Engine (combines all models)
│
├── signal_lab/                    # Signal Laboratory (Quant Layer)
│   ├── features/                  # Feature engineering
│   │   ├── base.py                # Feature & FeatureGroup base classes
│   │   ├── builder.py             # FeatureBuilder for combining features
│   │   └── groups/                # Feature group implementations
│   │       ├── price_volume.py    # Price & volume features
│   │       ├── valuation.py       # Valuation metrics
│   │       ├── financial.py       # Financial statement features
│   │       ├── fund_flow.py       # Fund flow indicators
│   │       ├── industry.py        # Industry relative features
│   │       └── macro.py           # Macro economic features
│   ├── labels/                    # Label generation
│   │   ├── base.py                # Labeler base class
│   │   ├── relative_return.py     # Relative return labels
│   │   └── event_driven.py        # Event-driven labels
│   ├── scoring/                   # Signal scoring
│   │   ├── scorer.py              # SignalScorer & CompositeScorer
│   │   └── ranker.py              # SignalRanker for ordering
│   └── backtests/                 # Backtesting engine
│       ├── base.py                # Backtester & BacktestResult base
│       ├── simple.py              # Simple backtest implementation
│       └── event_study.py         # Event study methodology
│
├── memory_learning/               # Memory & Learning Layer
│   ├── contracts.py               # Memory data contracts
│   ├── journal.py                 # Learning journal core
│   ├── persistent_journal.py      # Persistent storage implementation
│   └── pattern_learner.py         # Pattern recognition from history
│
├── reporting/                     # Reporting Layer
│   ├── composer/                  # Report composition
│   │   ├── report_composer.py     # Main composer
│   │   ├── report_pipeline.py     # Report generation pipeline
│   │   ├── section_generator.py   # Section content generation
│   │   ├── fact_card_builder.py   # Fact card assembly
│   │   ├── evidence_binder.py     # Evidence documentation
│   │   └── validator.py           # Report validation
│   ├── templates/                 # Report templates
│   │   └── template_manager.py    # Template management
│   └── projections/               # Output formatters
│       ├── markdown.py            # Markdown output
│       ├── word.py                # Word document (.docx) output
│       └── excel.py               # Excel spreadsheet output
│
├── ingestion/                     # Ingestion Pipeline
│   ├── structured_event_ingestion.py  # Structured event ingestion
│   └── knowledge_pipeline.py      # Knowledge processing pipeline
│
├── storage/                       # Storage Layer
│   └── migrations/                # Alembic database migrations
│       ├── alembic.ini            # Alembic config
│       ├── env.py                 # Migration environment
│       ├── script.py.mako         # Migration template
│       └── versions/              # Migration version files (7+)
│
├── cognitive_agents/              # Cognitive Agent System
│   ├── contracts.py               # Agent contracts
│   ├── blackboard.py              # Shared blackboard
│   └── agents/                    # Agent implementations
│       ├── information/           # Information agents
│       ├── cognitive/             # Cognitive agents
│       ├── adversarial/           # Adversarial agents (bull/bear/skeptic)
│       └── validation/            # Validation agents
│
├── cron_jobs/                     # Scheduled Jobs
│   ├── auto_ingest_service.py     # Automatic data ingestion service
│   └── auto_generate_signals.py   # Automatic signal generation
│
├── scripts/                       # Utility Scripts (30+)
│   ├── bootstrap_db.py            # Database initialization
│   ├── import_real_data.py        # Import real data archives
│   ├── backup_db.py               # Database backup
│   ├── restore_db.py              # Database restore
│   ├── smoke_runner.py            # Smoke test suite
│   ├── minimal_reingest_bootstrap.py # Minimal recovery bootstrap
│   ├── backfill_from_objects.py   # Backfill from object storage
│   ├── rebuild_derived_state.py   # Rebuild derived data
│   ├── view_db.py                 # Database viewing utility
│   └── [various test scripts]     # Testing and development utilities
│
├── examples/                      # Example Code
│   ├── test_simple.py             # Simple API test
│   ├── test_signal_lab_simple.py  # Signal Lab demo
│   ├── signal_lab_demo.py         # Signal Lab features
│   ├── demo_all_features.py       # All features demo
│   ├── akshare_usage_examples.py  # AKShare usage examples
│   ├── akshare_full_integration.py # Full AKShare integration
│   ├── report_composer_example.py # Report composition demo
│   └── test_june.py               # June milestone test
│
├── tests/                         # Test Suite
│   ├── conftest.py                # Pytest configuration & fixtures
│   ├── unit/                      # Unit tests
│   │   └── data_layer/            # Data layer tests
│   ├── integration/               # Integration tests
│   ├── contract/                  # Contract tests
│   ├── backtest/                  # Backtest tests
│   ├── reasoning/                 # Reasoning tests
│   ├── retrieval/                 # Retrieval tests
│   ├── scripts/                   # Script tests
│   └── golden/                    # Golden master tests
│
├── benchmarks/                    # Performance Benchmarks
│   ├── evaluate.py                # Benchmark evaluation
│   └── SCHEMA.py                  # Benchmark schema definitions
│
├── data/                          # Data Directory
│   ├── crawlers/                  # Crawler data
│   ├── examples/                  # Example data
│   ├── industry_graphs/           # Industry graph data
│   ├── objects/                   # Object storage (documents, artifacts)
│   ├── raw/                       # Raw data archives
│   ├── real/                      # Real imported data
│   └── samples/                   # Sample datasets
│
├── logs/                          # Log Directory
│
├── docs/                          # Documentation Directory
│   ├── FILE_GUIDE.md              # File guide (existing)
│   ├── REFERENCE.md               # Reference manual (existing)
│   ├── ARCHITECTURE.md            # Architecture docs (existing)
│   ├── CHANGELOG.md               # Change log (existing)
│   ├── backup_restore.md          # Backup/restore guide (existing)
│   ├── DATA_SOURCES.md            # Data sources guide (existing)
│   ├── archive/                   # Archived documentation
│   ├── issues/                    # GitHub issues documentation
│   └── research/                  # Research notes
│
├── .claude/                       # Claude Code project config
│   ├── rules/                     # Project-specific rules (7+)
│   └── archive/                   # Archived files
│
├── .git/                          # Git repository
├── .env                           # Environment variables (gitignored)
├── .env.example                   # Environment variables template
├── pyproject.toml                 # Project dependencies & config
├── pytest.ini                     # Pytest configuration
├── .gitignore                     # Git ignore rules
├── .bashrc                        # Bash config (project-specific)
└── README.md                      # Project README (comprehensive)
```

---

## Core Module Inventory

### 1. Core Contracts (`core/contracts/`)

| File | Purpose | Status |
|------|---------|--------|
| assertions.py | Fact assertion models | ✅ |
| assets.py | Asset analysis snapshot models | ✅ |
| backtest.py | Backtest result models | ✅ |
| dashboard.py | Dashboard data models | ✅ |
| decision_console.py | Decision console models | ✅ |
| documents_v1.py | Document envelope models v1 | ✅ |
| events.py | Canonical event models | ✅ |
| governance.py | Governance & version control models | ✅ |
| industry_chain.py | Industry chain models | ✅ |
| ingestion.py | Ingestion pipeline models | ✅ |
| monitoring.py | Monitoring & health models | ✅ |
| outcome_journal.py | Outcome journal models | ✅ |
| outcomes.py | Outcome tracking models | ✅ |
| paper_trading.py | Paper trading models | ✅ |
| portfolio.py | Portfolio models | ✅ |
| raw_storage.py | Raw storage models | ✅ |
| replay.py | Replay models | ✅ |
| reporting.py | Report composition models | ✅ |
| retrieval.py | Retrieval models | ✅ |
| review_framework.py | Review framework models | ✅ |
| signals.py | Alpha signal models | ✅ |
| timing_engine.py | Timing engine models | ✅ |
| traces.py | Reasoning trace models | ✅ |

**Total**: 25+ contract modules

---

### 2. Core Services (`core/services/`)

| Service | Purpose | Status |
|---------|---------|--------|
| asset_analysis_service.py | Asset analysis & snapshot generation | ✅ |
| closed_loop_service.py | Closed loop feedback orchestration | ✅ |
| crawl_orchestrator.py | Crawler orchestration & coordination | ✅ |
| crawl_scheduler.py | Crawling schedule management | ✅ |
| dashboard_service.py | Dashboard data aggregation | ✅ |
| data_tier_service.py | Data tier coordination | ✅ |
| decision_console_service.py | Decision console backend | ✅ |
| deduplication_service.py | Data deduplication | ✅ |
| document_chunker.py | Document segmentation | ✅ |
| document_classifier.py | Document type classification | ✅ |
| document_enrichment.py | Document metadata enrichment | ✅ |
| entity_extractor.py | Entity extraction from text | ✅ |
| event_auto_signal_generator.py | Automatic signal generation from events | ✅ |
| event_extractor.py | Event extraction from content | ✅ |
| failure_memory_service.py | Failure memory management | ✅ |
| governance_service.py | Governance & version control | ✅ |
| graph_data_service.py | Graph data management | ✅ |
| historical_replay_service.py | Historical replay capabilities | ✅ |
| ingest_service.py | Data ingestion service | ✅ |
| ingestion_queue_service.py | Ingestion queue management | ✅ |
| monitoring_service.py | Monitoring & health checks | ✅ |
| news_feature_service.py | News feature extraction | ✅ |
| outcome_journal_service.py | Outcome journal management | ✅ |
| outcome_service.py | Outcome tracking service | ✅ |
| paper_trading_service.py | Paper trading simulation | ✅ |
| pipeline_service.py | Pipeline orchestration | ✅ |
| portfolio_service.py | Portfolio management | ✅ |
| rag_retrieval.py | RAG retrieval service | ✅ |
| raw_storage_service.py | Raw storage management | ✅ |
| replay_service.py | Replay service | ✅ |
| report_generator.py | Report generation | ✅ |
| scenario_service.py | Scenario analysis service | ✅ |
| scenario_data_service.py | Scenario data service | ✅ |
| search_service.py | Search service | ✅ |
| signal_service.py | Signal management service | ✅ |
| signal_validator_impl.py | Signal validation implementation | ✅ |
| summary_generator.py | Summary generation | ✅ |
| taxonomy_service.py | Taxonomy management | ✅ |
| thesis_generator_service.py | Thesis generation | ✅ |
| thesis_review_service.py | Thesis review & validation | ✅ |

**Total**: 40+ service modules

---

### 3. Data Layer Crawlers (`data_layer/crawlers/`)

#### AKShare Crawler (`data_layer/crawlers/akshare/`)

| File | Purpose | Status |
|------|---------|--------|
| base.py | Base AKShare fetcher class | ✅ |
| config.py | AKShare configuration | ✅ |
| market.py | Market data (quotes, history, stock list) | ✅ |
| financial.py | Financial statement data | ✅ |
| news.py | News & announcements | ✅ |
| macro.py | Macro economic data | ✅ |
| utils.py | Utility functions (cleaning, normalization) | ✅ |

#### Other Crawlers

| Crawler | Source | Purpose |
|---------|--------|---------|
| cls/ | 财联社 | Real-time news & market telegrams |
| cnstock/ | 中国证券网 | Market news & announcements |
| zq/ | 知丘 | Research reports, articles, meeting notes |

---

### 4. Signal Lab Module (`signal_lab/`)

#### Features Submodule

| Component | Purpose |
|-----------|---------|
| base.py | Feature & FeatureGroup abstract base classes |
| builder.py | FeatureBuilder for combining multiple feature groups |
| groups/price_volume.py | Price & volume based features |
| groups/valuation.py | Valuation multiple features |
| groups/financial.py | Financial statement features |
| groups/fund_flow.py | Fund flow indicator features |
| groups/industry.py | Industry relative features |
| groups/macro.py | Macro-economic features |

#### Labels Submodule

| Component | Purpose |
|-----------|---------|
| base.py | Labeler abstract base class |
| relative_return.py | Relative return label generation |
| event_driven.py | Event-driven label generation |

#### Scoring Submodule

| Component | Purpose |
|-----------|---------|
| scorer.py | SignalScorer & CompositeScorer |
| ranker.py | SignalRanker for ordering candidates |

#### Backtests Submodule

| Component | Purpose |
|-----------|---------|
| base.py | Backtester & BacktestResult base classes |
| simple.py | Simple vector-based backtest |
| event_study.py | Event study methodology implementation |

---

### 5. Timing Engine (`timing_engine/`)

#### Timing Models (`timing_engine/models/`)

| Model | Purpose |
|-------|---------|
| base.py | Base TimingModel abstract class |
| regime_model.py | Market regime detection (risk-on/off, etc.) |
| flow_model.py | Capital flow analysis (northbound, institutions, etc.) |
| sentiment_model.py | Market sentiment measurement |
| theme_diffusion_model.py | Theme diffusion & spread patterns |
| crowding_model.py | Crowded trade detection |
| liquidity_model.py | Liquidity condition analysis |
| expectation_gap_model.py | Expectation vs reality gap |
| alpha_decay_model.py | Alpha decay pattern analysis |
| market_structure_model.py | Market structure analysis |
| registry.py | Model registry & factory |

#### Meta Engine

| File | Purpose |
|------|---------|
| meta.py | MetaTimingEngine - orchestrates all models, produces final timing decision |
| contracts.py | TimingDecision, TimingModelScore, MarketRegime enum |

---

### 6. API Routes (`app/api/routes/`)

| Endpoint | Purpose |
|----------|---------|
| assets.py | Asset analysis endpoints |
| audit.py | Audit log endpoints |
| dashboard.py | Dashboard data endpoints |
| decision_console.py | Decision console endpoints |
| event_ingestion.py | Event ingestion endpoints |
| governance.py | Governance endpoints |
| graph.py | Graph data endpoints |
| ingest.py | General ingestion endpoints |
| ingestion_queue.py | Ingestion queue endpoints |
| memory.py | Memory layer endpoints |
| monitoring.py | Monitoring & health endpoints |
| outcome_journal.py | Outcome journal endpoints |
| outcomes.py | Outcome tracking endpoints |
| paper_trading.py | Paper trading endpoints |
| portfolio.py | Portfolio endpoints |
| replay.py | Replay endpoints |
| report.py | Report generation endpoints |
| review.py | Review endpoints |
| scenarios.py | Scenario analysis endpoints |
| search.py | Search endpoints |
| signal_lab.py | Signal Lab endpoints |
| signals.py | Signal management endpoints |
| thesis_generator.py | Thesis generation endpoints |
| timing.py | Timing engine endpoints |

**Total**: 28+ API route modules

---

## Technology Stack

| Category | Technology | Version |
|----------|------------|---------|
| Language | Python | 3.11+ |
| Web Framework | FastAPI | Latest |
| API Documentation | Swagger/OpenAPI | Built-in |
| Data Validation | Pydantic | v2 |
| CLI Framework | Click | Latest |
| Database | PostgreSQL | 15+ |
| Vector DB | pgvector | Latest |
| ORM | SQLAlchemy | 2.0 |
| Migrations | Alembic | Latest |
| State Machine | LangGraph | Latest |
| Backtesting | vectorbt, Backtrader | - |
| Logging | structlog | Latest |
| Code Formatting | black, isort, ruff | Configured |
| LLM Gateway | Custom - supports volcano | - |
| Document Parsing | pdfplumber, python-docx | - |

---

## Configuration Files

| File | Purpose |
|------|---------|
| pyproject.toml | Project dependencies, black/ruff config |
| pytest.ini | Pytest configuration |
| .env.example | Environment variables template |
| .env | Active environment variables (gitignored) |
| .gitignore | Git ignore rules |
| storage/migrations/alembic.ini | Alembic migration config |

---

## Script Inventory

### Core Management Scripts

| Script | Purpose |
|--------|---------|
| bootstrap_db.py | Initialize database schema & seed data |
| import_real_data.py | Import real data archives (900+ items) |
| backup_db.py | Backup database to compressed file |
| restore_db.py | Restore database from backup |
| view_db.py | Database viewing & inspection utility |
| smoke_runner.py | Run smoke test suite |
| minimal_reingest_bootstrap.py | Minimal recovery bootstrap |
| backfill_from_objects.py | Backfill from object storage |
| rebuild_derived_state.py | Rebuild derived system state |

### Development & Test Scripts

| Script | Purpose |
|--------|---------|
| test_simple.py | Simple API test |
| test_signal_lab.py | Signal Lab test |
| test_akshare.py | AKShare integration test |
| test_all_iterations.py | All iterations test |
| test_closed_loop_api.py | Closed loop API test |
| test_outcome_api.py | Outcome API test |
| test_memory_learning.py | Memory learning test |
| demo_closed_loop.py | Closed loop demo |
| test_asset_analysis.py | Asset analysis test |

### Data Management Scripts

| Script | Purpose |
|--------|---------|
| add_event_type_column.py | Add event_type column migration |
| enrich_events.py | Enrich existing events with data |
| fix_event_subjects.py | Fix event subject data |
| fix_event_dates.py | Fix event date data |
| re_ingest_with_llm.py | Re-ingest with LLM processing |
| re_extract_with_llm.py | Re-extract with LLM |
| crawl_full_data.py | Full data crawl |
| init_price_data.py | Initialize price data |
| setup_price_cache.py | Setup price cache |
| import_outcomes_to_memory.py | Import outcomes to memory layer |
| reset_demo.py | Reset demo data |

---

## Data Inventory

### Real Data Archives

| Type | Count | Location |
|------|-------|----------|
| 财联社电报 | ~900 | data/real/cls/ |
| 中国证券网新闻 | ~24 | data/real/cnstock/ |
| 知丘研报 | ~747 | data/real/zq/ |
| 知丘公众号文章 | ~53 | data/real/zq/ |
| 知丘会议纪要 | ~92 | data/real/zq/ |
| 示例真实事件 | 5+ | data/real/events/ |

### Data Directories

| Directory | Purpose |
|-----------|---------|
| data/crawlers/ | Crawler output storage |
| data/examples/ | Example datasets |
| data/industry_graphs/ | Industry relationship graphs |
| data/objects/ | Object storage (documents, artifacts) |
| data/raw/ | Raw data archives |
| data/real/ | Real imported data |
| data/samples/ | Sample datasets for development |

---

## Test Inventory

### Test Categories

| Category | Location | Purpose |
|----------|----------|---------|
| Unit Tests | tests/unit/ | Individual module tests |
| Integration Tests | tests/integration/ | Cross-module integration tests |
| Contract Tests | tests/contract/ | API contract tests |
| Backtest Tests | tests/backtest/ | Backtesting engine tests |
| Reasoning Tests | tests/reasoning/ | Reasoning layer tests |
| Retrieval Tests | tests/retrieval/ | Retrieval tests |
| Script Tests | tests/scripts/ | Script tests |
| Golden Tests | tests/golden/ | Golden master tests |

### Key Test Files

| File | Purpose |
|------|---------|
| tests/conftest.py | Pytest configuration & shared fixtures |
| tests/test_data_layer.py | Data layer tests |

---

## Documentation Inventory

### Core Documents

| Document | Purpose |
|----------|---------|
| README.md | Project overview, quick start, features |
| docs/ARCHITECTURE.md | Architecture design & decisions |
| docs/REFERENCE.md | Complete reference manual |
| docs/FILE_GUIDE.md | File-by-file guide |
| docs/CHANGELOG.md | Change log |
| docs/backup_restore.md | Backup & recovery procedures |
| docs/DATA_SOURCES.md | Data sources documentation |

### Project Rules (`.claude/rules/`)

| Rule File | Purpose |
|-----------|---------|
| 001-code-quality.md | Code quality standards (black, isort, ruff) |
| 002-testing.md | Testing standards & practices |
| 003-logging.md | Logging standards |
| 004-database-migrations.md | Database migration standards |
| 005-pydantic-contracts.md | Pydantic model standards |
| 006-cli-development.md | CLI development standards |
| 007-auto-update-docs.md | Documentation update requirements |
| 008-signal-lab.md | Signal Lab development standards |

---

## Git Inventory

### Current State

| Metric | Value |
|--------|-------|
| Current Branch | master |
| HEAD Commit | d66b896 |
| Status | Clean (1 untracked: .bashrc) |
| Recent Commits | 5 (ref: d66b896, 9239e3f, e83a164, 40818d3, bf0b17a) |

### Latest Commit Messages

1. `refactor: 深化搜索和知识加工模块，创建深模块` (d66b896)
2. `docs: 更新项目文档以反映架构重构` (9239e3f)
3. `refactor: 深化时序引擎模块，移除冗余服务层` (e83a164)
4. `refactor: 深化事件摄入模块，移除冗余服务层` (40818d3)
5. `docs: 更新项目文档与实际结构保持一致` (bf0b17a)

---

## Dependency Inventory

### Python Dependencies (Key)

See `pyproject.toml` for complete list. Major dependencies include:

- FastAPI - Web framework
- SQLAlchemy - ORM
- Pydantic v2 - Data validation
- Alembic - Migrations
- LangGraph - State machine
- vectorbt, Backtrader - Backtesting
- structlog - Logging
- pdfplumber, python-docx - Document parsing
- openai - LLM API (compatible interface)
- black, isort, ruff - Code quality
- pytest - Testing

---

## Health Check Summary

### What's Working

✅ Comprehensive modular architecture with clear boundaries  
✅ 30+ business services implemented  
✅ 28+ API endpoints available  
✅ 4 data crawlers (AKShare, CLS, CNStock, ZQ)  
✅ Full Signal Lab feature engineering pipeline  
✅ Timing engine with 10+ models  
✅ Memory & learning layer implemented  
✅ Report generation in Markdown, Word, Excel  
✅ Real data archives available (900+ items)  
✅ Database migration system (7+ migrations)  
✅ CLI & Web UI both available  
✅ Comprehensive test structure  
✅ Logging & observability infrastructure  
✅ Backup & recovery scripts  

### What Needs Attention

⚠️ Web UI implementation appears minimal (templates/static)  
⚠️ Test coverage not yet verified  
⚠️ Some services may be placeholders (see gap analysis)  
⚠️ Documentation drift possible (see gap analysis)  

---

## File Type Distribution

| Type | Count |
|------|-------|
| Python (.py) | 300+ |
| Markdown (.md) | 20+ |
| Alembic Migrations | 7+ |
| Configuration (.toml, .ini, .env) | 5+ |
| Templates/Static Assets | 10+ |
| Data Files (JSON, Pickle, etc.) | 100+ |

---

## Key Integration Points

### External Dependencies

1. **LLM Provider**: Volcano (火山引擎) via Model Gateway
2. **Data Sources**: AKShare, 财联社, 中国证券网, 知丘
3. **Database**: PostgreSQL + pgvector (or SQLite fallback)
4. **Document Parsing**: pdfplumber, python-docx

### Internal Module Dependencies

```
app/api → core/services → data_layer/repositories → storage
         ↓
    knowledge_layer ← reasoning ← cognitive_agents
         ↓
    signal_lab ← timing_engine ← memory_learning
         ↓
    reporting → output (Markdown/Word/Excel)
```

---

## Audit Notes

### Strengths

1. Excellent modular structure with clear separation of concerns
2. Comprehensive domain modeling with Pydantic v2
3. Deep feature set for investment research
4. Good documentation (README, ARCHITECTURE, etc.)
5. Proper use of interfaces and abstraction
6. Real data available for testing
7. Backup/recovery infrastructure

### Areas for Further Investigation

1. Test coverage needs assessment
2. Service completeness verification
3. API endpoint documentation status
4. Web UI implementation status
5. Performance benchmarks
6. Security audit (authentication, secrets management)

---

*Last updated: 2026-05-10*
