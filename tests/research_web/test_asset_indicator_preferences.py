"""Closed indicator preferences retain old clients and account-owned persistence."""

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.research_web.asset_indicator_preferences import (
    INDICATOR_RULES,
    normalize_indicator_settings,
)
from app.research_web.asset_routes import ChartPreferencesRequest
from app.research_web.asset_workspace import AssetWorkspace
from app.research_web.store import Store


def workspace(root):
    return AssetWorkspace(SimpleNamespace(store=Store(root)))


def test_catalog_matches_browser_schema():
    node = shutil.which("node")
    assert node, "Node is required for the browser/backend contract"
    script = "import {INDICATOR_RULES} from './app/research_web/ui/asset-indicator-library.mjs';console.log(JSON.stringify(INDICATOR_RULES));"
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=Path(__file__).resolve().parents[2],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == json.loads(json.dumps(INDICATOR_RULES))


@pytest.mark.parametrize(
    "settings",
    [
        {"rsi": {"period": True}},
        {"rsi": {"period": "14"}},
        {"rsi": {"period": 10**400}},
        {"rsi": {"period": float("nan")}},
        {"rsi": {"period": float("inf")}},
        {"rsi": None},
        {"rsi": {"formula": "x"}},
        {"unknown": {}},
        {"volume": {"short": 10}},
        {"macd": {"fast": 26}},
        {"bias": {"short": 24}},
        {"sar": {"step": 0.5}},
    ],
)
def test_invalid_parameters_rejected_at_request_boundary(settings):
    with pytest.raises(ValidationError):
        ChartPreferencesRequest(panels=[], indicator_settings=settings)


def test_all_indicators_and_custom_parameters_are_closed():
    request = ChartPreferencesRequest(
        panels=list(INDICATOR_RULES),
        favorites=["sar", "atr"],
        indicator_settings={"cci": {"period": 20}},
    )
    assert request.indicator_settings["cci"]["period"] == 20
    for ids in [["rsi", "rsi"], ["formula"], [{}]]:
        with pytest.raises(ValidationError):
            ChartPreferencesRequest(panels=ids)


def test_read_does_not_persist_defaults_and_legacy_put_preserves_new_keys(tmp_path):
    ws = workspace(tmp_path)
    ws.store.create("fingpt", "fixture")
    before = ws.store.index.read_bytes()
    assert "indicator_settings" not in ws.chart_preferences()
    assert ws.store.index.read_bytes() == before
    settings = {"cci": {"period": 20}}
    value = ws.set_chart_preferences(["cci"], favorites=["cci", "atr"], indicator_settings=settings)
    settings["cci"]["period"] = 1
    value["indicator_settings"]["cci"]["period"] = 2
    ws.set_chart_preferences(["macd"])
    assert ws.chart_preferences()["indicator_settings"]["cci"]["period"] == 20
    assert ws.chart_preferences()["favorites"] == ["cci", "atr"]
    assert workspace(tmp_path).chart_preferences() == ws.chart_preferences()
    assert "favorites" not in workspace(tmp_path / "other").chart_preferences()


def test_store_failure_rolls_back_memory_and_disk(tmp_path, monkeypatch):
    ws = workspace(tmp_path)
    ws.set_chart_preferences(["volume"], favorites=["volume"], indicator_settings={})
    before = ws.chart_preferences()
    disk = ws.store.index.read_bytes()

    def fail():
        raise OSError("simulated storage failure")

    monkeypatch.setattr(ws.store, "save", fail)
    with pytest.raises(OSError):
        ws.set_chart_preferences(["atr"], favorites=[], indicator_settings={"atr": {"period": 3}})
    assert ws.chart_preferences() == before
    assert ws.store.index.read_bytes() == disk
    assert normalize_indicator_settings({})["atr"]["period"] == 14
