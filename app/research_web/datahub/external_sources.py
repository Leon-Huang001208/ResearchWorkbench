"""Versioned external-source inventory; importing it never performs network I/O."""

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

INVENTORY = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
EXTERNAL_SOURCES = {"ext_" + item["id"].replace("-", "_"): item for item in INVENTORY["sources"]}
SECRET_SOURCES = {"ext_ths", "ext_daole", "ext_tikhub", "ext_cicc"}
CONFIGURATION_ENDPOINTS = {("ext_ths", "refresh"), ("ext_ths", "ths_login")}


def credential_transport_blocked(endpoint: dict[str, Any]) -> bool:
    """Authenticated HTTP inventory entries remain registered but cannot execute."""
    return (
        bool(endpoint.get("auth") or endpoint.get("specialAuth"))
        and urlsplit(endpoint["url"]).scheme != "https"
    )


def readable_endpoints(source_id: str) -> list[dict[str, Any]]:
    return [
        endpoint
        for endpoint in EXTERNAL_SOURCES[source_id].get("endpoints", [])
        if (source_id, endpoint["id"]) not in CONFIGURATION_ENDPOINTS
    ]


def inventory_rows(source_id: str = "ext_registry") -> list[dict[str, Any]]:
    selected = (
        EXTERNAL_SOURCES.items()
        if source_id == "ext_registry"
        else [(source_id, EXTERNAL_SOURCES[source_id])]
    )
    rows = []
    for sid, item in selected:
        endpoints = readable_endpoints(sid)
        rows.append(
            {
                "source": sid,
                "name": item["name"],
                "category": item["category"],
                "purpose": item["purpose"],
                "endpoints": [
                    {
                        "dataset": ep["id"],
                        "method": ep["method"],
                        "parameters": re.findall(r"\{(\w+)\}", ep["url"]),
                        "requires_credentials": bool(ep.get("auth") or ep.get("specialAuth")),
                        "transport_status": (
                            "credential_transport_blocked"
                            if credential_transport_blocked(ep)
                            else "eligible_not_live_verified"
                        ),
                    }
                    for ep in endpoints
                ],
                "status": (
                    "credential_transport_blocked"
                    if endpoints and all(credential_transport_blocked(ep) for ep in endpoints)
                    else (
                        "adapter_available_not_live_verified"
                        if endpoints
                        else "connector_authorization_required"
                    )
                ),
                "notes": item.get("notes") or [],
            }
        )
    if source_id == "ext_registry":
        rows.extend(
            {"name": item["name"], "status": "reference_only", "reference_url": item["url"]}
            for item in INVENTORY["referenceOnly"]
        )
    return rows


def source_label(source_id: str) -> str | None:
    if source_id == "ext_registry":
        return "外部数据源总目录"
    item = EXTERNAL_SOURCES.get(source_id)
    return item["name"] if item else None


def catalog_entries(
    connection_statuses: dict | None = None, probes: dict | None = None
) -> tuple[list[dict], list[dict]]:
    sources: list[dict] = []
    bindings: list[dict] = []
    statuses, probes = connection_statuses or {}, probes or {}
    entries = {
        "ext_registry": {
            "name": "外部数据源总目录",
            "purpose": "已整理的 41 个来源与 10 个参考来源；先查目录，再按来源和数据集取数。",
        },
        **EXTERNAL_SOURCES,
    }
    for sid, item in entries.items():
        endpoints = readable_endpoints(sid) if sid != "ext_registry" else []
        integrated = sid == "ext_registry" or bool(endpoints)
        has_public = any(not ep.get("auth") and not ep.get("specialAuth") for ep in endpoints)
        configured = (
            sid == "ext_registry"
            or has_public
            or bool(statuses.get(sid, {}).get("secret_configured"))
        )
        blocked = bool(endpoints) and all(credential_transport_blocked(ep) for ep in endpoints)
        state = (
            "credential_transport_blocked"
            if blocked
            else "disabled" if not integrated else "ready" if configured else "blocked_config"
        )
        probe = probes.get(sid, {})
        health = probe.get("health", "untested")
        limitations = ["按供应商原字段保存单次响应；不保证完整历史或跨来源口径等价。"]
        if blocked:
            limitations.append("认证入口没有已核实的 HTTPS 地址，取数在读取凭据前拒绝。")
        if sid in SECRET_SOURCES:
            limitations.append("部分入口需要本项目连接凭据；公开入口与付费入口分别判断。")
        if not integrated:
            limitations.append("需要独立连接器授权，Codex 中可见不等于本项目已获授权。")
        sources.append(
            {
                "id": sid,
                "name": item["name"],
                "family": "datahub",
                "source_type": "public",
                "description": item["purpose"],
                "auth_type": "api_key" if sid in SECRET_SOURCES else "none",
                "config_keys": ["api_key"] if sid in SECRET_SOURCES else [],
                "dependencies": [],
                "markets": ["全球"],
                "fee": "possibly_metered" if sid in SECRET_SOURCES else "free",
                "limitations": limitations,
                "readiness": {
                    "code_exists": True,
                    "integration_completed": integrated,
                    "configured": configured,
                    "dependency_ready": True,
                    "allowed": integrated,
                    "callable": state == "ready" and health != "unavailable",
                    "integration_state": state,
                    "health": health,
                    "last_checked_at": probe.get("last_checked_at"),
                    "failure_code": (
                        "credential_transport_blocked" if blocked else probe.get("failure_code")
                    ),
                    "duration_ms": probe.get("duration_ms"),
                },
            }
        )
        bindings.append(
            {
                "capability_id": "external_data",
                "source_id": sid,
                "datasets": ["catalog", *[ep["id"] for ep in endpoints]],
                "priority": len(bindings) + 1,
                "markets": ["全球"],
                "assets": [],
                "coverage": item["purpose"],
                "implemented": integrated,
                "semantics": {},
            }
        )
    return sources, bindings
