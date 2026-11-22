"""Ordinary Catalog lifecycle for the three versioned owned methods."""

import hashlib
import importlib.util
import json
import sys

import pytest
from test_scenario_method_sources import context

from app.research_web.capabilities import catalog as catalog_module
from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.scenario_method_packages import scenario_method_packages


@pytest.fixture
def methods(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog_module, "seed_packages", scenario_method_packages)
    return CapabilityCatalog(tmp_path / "store")


def test_three_skill_packages_publish_select_and_freeze_all_resources(methods, tmp_path):
    for cid, draft in scenario_method_packages():
        assert draft["kind"] == "skill"
        assert methods.check(cid)["valid"]
        selected = methods.selection(cid)
        assert selected["version"] == 1
        methods.snapshot(selected, tmp_path / "session")
        folder = tmp_path / "session" / "resources" / "capabilities" / cid / "1"
        manifest = json.loads((folder / "references/method-code-manifest.json").read_text())
        assert manifest["method_version"] == "1.0.0"
        for item in manifest["files"]:
            assert (
                hashlib.sha256((folder / item["path"]).read_bytes()).hexdigest() == item["sha256"]
            )


def test_published_action_reopens_original_and_saves_analytical_ledger(
    methods, tmp_path, monkeypatch
):
    # Executes the actual frozen package resource. Native ToolRuntime is a
    # separate acceptance layer and is not mocked or claimed by this test.
    cid = "owned-news-evidence"
    selected = methods.selection(cid)
    root = tmp_path / "session"
    methods.snapshot(selected, root)
    scripts = root / "resources" / "capabilities" / cid / "1" / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "owned_method_check", scripts / "check_sources.py"
    )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        value = context(root)
        artifact = module.execute(root, value, "b" * 32)
        raw = (root / artifact["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]
        ledger = json.loads(raw)
        assert ledger["research_quality"] == "NOT_RUN"
        assert ledger["status"] == "incomplete"
        with pytest.raises(FileExistsError):
            module.execute(root, value, "b" * 32)
    finally:
        sys.modules.pop("source_actions", None)


def test_unreviewed_source_action_blocks_publication(methods):
    cid = methods.copy("owned-news-evidence", "Unreviewed owned method", "unreviewed-owned-method")[
        "id"
    ]
    assert not methods.check(cid)["valid"]
