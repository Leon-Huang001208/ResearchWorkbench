"""Contract tests for the declarative Research Pack registry."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.contracts.theme_research import PackLifecycle
from services.theme_pack_registry import (
    PluginSecurityError,
    ThemePackRegistry,
    ThemePackValidationError,
)

PACK_ROOT = Path(__file__).parents[2] / "resources" / "research_packs"


def test_registry_loads_the_four_versioned_pack_manifests() -> None:
    registry = ThemePackRegistry(PACK_ROOT)

    manifests = registry.discover()

    assert {manifest.pack_key for manifest in manifests} == {
        "gold",
        "aerospace",
        "photovoltaic",
        "ai_infrastructure",
    }
    assert all(manifest.status is PackLifecycle.DISCOVERED for manifest in manifests)
    assert all(manifest.datasets for manifest in manifests)
    assert all(manifest.research_template_keys for manifest in manifests)


def test_manifest_declares_schema_source_freshness_and_units() -> None:
    gold = ThemePackRegistry(PACK_ROOT).get("gold")

    assert {dataset.dataset_key for dataset in gold.datasets} >= {
        "gold_price",
        "gold_supply_demand",
        "gold_etf_flow",
        "sge_spot",
        "central_bank_reserves",
        "gold_macro",
    }
    assert all(dataset.fields for dataset in gold.datasets)
    assert all(dataset.source_priority for dataset in gold.datasets)
    assert all(dataset.freshness_seconds > 0 for dataset in gold.datasets)
    assert all(kpi.unit and kpi.frequency for kpi in gold.kpis)


def test_chinext_50_is_only_an_index_exposure_for_pv_and_ai() -> None:
    registry = ThemePackRegistry(PACK_ROOT)

    photovoltaic = registry.get("photovoltaic")
    ai = registry.get("ai_infrastructure")

    for manifest in (photovoltaic, ai):
        exposure = next(
            item for item in manifest.asset_exposures if item.asset.asset_id == "index:399673.SZ"
        )
        assert exposure.asset.asset_type.value == "index"
        assert exposure.exposure_type == "market_proxy"


def test_registry_rejects_forbidden_plugin_permission(tmp_path: Path) -> None:
    manifest = yaml.safe_load((PACK_ROOT / "gold" / "manifest.yaml").read_text("utf-8"))
    manifest["plugin_permissions"] = ["network"]
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")

    registry = ThemePackRegistry(tmp_path)

    with pytest.raises(ThemePackValidationError, match="forbidden permission"):
        registry.load(path)


@pytest.mark.parametrize(
    "source",
    [
        "import socket\ndef normalize(row): return row\n",
        "from sqlalchemy import select\ndef validate(row): return True\n",
        "import subprocess\ndef derive(row): return subprocess.run(['x'])\n",
        "def normalize(row):\n    return open('/tmp/x').read()\n",
        "from core.model_gateway import gateway\ndef derive(row): return gateway.chat([])\n",
    ],
)
def test_plugin_static_gate_rejects_network_database_model_shell_and_filesystem(
    source: str,
) -> None:
    registry = ThemePackRegistry(PACK_ROOT)

    with pytest.raises(PluginSecurityError):
        registry.validate_plugin_source(source)


def test_plugin_runtime_gate_only_exposes_registered_pure_operations() -> None:
    registry = ThemePackRegistry(PACK_ROOT)
    registry.register_plugin("trim", "normalize", lambda value: value.strip())

    assert registry.run_plugin("trim", "  gold  ") == "gold"
    with pytest.raises(PluginSecurityError, match="not registered"):
        registry.run_plugin("unknown", "value")


def test_plugin_runtime_gate_rejects_non_json_capability_input() -> None:
    registry = ThemePackRegistry(PACK_ROOT)
    registry.register_plugin("identity", "validate", lambda value: value)

    with pytest.raises(PluginSecurityError, match="JSON-like"):
        registry.run_plugin("identity", Path("/tmp/secret"))


def test_pack_lifecycle_only_allows_documented_transitions() -> None:
    registry = ThemePackRegistry(PACK_ROOT)

    assert registry.transition("gold", PackLifecycle.VALIDATED).status is PackLifecycle.VALIDATED
    assert registry.transition("gold", PackLifecycle.ENABLED).status is PackLifecycle.ENABLED
    assert registry.transition("gold", PackLifecycle.DEGRADED).status is PackLifecycle.DEGRADED
    assert registry.transition("gold", PackLifecycle.ENABLED).status is PackLifecycle.ENABLED
    assert registry.transition("gold", PackLifecycle.DISABLED).status is PackLifecycle.DISABLED
    with pytest.raises(ThemePackValidationError, match="invalid lifecycle transition"):
        registry.transition("aerospace", PackLifecycle.ENABLED)
