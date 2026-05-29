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
- Maintains instances of all 8 adapters: WindAdapter, IFinDAdapter, AKShareAdapter, ChinaStockAdapter, CLSAdapter, CNStockAdapter, ZQAdapter.
- Provides async methods for each data category: `fetch_stock_quotes`, `fetch_financial_report`, `fetch_fund_flow`, `fetch_industry_classification`, `fetch_macro_indicators`, `fetch_technical_indicators`, `fetch_sentiment`.
- Direct adapter calls for news: `fetch_news_cls`, `fetch_news_cnstock`, `fetch_reports_zq`.
- Falls back to `AssetAnalysisSnapshot` with `evidence_refs=["insufficient_evidence"]` when all adapters fail.

Update this section when:

- New adapter is added.
- Degradation strategy changes.
- New data category method is added.
- Insufficient evidence fallback behavior changes.

---

### `data_layer/adapters/wind/` — Wind Excel 适配器

新增于 2026-05-29。通过 xlwings → AppleScript → Excel Wind 插件获取专业金融数据，macOS 原生支持。

**组成文件：**

| 文件 | 职责 |
|------|------|
| `exceptions.py` | 5 个自定义异常：`WindError`、`WindSessionExpiredError`、`WindNotConnectedError`、`WindFormulaError`、`WindTimeoutError` |
| `client.py` | `WindExcelClient`：xlwings 连接管理、心跳检测（`s_info_compname`）、批量列式公式执行、后台保活线程（30min 间隔防自动登出）、15s 超时 |
| `formulas.py` | 35 个 Wind 公式生成器（所有公式名已通过 Mac 版 Wind Excel 函数浏览器逐个验证并实测通过） |
| `wind_adapter.py` | `WindAdapter(BaseDataAdapter)`：三个高层接口 `fetch_consensus_estimates`、`fetch_margin_trading`、`fetch_block_trades` |
| `__init__.py` | 模块导出 |

**三类数据接口：**

| 接口 | 数据覆盖 | Wind 公式前缀 |
|------|----------|--------------|
| 一致预期/分析师预测 | 净利润、EPS、营业收入 (fy1/fy2/fy3/ftm/avg)，目标价 (180/90/30天)，综合评级 (数值/中文/英文) | `s_west_*`, `s_wrating_*`, `s_rating_*` |
| 融资融券 | 融资余额、融券余量、融资买入额、融资偿还额、融券卖出量、融券偿还量 | `s_margin_*` |
| 龙虎榜 | 净买入额、买入金额、卖出金额、上榜次数 | `s_abnormaltrade_*`, `s_pq_abnormaltrade_*` |

**关键设计决策：**
- 连接复用：整个 session 复用同一 Excel 连接，优先连接已运行的实例
- 批量执行：列式写入公式（Z 列），一次等待 Excel 完成所有计算
- 心跳检测：每次批量执行前自动检测 Wind 会话有效性，过期时抛出 `WindSessionExpiredError`
- 保活机制：后台 daemon 线程每 30 分钟执行心跳，防止 Wind 自动登出；过期时触发回调

**测试：** `tests/unit/test_wind_adapter.py` — 43 个单元测试（5 异常 + 23 公式 + 5 结构 + 4 客户端逻辑）

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