"""Dashboard cninfo monitoring wiring tests."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "app" / "web" / "templates" / "index.html"
MONITOR_JS = ROOT / "app" / "web" / "static" / "js" / "monitor.js"


def test_dashboard_monitor_has_cninfo_feed_card():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-source="cninfo"' in html
    assert 'id="feed-status-cninfo"' in html
    assert 'id="feed-count-cninfo"' in html
    assert 'id="feed-list-cninfo"' in html
    assert "巨潮公告" in html


def test_monitor_polling_includes_cninfo_source():
    source = MONITOR_JS.read_text(encoding="utf-8")

    assert "{ id: 'cninfo', label: '巨潮公告', limit: 200 }" in source
