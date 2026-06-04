# Module: timing_engine

## Responsibility

`timing_engine` provides market timing models, including regime, flow, sentiment, diffusion, crowding, liquidity, and expectation-gap signals, plus meta timing assessment.

---

## Design Rules

- Timing signals should be reproducible
- Model parameters should be explicit
- Blocking logic should be conservative
- Keep calculations deterministic
- Add or update tests when timing logic changes

---

## Files

### `timing_engine/*.py`

Purpose:
- Market regime detection
- Flow and sentiment indicators
- Crowding and liquidity metrics
- Readiness scoring
- Blocking assessment

Update this section when:
- Timing factor calculation changes
- Readiness score logic changes
- Blocking criteria change
- Meta timing behavior changes

#### Recent Changes

- **2026-06**: Added `Literal` import and `_action(...) -> Literal["enter", "wait", "reduce", "exit", "block"]` return type annotation in `meta.py`; added `-> None` return type annotations on `__init__` and `_register_defaults` in `models/registry.py` for improved type safety.

---

## Required Tests

- Deterministic calculation tests
- Edge case handling tests
- Invalid input tests
- Blocking/readiness logic tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/timing_engine.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`