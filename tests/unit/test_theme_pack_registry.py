"""Contract tests for the declarative Research Pack registry."""

from __future__ import annotations

import copy
import importlib
import os
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
    assert all(kpi.unit and kpi.frequency and kpi.metric_key for kpi in gold.kpis)
    assert all(binding.plugin_id.startswith("builtin.") for binding in gold.plugins)


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


def test_plugin_runtime_gate_only_exposes_trusted_builtin_ids() -> None:
    registry = ThemePackRegistry(PACK_ROOT)

    assert registry.run_plugin("builtin.trim_string.v1", "  gold  ") == "gold"
    with pytest.raises(PluginSecurityError, match="trusted built-in"):
        registry.run_plugin("unknown", "value")


def test_plugin_runtime_gate_rejects_non_json_capability_input() -> None:
    registry = ThemePackRegistry(PACK_ROOT)

    with pytest.raises(PluginSecurityError, match="JSON-like"):
        registry.run_plugin("builtin.identity.v1", Path("/tmp/secret"))


@pytest.mark.parametrize(
    "function",
    [
        lambda value: getattr(__builtins__, "__import__")("os").getcwd(),
        lambda value: importlib.import_module("os").getcwd(),
        (lambda container: lambda value: container["os"].getcwd())({"os": os}),
    ],
    ids=["getattr-import", "importlib", "container-os"],
)
def test_registry_rejects_all_arbitrary_python_callable_escape_routes(function) -> None:
    registry = ThemePackRegistry(PACK_ROOT)

    with pytest.raises(PluginSecurityError, match="trusted built-in"):
        registry.register_plugin("escape", "normalize", function)


def test_manifest_forbids_unknown_keys_empty_sections_duplicates_and_bad_refs(
    tmp_path: Path,
) -> None:
    raw = yaml.safe_load((PACK_ROOT / "gold" / "manifest.yaml").read_text("utf-8"))
    invalid_variants = []

    whitespace_boundary = dict(raw, boundary="   ")
    invalid_variants.append(whitespace_boundary)

    whitespace_source = copy.deepcopy(raw)
    whitespace_source["datasets"][0]["source_priority"] = ["   "]
    invalid_variants.append(whitespace_source)

    asset_extra = copy.deepcopy(raw)
    asset_extra["asset_exposures"][0]["asset"]["provider_symbol"] = "attacker"
    invalid_variants.append(asset_extra)

    impossible_kpi = copy.deepcopy(raw)
    impossible_kpi["kpis"][0]["metric_key"] = "not_declared_by_dataset"
    invalid_variants.append(impossible_kpi)

    missing_rationale_entity = copy.deepcopy(raw)
    missing_rationale_entity["asset_exposures"][0]["rationale_ref"] = "manifest:gold:not_declared"
    invalid_variants.append(missing_rationale_entity)

    optional_identity = copy.deepcopy(raw)
    optional_identity["datasets"][0]["identity_fields"].append("source_url")
    invalid_variants.append(optional_identity)

    optional_dimension = copy.deepcopy(raw)
    optional_dimension["datasets"][0]["dimension_fields"] = ["source_url"]
    invalid_variants.append(optional_dimension)

    optional_structural = copy.deepcopy(raw)
    optional_structural["datasets"][0]["subject_field"] = "source_url"
    invalid_variants.append(optional_structural)

    extra = dict(raw, undeclared_capability=True)
    invalid_variants.append(extra)

    empty_templates = dict(raw, research_template_keys=[])
    invalid_variants.append(empty_templates)

    duplicate_dataset = dict(raw, datasets=[*raw["datasets"], raw["datasets"][0]])
    invalid_variants.append(duplicate_dataset)

    bad_reference = dict(raw)
    bad_reference["value_chain"] = [
        {
            "node_key": "bad",
            "name": "bad",
            "stage": "upstream",
            "evidence_refs": ["dataset:not_declared"],
        }
    ]
    invalid_variants.append(bad_reference)

    for index, variant in enumerate(invalid_variants):
        root = tmp_path / str(index)
        root.mkdir()
        path = root / "manifest.yaml"
        path.write_text(yaml.safe_dump(variant, allow_unicode=True), encoding="utf-8")
        with pytest.raises(ThemePackValidationError, match="manifest validation failed"):
            ThemePackRegistry(root).load(path)


def test_pack_lifecycle_only_allows_documented_transitions() -> None:
    registry = ThemePackRegistry(PACK_ROOT)

    assert registry.transition("gold", PackLifecycle.VALIDATED).status is PackLifecycle.VALIDATED
    assert registry.transition("gold", PackLifecycle.ENABLED).status is PackLifecycle.ENABLED
    assert registry.transition("gold", PackLifecycle.DEGRADED).status is PackLifecycle.DEGRADED
    assert registry.transition("gold", PackLifecycle.ENABLED).status is PackLifecycle.ENABLED
    assert registry.transition("gold", PackLifecycle.DISABLED).status is PackLifecycle.DISABLED
    with pytest.raises(ThemePackValidationError, match="invalid lifecycle transition"):
        registry.transition("aerospace", PackLifecycle.ENABLED)


def test_manifest_content_hash_excludes_database_owned_lifecycle_status() -> None:
    registry = ThemePackRegistry(PACK_ROOT)
    discovered = registry.get("gold")
    enabled = discovered.model_copy(update={"status": PackLifecycle.ENABLED})

    assert registry.content_hash(discovered) == registry.content_hash(enabled)
