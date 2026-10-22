"""Tinysoft auto routing checks the exact series rather than broad macro coverage."""

import pytest

from app.research_web.datahub import BusinessQuery
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
