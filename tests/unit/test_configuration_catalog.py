"""Tests for static configuration catalog metadata."""


def test_catalog_exposes_all_supported_sections_in_product_order():
    """Return the six configuration sections with the required metadata shape."""
    from services.configuration_catalog import get_configuration_catalog

    catalog = get_configuration_catalog()

    assert [section["key"] for section in catalog["sections"]] == [
        "llm",
        "zhiqiu",
        "ifind",
        "database",
        "advanced",
        "web_search",
    ]
    for section in catalog["sections"]:
        assert set(section) == {
            "key",
            "label",
            "scope",
            "platforms",
            "restart_required",
            "testable",
            "fields",
        }
        assert isinstance(section["platforms"], list)
        assert isinstance(section["fields"], list)
        for field in section["fields"]:
            assert set(field) == {"key", "label", "kind", "environment_keys"}
            assert isinstance(field["environment_keys"], list)


def test_database_metadata_describes_the_database_url_secret():
    """Describe the database URL precisely without exposing a value."""
    from services.configuration_catalog import get_configuration_catalog

    catalog = get_configuration_catalog()
    database = next(section for section in catalog["sections"] if section["key"] == "database")

    assert database["restart_required"] is True
    assert database["testable"] is True
    assert database["fields"] == [
        {
            "key": "database_url",
            "label": "数据库连接地址",
            "kind": "secret",
            "environment_keys": ["DATABASE_URL"],
        }
    ]


def test_zhiqiu_metadata_uses_the_existing_enabled_field_name():
    """Match the field name accepted by the existing configuration API."""
    from services.configuration_catalog import get_configuration_catalog

    catalog = get_configuration_catalog()
    zhiqiu = next(section for section in catalog["sections"] if section["key"] == "zhiqiu")
    field_keys = {field["key"] for field in zhiqiu["fields"]}

    assert "enabled" in field_keys
    assert "rotation_enabled" not in field_keys


def test_account_collections_include_all_locked_environment_keys():
    """Expose every environment key that can lock an account collection."""
    from services.configuration_catalog import get_configuration_catalog

    catalog = get_configuration_catalog()
    sections = {section["key"]: section for section in catalog["sections"]}
    zhiqiu_accounts = next(
        field for field in sections["zhiqiu"]["fields"] if field["key"] == "accounts"
    )
    web_search_accounts = next(
        field for field in sections["web_search"]["fields"] if field["key"] == "accounts"
    )

    assert zhiqiu_accounts["environment_keys"] == ["ZQ_ACCOUNTS_JSON", "ZQ_ACCOUNTS"]
    assert web_search_accounts["environment_keys"] == [
        "WEB_SEARCH_API_KEYS",
        "TAVILY_API_KEY",
        "BING_API_KEY",
    ]


def test_catalog_returns_an_independent_json_safe_copy():
    """Prevent callers from mutating the static catalog source."""
    from services.configuration_catalog import get_configuration_catalog

    first = get_configuration_catalog()
    first["sections"][0]["platforms"].append("modified")
    first["sections"][0]["fields"][0]["environment_keys"].append("MODIFIED")

    second = get_configuration_catalog()

    assert "modified" not in second["sections"][0]["platforms"]
    assert "MODIFIED" not in second["sections"][0]["fields"][0]["environment_keys"]
    assert isinstance(second["sections"][0]["platforms"], list)


def test_catalog_contains_no_runtime_configuration_values_or_paths():
    """Keep catalog data limited to safe labels, types, and environment key names."""
    import json

    from services.configuration_catalog import get_configuration_catalog

    serialized = json.dumps(get_configuration_catalog(), ensure_ascii=False).lower()

    for forbidden in ("postgres://", "postgresql://", ".env", "/users/", "api_key="):
        assert forbidden not in serialized
