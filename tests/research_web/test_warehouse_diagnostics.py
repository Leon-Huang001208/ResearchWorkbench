"""Private profile diagnosis never opens a database or exposes saved settings."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.research_web import warehouse_diagnostics as diagnostics


def profile():
    return {
        "id": "a" * 32,
        "owner": "warehouse-" + "b" * 32,
        "enabled": True,
        "configuration": {
            "host": "private-host.example",
            "port": 55432,
            "database": "rwb_market_private",
            "username": "private_user",
            "sslmode": "verify-full",
        },
    }


def save(root: Path, document=None):
    root.mkdir(mode=0o700)
    path = root / "warehouse.json"
    path.write_text(json.dumps(document if document is not None else profile()))
    path.chmod(0o600)
    return path


@pytest.fixture(autouse=True)
def no_database_or_credentials(monkeypatch):
    from app.research_web.datahub.research_warehouse import ResearchWarehouse

    def forbidden(*args, **kwargs):
        raise AssertionError("diagnosis_must_not_construct_warehouse")

    monkeypatch.setattr(ResearchWarehouse, "__init__", forbidden)
    monkeypatch.setattr(diagnostics.importlib.util, "find_spec", lambda name: object())


def test_unconfigured_does_not_create_root(tmp_path):
    root = tmp_path / "not-created"
    result = diagnostics.warehouse_diagnostic(root)
    assert result["state"] == "unconfigured"
    assert result["optional"] is True
    assert result["driver"] == "installed"
    assert result["connectivity"] == "unknown"
    assert not root.exists()


@pytest.mark.parametrize("enabled", [True, False])
def test_configured_enabled_is_never_connectivity_proof(tmp_path, enabled):
    root = tmp_path / "instance"
    value = profile()
    value["enabled"] = enabled
    path = save(root, value)
    before = path.read_bytes(), path.stat().st_mtime_ns
    result = diagnostics.warehouse_diagnostic(root)
    assert result["state"] == "configured"
    assert result["enabled"] is enabled
    assert result["connectivity"] == "unknown"
    assert result["readiness"] == "not_verified"
    assert result["code"] == "warehouse_explicit_validation_required"
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    public = json.dumps(result)
    for private in (
        str(root),
        value["id"],
        value["owner"],
        *[value["configuration"][key] for key in ("host", "database", "username")],
    ):
        assert private not in public


@pytest.mark.parametrize("field", ["password", "token", "api_key"])
def test_secret_fields_rejected_without_disclosure(tmp_path, field, caplog):
    root = tmp_path / "instance"
    value = profile()
    value["configuration"][field] = "sensitive-do-not-log"
    save(root, value)
    result = diagnostics.warehouse_diagnostic(root)
    assert result["state"] == "invalid"
    assert result["enabled"] is None
    assert "sensitive-do-not-log" not in json.dumps(result) + caplog.text


@pytest.mark.skipif(os.name == "nt", reason="POSIX private mode contract")
@pytest.mark.parametrize("target", ["file", "directory"])
def test_nonprivate_profile_or_directory_rejected(tmp_path, target):
    root = tmp_path / "instance"
    path = save(root)
    (path if target == "file" else root).chmod(0o644 if target == "file" else 0o755)
    result = diagnostics.warehouse_diagnostic(root)
    assert result["state"] == "invalid"
    assert result["code"] == "warehouse_profile_invalid"


def test_symlink_profile_is_not_followed(tmp_path):
    root = tmp_path / "instance"
    root.mkdir(mode=0o700)
    target = tmp_path / "private-other-instance"
    target.write_text(json.dumps(profile()))
    target.chmod(0o600)
    (root / "warehouse.json").symlink_to(target)
    assert diagnostics.warehouse_diagnostic(root)["state"] == "invalid"


@pytest.mark.parametrize(
    "document",
    [
        {},
        {**profile(), "enabled": "yes"},
        {**profile(), "token": "hidden"},
        {**profile(), "configuration": {**profile()["configuration"], "port": 5432}},
    ],
)
def test_bad_shape_and_protected_endpoint_invalid(tmp_path, document):
    root = tmp_path / "instance"
    save(root, document)
    assert diagnostics.warehouse_diagnostic(root)["state"] == "invalid"


def test_missing_driver_separate_from_configuration(tmp_path, monkeypatch):
    root = tmp_path / "instance"
    save(root)
    monkeypatch.setattr(diagnostics.importlib.util, "find_spec", lambda name: None)
    result = diagnostics.warehouse_diagnostic(root)
    assert result["driver"] == "missing"
    assert result["state"] == "configured"
    assert result["connectivity"] == "unknown"


@pytest.mark.parametrize("invalid", [False, True])
def test_optional_diagnosis_does_not_rewrite_installation_readiness(tmp_path, monkeypatch, invalid):
    from app.research_web.service_manager import WebServiceManager
    from research_workbench_entrypoint.resident import admission

    root = tmp_path / "instance"
    if invalid:
        save(root, {"token": "secret"})
    monkeypatch.setattr(admission, "diagnostic", lambda root: {"state": "unconfigured"})
    manager = SimpleNamespace(
        data_root=root,
        _installation_diagnosis=lambda: {"ok": True, "issues": []},
        _service_probes=lambda: (),
        _model_diagnosis=lambda: (False, ()),
        _ai_news_diagnostic=lambda: {"state": "unconfigured"},
    )
    result = WebServiceManager.doctor(manager)
    assert result["ok"] and result["installation_ok"]
    assert result["issues"] == []
    assert result["research_warehouse"]["state"] == ("invalid" if invalid else "unconfigured")
    assert result["research_warehouse"]["connectivity"] == "unknown"
