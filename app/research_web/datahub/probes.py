"""Controlled probes for user-owned vendor integrations."""

from __future__ import annotations

import asyncio
import platform
from importlib import import_module
from importlib.util import find_spec
from types import SimpleNamespace
from typing import Any, cast

from core.observability import get_logger
from data_layer.adapters.ifind.exceptions import (
    IFinDAuthError,
    IFinDDatasourceError,
    IFinDPermissionError,
    IFinDQuotaExceededError,
    IFinDRateLimitError,
)

from .connections import CredentialStoreError

log = get_logger(__name__)


def _available(module: str) -> bool:
    try:
        return find_spec(module) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _load_module(*names: str):
    for name in names:
        if _available(name):
            return import_module(name)
    return None


def _read_accounts(configuration: dict, secret_reader) -> list[tuple[str, str]]:
    available = []
    for item in configuration.get("accounts", []):
        try:
            secret = secret_reader("ifind", item["id"])
        except CredentialStoreError as exc:
            if str(exc) == "credential_missing":
                continue
            raise
        if secret:
            available.append((item["username"], secret))
    return available


def _probe_ifind_sdk(module, accounts: list[tuple[str, str]]) -> dict:
    login = getattr(module, "THS_iFinDLogin", None)
    logout = getattr(module, "THS_iFinDLogout", None)
    if not callable(login) or not callable(logout):
        return {"health": "degraded", "failure_code": "sdk_contract_unavailable"}
    for username, password in accounts:
        try:
            result = login(username, password)
            if result in {0, "0"}:
                return {"health": "healthy", "failure_code": None}
        except Exception as exc:  # noqa: BLE001 - proprietary SDK errors are not stable.
            log.warning("ifind_login_probe_failed", error_type=type(exc).__name__)
        finally:
            try:
                logout()
            except Exception as exc:  # noqa: BLE001 - logout must not hide probe state.
                log.warning("ifind_logout_probe_failed", error_type=type(exc).__name__)
    return {"health": "unavailable", "failure_code": "vendor_login_failed"}


def _probe_wind_client(module) -> dict:
    session = getattr(module, "w", None)
    is_connected = getattr(session, "isconnected", None)
    if not callable(is_connected):
        return {"health": "degraded", "failure_code": "sdk_contract_unavailable"}
    try:
        connected = bool(is_connected())
    except Exception as exc:  # noqa: BLE001 - proprietary SDK errors are not stable.
        log.warning("wind_session_probe_failed", error_type=type(exc).__name__)
        return {"health": "unavailable", "failure_code": "vendor_probe_failed"}
    return (
        {"health": "healthy", "failure_code": None}
        if connected
        else {"health": "unavailable", "failure_code": "vendor_session_not_logged_in"}
    )


def _default_ifind_http_client(base_url: str, username: str, password: str):
    from data_layer.adapters.ifind.http_client import IFinDHTTPClient

    settings = SimpleNamespace(
        IFIND_HTTP_BASE_URL=base_url,
        IFIND_USERNAME=username,
        IFIND_PASSWORD=password,
    )
    return IFinDHTTPClient(cast(Any, settings))


async def _probe_ifind_http(base_url, accounts, client_factory) -> dict:
    failure_code = "vendor_login_failed"
    for username, password in accounts:
        client = client_factory(base_url, username, password)
        try:
            if not await client.login() or not await client.is_alive():
                failure_code = "vendor_login_failed"
                continue
            rows = await client.probe_query()
            if not isinstance(rows, list) or not rows:
                failure_code = "vendor_query_empty"
                continue
            return {"health": "healthy", "failure_code": None}
        except IFinDAuthError as exc:
            failure_code = "vendor_login_failed"
            log.warning("ifind_http_probe_auth_failed", error_type=type(exc).__name__)
        except (IFinDPermissionError, PermissionError) as exc:
            failure_code = "vendor_permission_denied"
            log.warning("ifind_http_probe_permission_failed", error_type=type(exc).__name__)
        except (IFinDRateLimitError, IFinDQuotaExceededError) as exc:
            failure_code = "vendor_quota_limited"
            log.warning("ifind_http_probe_quota_failed", error_type=type(exc).__name__)
        except IFinDDatasourceError as exc:
            failure_code = "vendor_probe_failed"
            log.warning("ifind_http_probe_failed", error_type=type(exc).__name__)
        except Exception as exc:  # noqa: BLE001 - vendor errors are normalized below.
            failure_code = "vendor_probe_failed"
            log.warning("ifind_http_probe_failed", error_type=type(exc).__name__)
        finally:
            try:
                await client.logout()
            except Exception as exc:  # noqa: BLE001 - close failures must not expose secrets.
                log.warning("ifind_http_close_failed", error_type=type(exc).__name__)
    return {"health": "unavailable", "failure_code": failure_code}


async def probe_source(
    source_id: str,
    configuration: dict,
    secret_reader,
    *,
    ifind_http_client_factory=None,
) -> dict:
    """Probe installed integrations without retaining vendor sessions or secrets."""
    if source_id == "wind":
        preferred = configuration.get("preferred_adapter", "auto")
        desktop = platform.system().lower() in {"darwin", "windows"}
        if preferred == "excel":
            if not desktop:
                return {"health": "unavailable", "failure_code": "platform_not_supported"}
            if not _available("xlwings"):
                return {"health": "unavailable", "failure_code": "dependency_missing"}
            return {"health": "degraded", "failure_code": "workbook_probe_required"}
        wind = _load_module("WindPy")
        if wind is not None:
            return await asyncio.to_thread(_probe_wind_client, wind)
        if preferred == "client_api":
            return {"health": "unavailable", "failure_code": "dependency_missing"}
        if desktop and _available("xlwings"):
            return {"health": "degraded", "failure_code": "workbook_probe_required"}
        return {"health": "unavailable", "failure_code": "dependency_missing"}
    if source_id == "ifind":
        try:
            accounts = await asyncio.to_thread(_read_accounts, configuration, secret_reader)
        except CredentialStoreError:
            return {"health": "unavailable", "failure_code": "credential_store_unavailable"}
        if not accounts:
            return {"health": "unavailable", "failure_code": "blocked_config"}
        backend = configuration.get("backend", "auto")
        if backend != "http_api":
            sdk = _load_module("iFinD", "iFinDPy")
            if sdk is not None:
                return await asyncio.to_thread(_probe_ifind_sdk, sdk, accounts)
            if backend == "python_sdk":
                return {"health": "unavailable", "failure_code": "dependency_missing"}
        if configuration.get("http_base_url"):
            return await _probe_ifind_http(
                configuration["http_base_url"],
                accounts,
                ifind_http_client_factory or _default_ifind_http_client,
            )
        return {"health": "unavailable", "failure_code": "dependency_missing"}
    return {"health": "unavailable", "failure_code": "probe_not_implemented"}
