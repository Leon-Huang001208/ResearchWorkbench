import re
from pathlib import Path

ASSET_JS = Path(__file__).resolve().parents[2] / "app" / "web" / "static" / "js" / "asset.js"
APP_JS = Path(__file__).resolve().parents[2] / "app" / "web" / "static" / "js" / "app.js"
INDEX_HTML = Path(__file__).resolve().parents[2] / "app" / "web" / "templates" / "index.html"


def test_kline_mouse_leave_resets_quote_to_visible_rightmost_bar():
    source = ASSET_JS.read_text(encoding="utf-8")

    assert re.search(
        r"function\s+getKLineVisibleRightIndex\s*\(\s*count\s*,\s*zoomState\s*=\s*{}\s*\)",
        source,
    )
    assert source.index("const endPercent = Number(zoomState.end);") < source.index(
        "const endValue = Number(zoomState.endValue);"
    )
    assert re.search(
        r"const\s+resetKLineQuoteToVisibleRight\s*=\s*\(\)\s*=>\s*{[^}]*chartKLine\.getOption\(\)\?\.dataZoom\?\.\[0\][^}]*getKLineVisibleRightIndex\(\s*bars\.length\s*,\s*zoomState\s*\)",
        source,
        flags=re.S,
    )
    assert re.search(
        r"container\.addEventListener\(\s*['\"]mouseleave['\"]\s*,\s*resetKLineQuoteToVisibleRight\s*\)",
        source,
        flags=re.S,
    )
    assert re.search(
        r"document\.addEventListener\(\s*['\"]mousemove['\"]\s*,\s*documentMouseMoveHandler\s*\)",
        source,
        flags=re.S,
    )


def test_kline_static_module_versions_are_bumped():
    app_source = APP_JS.read_text(encoding="utf-8")
    index_source = INDEX_HTML.read_text(encoding="utf-8")

    assert "./asset.js?v=20250604d" in app_source
    assert "/static/js/app.js?v=20250604d" in index_source


def test_chip_distribution_uses_visible_range_volume_profile_like_wind():
    source = ASSET_JS.read_text(encoding="utf-8")
    index_source = INDEX_HTML.read_text(encoding="utf-8")

    assert "function calculateVisibleChipDistributionFromBars" in source
    assert "buildChipDistributionSnapshot(baseData, priceBars, startIndex, endIndex)" in source
    assert "chip_window_label: formatChipWindowLabel(sourceBars, safeStart, safeEnd)" in source
    assert "scheduleVisibleChipDistributionUpdate" in source
    assert re.search(
        r"const\s+updateActiveKLineIndex\s*=\s*\(index\)\s*=>\s*{[\s\S]*?scheduleVisibleChipDistributionUpdate\(\s*startIndex\s*,\s*safeIndex\s*\)",
        source,
    )
    assert "scheduleChipDistributionUpdate(safeIndex)" not in source
    assert "windowDays = 90" not in source
    assert "normalizeChipTurnover" not in source
    assert "近90日" not in source
    assert "近90日" not in index_source
    assert "移动成本" not in index_source
    assert "<h4>普通筹码</h4>" in index_source


def test_kline_overlay_colors_match_wind_and_distinguish_ma60():
    source = ASSET_JS.read_text(encoding="utf-8")

    assert "{ key: 'ma60', name: 'MA60', color: '#10b981' }" in source
    assert "{ key: 'ma250', name: 'MA250', color: '#a3a3a3' }" in source
    assert "{ key: 'boll_upper', name: 'BOLL上轨', label: 'UPPER', color: '#ffff00', lineColor: '#ffff00' }" in source
    assert "{ key: 'boll_middle', name: 'BOLL中轨', label: 'MID', color: '#d9d9d9', lineColor: '#d9d9d9' }" in source
    assert "{ key: 'boll_lower', name: 'BOLL下轨', label: 'LOWER', color: '#ff00ff', lineColor: '#ff00ff' }" in source
    assert "lineStyle: { width: 1, color: cfg.lineColor }" in source


def test_kline_quote_open_high_low_avg_use_price_direction_classes():
    source = ASSET_JS.read_text(encoding="utf-8")

    assert "function getQuotePriceClass(value, reference)" in source
    assert "const priceReference = safeIndex > 0 ? toFiniteNumber(quoteBars[safeIndex - 1]?.close) : toFiniteNumber(activeBar.open);" in source
    assert "setClass('kline-quote-open', getQuotePriceClass(activeBar.open, priceReference));" in source
    assert "setClass('kline-quote-high', getQuotePriceClass(activeBar.high, priceReference));" in source
    assert "setClass('kline-quote-low', getQuotePriceClass(activeBar.low, priceReference));" in source
    assert "setClass('kline-quote-avg', getQuotePriceClass(avgPrice, priceReference));" in source
