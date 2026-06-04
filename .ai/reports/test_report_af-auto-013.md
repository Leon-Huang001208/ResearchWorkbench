# Test Report: AF-AUTO-013 Asset Analysis Page Fixes (Final)

## Task ID
af-auto-013 (ETF search + Wind direct fallback + 前十大股东明细 + 近期事件 + 宏观敏感性)

## Changed Source Files

### This Session (Phase 4-5 + 前十大股东明细)

#### Macro Sensitivity (新功能)
- `services/macro_sensitivity.py` — **新建**: `MacroSensitivityCalculator` 类 + `MACRO_PROXY_ETFS` 映射，Cjpy 批量获取标的+5 个代理 ETF，`numpy.linalg.lstsq` OLS 回归，5 个 Beta 系数
- `services/asset_analysis_service.py` — `_enrich_from_coordinator()` 中集成 `_compute_macro_sensitivity()`，替代空 `MacroSensitivity()`

#### 前十大股东明细 (修复)
- `data_layer/adapters/akshare_adapter.py` — `fetch_top_shareholders()` 从 mock 数据改为真实 `AkShareClient.get_stock_gdfx_top_10_em()`
- `data_layer/adapters/wind/formulas.py` — 新增 `s_info_top10_holdername/ratio/quantity` 三个按排名公式
- `data_layer/adapters/wind/wind_adapter.py` — 新增 `fetch_top10_holder_details()` 逐项股东明细
- `services/asset_analysis_service.py` — `_fill_shareholder_data()` 改为 async，4 级优先级：DB → Wind逐项 → Wind聚合 → AKShare

#### 近期事件 (修复)
- `services/asset_analysis_service.py` — `_fill_recent_events()` 新增 3 级 fallback；新增 `_map_to_event_impact()` 静态方法
- `data_layer/adapters/akshare/akshare_client.py` — 新增 `get_stock_notice_report()` 封装 `ak.stock_individual_notice_report`

### Prior Sessions
- `services/asset_analysis_service.py` — `_fill_wind_market_snapshot()`, `_fill_industry_data()` Wind fallback, `_fill_shareholder_data()` Wind aggregate fallback, `_get_available_wind_adapter()`, `_build_basic_info()`, `_optional_str()`, `_latest_report_date()`
- `data_layer/adapters/wind/wind_adapter.py` — `fetch_market_snapshot()` 轻量快照
- `services/asset_search_index_service.py` — ETF 搜索
- `data_layer/normalizers/symbol.py` — ETF 前缀映射

## Changed Test Files
- `tests/unit/test_macro_sensitivity.py` — **新建**: 16 个测试覆盖回归逻辑、边界情况、Cjpy mock、AssetAnalysisService 集成
- `tests/unit/test_asset_analysis_service.py` — 原有 9 个测试全部更新适配 async shareholder + 新增 fallback 路径 mock

## Changed Docs
- `docs/CHANGELOG.md` — Added entries for all three new features
- `docs/FILE_GUIDE.md` — Added `macro_sensitivity.py` entry
- `docs/generated/py_file_index.md` — Auto-regenerated

## Commands Run
```bash
ruff check . — PASSED
black . — 1 file reformatted (wind/client.py), re-check PASSED
isort . — PASSED (2 files auto-fixed)
mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/ — 5935 pre-existing errors, 0 new
python -m pytest tests/unit/test_asset_analysis_service.py tests/unit/test_macro_sensitivity.py -v -q — 25 passed (17.77s)
python scripts/generate_py_file_index.py — PASSED
python scripts/check_doc_sync.py — PASSED
python scripts/check_task_completion.py — PASSED
```

## Command Results
- **ruff**: All checks passed
- **black**: All files formatted correctly
- **isort**: All imports sorted correctly
- **mypy**: No new errors (all 5935 pre-existing)
- **pytest (focused)**: 25/25 passed
- **file index**: Regenerated
- **doc sync**: PASSED
- **task completion**: PASSED

## Test Details

### test_macro_sensitivity.py (16 tests)
| Test | Result |
|------|--------|
| test_regression_returns_sensitivity_with_enough_data | PASSED |
| test_regression_returns_empty_with_insufficient_data | PASSED |
| test_regression_handles_missing_stock_column | PASSED |
| test_regression_handles_empty_dataframe | PASSED |
| test_regression_handles_no_date_column | PASSED |
| test_regression_handles_no_close_column | PASSED |
| test_regression_identifies_key_factors_by_beta_threshold | PASSED |
| test_regression_handles_date_column_name_variants | PASSED |
| test_compute_uses_cjpy_adapter_and_returns_sensitivity | PASSED |
| test_compute_returns_empty_when_cjpy_unavailable | PASSED |
| test_compute_returns_empty_when_data_empty | PASSED |
| test_compute_handles_cjpy_adapter_exception | PASSED |
| test_regression_handles_partial_factor_data | PASSED |
| test_regression_handles_tiny_beta_values | PASSED |
| test_enrich_sets_macro_sensitivity | PASSED |
| test_compute_macro_sensitivity_returns_empty_on_failure | PASSED |

### test_asset_analysis_service.py (9 tests)
| Test | Result |
|------|--------|
| test_generate_snapshot_with_mock_data | PASSED |
| test_get_latest_snapshot | PASSED |
| test_mock_snapshot_contains_all_fields | PASSED |
| test_price_bar_keeps_technical_indicator_fields | PASSED |
| test_generate_analysis_card_uses_requested_time_range | PASSED |
| test_days_from_time_range_maps_wind_style_ranges | PASSED |
| test_fill_wind_market_snapshot_populates_valuation_turnover_and_basic_info | PASSED |
| test_fill_industry_data_uses_wind_when_stock_master_has_only_level1 | PASSED |
| test_fill_shareholder_data_falls_back_to_wind_aggregates_when_db_empty | PASSED |

## Remaining Risks
- **Wind availability**: Wind fallback paths gracefully return empty when Wind unavailable (unit tests verified), but actual Wind integration not tested (requires Excel + Wind plugin)
- **AKShare availability**: Both shareholder (`stock_gdfx_top_10_em`) and announcement (`stock_individual_notice_report`) APIs require AKShare; gracefully degrade when unavailable
- **Cjpy availability**: Macro sensitivity requires Cjpy for ETF proxy data; gracefully returns empty MacroSensitivity() when unavailable
- **Proxy ETF selection**: Hardcoded mapping (511010.SH for rates, 510880.SH for inflation, etc.) may need refinement for certain sectors
- **CanonicalEvent table**: Likely empty until event ingestion pipeline runs; falls back to AKShare announcements
- **min_observations=60**: Macro sensitivity requires ~3 months of data minimum; shorter time ranges return empty
- Pre-existing issues (zero-float-to-None in `_build_from_structured_tables`, event loop blocking in filler methods, file size 1108+ lines) noted but not introduced by this task

## Final Test Decision
**PASS** — All 25 targeted tests pass, all quality gates pass, no new mypy errors, doc sync verified.

Phase 1 (valuation/turnover/market_cap) ✅
Phase 2 (industry level2/3) ✅
Phase 3 (shareholder aggregates) ✅
Phase 4 (recent events) ✅ — 3-tier fallback: DocumentEventV1DB → CanonicalEvent → AKShare
Phase 5 (macro sensitivity) ✅ — OLS regression with Cjpy proxy ETFs
前十大股东明细 ✅ — 4-tier priority: DB → Wind individual → Wind aggregate → AKShare
