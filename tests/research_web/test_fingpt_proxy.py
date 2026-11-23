"""The full native app must keep RWB cookies out of WeKnora."""

import pytest

from integrations.weknora.workspace_proxy import configure_workspace


def test_proxy_filters_both_directions_and_preserves_relay():
    original = """server {
    listen 80;
    add_header X-Frame-Options "SAMEORIGIN" always;
    location /api/ { proxy_pass http://app:8080/api/; }
    location /mcp/ { proxy_pass http://app:8080; }
}
server {
    listen 11435;
    location / { proxy_pass http://embedding; }
}
"""
    result = configure_workspace(original, "https://rwb.tail123.ts.net")
    assert result.count("proxy_set_header Cookie $rwb_weknora_cookie") == 2
    assert result.count("proxy_hide_header Set-Cookie") == 2
    assert "~^weknora_oidc_nonce=" in result
    assert "default_type application/javascript" in result
    assert "frame-ancestors 'self' https://rwb.tail123.ts.net" in result
    assert (
        result.split("server {\n    listen 11435;")[1]
        == original.split("server {\n    listen 11435;")[1]
    )


def test_proxy_rejects_missing_frontend_and_duplicate_application():
    with pytest.raises(ValueError):
        configure_workspace("server {listen 11435;}", "http://localhost")
    with pytest.raises(ValueError):
        configure_workspace("# RWB full workspace cookie boundary", "http://localhost")


def test_same_host_mcp_requires_explicit_cookie_boundary():
    from app.research_web.mcp_facade.config import resident_execution, validate_weknora_gateway

    origin = "https://rwb.tail123.ts.net"
    with pytest.raises(ValueError, match="cookie_host_conflict"):
        validate_weknora_gateway(origin, origin + ":9443", 8089)
    validate_weknora_gateway(origin, origin + ":9443", 8089, cookie_isolated=True)
    assert resident_execution(
        {
            "origin": origin,
            "port": 8089,
            "weknora_oauth_origin": origin + ":9443",
            "weknora_cookie_isolated": True,
        },
        mcp_enabled=True,
    ) == (False, origin + ":9443")


def test_workspace_ci_rejects_unrelated_changes():
    from scripts.fingpt_workspace_ci import selected

    files = ["app/research_web/multiuser/fingpt.py", "integrations/weknora/workspace_proxy.py"]
    assert selected(files)
    assert not selected(files + ["app/research_web/datahub/providers.py"])
    assert not selected(["docs/research-web-fingpt-workspace.md"])

    gateway_fix = [
        "research_workbench_entrypoint/resident/model_provider_upgrade.py",
        "tests/research_web/test_fingpt_retirement.py",
    ]
    assert selected(gateway_fix)
    assert not selected(gateway_fix[:1])
    assert not selected(gateway_fix + ["app/research_web/datahub/providers.py"])
