"""Static boundary tests for the existing UI's merged-platform API adapters."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "app/web/static/js"


def _script(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_market_home_reads_only_the_facts_domain_and_has_no_generated_brief():
    """Regression caught: the homepage must not drift back to legacy/AI aggregation."""

    script = _script("dashboard.js")

    assert "/api/market-home/live" in script
    assert "'/api/dashboard'" not in script
    assert "/api/dashboard/market-overview" not in script
    assert "renderMarketAiBrief" not in script


def test_asset_page_reads_the_canonical_observation_without_automatic_agent_run():
    """Regression caught: opening a fact page must not invoke a research agent."""

    script = _script("asset.js")

    assert "/api/asset-observation/assets/" in script
    assert "'/api/assets/analysis-card'" not in script
    assert "'/api/assets/agent-committee'" not in script


def test_theme_page_uses_theme_domain_views_instead_of_the_legacy_graph_api():
    """Regression caught: theme value-chain/event reads must stay behind Pack APIs."""

    script = _script("industry.js")

    assert "/api/themes/" in script
    assert "/value-chain" in script
    assert "/events" in script
    assert "/api/graph/industry-chain" not in script
    assert "/api/graph/propagation" not in script


def test_research_entry_creates_workspace_session_and_never_writes_fact_domains():
    """Regression caught: research output must remain in the research zone."""

    script = _script("research-workbench.js")

    assert "/api/research-workspaces" in script
    assert "/api/research-sessions" in script
    assert "/messages" in script
    assert "/api/research-runs" in script
    forbidden_writes = (
        "apiCall('POST', '/api/market-home",
        "apiCall('POST', '/api/themes",
        "apiCall('POST', '/api/asset-observation/assets",
    )
    assert not any(pattern in script for pattern in forbidden_writes)
