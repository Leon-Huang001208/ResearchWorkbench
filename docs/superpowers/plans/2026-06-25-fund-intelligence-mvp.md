# Fund Intelligence MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add the first backend slice of Fund Intelligence so Research Workbench can store funds, NAVs, holdings, managers, and expose fund detail/portfolio exposure data through API endpoints.

**Architecture:** Keep the feature as a focused vertical module. Domain contracts live in `core/contracts/funds.py`, persistence lives in `data_layer/repositories/fund_repository.py`, orchestration lives in `services/fund_intelligence_service.py`, and HTTP exposure lives in `app/api/routes/funds.py`. This MVP avoids frontend implementation and external data ingestion; it creates the durable seam for later Wind/AKShare/announcement ingestion.

**Tech Stack:** Python 3.11, Pydantic v2, SQLAlchemy Core/ORM, FastAPI, pytest.

---

### Task 1: Fund Contracts

**Files:**
- Create: `core/contracts/funds.py`
- Test: `tests/unit/test_fund_contracts.py`

- [x] **Step 1: Write failing tests**

Create tests that prove fund detail objects validate required identifiers, normalize numeric risk metrics, and preserve report-date holdings.

- [x] **Step 2: Run red test**

Run: `python -m pytest tests/unit/test_fund_contracts.py -q`

Expected: import failure for `core.contracts.funds`.

- [x] **Step 3: Implement contracts**

Define Pydantic models for `FundMaster`, `FundNavPoint`, `FundHolding`, `FundManagerProfile`, `FundPerformanceMetrics`, `FundDetail`, `FundExposureBreakdown`, and `PortfolioFundExposure`.

- [x] **Step 4: Run green test**

Run: `python -m pytest tests/unit/test_fund_contracts.py -q`

Expected: all tests pass.

### Task 2: Fund Repository

**Files:**
- Create: `data_layer/repositories/fund_repository.py`
- Test: `tests/unit/data_layer/repositories/test_fund_repository.py`

- [x] **Step 1: Write failing repository tests**

Use an in-memory SQLite database to create MVP tables and assert upsert/query behavior for master data, NAV history, holdings, and manager tenure.

- [x] **Step 2: Run red test**

Run: `python -m pytest tests/unit/data_layer/repositories/test_fund_repository.py -q`

Expected: import failure for `FundRepository`.

- [x] **Step 3: Implement repository**

Implement explicit SQLAlchemy table definitions local to the repository plus methods:
`ensure_schema()`, `upsert_fund_master()`, `upsert_nav_points()`, `upsert_holdings()`, `upsert_manager_tenures()`, `get_fund_master()`, `get_nav_history()`, `get_latest_holdings()`, and `get_manager_profiles()`.

- [x] **Step 4: Run green test**

Run: `python -m pytest tests/unit/data_layer/repositories/test_fund_repository.py -q`

Expected: all tests pass.

### Task 3: Fund Intelligence Service

**Files:**
- Create: `services/fund_intelligence_service.py`
- Test: `tests/unit/test_fund_intelligence_service.py`

- [x] **Step 1: Write failing service tests**

Test that the service builds a fund detail response, calculates performance metrics from NAV history, aggregates holdings into industry exposure, and calculates weighted portfolio exposures across multiple funds.

- [x] **Step 2: Run red test**

Run: `python -m pytest tests/unit/test_fund_intelligence_service.py -q`

Expected: import failure for `FundIntelligenceService`.

- [x] **Step 3: Implement service**

Implement service methods:
`get_fund_detail(symbol)`, `get_fund_exposure(symbol)`, and `calculate_portfolio_exposure(positions)`.

- [x] **Step 4: Run green test**

Run: `python -m pytest tests/unit/test_fund_intelligence_service.py -q`

Expected: all tests pass.

### Task 4: Fund API Routes

**Files:**
- Create: `app/api/routes/funds.py`
- Modify: `app/api/main.py`
- Test: `tests/unit/test_funds_api.py`

- [x] **Step 1: Write failing API tests**

Use FastAPI `TestClient` with dependency override to assert:
`GET /api/funds/{symbol}` returns fund detail,
`GET /api/funds/{symbol}/exposure` returns exposure,
and `POST /api/funds/portfolio/exposure` returns weighted portfolio exposure.

- [x] **Step 2: Run red test**

Run: `python -m pytest tests/unit/test_funds_api.py -q`

Expected: route import or 404 failure.

- [x] **Step 3: Implement routes**

Add a thin FastAPI route module that delegates to `FundIntelligenceService`, logs errors, and raises 404 for missing funds.

- [x] **Step 4: Register router and run green test**

Run: `python -m pytest tests/unit/test_funds_api.py -q`

Expected: all tests pass.

### Task 5: Documentation and Verification

**Files:**
- Modify: `docs/modules/app_api.md`
- Modify: `docs/modules/data_layer_repositories.md`
- Modify: `docs/modules/services.md`
- Modify: `docs/CHANGELOG.md`

- [x] **Step 1: Update module docs**

Document the new fund API, repository, and service responsibilities.

- [x] **Step 2: Run targeted verification**

