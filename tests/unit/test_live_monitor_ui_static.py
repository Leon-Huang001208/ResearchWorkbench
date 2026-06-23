from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_live_monitor_removes_derived_event_count_and_detail_meta_cards():
    template = (ROOT / "app/web/templates/index.html").read_text()
    monitor_js = (ROOT / "app/web/static/js/monitor.js").read_text()

    assert 'id="monitor-summary-events"' not in template
    assert 'id="monitor-detail-source"' not in template
    assert 'id="monitor-detail-time"' not in template
    assert "monitor-summary-events" not in monitor_js
    assert "monitor-detail-source" not in monitor_js
    assert "monitor-detail-time" not in monitor_js


def test_live_monitor_removes_secondary_header_copy():
    template = (ROOT / "app/web/templates/index.html").read_text()
    monitor_js = (ROOT / "app/web/static/js/monitor.js").read_text()

    assert "点击筛选" not in template
    assert 'id="workers-last-updated"' not in template
    assert 'id="monitor-feed-meta"' not in template
    assert "workers-last-updated" not in monitor_js
    assert "monitor-feed-meta" not in monitor_js
    assert "实时事件流" not in monitor_js


def test_live_monitor_feed_title_uses_selected_source_only():
    template = (ROOT / "app/web/templates/index.html").read_text()
    monitor_js = (ROOT / "app/web/static/js/monitor.js").read_text()

    assert '<h3 id="monitor-feed-title">全部来源</h3>' in template
    assert "const title = document.getElementById('monitor-feed-title');" in monitor_js
    assert "activeMonitorSource === 'all' ? '全部来源'" in monitor_js
    assert "title.textContent = activeSourceLabel();" in monitor_js


def test_live_monitor_keeps_250_items_per_source():
    monitor_js = (ROOT / "app/web/static/js/monitor.js").read_text()

    assert "const MAX_UNIFIED_ITEMS = 250;" in monitor_js
    assert "limit: 200" not in monitor_js
    assert "items.slice(0, MAX_UNIFIED_ITEMS)" in monitor_js


def test_live_monitor_cache_versions_are_bumped():
    template = (ROOT / "app/web/templates/index.html").read_text()
    app_js = (ROOT / "app/web/static/js/app.js").read_text()

    assert "/static/js/app.js?v=20260623d" in template
    assert "./monitor.js?v=20260623d" in app_js
