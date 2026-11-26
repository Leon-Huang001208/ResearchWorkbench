"""Select the exact model-connection scope without widening the full matrix."""


def selected(files):
    core = {"app/research_web/model_profiles.py", "app/research_web/ui/model-settings.mjs"}
    paths = core | {
        "tests/research_web/test_model_profiles.py",
        "tests/research_web/test_model_connections.py",
        "tests/javascript/research_web_model_profiles.test.mjs",
        "tests/javascript/actions_quota_governance.test.mjs",
        ".github/workflows/research-web-checks.yml",
        "scripts/run_model_profile_ci.sh",
        "docs/architecture/research-web/readme-review.json",
    }
    return bool(core.intersection(files)) and all(
        name in paths or name.endswith(".md") and name.startswith(("docs/", ".ai/reports/"))
        for name in files
    )