Run:
`python -m pytest tests/unit/test_fund_contracts.py tests/unit/data_layer/repositories/test_fund_repository.py tests/unit/test_fund_intelligence_service.py tests/unit/test_funds_api.py -q`

Expected: all tests pass.

- [x] **Step 3: Run smoke verification**

Run:
`python -m pytest tests/unit/test_portfolio.py tests/unit/test_api.py -q`

Expected: all tests pass.

### Task 6: Local Fund Data Ingestion

**Files:**
- Create: `services/fund_data_ingestion_service.py`
- Test: `tests/unit/test_fund_data_ingestion_service.py`
- Modify: `docs/modules/services.md`
- Modify: `docs/FILE_GUIDE.md`
- Modify: `docs/CHANGELOG.md`

- [x] **Step 1: Write failing ingestion tests**

Test local row ingestion for `master`, `nav`, `holdings`, and `managers`; test CSV reading; test invalid rows mark ETL runs as failed.

- [x] **Step 2: Run red test**

Run: `python -m pytest tests/unit/test_fund_data_ingestion_service.py -q`

Expected: import failure for `services.fund_data_ingestion_service`.

- [x] **Step 3: Implement local ingestion service**

Implement `FundDataIngestionService` with `ingest_rows(dataset, rows, source)` and `ingest_csv(dataset, path, source)` using only Python standard library CSV parsing and repository upsert methods.

- [x] **Step 4: Run green test**

Run: `python -m pytest tests/unit/test_fund_data_ingestion_service.py -q`

Expected: all tests pass.

### Task 7: Fund Ingest API Endpoint

**Files:**
- Modify: `app/api/routes/funds.py`
- Modify: `tests/unit/test_funds_api.py`
- Modify: `docs/modules/app_api.md`
- Modify: `docs/REFERENCE.md`
- Modify: `docs/CHANGELOG.md`

- [x] **Step 1: Write failing API test**

Add a test proving `POST /api/funds/ingest` delegates `dataset`, `rows`, and `source` to `FundDataIngestionService.ingest_rows()`.

- [x] **Step 2: Run red test**

Run: `python -m pytest tests/unit/test_funds_api.py::test_ingest_fund_rows_delegates_to_ingestion_service -q`

Expected: import or route failure because `get_fund_ingestion_service` / `/api/funds/ingest` is missing.

- [x] **Step 3: Implement endpoint**

Add `FundIngestRowsRequest`, `get_fund_ingestion_service()`, and `POST /api/funds/ingest` to `app/api/routes/funds.py`. The route should return service results, map `ValueError` to HTTP 400, and log unexpected failures as HTTP 500.

- [x] **Step 4: Run green test**

Run: `python -m pytest tests/unit/test_funds_api.py -q`

Expected: all tests pass.

- [x] **Step 5: Update docs and verification**

Run:
`python -m pytest tests/unit/test_fund_data_ingestion_service.py tests/unit/test_fund_contracts.py tests/unit/data_layer/repositories/test_fund_repository.py tests/unit/test_fund_intelligence_service.py tests/unit/test_funds_api.py -q`

Expected: all tests pass.

### Task 8: Fund Intelligence Web Panel

**Files:**
- Modify: `app/web/templates/index.html`
- Modify: `app/web/static/js/app.js`
- Create: `app/web/static/js/funds.js`
- Modify: `app/web/static/style.css`
- Modify: `docs/modules/app_web.md`
- Modify: `docs/FILE_GUIDE.md`
- Modify: `docs/CHANGELOG.md`
- Test: `tests/unit/test_funds_frontend_static.py`

- [x] **Step 1: Write failing static wiring tests**

Add tests that prove the workbench has a `fund-intelligence` navigation item, a `section-funds` page, a module import/export for `initFundsPanel()`, and UI code that calls `/api/funds/{symbol}`, `/api/funds/{symbol}/exposure`, `/api/funds/portfolio/exposure`, and `/api/funds/ingest`.

- [x] **Step 2: Run red test**

Run:
`python -m pytest tests/unit/test_funds_frontend_static.py -q`

Expected: fail because the fund web panel and `funds.js` module do not exist yet.

- [x] **Step 3: Implement HTML and app wiring**

Add a left-nav entry and `section-funds` with search, metrics, holdings/exposure, portfolio exposure, and row-ingestion controls. Import `initFundsPanel()` in `app/web/static/js/app.js`, export it to `window`, and initialize it when the section is opened.

- [x] **Step 4: Implement focused JS module**

Create `app/web/static/js/funds.js` with API calls, loading/error handling, HTML escaping, fund detail rendering, exposure rendering, portfolio exposure parsing, and JSON row ingestion.

- [x] **Step 5: Add panel styles and docs**

Add compact Fund Intelligence styles to `app/web/static/style.css`, update web module/file docs, and record the frontend integration in `docs/CHANGELOG.md`.

- [x] **Step 6: Run green tests and smoke checks**

Run:
`python -m pytest tests/unit/test_funds_frontend_static.py tests/unit/test_funds_api.py -q`

Expected: all tests pass.

Run:
`node --check app/web/static/js/funds.js && node --check app/web/static/js/app.js`

Expected: both files parse successfully.
