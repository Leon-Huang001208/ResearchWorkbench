"""Configuration registry tests."""

from core.settings.registry import DESKTOP_CONFIGURATION_FIELDS, desktop_env_template


def test_desktop_template_uses_registered_postgresql_contract():
    template = desktop_env_template()
    configured_keys = {field.key for field in DESKTOP_CONFIGURATION_FIELDS}

    assert (
        "# DATABASE_URL=postgresql+psycopg://<username>:<password>@127.0.0.1:5432/research_workbench"
        in template
    )
    assert (
        "DATABASE_URL=postgresql+psycopg://user:password@127.0.0.1:5432/research_workbench"
        not in template
    )
    assert "DATABASE_URL" in configured_keys
    assert "RESEARCH_CRAWLER_AUTOSTART=1" in template
    assert next(
        field for field in DESKTOP_CONFIGURATION_FIELDS if field.key == "DATABASE_URL"
    ).restart_required
    assert next(
        field
        for field in DESKTOP_CONFIGURATION_FIELDS
        if field.key == "RESEARCH_CRAWLER_AUTOSTART"
    ).restart_required
    assert (
        next(field for field in DESKTOP_CONFIGURATION_FIELDS if field.key == "DATABASE_URL").default
        == ""
    )
    assert "sqlite:///" not in template
