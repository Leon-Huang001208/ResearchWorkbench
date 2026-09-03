"""Offline read-only projection of the pinned composition and final-veto registry.

Schemas are verified against the native registrations by test_capabilities_native.py.
This catalog never installs tools or grants execution authority.
"""

import re
from pathlib import Path

from ..datahub.contracts import SOURCES, Query
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
        "公开研究资料",
        "runtime/public-data.mjs",
        {},
        ["source"],
        "每次取数需原生审批，父 Agent 准备资料；子 Agent 不能绕过审批",
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
SELECTABLE = {"af_run_script", "af_public_data", "web_search"}


def tool_catalog():
    guard = (Path(__file__).parents[1] / "runtime/guard.mjs").read_text()
    match = re.search(r"RESEARCH_TOOLS = new Set\(\[(.*?)\]\)", guard)
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
    return {"items": items, "read_only": True, "runtime_checked": False}
