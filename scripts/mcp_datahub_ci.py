"""Exact MCP/DataHub path scope; the runner and evidence contract stay unchanged."""

MCP_PATHS = {
    ".agents/verification-policy.json",
    ".github/workflows/project-constraints.yml",
    ".github/workflows/research-web-bootstrap.yml",
    ".github/workflows/research-web-checks.yml",
    "README.md",
    "app/research_web/asset_history_jobs.py",
    "app/research_web/asset_workspace.py",
    "app/research_web/datahub/__init__.py",
    "app/research_web/datahub/broker.py",
    "app/research_web/datahub/catalog.py",
    "app/research_web/datahub/connections.py",
    "app/research_web/datahub/contracts.py",
    "app/research_web/datahub/external_sources.json",
    "app/research_web/datahub/external_sources.py",
    "app/research_web/datahub/planning.py",
    "app/research_web/datahub/providers.py",
    "app/research_web/datahub/providers_finance_market.py",
    "app/research_web/datahub/providers_finance_mcp.py",
    "app/research_web/datahub/providers_wind.py",
    "app/research_web/datahub/research_warehouse.py",
    "app/research_web/datahub/warehouse.py",
    "app/research_web/mcp_facade/backend.py",
    "app/research_web/mcp_facade/models.py",
    "app/research_web/mcp_facade/oauth_views.py",
    "app/research_web/mcp_facade/server.py",
    "app/research_web/mcp_facade/task_contracts.py",
    "app/research_web/mcp_facade/tools.py",
    "app/research_web/ui/progress-data.json",
    "docs/architecture/research-web/readme-review.json",
    "outputs/weknora-datahub-skill-layer/index.html",
    "scripts/architecture/build_weknora_skill_layer_reader.mjs",
    "scripts/run_mcp_datahub_ci.sh",
    "tests/javascript/actions_quota_governance.test.mjs",
    "tests/javascript/verification_policy.test.mjs",
    "tests/research_web/test_asset_history.py",
    "tests/research_web/test_asset_loading.py",
    "tests/research_web/test_asset_workspace.py",
    "tests/research_web/test_connection_center.py",
    "tests/research_web/test_datahub_catalog.py",
    "tests/research_web/test_datahub_finance_mcp.py",
    "tests/research_web/test_datahub_planning.py",
    "tests/research_web/test_external_sources.py",
    "tests/research_web/test_finance_market_contract.py",
    "tests/research_web/test_mcp_facade_datahub.py",
    "tests/research_web/test_mcp_task_contracts.py",
}
CORE = {
    "app/research_web/mcp_facade/backend.py",
    "app/research_web/datahub/providers_finance_mcp.py",
}
ASSET_CONTRACT = {
    "app/research_web/datahub/contracts.py",
    "app/research_web/mcp_facade/task_contracts.py",
    "app/research_web/asset_workspace.py",
}


def selected(files):
    files = set(files)
    return (bool(CORE.intersection(files)) or ASSET_CONTRACT.issubset(files)) and all(
        name in MCP_PATHS or name.endswith(".md") and name.startswith(("docs/", ".ai/reports/"))
        for name in files
    )
