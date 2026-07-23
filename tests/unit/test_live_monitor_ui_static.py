from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_live_monitor_removes_derived_event_count_and_detail_meta_cards():
    template = (ROOT / "app/web/templates/index.html").read_text(encoding="utf-8")
    monitor_js = (ROOT / "app/web/static/js/monitor.js").read_text(encoding="utf-8")

    assert 'id="monitor-summary-events"' not in template
    assert 'id="monitor-detail-source"' not in template
    assert 'id="monitor-detail-time"' not in template
    assert "monitor-summary-events" not in monitor_js
    assert "monitor-detail-source" not in monitor_js
    assert "monitor-detail-time" not in monitor_js


def test_live_monitor_removes_secondary_header_copy():
    template = (ROOT / "app/web/templates/index.html").read_text(encoding="utf-8")
    monitor_js = (ROOT / "app/web/static/js/monitor.js").read_text(encoding="utf-8")

    assert "点击筛选" not in template
    assert 'id="workers-last-updated"' not in template
    assert 'id="monitor-feed-meta"' not in template
    assert "workers-last-updated" not in monitor_js
    assert "monitor-feed-meta" not in monitor_js
    assert "实时事件流" not in monitor_js


def test_live_monitor_feed_title_uses_selected_source_only():
    template = (ROOT / "app/web/templates/index.html").read_text(encoding="utf-8")
    monitor_js = (ROOT / "app/web/static/js/monitor.js").read_text(encoding="utf-8")

    assert '<h3 id="monitor-feed-title">全部来源</h3>' in template
    assert "const title = document.getElementById('monitor-feed-title');" in monitor_js
    assert "activeMonitorSource === 'all' ? '全部来源'" in monitor_js
    assert "title.textContent = activeSourceLabel();" in monitor_js


def test_live_monitor_hides_source_label_in_single_source_mode():
    monitor_js = (ROOT / "app/web/static/js/monitor.js").read_text(encoding="utf-8")

    assert "const sourceLabelMarkup = activeMonitorSource === 'all'" in monitor_js
    assert "${sourceLabelMarkup}" in monitor_js
    assert "? `<span>${esc(sourceLabel)}</span>`" in monitor_js
    assert ": '';" in monitor_js


def test_live_monitor_uses_clean_display_title_for_report_list():
    monitor_js = (ROOT / "app/web/static/js/monitor.js").read_text(encoding="utf-8")

    assert "const displayTitle = cleanMonitorDisplayTitle(item.title || '');" in monitor_js
    assert "title=\"${esc(item.title || '')}\"" in monitor_js
    assert "${esc(displayTitle || item.title || '(无标题)')}" in monitor_js
    assert "function cleanMonitorDisplayTitle(title)" in monitor_js
    assert "[\\\\s\\\\-—_：:]*\\\\d{8}$" in monitor_js


def test_live_monitor_refreshes_cnstock_detail_content_on_demand():
    monitor_js = (ROOT / "app/web/static/js/monitor.js").read_text(encoding="utf-8")

    assert "function refreshMonitorEventContent(item)" in monitor_js
    assert "shouldRefreshMonitorContent(item)" in monitor_js
    assert "/api/dashboard/crawl-feed/${encodeURIComponent(item.doc_id)}/content" in monitor_js
    assert "method: 'POST'" in monitor_js
    assert "monitorContentRefreshes" in monitor_js


def test_dashboard_exposes_crawl_feed_content_refresh_route():
    route_source = (ROOT / "app/api/routes/dashboard.py").read_text(encoding="utf-8")

    assert '@router.post("/crawl-feed/{doc_id}/content"' in route_source
    assert "CrawlFeedContentService" in route_source


def test_live_monitor_keeps_250_items_per_source():
    monitor_js = (ROOT / "app/web/static/js/monitor.js").read_text(encoding="utf-8")

    assert "const MAX_UNIFIED_ITEMS = 250;" in monitor_js
    assert "limit: 200" not in monitor_js
    assert "items.slice(0, MAX_UNIFIED_ITEMS)" in monitor_js


def test_live_monitor_source_dot_distinguishes_idle_sources():
    monitor_js = (ROOT / "app/web/static/js/monitor.js").read_text(encoding="utf-8")
    style_css = (ROOT / "app/web/static/style.css").read_text(encoding="utf-8")

    # 未启动抓取的数据源（无 lastCrawledAt / items / totalToday）判定为非 running
    assert (
        "const running = Boolean(state.lastCrawledAt || state.items.length || state.totalToday)"
        in monitor_js
    )
    assert "running," in monitor_js
    # running=false 时圆点附加 idle class，否则保持默认绿色圆点
    assert (
        "const dotClass = running ? 'monitor-status-dot' : 'monitor-status-dot idle';" in monitor_js
    )
    # CSS 提供 idle 红色样式
    assert "#section-dashboard .monitor-status-dot.idle {" in style_css
    assert "#ff453a" in style_css


def test_live_monitor_cache_versions_are_bumped():
    template = (ROOT / "app/web/templates/index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "app/web/static/js/app.js").read_text(encoding="utf-8")

    assert "/static/js/app.js?v=20260723refresh1" in template
    assert "./monitor.js?v=20260714a" in app_js
