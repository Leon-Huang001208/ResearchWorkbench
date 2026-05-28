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

### `data_layer/crawlers/zq/zhiqiu/processors/report_processor.py`

Purpose:

- Processes ZhiQiu research report PDFs: download, register as `PDFArtifactV1DB` (parse_status=pending), and save metadata.
- `_download_and_record_pdf()` — downloads PDF to disk, computes SHA-256 hash, registers in `pdf_artifact_v1` for automatic pickup by `CrawlScheduler` → `PDFConversionService`.
- `process()`, `_process_old_format()`, `_process_new_format()` — entry points for report processing.

Update this section when:

- PDF download/registration logic changes.
- Report format detection changes.
- PDF artifact metadata fields change.

---

### `data_layer/crawlers/cls/utils/deduplication.py`

Purpose:

- File-based deduplication store for CLS crawler (`DeduplicationStore`).
- `is_processed(item_id)` — checks if an item was already crawled.
- `mark_processed(item_id)` — marks an item as processed.
- `remove_stale(valid_ids)` — removes processed entries no longer present in the database, preventing permanent crawl skip after document deletion.
- `has_reached_watermark()` — watermark-based dedup for time-series items.

Update this section when:

- Dedup state file format changes.
- New dedup methods are added.
- Watermark logic changes.

---

### `data_layer/crawlers/utils/__init__.py`

Purpose:

- Exports anti-crawling utilities: `AntiScrapeKit`, `UserAgentRotator`, `SmartDelayer`, `retry_with_backoff`.
- PDF conversion exports were removed (dead code — `pdf_converter.py` deleted, conversion handled by `PDFConversionService`).

Update this section when:

- New crawler utilities are added.
- Anti-crawling exports change.

---

### `data_layer/crawlers/utils/pdf_converter.py` (DELETED)

This file was deleted as dead code. It contained a crawler-level `PDFConverter` (pdfplumber-based) that was never activated (`enable_pdf_conversion` always `False`). PDF conversion is now handled exclusively by `services/pdf_conversion_service.py` with MinerU/MarkItDown/RawText strategies and full database tracking.

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

### `data_layer/adapters/data_source_router.py`

Purpose:

- Implements a 3-tier degradation strategy: iFinD → AKShare → ChinaStock.
- Maintains instances of all 7 adapters: IFinDAdapter, AKShareAdapter, ChinaStockAdapter, CLSAdapter, CNStockAdapter, ZQAdapter.
- Provides async methods for each data category: `fetch_stock_quotes`, `fetch_financial_report`, `fetch_fund_flow`, `fetch_industry_classification`, `fetch_macro_indicators`, `fetch_technical_indicators`, `fetch_sentiment`.
- Direct adapter calls for news: `fetch_news_cls`, `fetch_news_cnstock`, `fetch_reports_zq`.
- Falls back to `AssetAnalysisSnapshot` with `evidence_refs=["insufficient_evidence"]` when all adapters fail.

Update this section when:

- New adapter is added.
- Degradation strategy changes.
- New data category method is added.
- Insufficient evidence fallback behavior changes.

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