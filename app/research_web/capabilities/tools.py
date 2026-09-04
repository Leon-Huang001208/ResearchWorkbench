"""Offline read-only projection of the pinned composition and final-veto registry.

Schemas are verified against the native registrations by test_capabilities_native.py.
This catalog never installs tools or grants execution authority.
"""

import re
from pathlib import Path

from ..datahub.catalog import build_catalog
from ..datahub.contracts import BUSINESS_TOOLS, SOURCES, Query
from .models import CapabilityError

PIN = "b150a551b8d465e31e418e1b2eaf5e79bbb7d28e"
DECLARATIONS = {
    "report": (
        "子 Agent 汇报",
        "packages/subagent/tool-subagent-report/src/index.ts",
        {"output": "string"},
        ["output"],
        "仅 continuable 子 Agent 的原生作用域可见；向直接父 Agent 汇报，不结束回合",
    ),
    "af_run_script": (
        "研究 Python",
        "runtime/research-tools.mjs",
        {"code": "string"},
        ["code"],
        "仅本会话，严格沙箱；不允许联网或安装依赖",
    ),
    "af_public_data": (
        "公开研究资料（旧版）",
        "runtime/public-data.mjs",
        {},
        ["source"],
        "仅兼容历史会话；新研究使用 datahub_* 业务工具",
    ),
    "web_search": (
        "网页检索",
        "packages/web/tool-web/src/search.ts",
        {"queries": "array"},
        ["queries"],
        "原生 DeepSeek 搜索提供方已配置；最多四条查询，不开放任意 URL fetch",
    ),
    "skill": (
        "加载原生 Skill",
        "packages/skill/tool-skill/src/index.ts",
        {"name": "string"},
        ["name"],
        "仅原生目录已发现的 Skill；内部控制，不可单独选择",
    ),
    "subagent": (
        "委派子 Agent",
        "packages/subagent/tool-subagent/src/index.ts",
        {"prompt": "string", "description": "string", "run_in_background": "boolean"},
        ["prompt", "description"],
        "原生 spawn；最多四个子 Agent、深度一；不递归委派",
    ),
    "send_message": (
        "子 Agent 消息",
        "packages/subagent/tool-subagent-control/src/index.ts",
        {"subagent_id": "string", "message": "string"},
        ["subagent_id", "message"],
        "仅原生授权的直接子 Agent；内部控制",
    ),
    "interrupt_agent": (
        "中断子 Agent",
        "packages/subagent/tool-subagent-control/src/index.ts",
        {"agent_id": "string"},
        ["agent_id"],
        "仅原生授权后代；受理不等于已停止",
    ),
    "list_agents": (
        "查看子 Agent",
        "packages/subagent/tool-subagent-control/src/list-agents.ts",
        {"scope": "string"},
        [],
        "原生父子归属；内部控制",
    ),
}
SELECTABLE = {"af_run_script", "web_search", *BUSINESS_TOOLS.values()}

DATA_PROPERTIES = {
    "search_assets": ({"query": "string", "market": "string", "asset_type": "string"}, ["query"]),
    "trading_calendar": (
        {"market": "string", "start_date": "string", "end_date": "string"},
        ["market", "start_date", "end_date"],
    ),
    "market_bars": (
        {
            "asset": "string",
            "start_date": "string",
            "end_date": "string",
            "frequency": "string",
            "adjustment": "string",
        },
        ["asset", "start_date", "end_date"],
    ),
    "market_snapshot": ({"assets": "array", "fields": "array"}, ["assets"]),
    "index_data": (
        {"index": "string", "dataset": "string", "date": "string"},
        ["index", "dataset"],
    ),
    "financials": ({"asset": "string", "statements": "array", "periods": "array"}, ["asset"]),
    "market_activity": (
        {"asset": "string", "dataset": "string", "start_date": "string", "end_date": "string"},
        ["asset", "dataset"],
    ),
    "factor_macro": (
        {"series": "array", "assets": "array", "start_date": "string", "end_date": "string"},
        ["series"],
    ),
    "fund_data": (
        {
            "dataset": "string",
            "code": "string",
            "start_date": "string",
            "end_date": "string",
            "year": "integer",
            "limit": "integer",
        },
        ["dataset", "code"],
    ),
    "search_news": (
        {"query": "string", "limit": "integer", "start_date": "string", "end_date": "string"},
        [],
    ),
    "search_announcements": (
        {"asset": "string", "query": "string", "start_date": "string", "end_date": "string"},
        [],
    ),
    "search_research": (
        {"query": "string", "document_type": "string", "limit": "integer"},
        ["query"],
    ),
    "search_web": ({"query": "string", "limit": "integer"}, ["query"]),
}


