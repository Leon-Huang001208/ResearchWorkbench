"""Explicit WeKnora registration is independent of the research host mode."""

import pytest

from app.research_web.mcp_facade.config import resident_execution, validate_weknora_gateway
from app.research_web.multiuser.origin import validate_origin

ISSUER = "https://research.tail123.ts.net"
CALLBACK_ORIGIN = ISSUER + ":9443"


def test_weknora_https_callback_accepts_same_host_at_a_different_origin():
    validate_weknora_gateway(ISSUER, CALLBACK_ORIGIN, 8089)


def test_tailnet_https_origin_preserves_a_nondefault_port():
    assert validate_origin(ISSUER + ":9543") == ISSUER + ":9543"
    assert validate_origin(ISSUER) == ISSUER
    assert validate_origin(ISSUER + ":443") == ISSUER + ":443"


def test_weknora_registration_supports_a_tailnet_https_issuer_port():
    config = {
        "origin": ISSUER + ":9543",
        "port": 51235,
        "service_only": True,
        "weknora_oauth_origin": CALLBACK_ORIGIN,
    }
    assert resident_execution(config, mcp_enabled=True) == (True, CALLBACK_ORIGIN)


@pytest.mark.parametrize(
    "origin",
    [
        ISSUER + ":0",
        ISSUER + ":65536",
        ISSUER + ":-1",
        ISSUER + ":9543/path",
        ISSUER + ":9543?owner=another",
        ISSUER + ":9543#fragment",
        "https://user:password@research.tail123.ts.net:9543",
        "https://unapproved.example:9543",
    ],
)
def test_tailnet_https_port_does_not_allow_invalid_origins(origin):
    with pytest.raises(ValueError, match="server_origin_invalid"):
        validate_origin(origin)


@pytest.mark.parametrize("service_only", [False, True])
def test_weknora_registration_preserves_the_selected_host_mode(service_only):
    config = {
        "origin": ISSUER,
        "port": 8089,
        "service_only": service_only,
        "weknora_oauth_origin": CALLBACK_ORIGIN,
    }
    assert resident_execution(config, mcp_enabled=True) == (service_only, CALLBACK_ORIGIN)


def test_weknora_registration_still_requires_the_mcp_switch():
    with pytest.raises(ValueError, match="weknora_oauth_requires_mcp"):
        resident_execution({"weknora_oauth_origin": CALLBACK_ORIGIN}, mcp_enabled=False)


def test_weknora_callback_rejects_the_same_origin():
    with pytest.raises(ValueError, match="weknora_oauth_origin_conflict"):
        validate_weknora_gateway(ISSUER, ISSUER, 8089)


@pytest.mark.parametrize(
    "origin",
    [
        CALLBACK_ORIGIN + "/callback",
        CALLBACK_ORIGIN + "?next=/",
        CALLBACK_ORIGIN + "#callback",
        "https://user@research.tail123.ts.net:9443",
        "https://research.tail123.ts.net:443",
        "https://research.tail123.ts.net:0",
        "http://research.tail123.ts.net:9443",
    ],
)
def test_weknora_callback_rejects_noncanonical_origins(origin):
    with pytest.raises(ValueError, match="weknora_oauth_origin_invalid"):
        validate_weknora_gateway(ISSUER, origin, 8089)


def test_weknora_callback_rejects_unapproved_https_hosts():
    with pytest.raises(ValueError, match="server_origin_invalid"):
        validate_weknora_gateway(ISSUER, "https://unapproved.example:9443", 8089)


def test_weknora_remains_disabled_without_explicit_registration():
    assert resident_execution({}, mcp_enabled=True) == (False, None)
