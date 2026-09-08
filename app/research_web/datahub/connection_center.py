"""Safe projection for the unified DataHub connection center."""

from __future__ import annotations

import platform as platform_module
from importlib.util import find_spec

from .connections import (
    SUPPORTED_CONFIGURATION_SOURCES,
    CredentialStoreError,
    canonical_source_id,
)

GROUP_SPECS = (
    ("professional", "专业数据源", ["wind", "tinysoft", "ifind", "mysql"]),
    (
        "api",
        "API 数据源",
        [
            "tushare",
            "tavily",
            "bing",
            "zhiqiu_reports",
            "zhiqiu_wechat",
            "zhiqiu_transcript",
        ],
    ),
    (
        "public",
        "公开来源",
        [
            "akshare",
            "baostock",
            "yahoo",
            "chinastock",
            "csindex",
            "szse",
            "cninfo",
            "cls",
            "cnstock_flash",
            "cnstock_news",
            "eastmoney_fund",
        ],
    ),
    ("local", "本机集成", ["local_cache"]),
)


def _module_detected(*names: str) -> bool:
    try:
        return any(find_spec(name) is not None for name in names)
    except (ImportError, AttributeError, ValueError):
        return False


def platform_summary(*, system_name: str | None = None) -> dict:
    os_name = (system_name or platform_module.system()).lower()
    desktop_excel = os_name in {"darwin", "windows"}
    excel_status = (
        "not_applicable"
        if not desktop_excel
        else "unverified" if _module_detected("xlwings") else "not_installed"
    )
    return {
        "os": os_name,
        "excel_automation": {"status": excel_status},
        "wind_excel": {
            "status": (
                "not_applicable"
                if not desktop_excel
                else "unverified" if _module_detected("WindPy") else "not_installed"
            )
        },
        "ifind_excel": {
            "status": (
                "not_applicable"
                if not desktop_excel
                else "unverified" if _module_detected("iFinD", "iFinDPy") else "not_installed"
            )
        },
        "report_workflow": {"status": "unverified"},
    }


def build_connection_center(catalog: dict, connections) -> dict:
    statuses = connections.statuses()
    group_by_source = {
        source_id: group_id
        for group_id, _label, source_ids in GROUP_SPECS
        for source_id in source_ids
    }
    sources = []
    for descriptor in catalog["sources"]:
        source_id = descriptor["id"]
        readiness = descriptor["readiness"]
        canonical = canonical_source_id(source_id)
        status = statuses.get(source_id, {})
        supported = canonical in SUPPORTED_CONFIGURATION_SOURCES
        warnings = []
        for failure in (status.get("failure_code"), readiness.get("failure_code")):
            if failure and failure not in warnings:
                warnings.append(failure)
        actions = ["probe"]
        if supported:
            actions.insert(0, "configure")
            if status.get("configured") or connections._path(canonical).exists():
                actions.append("delete")
        sources.append(
            {
                "id": source_id,
                "label": (
                    "Excel 与本机工作流" if source_id == "local_cache" else descriptor["name"]
                ),
                "group": group_by_source[source_id],
                "auth_kind": descriptor["auth_type"],
                "configured": bool(status.get("configured", readiness["configured"])),
                "secret_configured": bool(status.get("secret_configured", False)),
                "probe_status": readiness["health"],
                "integration_completed": readiness["integration_completed"],
                "callable": readiness["callable"],
                "configuration_supported": supported,
                "actions": actions,
                "restart_required": bool(status.get("restart_required", False)),
                "warnings": warnings,
            }
        )
    try:
        migration = connections.migration_preview()
    except CredentialStoreError as exc:
        migration = {
            "available": False,
            "conflicts": [],
            "targets": [],
            "failure_code": str(exc),
        }
    return {
        "groups": [
            {"id": group_id, "label": label, "items": source_ids}
            for group_id, label, source_ids in GROUP_SPECS
        ],
        "sources": sources,
        "platform": platform_summary(),
        "migration": migration,
    }
