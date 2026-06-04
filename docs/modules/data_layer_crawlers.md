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

### `data_layer/crawlers/cninfo/`

Purpose:

- Fetch listed-company announcements from 巨潮资讯网 (CNINFO) through `CninfoCrawler`.
- Own CNINFO HTTP session setup, search API pagination, timeout, and rate-limit delay behavior.
- Return raw announcement dictionaries for `CninfoAdapter` to convert into `DocumentEnvelope` records.

Update this section when:

- CNINFO query parameters, pagination, or retry/rate-limit behavior changes.
- Raw announcement field mapping changes.
- New CNINFO datasets are added.

---

### `data_layer/adapters/cninfo_adapter.py`

Purpose:

- Wrap `CninfoCrawler` and convert CNINFO announcement dictionaries into `DocumentEnvelope` objects.
- Generate idempotent document IDs from `adjunctUrl` or stable announcement fields.
- Normalize CNINFO metadata (`sec_code`, `sec_name`, `announcement_type`, `announcement_id`) for downstream document ingestion.

Update this section when:

- CNINFO envelope fields or metadata mapping changes.
- CNINFO adapter fetch parameters change.
- Document source type or canonical text construction changes.

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

### `data_layer/crawlers/cnstock/cnstock.py`

Purpose:

- Core CNStock (中国证券网) crawler: fetch flash news (快讯) and regular channel news (证券/公司/产经/金融/时政).
- Dual-path architecture: **Playwright** (primary) for WAF bypass, **requests** (fallback) when Playwright unavailable.
- Flash news extracted from `__NEXT_DATA__` SSR payload embedded in page HTML.
- Regular channels captured by intercepting `channelNewsList` XHR responses triggered by page navigation.
- Browser reuse across channels: single `playwright.Browser` instance shared in `crawl_news_list()`.

**WAF bypass background**: On 2026-05, cnstock.com deployed Alibaba Cloud WAF that blocks direct `requests` calls (returns `10304` "未登录"). Both `requests.Session` with Playwright cookies and `page.evaluate(fetch)` are blocked — only page-native XHR/fetch responses captured via `page.on("response")` before `page.goto()` succeed.

Update this section when:

- CNStock site structure or URL scheme changes.
- WAF behavior or bypass strategy changes.
- Playwright interaction pattern changes.
- SSR data extraction path changes.

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
| `formulas.py` | ~75 个 Wind 公式生成器，覆盖一致预期/两融/龙虎榜/价格K线/财务/行业指数/资金流向/持有人 |
| `wind_adapter.py` | `WindAdapter(BaseDataAdapter)`：8 个高层接口（一致预期、两融、龙虎榜、日行情、财务、行业、资金流向、持有人） |
| `__init__.py` | 模块导出 |

**三类数据接口：**

| 接口 | 数据覆盖 | Wind 公式前缀 |
|------|----------|--------------|
| 一致预期/分析师预测 | 净利润、EPS、营业收入 (fy1/fy2/fy3/ftm/avg)，目标价 (180/90/30天)，综合评级 (数值/中文/英文) | `s_west_*`, `s_wrating_*`, `s_rating_*` |
| 融资融券 | 融资余额、融券余量、融资买入额、融资偿还额、融券卖出量、融券偿还量 | `s_margin_*` |
| 龙虎榜 | 净买入额、买入金额、卖出金额、上榜次数 | `s_abnormaltrade_*`, `s_pq_abnormaltrade_*` |

**关键设计决策：**

- 连接复用：整个 session 复用同一 Excel 连接，优先连接已运行的实例
- 自动启动：如果未检测到运行中的 Excel，`WindExcelClient._connect()` 会通过 `xlwings.App(visible=..., add_book=True)` 启动新实例，而不是跳过 Wind 健康检查
- 批量执行：列式写入公式（Z 列），一次等待 Excel 完成所有计算
- 心跳检测：每次批量执行前自动检测 Wind 会话有效性，过期时抛出 `WindSessionExpiredError`
- 保活机制：后台 daemon 线程每 30 分钟执行心跳，防止 Wind 自动登出；过期时触发回调

**测试：** `tests/unit/test_wind_adapter.py` — 90+ 个单元测试（5 异常 + 50+ 公式 + 7 结构 + 4 客户端 + 9 新方法）

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

---

## Related Subsystems

- `connectors/` — 连接器实现通过 Wrapper-first 策略委托本模块的适配器（如 `CLSDocumentConnector` → `CLSAdapter`）。当前调度和 CLI 的统一入口是 Connector；`data_layer/adapters/` 只保留为连接器内部委托层和少量 legacy 调用层。
- `core/connectors/` — 连接器抽象基类和注册表
