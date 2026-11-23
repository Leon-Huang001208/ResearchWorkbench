"""Select only the FinGPT native-workspace change set; unknown files stay full."""

PATHS = {
    "tests/research_web/test_api.py",
    "app/research_web/service_manager.py",
    "tests/research_web/test_service_manager.py",
    "app/research_web/ui/core.mjs",
    "app/research_web/ui/qa-navigation.mjs",
    "tests/javascript/research_web_asset_tabs.test.mjs",
    "app/research_web/multiuser/fingpt_config.py",
    "app/research_web/qa_execution.py",
    "docs/generated/py_file_index.md",
    "README.md",
    "docs/architecture/research-web/readme-review.json",
    "tests/javascript/actions_quota_governance.test.mjs",
    "tests/javascript/verification_policy.test.mjs",
    ".agents/verification-policy.json",
    "outputs/research-web-architecture/api-atlas.html",
    "outputs/research-web-architecture/index.html",
    "docs/architecture/research-web/architecture-map.json",
    ".github/workflows/research-web-checks.yml",
    ".github/workflows/research-web-bootstrap.yml",
    "app/research_web/multiuser/fingpt.py",
    "app/research_web/multiuser/gateway.py",
    "app/research_web/multiuser/__main__.py",
    "app/research_web/mcp_facade/config.py",
    "app/research_web/knowledge_backend/client.py",
    "app/research_web/knowledge_backend/service.py",
    "app/research_web/fingpt_retirement.py",
    "app/research_web/service.py",
    "app/research_web/ui/app.mjs",
    "app/research_web/ui/index.html",
    "app/research_web/ui/server/session.mjs",
    "app/research_web/ui/fingpt-workspace.mjs",
    "app/research_web/ui/fingpt-workspace.css",
    "app/research_web/ui/progress-data.json",
    "integrations/weknora/workspace_proxy.py",
    "integrations/weknora/rwb-fingpt.html",
    "integrations/weknora/rwb-fingpt.mjs",
    "research_workbench_entrypoint/resident/model_provider_upgrade.py",
    "scripts/fingpt_workspace_ci.py",
    "scripts/run_fingpt_workspace_ci.sh",
    "tests/research_web/test_fingpt_identity.py",
    "tests/research_web/test_fingpt_proxy.py",
    "tests/research_web/test_fingpt_retirement.py",
    "tests/javascript/research_web_fingpt_workspace.test.mjs",
}


def selected(files):
    return bool(
        
            set(files)
            & {"app/research_web/multiuser/fingpt.py", "app/research_web/fingpt_retirement.py"}
            or {
                "research_workbench_entrypoint/resident/model_provider_upgrade.py",
                "tests/research_web/test_fingpt_retirement.py",
            }
            <= set(files)
        
    ) and all(
        name in PATHS or name.endswith(".md") and name.startswith(("docs/", ".ai/reports/"))
        for name in files
    )
