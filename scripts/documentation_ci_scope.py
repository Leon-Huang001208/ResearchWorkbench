"""The closed static-document slice shared by the existing Web CI selector."""


def documentation_paths():
    pages = [
        "architecture",
        "getting-started",
        "guide-data",
        "guide-skills",
        "guide-mcp",
        "reference-data",
        "reference-skills",
        "reference-mcp",
        "reference-api",
        "architecture-guide",
        "operations-guide",
        "troubleshooting",
        "glossary",
        "documentation-version",
    ]
    domains = [
        "sessions",
        "datahub",
        "assets",
        "capabilities",
        "mcp",
        "events",
        "ai-news",
        "report-workflows",
        "legacy-reports",
        "automation",
        "hot",
        "knowledge",
        "frameworks",
        "operations",
        "integrations",
        "local-integrations",
        "strategy",
        "documentation",
    ]
    pages += ["reference-api-" + domain for domain in domains]
    return {"outputs/research-web-architecture/" + page + ".html" for page in pages} | {
        "scripts/build_documentation_center.mjs",
        "scripts/documentation_center.py",
        "scripts/documentation_markdown.py",
        "scripts/documentation_ci_scope.py",
        "docs/manual/navigation.json",
        "docs/manual/api-reference.json",
        "tests/research_web/test_documentation_center.py",
        "app/research_web/ui/settings.mjs",
        "tests/javascript/research_web_settings_ui.test.mjs",
        "docs/architecture/research-web/architecture-map.json",
        "outputs/research-web-architecture/api-atlas.html",
    }
