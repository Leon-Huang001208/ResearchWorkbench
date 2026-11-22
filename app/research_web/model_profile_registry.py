"""Non-secret profile identities shared by Host and the isolated credential bridge."""

from __future__ import annotations

import copy
import json
import logging
import re
from pathlib import Path
from urllib.parse import urlsplit

log = logging.getLogger(__name__)
PROFILE_PREFIX = "RESEARCH_MODEL_PROFILE_"
LEGACY_IDS = {"deepseek-official": "0" * 31 + "1", "openai-compatible": "0" * 31 + "2"}
LEGACY_REFS = {
    "deepseek-official": "RESEARCH_DSH_API_KEY",
    "openai-compatible": "RESEARCH_COMPAT_API_KEY",
}


def is_profile_ref(value):
    return (
        isinstance(value, str) and re.fullmatch(PROFILE_PREFIX + r"[0-9a-f]{32}", value) is not None
    )


def validate_registry(value):
    try:
        if (
            not isinstance(value, dict)
            or set(value) != {"version", "items", "routes", "active_id"}
            or type(value["version"]) is not int
            or value["version"] != 1
        ):
            raise ValueError()
        items, routes = value["items"], value["routes"]
        if (
            not isinstance(items, dict)
            or not isinstance(routes, dict)
            or not 1 <= len(items) <= 256
            or set(routes) - set(LEGACY_REFS)
        ):
            raise ValueError()
        for identity, item in items.items():
            if (
                not re.fullmatch(r"[0-9a-f]{32}", identity)
                or not isinstance(item, dict)
                or item.get("id") != identity
            ):
                raise ValueError()
            if set(item) - {
                "id",
                "name",
                "provider",
                "model",
                "credential_ref",
                "credential_mode",
                "base_url",
                "protocol",
                "archived",
                "uncertain",
                "cleared",
                "revision",
            }:
                raise ValueError()
            provider = item.get("provider")
            expected = (
                LEGACY_REFS.get(provider)
                if identity == LEGACY_IDS.get(provider)
                else PROFILE_PREFIX + identity
            )
            if (
                provider not in LEGACY_REFS
                or item.get("credential_ref") != expected
                or not isinstance(item.get("name"), str)
                or not 1 <= len(item["name"]) <= 80
            ):
                raise ValueError()
            if not isinstance(item.get("model"), str) or not re.fullmatch(
                r"[a-zA-Z0-9._:/-]{1,100}", item["model"]
            ):
                raise ValueError()
            if (
                item.get("credential_mode") not in {"api_key", "none"}
                or type(item.get("archived")) is not bool
            ):
                raise ValueError()
            if any(key in item and type(item[key]) is not bool for key in ("uncertain", "cleared")):
                raise ValueError()
            if provider == "deepseek-official":
                if item["credential_mode"] != "api_key" or any(
                    key in item for key in ("base_url", "protocol")
                ):
                    raise ValueError()
            else:
                url = item.get("base_url")
                if (
                    not isinstance(url, str)
                    or not 1 <= len(url) <= 2048
                    or re.search(r"[\x00-\x20\x7f-\x9f?#]", url)
                    or item.get("protocol") != "openai-completions"
                ):
                    raise ValueError()
                parsed = urlsplit(url)
                local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
                if (
                    parsed.scheme not in {"http", "https"}
                    or not parsed.hostname
                    or parsed.username is not None
                    or parsed.password is not None
                    or parsed.port == 0
                    or (parsed.scheme == "http" and not local)
                    or (item["credential_mode"] == "none" and not local)
                ):
                    raise ValueError()
            if "revision" in item and (
                not isinstance(item["revision"], str)
                or re.fullmatch(r"[0-9a-f]{32}", item["revision"]) is None
            ):
                raise ValueError()
        for provider, identity in routes.items():
            if (
                identity not in items
                or items[identity]["provider"] != provider
                or items[identity]["archived"]
            ):
                raise ValueError()
        if (
            value["active_id"] not in items
            or items[value["active_id"]]["archived"]
            or routes.get(items[value["active_id"]]["provider"]) != value["active_id"]
        ):
            raise ValueError()
        return value
    except (KeyError, TypeError, ValueError):
        log.warning("model_profile_registry_invalid")
        raise ValueError("model_profile_registry_invalid") from None


def bootstrap_profiles(data):
    if "model_profiles" in data:
        return copy.deepcopy(validate_registry(data["model_profiles"]))
    selection = data.get("model") or {"provider": "deepseek-official", "model": "deepseek-flash"}
    official = {
        "id": LEGACY_IDS["deepseek-official"],
        "name": "DeepSeek 官方",
        "provider": "deepseek-official",
        "model": (
            selection["model"] if selection["provider"] == "deepseek-official" else "deepseek-flash"
        ),
        "credential_ref": LEGACY_REFS["deepseek-official"],
        "credential_mode": "api_key",
        "archived": False,
    }
    items = {official["id"]: official}
    routes = {"deepseek-official": official["id"]}
    compatible = data.get("compatible_model_connection")
    if compatible:
        entry = {
            **compatible,
            "id": LEGACY_IDS["openai-compatible"],
            "name": "兼容服务（已有连接）",
            "credential_ref": LEGACY_REFS["openai-compatible"],
            "archived": False,
        }
        items[entry["id"]] = entry
        routes["openai-compatible"] = entry["id"]
    for provider, identity in routes.items():
        prefix = "compatible_" if provider == "openai-compatible" else ""
        items[identity]["uncertain"] = bool(data.get(prefix + "model_configuration_uncertain"))
        items[identity]["cleared"] = bool(data.get(prefix + "model_credential_cleared"))
    return validate_registry(
        {"version": 1, "items": items, "routes": routes, "active_id": routes[selection["provider"]]}
    )


def credential_account(data_home: Path, ref: str, *, allow_uncertain=False) -> str:
    """Resolve fixed runtime aliases without reading, copying or logging any Key."""
    try:
        if ref not in LEGACY_REFS.values() and not is_profile_ref(ref):
            raise ValueError()
        index = data_home / "index.json"
        data = json.loads(index.read_text(encoding="utf-8")) if index.exists() else {}
        if "model_profiles" not in data:
            if ref not in LEGACY_REFS.values():
                raise ValueError()
            return ref
        registry = validate_registry(data["model_profiles"])
        provider = next((name for name, account in LEGACY_REFS.items() if account == ref), None)
        if provider is not None:
            identity = registry["routes"].get(provider)
            if identity is None:
                return ref
            item = registry["items"][identity]
        else:
            item = registry["items"].get(ref.removeprefix(PROFILE_PREFIX))
            if item is None:
                raise ValueError()
        if (item.get("uncertain") or item.get("cleared")) and not allow_uncertain:
            raise ValueError()
        return item["credential_ref"]
    except (OSError, ValueError, TypeError, KeyError):
        log.warning("model_profile_credential_route_invalid")
        raise ValueError("model_profile_credential_route_invalid") from None
