"""Official index structure ingestion script tests."""


def test_resolve_provider_index_codes_uses_discovered_active_codes():
    from scripts.run_official_index_structure_ingestion import _resolve_provider_index_codes

    calls = []

    def fake_discoverer(provider, *, max_count):
        calls.append((provider, max_count))
        return {"CSI": ["000300"], "CNI": ["399001", "399006"]}[provider]

    assert _resolve_provider_index_codes(
        "CSI",
        explicit_codes=[],
        discover_active=True,
        max_count=25,
        discoverer=fake_discoverer,
    ) == ["000300"]
    assert calls == [("CSI", 25)]


def test_resolve_provider_index_codes_prefers_explicit_codes():
    from scripts.run_official_index_structure_ingestion import _resolve_provider_index_codes

    def fake_discoverer(provider, *, max_count):
        raise AssertionError("discovery should not run when explicit codes are provided")

    assert _resolve_provider_index_codes(
        "CNI",
        explicit_codes=["399001"],
        discover_active=True,
        max_count=10,
        discoverer=fake_discoverer,
    ) == ["399001"]
