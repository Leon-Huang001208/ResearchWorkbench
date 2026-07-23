"""系统配置控制面的本地来源与进程内 CSRF 防护。"""

import ipaddress
import os
import re
import secrets
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Header, HTTPException

CONFIGURATION_CSRF_META_PLACEHOLDER = "__ALPHAFOUNDRY_CONFIG_TOKEN__"
CONFIGURATION_CSRF_TOKEN = secrets.token_urlsafe(32)
DEFAULT_TRUSTED_HOSTS = ("localhost", "127.0.0.1", "testserver")
DESKTOP_CORS_ORIGINS = (
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
)
DESKTOP_CONFIGURATION_ORIGINS = frozenset(DESKTOP_CORS_ORIGINS)


def parse_cors_origins(raw_origins: str | None) -> list[str]:
    """解析显式 CORS origin 列表，拒绝通配符和非 origin URL。"""
    if not raw_origins or not raw_origins.strip():
        return []
    origins: list[str] = []
    for raw_origin in raw_origins.split(","):
        origin = raw_origin.strip()
        try:
            parsed = urlsplit(origin)
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("ALPHAFOUNDRY_CORS_ORIGINS contains an invalid origin") from exc
        if (
            origin == "*"
            or parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("ALPHAFOUNDRY_CORS_ORIGINS contains an invalid origin")
        if origin not in origins:
            origins.append(origin)
    return origins


def _is_hostname_or_ipv4(value: str) -> bool:
    # 显式允许 IPv6 loopback，使 http://[::1]:8765/ 这类本地访问可配进信任边界。
    if value == "::1":
        return True
    try:
        return ipaddress.ip_address(value).version == 4
    except ValueError:
        pass
    if len(value) > 253 or not re.fullmatch(r"[A-Za-z0-9.-]+", value):
        return False
    labels = value.split(".")
    return all(
        label and len(label) <= 63 and not label.startswith("-") and not label.endswith("-")
        for label in labels
    )


def parse_trusted_hosts(raw_hosts: str | None) -> list[str]:
    """解析 Host 白名单扩展；端口由 HTTP Host 头正常携带，不写入配置。"""
    hosts = list(DEFAULT_TRUSTED_HOSTS)
    if not raw_hosts or not raw_hosts.strip():
        return hosts
    for raw_host in raw_hosts.split(","):
        host = raw_host.strip()
        if host == "*" or not _is_hostname_or_ipv4(host):
            raise ValueError("ALPHAFOUNDRY_TRUSTED_HOSTS contains an invalid host")
        if host not in hosts:
            hosts.append(host)
    return hosts


def validate_cors_trusted_host_consistency(
    cors_origins: list[str], trusted_hosts: list[str]
) -> None:
    """确保显式跨域调用方也属于明确扩展的 Host 信任边界。"""
    trusted = set(trusted_hosts)
    for origin in cors_origins:
        hostname = urlsplit(origin).hostname
        if hostname not in trusted:
            raise ValueError(
                "ALPHAFOUNDRY_CORS_ORIGINS host must also be listed in "
                "ALPHAFOUNDRY_TRUSTED_HOSTS"
            )


CONFIGURATION_TRUSTED_HOSTS = parse_trusted_hosts(os.environ.get("ALPHAFOUNDRY_TRUSTED_HOSTS"))
CONFIGURATION_CORS_ORIGINS = parse_cors_origins(os.environ.get("ALPHAFOUNDRY_CORS_ORIGINS"))
validate_cors_trusted_host_consistency(CONFIGURATION_CORS_ORIGINS, CONFIGURATION_TRUSTED_HOSTS)
APPLICATION_CORS_ORIGINS = list(dict.fromkeys((*DESKTOP_CORS_ORIGINS, *CONFIGURATION_CORS_ORIGINS)))


def _configuration_origin_is_allowed(origin: str) -> bool:
    if origin in DESKTOP_CONFIGURATION_ORIGINS:
        return True
    try:
        parsed_origins = parse_cors_origins(origin)
    except ValueError:
        return False
    if not parsed_origins:
        return False
    hostname = urlsplit(origin).hostname
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return True
    return origin in CONFIGURATION_CORS_ORIGINS and hostname in CONFIGURATION_TRUSTED_HOSTS


def require_configuration_csrf_token(
    submitted_token: Annotated[str | None, Header(alias="X-AlphaFoundry-Config-Token")] = None,
    origin: Annotated[str | None, Header(alias="Origin")] = None,
) -> None:
    """拒绝非本地来源，并以常量时间比较进程级 CSRF token。"""
    origin_forbidden = origin is not None and not _configuration_origin_is_allowed(origin)
    token_invalid = not secrets.compare_digest(submitted_token or "", CONFIGURATION_CSRF_TOKEN)
    if origin_forbidden or token_invalid:
        raise HTTPException(status_code=403, detail="Forbidden")


def require_configuration_origin_only(
    origin: Annotated[str | None, Header(alias="Origin")] = None,
) -> None:
    """仅校验 Origin/Host 来源合法性，不校验 CSRF token。

    用于 token 分发端点本身——该端点的职责就是颁发 token，
    因此不能要求调用方预先持有 token。
    """
    if origin is not None and not _configuration_origin_is_allowed(origin):
        raise HTTPException(status_code=403, detail="Forbidden")