def tool_catalog():
    guard = (Path(__file__).parents[1] / "runtime/guard.mjs").read_text()
    match = re.search(
        r"(?:export\s+)?const\s+RESEARCH_TOOLS\s*=\s*new Set\(\[(.*?)\]\)",
        guard,
        re.DOTALL,
    )
    if not match:
        raise CapabilityError("原生工具 guard 声明不可核对", "tool_registry_unavailable", 503)
    allowed = set(re.findall(r"'([^']+)'", match[1]))
    items = []
    for name, (label, source, fields, required, condition) in DECLARATIONS.items():
        if name not in allowed:
            continue
        parameters = {
            "type": "object",
            "properties": {key: {"type": value} for key, value in fields.items()},
            "required": required,
        }
        if name == "af_public_data":
            parameters = Query.model_json_schema()
        if name == "web_search":
            parameters["properties"]["queries"]["items"] = {"type": "string"}
        items.append(
            {
                "id": name,
                "name": label,
                "kind": "tool",
                "description": condition,
                "selectable": name in SELECTABLE,
                "read_only": True,
                "parameters": parameters,
                "source": source,
                "source_commit": PIN if source.startswith("packages/") else None,
                "approval": (
                    "native-per-call" if name == "af_public_data" else "native-policy-unchanged"
                ),
                "conditions": ["需专属研究工具 preset，目录声明不代表实例在线或授权", condition],
                "availability": "declared",
                "data_sources": SOURCES if name == "af_public_data" else {},
            }
        )
    data_catalog = build_catalog()
    capabilities = {item["id"]: item for item in data_catalog["capabilities"]}
    for capability_id, tool_id in BUSINESS_TOOLS.items():
        if tool_id not in allowed:
            continue
        capability = capabilities[capability_id]
        fields, required = DATA_PROPERTIES[capability_id]
        properties = {key: {"type": value} for key, value in fields.items()}
        for key in ("assets", "fields", "statements", "periods", "series"):
            if key in properties:
                properties[key]["items"] = {"type": "string"}
        properties.update(
            source={"type": "string", "description": "目录来源 ID；默认 auto"},
            allow_fallback={"type": "boolean"},
            refresh={"type": "boolean"},
        )
        if capability_id == "fund_data":
            properties["dataset"]["enum"] = ["nav", "profile", "distributions", "holdings"]
        selectable = capability["callable_source_count"] > 0
        items.append(
            {
                "id": tool_id,
                "name": capability["name"],
                "kind": "tool",
                "description": capability["description"],
                "selectable": selectable,
                "read_only": True,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
                "source": "runtime/public-data.mjs",
                "source_commit": None,
                "approval": "native-per-call",
                "conditions": [
                    "每次外部取数均需原生审批",
                    "仅 DataHub 已适配、配置齐备且允许的来源可执行",
                ],
                "availability": "ready" if selectable else "blocked_no_provider",
                "data_sources": {
                    binding["source_id"]: binding["datasets"]
                    for binding in data_catalog["bindings"]
                    if binding["capability_id"] == capability_id
                },
            }
        )
    return {"items": items, "read_only": True, "runtime_checked": False}
