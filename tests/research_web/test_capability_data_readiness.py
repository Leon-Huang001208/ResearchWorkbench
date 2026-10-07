"""Independent expectations for declared data scope, not provider brand names."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.research_web.capabilities.models import DataRequirement, data_preflight


def catalog(*, allowed=True, frequency="daily", adjustment="qfq", pit=False, health="healthy"):
    return {
        "sources": [
            {
                "id": "fixture",
                "readiness": {
                    "integration_completed": True,
                    "configured": True,
                    "dependency_ready": True,
                    "allowed": allowed,
                    "callable": allowed,
                    "health": health,
                },
            }
        ],
        "bindings": [
            {
                "capability_id": "market_bars",
                "source_id": "fixture",
                "datasets": ["bars"],
                "implemented": True,
                "semantics": {
                    "bars": {
                        "frequencies": [frequency],
                        "adjustments": [adjustment],
                        "historical_point_in_time": pit,
                        "units": {"close": "currency_per_share"},
                        "currency": "CNY",
                    }
                },
            }
        ],
    }


def metadata(**requirements):
    return {
        "required_tools": ["datahub_get_market_bars"],
        "data_requirements": [{"capability": "market_bars", "dataset": "bars", **requirements}],
    }


def test_declared_current_semantics_and_probe_allow_the_narrow_scope():
    result = data_preflight(metadata(frequency="daily", adjustment="qfq"), catalog())
    assert result["status"] == "available" and result["admitted"] is True
    assert result["omitted_sections"] == []


@pytest.mark.parametrize(
    "requirement",
    [
        {"frequency": "minute"},
        {"adjustment": "hfq"},
        {"historical_point_in_time": True},
    ],
)
def test_daily_latest_or_different_adjustment_is_not_an_equivalent_substitute(requirement):
    result = data_preflight(metadata(**requirement), catalog())
    assert result["status"] == "unavailable" and result["admitted"] is False
    assert result["missing"][0]["code"] == "data_semantics_not_equivalent"


def test_unknown_semantics_and_legacy_data_dependencies_are_not_claimed_available():
    unknown = catalog()
    unknown["bindings"][0].pop("semantics")
    assert data_preflight(metadata(frequency="minute"), unknown)["status"] == "unverified"
    assert (
        data_preflight({"required_tools": ["datahub_get_market_bars"]}, catalog())["admitted"]
        is False
    )


def test_optional_dependency_has_a_declared_limited_scope_and_revocation_is_fresh():
    optional = metadata(required=False, omit_sections=["分钟交易分析"])
    assert data_preflight(optional, catalog())["status"] == "available"
    revoked = data_preflight(optional, catalog(allowed=False))
    assert revoked["status"] == "limited" and revoked["admitted"] is True
    assert revoked["omitted_sections"] == ["分钟交易分析"]
    assert data_preflight(metadata(), catalog(allowed=False))["admitted"] is False


def test_untested_source_is_distinct_from_verified_callable_and_invalid_contract_fails_closed():
    assert data_preflight(metadata(), catalog(health="untested"))["status"] == "unverified"
    invalid = deepcopy(metadata())
    invalid["data_requirements"][0]["url"] = "https://arbitrary.example"
    assert data_preflight(invalid, catalog())["admitted"] is False
    with pytest.raises(ValidationError):
        DataRequirement(capability="market_bars", required=False)


def test_non_data_package_does_not_gain_a_data_requirement():
    result = data_preflight({"required_tools": ["research_run_script"]}, catalog(allowed=False))
    assert result["status"] == "available" and result["admitted"] is True
