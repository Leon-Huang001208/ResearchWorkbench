# Test Report: Cjpy Asset Analysis Page Wiring

**Task**: Wire Cjpy into asset analysis page data flow  
**Date**: 2026-06-02  
**Status**: ✅ Complete

---

## Background

User reported the web asset analysis page was very slow. Investigation revealed Cjpy (天软) was completely absent from the asset analysis data flow; the page was falling through to Wind Excel (45s, all-zero OHLCV data).

## Root Cause

1. `AssetAnalysisService._enrich_from_coordinator()` only used Wind → MultiSourceCoordinator as data sources
2. `MultiSourceCoordinator` had no Cjpy adapter initialized
3. Cjpy DataFrame column names (`时间`, `vol`, `preclose`) not mapped to expected English names (`date`, `volume`, `pre_close`)

## Changes

### Source Files Modified

1. **`services/asset_analysis_service.py`** — Cjpy added as primary K-line source
   - `_enrich_from_coordinator()`: Priority chain changed to Cjpy → Wind → MultiSourceCoordinator
   - `_fetch_cjpy_price_bars_with_timeout()`: New async wrapper with 10s timeout
   - `_fetch_cjpy_price_bars()`: New sync method calling CjpyAdapter + column rename
   - Column mapping: `时间`→`date`, `vol`→`volume`, `preclose`→`pre_close`

2. **`data_layer/coordinator/multi_source_coordinator.py`** — Cjpy added as first priority source
   - `_init_cjpy_adapter()`: Lazy init with try/except (fixed `self.logger`→`logger`)
   - `_get_available_sources()`: Cjpy prepended as first priority
   - `_fetch_from_cjpy()`: Cjpy DataFrame → MarketData conversion with column rename
   - `_safe_float()`, `_safe_int()`: Static helper methods

### Test Files Modified

3. **`tests/unit/test_asset_analysis_service.py`** — Updated to mock Cjpy as unavailable
   - `test_analysis_card_prefers_wind_price_bars_and_adds_technical_series`: Patched `_fetch_cjpy_price_bars_with_timeout` to return []
   - `test_analysis_card_falls_back_to_coordinator_when_wind_unavailable`: Same patch for fallback chain test

## Commands Run

| Command | Result |
|---------|--------|
| `ruff check .` | ✅ All checks passed |
| `black --check .` | ⚠️ 9 pre-existing files need reformat (not from this change) |
| `isort --check-only .` | ✅ Passed |
| `mypy core/ data_layer/ ...` | ⚠️ 1 pre-existing apscheduler stub warning |
| `python -m pytest tests/ -v` | ✅ 1546 passed, 0 failed |
| `python scripts/generate_py_file_index.py` | ✅ Generated |
| `python scripts/check_doc_sync.py` | ✅ Passed |

## E2E Verification

```text
AssetAnalysisService.generate_analysis_card("600519.SH"):
  Total time: 1.08s (was 45s+)
  Source: cjpy ✅
  Current price: 1307.22 (real data)
  Price bars: 243 (1 year of daily bars)
  Latest: 2026-06-02 O=1306.0 H=1326.36 L=1301.0 C=1307.22 V=3,636,185
  Technical: MA5=1304.36, MA20=1324.93, MACD DIF=-27.08, BOLL Upper=1388.16
  52w High: 1568.0, 52w Low: 1250.1
```

## Performance Comparison

| Metric | Before (Wind) | After (Cjpy) |
|--------|--------------|--------------|
| Fetch time | 45s+ | 1.08s |
| Speedup | — | **42x faster** |
| Data quality | All-zero OHLCV | Real market data |
| Technical indicators | None | MA/MACD/BOLL/RSI/ATR |
| Fields | ~10 | 41 (incl. order book) |
| Availability | Fragile (numpy/xlwings) | Reliable (HTTP Token) |

## Remaining Risks

- None. Cjpy is the primary source; Wind and MultiSourceCoordinator remain as fallbacks.
- The fix is backward-compatible: if Cjpy is unavailable, the old Wind → Coordinator chain still works.
