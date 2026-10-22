"""Tinysoft auto routing checks the exact series rather than broad macro coverage."""

from types import SimpleNamespace

import pytest

from app.research_web.datahub import BusinessQuery, DataHub
from app.research_web.datahub.broker import resolve
from app.research_web.datahub.catalog import build_catalog
from app.research_web.store import StoreError


@pytest.fixture
def ready(monkeypatch):
    from app.research_web.datahub import catalog

    monkeypatch.setattr(catalog, "_dependency_status", lambda *_args: (True, None))
    return {"tinysoft": {"configured": True, "secret_configured": True}}


def test_auto_selects_only_supported_tinysoft_adjustment_series(ready):
    resolution = resolve(
        BusinessQuery(capability="factor_macro", parameters={"series": "adjustment_metadata"}),
        environ={},
        connection_statuses=ready,
    )
    assert resolution.provider_id == "tinysoft"
    assert resolution.query.source == "tinysoft"
    with pytest.raises(StoreError) as error:
        resolve(
            BusinessQuery(capability="factor_macro", parameters={"series": "CPI"}),
            environ={},
            connection_statuses=ready,
        )
    assert error.value.code == "factor_series_unsupported"


def test_catalog_declares_only_three_adjustment_series(ready):
    catalog = build_catalog(environ={}, connection_statuses=ready)
    binding = next(
        item
        for item in catalog["bindings"]
        if item["source_id"] == "tinysoft" and item["capability_id"] == "factor_macro"
    )
    assert binding["implemented"] is True
    assert binding["datasets"] == ["adjustment_metadata", "listing_date", "adjustment_factors"]
    assert binding["markets"] == ["沪深A股"]
    assert binding["assets"] == ["股票"]
    assert "宏观" not in binding["coverage"]


@pytest.mark.parametrize("storage_read", [False, True])
@pytest.mark.parametrize("asset", ["000001.SH", "510050.SH"])
@pytest.mark.parametrize("capability", ["market_bars", "market_snapshot"])
def test_cached_wind_authorization_rejects_nonstock_identity(
    ready, storage_read, asset, capability
):
    statuses = {
        **ready,
        "wind": {
            "configured": True,
            "credential_store_available": True,
            "preferred_adapter": "excel",
        },
    }
    hub = SimpleNamespace(
        connections=SimpleNamespace(statuses=lambda: statuses),
        source_configuration_digest=lambda _: "a" * 64,
        _latest_probes=dict,
        admission=None,
    )
    parameters = {
        "asset_type": "stock",
        **({"asset": asset} if capability == "market_bars" else {"assets": ["600000.SH", asset]}),
    }
    query = BusinessQuery(capability=capability, source="auto", parameters=parameters)
    with pytest.raises(StoreError) as error:
        DataHub._authorize_query(
            hub,
            "session",
            query,
            cached=True,
            provider="wind",
            authorization_fingerprint="a" * 64,
            storage_read=storage_read,
        )
    assert error.value.code == "data_not_equivalent"


@pytest.mark.parametrize("storage_read", [False, True])
@pytest.mark.parametrize("asset", ["600000.SH", "000001.SZ"])
@pytest.mark.parametrize("capability", ["market_bars", "market_snapshot"])
def test_cached_wind_authorization_keeps_valid_explicit_stock_unchanged(
    ready, storage_read, asset, capability
):
    statuses = {
        **ready,
        "wind": {
            "configured": True,
            "credential_store_available": True,
            "preferred_adapter": "excel",
        },
    }
    hub = SimpleNamespace(
        connections=SimpleNamespace(statuses=lambda: statuses),
        source_configuration_digest=lambda _: "a" * 64,
        _latest_probes=dict,
        admission=None,
    )
    parameters = {
        "asset_type": "stock",
        **({"asset": asset} if capability == "market_bars" else {"assets": [asset]}),
    }
    query = BusinessQuery(capability=capability, source="auto", parameters=parameters)
    result = DataHub._authorize_query(
        hub,
        "session",
        query,
        cached=True,
        provider="wind",
        authorization_fingerprint="a" * 64,
        storage_read=storage_read,
    )
    assert result.provider_id == result.query.source == "wind"
    assert result.query.parameters == parameters


def test_auto_activity_filters_sources_by_the_requested_dataset(ready):
    result = resolve(
        BusinessQuery(
            capability="market_activity",
            parameters={"asset": "000001.SZ", "dataset": "holder_details"},
        ),
        environ={},
        connection_statuses=ready,
    )
    assert result.provider_id == "tinysoft"
    result = resolve(
        BusinessQuery(
            capability="market_activity", parameters={"asset": "000001.SZ", "dataset": "fund_flow"}
        ),
        environ={},
        connection_statuses=ready,
    )
    assert result.provider_id != "tinysoft"


def test_explicit_unsupported_activity_source_does_not_fallback(ready):
    with pytest.raises(StoreError):
        resolve(
            BusinessQuery(
                capability="market_activity",
                source="tinysoft",
                parameters={"asset": "000001.SZ", "dataset": "fund_flow"},
            ),
            environ={},
            connection_statuses=ready,
        )
