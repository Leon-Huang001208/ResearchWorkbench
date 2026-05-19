# Module: app/api

## Responsibility

`app/api` exposes AlphaFoundry capabilities through FastAPI.

API routes should be thin and delegate business logic to `core/services`.

---

## Design Rules

- Route files should not contain business logic.
- Request/response schemas should use `app/api/models.py` or `core/contracts`.
- Service dependencies should be explicit.
- API behavior changes must update `docs/REFERENCE.md`.
- Add or update API tests when endpoint behavior changes.

---

## Files

### `app/api/main.py`

Purpose:

- Create FastAPI app.
- Register routes.
- Configure middleware and health checks.

Update this section when:

- App initialization changes.
- Middleware changes.
- Route registration changes.

---

### `app/api/models.py`

Purpose:

- Define API-level request/response models when not using core contracts directly.

Update this section when:

- API schema changes.
- Request/response models are added or modified.

---

### `app/api/routes/dashboard.py`

Purpose:

- Expose dashboard endpoints.

Related service:

- `core/services/dashboard_service.py`

Related contracts:

- `core/contracts/dashboard.py`

Update this section when:

- Dashboard endpoint changes.
- Response schema changes.
- Dashboard route dependency changes.

---

### `app/api/routes/market_data.py`

Purpose:

- Expose market data ETL endpoints.

Endpoints:

- `POST /api/market-data/stocks/sync` — trigger stock master sync.
- `POST /api/market-data/daily-bars/sync` — trigger daily bars sync.
- `GET /api/market-data/{symbol}/daily-bars` — query daily bars for a symbol.
- `GET /api/market-data/etl-runs` — query ETL run history.

Related service:

- `core/services/market_data_ingestion_service.py`

Related repositories:

- `data_layer/repositories/market_data_repository.py`
- `data_layer/repositories/etl_run_repository.py`

Update this section when:

- Market data endpoint changes.
- Request/response schema changes.
- Market data route dependency changes.

---

## Required Tests

- API route tests
- Error response tests
- Request/response schema tests

---

## Required Documentation Updates

When files in this module change, check:

- `docs/modules/app_api.md`
- `docs/REFERENCE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`