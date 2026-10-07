"""Capability declarations describe implementations, never native acceptance."""

import json

import pytest

from research_workbench_entrypoint import platform_capabilities as boundaries


@pytest.mark.parametrize("platform", ["darwin", "linux", "win32", "unknown"])
def test_native_projection_never_claims_platform_validation(platform):
    capabilities = boundaries.platform_capabilities("native", platform_name=platform)
    sandbox = capabilities["research_script_sandbox"]
    assert sandbox["status"] == ("available" if platform == "darwin" else "unsupported")
    assert all(item["validated"] is False for item in capabilities.values())
    assert capabilities["architecture_documentation"]["status"] == (
        "available" if platform in {"darwin", "linux"} else "unsupported"
    )
    assert "docker_credential_acl" not in capabilities


@pytest.mark.parametrize("mode", ["native", "docker"])
@pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
def test_model_system_storage_is_only_a_macos_native_implementation(mode, platform):
    capabilities = boundaries.platform_capabilities(mode, platform_name=platform)
    storage = capabilities["model_system_storage"]
    assert storage["status"] == (
        "available" if mode == "native" and platform == "darwin" else "unsupported"
    )
    assert storage["validated"] is False


@pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
def test_docker_projection_preserves_legacy_status_and_acl_boundary(platform):
    capabilities = boundaries.platform_capabilities("docker", platform_name=platform)
    for name in ("office", "wind", "tabbit"):
        assert capabilities[name]["status"] == "unavailable_in_docker"
        assert capabilities[name]["support_status"] == "unsupported"
        assert capabilities[name]["required"] is False
    assert capabilities["research_script_sandbox"]["status"] == "unsupported"
    assert capabilities["architecture_documentation"]["status"] == "available"
    assert capabilities["docker_credential_acl"]["status"] == (
        "not_verified" if platform == "win32" else "available"
    )
    assert all(item["validated"] is False for item in capabilities.values())


def test_projection_is_safe_fresh_and_rejects_unknown_mode(monkeypatch):
    monkeypatch.setenv("API_KEY", "private-test-sentinel")
    first = boundaries.platform_capabilities("native", platform_name="darwin")
    first["research_script_sandbox"]["validated"] = True
    second = boundaries.platform_capabilities("native", platform_name="darwin")
    assert second["research_script_sandbox"]["validated"] is False
    assert "private-test-sentinel" not in json.dumps(second)
    with pytest.raises(ValueError, match="runtime mode"):
        boundaries.platform_capabilities("invalid")


@pytest.mark.parametrize("primitive", ["nofollow", "directory", "nonblock", "dir_fd"])
def test_document_reader_never_falls_back_when_safe_primitives_are_missing(monkeypatch, primitive):
    if primitive == "dir_fd":
        monkeypatch.setattr(boundaries.os, "supports_dir_fd", set())
    else:
        name = {"nofollow": "O_NOFOLLOW", "directory": "O_DIRECTORY", "nonblock": "O_NONBLOCK"}[
            primitive
        ]
        monkeypatch.delattr(boundaries.os, name)
    assert boundaries.documentation_reader_available(platform_name="darwin") is False
    assert (
        boundaries.platform_capabilities("native", platform_name="darwin")[
            "architecture_documentation"
        ]["status"]
        == "unsupported"
    )


def test_fallback_doctor_keeps_same_capability_projection(tmp_path, monkeypatch):
    from research_workbench_entrypoint import web_bootstrap

    monkeypatch.setattr(web_bootstrap, "bootstrap_service_facts", lambda *_: {})
    monkeypatch.setattr(web_bootstrap, "_python_issue", lambda *_: "python_environment_missing")
    assert web_bootstrap.diagnose(tmp_path, {})["capabilities"] == boundaries.platform_capabilities(
        "native"
    )
