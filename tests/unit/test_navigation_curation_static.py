"""Static wiring tests for the curated desktop navigation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sidebar_groups_available_sections_before_in_development_sections():
    template = (ROOT / "app/web/templates/index.html").read_text(encoding="utf-8")

    workspace_label = template.index('<div class="activity-group-label">工作区</div>')
    in_development_label = template.index('<div class="activity-group-label">待开发</div>')

    available_sections = [
        'data-section="dashboard"',
        'data-section="asset-analysis"',
        'data-section="funds"',
        'data-section="signal-lab"',
        'data-section="commentary"',
        'data-section="templates"',
        'data-section="pipeline-monitor"',
        'data-section="event-signal"',
        'data-section="signals"',
        'data-section="memory"',
        'data-section="wind"',
    ]
    in_development_sections = [
        'data-section="scenario"',
        'data-section="industry-chain"',
        'data-section="review"',
        'data-section="outcomes"',
        'data-section="ingest"',
    ]

    assert workspace_label < in_development_label
    for section in available_sections:
        assert workspace_label < template.index(section) < in_development_label
    for section in in_development_sections:
        assert in_development_label < template.index(section)
    assert "工具" not in template[: template.index('<div class="activity-bar-bottom">')]


def test_navigation_curation_toggle_targets_in_development_sections():
    source = (ROOT / "app/web/static/js/navigation-curation.js").read_text(encoding="utf-8")

    assert "显示待开发入口" in source
    assert "隐藏待开发入口" in source
    assert "ARCHIVED_SECTIONS[0]" in source
    assert "barTop.insertBefore(btn, firstArchivedBtn);" in source
