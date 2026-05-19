# Module: data_layer crawlers

## Responsibility

This module collects external market, news, financial, and research data.

Main source families:

- AKShare
- CaiLianShe
- China Securities Journal
- ZhiQiu
- Other future financial/news/research sources

---

## Design Rules

- Unit tests should not depend on live network access.
- External calls should be mockable.
- Field mappings must be documented.
- Source-specific assumptions must be recorded in `docs/DATA_SOURCES.md`.
- Retry, timeout, and rate-limit behavior must be explicit.

---

## Files

### `data_layer/adapters/akshare_adapter.py`

Purpose:

- Provide a unified adapter over AKShare crawler functionality.
- Expose market, financial, news, and shareholder data retrieval.

Update this section when:

- New AKShare capability is added.
- Returned field mapping changes.
- Adapter method behavior changes.

---

### `data_layer/crawlers/akshare/market.py`

Purpose:

- Fetch stock list, historical market data, real-time quotes, and index data.

Update this section when:

- New market endpoint is added.
- Field mapping changes.
- Retry/rate-limit behavior changes.

---

### `data_layer/crawlers/akshare/financial.py`

Purpose:

- Fetch financial summary, indicators, statements, and related financial data.

Update this section when:

- Financial endpoint changes.
- Statement field mapping changes.
- Data cleaning behavior changes.

---

### `data_layer/normalizers/` (normalizer layer)

Normalizers transform raw crawler output into structured dicts for repository upsert. They are pure functions: deterministic, no side effects, directly unit-testable.

Main normalizers:

| File | Input | Output |
|---|---|---|
| `normalizers/symbol.py` | raw A-share code | normalized `XXXXXX.SH/SZ/BJ` |
| `normalizers/akshare_market.py` | `MarketData` / `StockInfo` | dict for `stock_master` / `stock_daily_bar` |
| `normalizers/akshare_financial.py` | `FinancialData` | dict for `stock_financial_metric` |

Update this section when:

- New normalizer is added.
- Field mapping changes.
- Symbol normalization rules change.

---

## Required Tests

- Mocked crawler tests
- Parser tests
- Normalizer tests
- Field mapping tests
- Failure/retry tests

---

## Required Documentation Updates

When files in this module change, check:

- `docs/modules/data_layer_crawlers.md`
- `docs/DATA_SOURCES.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`