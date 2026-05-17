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