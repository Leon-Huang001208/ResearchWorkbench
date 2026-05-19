# Module: core/services

## Responsibility

`core/services` contains AlphaFoundry's business orchestration logic.

Services coordinate:

- Contracts
- Repositories
- Crawlers
- Retrieval
- Reasoning
- Timing
- Signal generation
- Memory
- Reporting
- API/CLI use cases

---

## Design Rules

- Keep API route files thin.
- Put business logic in services.
- Use Pydantic contracts from `core/contracts`.
- Delegate persistence to repositories or storage utilities.
- Mock external dependencies in tests.
- Avoid UI-specific assumptions.
- Avoid direct network calls unless wrapped by adapters/gateways.
- Add or update tests when service behavior changes.

---

## Data Flow

Typical flow:

```text
app/api or app/cli
→ core/services
→ core/contracts
→ data_layer / knowledge_layer / reasoning / signal_lab / timing_engine / memory_learning
→ storage or repositories
→ response contract
```

---

## Files

### `core/services/dashboard_service.py`

Purpose:

- Aggregates dashboard data for the Web Workbench.
- Provides market status, recent news, signal summary, and research queue summary.

Related API:

- `app/api/routes/dashboard.py`

Related contracts:

- `core/contracts/dashboard.py`

Tests:

- Add or update dashboard service tests when dashboard fields or aggregation logic changes.

Update this section when:

- Dashboard output changes.
- Market summary logic changes.
- New dashboard panel is added.
- Dashboard API dependency changes.

---

### `core/services/ingest_service.py`

Purpose:

- Orchestrates document and event ingestion.
- Coordinates chunking, classification, entity extraction, event extraction, storage, and indexing.

Related files:

- `core/services/document_chunker.py`
- `core/services/document_classifier.py`
- `core/services/entity_extractor.py`
- `core/services/event_extractor.py`
- `core/services/raw_storage_service.py`

Tests:

- Add ingestion service tests when pipeline order, input type, or extraction behavior changes.

Update this section when:

- Ingestion pipeline changes.
- New document type is added.
- Extraction behavior changes.
- Storage/indexing behavior changes.

---

### `core/services/market_data_ingestion_service.py`

Purpose:

- Orchestrates ETL pipeline for market data: crawler → normalizer → structured SQL tables → ETL run tracking.
- `ingest_stock_master(limit)`: fetch stock list from AKShare, normalize, upsert to `stock_master` table.
- `ingest_daily_bars(symbols, start_date, end_date)`: fetch daily bars, normalize, upsert to `stock_daily_bar` table.

Related files:

- `data_layer/normalizers/akshare_market.py`
- `data_layer/repositories/market_data_repository.py`
- `data_layer/repositories/etl_run_repository.py`
- `data_layer/adapters/akshare_adapter.py`

Related API:

- `app/api/routes/market_data.py`

Tests:

- Add ingestion service tests when ETL pipeline order, input type, or failure recovery behavior changes.

Update this section when:

- ETL steps change.
- Normalizer adapter changes.
- New ingestion target is added.
- Failure/retry behavior changes.

---

## Common Pitfalls

- Do not put API-specific response formatting inside services.
- Do not bypass contracts.
- Do not make live external calls in unit tests.
- Do not update service behavior without updating tests and docs.

---

## Required Documentation Updates

When files in this module change, check:

- `docs/modules/core_services.md`
- `docs/FILE_GUIDE.md`
- `docs/ARCHITECTURE.md` if flow or boundary changes
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`