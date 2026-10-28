"""Offline read-only projection of the pinned composition and final-veto registry.

Schemas are verified against the native registrations by test_capabilities_native.py.
This catalog never installs tools or grants execution authority.
"""

import re
from pathlib import Path
from typing import Any

from .. import RUNTIME_CONTRACT
from ..datahub.catalog import build_catalog
from ..datahub.connections import MySQLConnectionStore
from ..datahub.contracts import BUSINESS_TOOLS
from .models import CapabilityError

PIN = RUNTIME_CONTRACT.dsh_commit
DECLARATIONS = {
    "specialist_plan": (
        "专业研究计划",
        "runtime/specialists.mjs",
        {"nodes": "array", "expected_version": "integer"},
        ["nodes", "expected_version"],
        "仅冻结协作任务中的受审角色与预算内计划；程序校验依赖和修订",
    ),
    "specialist_run": (
        "专业节点执行",
        "runtime/specialists.mjs",
        {"node_id": "string", "expected_version": "integer"},
        ["node_id", "expected_version"],
        "Host 留痕准入后使用原生可继续子会话；未知请求不重发",
    ),
    "specialist_status": (
        "协作执行状态",
        "runtime/specialists.mjs",
        {},
        [],
        "只观察本研究的真实状态，不授予重试权限",
    ),
    "specialist_cancel": (
        "取消专业节点",
        "runtime/specialists.mjs",
        {"attempt_id": "string"},
        ["attempt_id"],
        "取消回执不等于终态，待原生历史核验",
    ),
    "rwb_prepare_automation": (
        "提出研究日程草稿",
        "runtime/research-tools.mjs",
        {
            "name": "string",
            "target_kind": "string",
            "target_id": "string",
            "target_version": "integer",
            "input_template": "string",
            "output_formats": "array",
            "schedule": "object",
            "research_task": "object",
        },
        ["name", "target_kind", "schedule"],
        "仅提出日程草稿；研究任务经确认卡创建并启用，不立即执行；不授予 MCP 或投递权限",
    ),
    "rwb_list_automations": (
        "查询研究日程",
        "runtime/research-tools.mjs",
        {"automation_id": "string"},
        [],
        "只读真实任务、定义版本及最近运行结果",
    ),
    "rwb_prepare_automation_update": (
        "提出日程修改",
        "runtime/research-tools.mjs",
        {"automation_id": "string", "body": "object"},
        ["automation_id", "body"],
        "同一任务 ID 与预期版本；确认卡批准后更新",
    ),
    "rwb_run_automation": (
        "用户请求试跑",
        "runtime/research-tools.mjs",
        {"automation_id": "string"},
        ["automation_id"],
        "仅明确用户试跑请求；独立执行会话，不修改计划时间",
    ),
    "ask_user_question": (
        "澄清研究参数",
        "packages/interaction/tool-ask-user/src/index.ts",
        {"questions": "array"},
        ["questions"],
        "原生用户提问；不授予执行权限",
    ),
    "research_check_quality": (
        "检查研究质量",
        "runtime/research-tools.mjs",
        {"operation": "string"},
        [],
        "本轮冻结要求与已取得证据；最多一次补查，不改变研究权限",
    ),
    "research_read_source": (
        "读取来源正文",
        "runtime/research-tools.mjs",
        {"operation": "string", "source_id": "string"},
        ["operation"],
        "本会话登记的公开HTTPS来源，或用户通过冻结交接显式绑定的档案证据；逐次鉴权，拒绝私网、凭据、任意路径与伪造正文",
    ),
    "research_document_operation": (
        "Office 文档操作",
        "runtime/research-tools.mjs",
        {
            "format": "string",
            "operation": "string",
            "mode": "string",
            "file_id": "string",
            "expected_sha256": "string",
            "output_name": "string",
            "content": "object",
            "changes": "array",
        },
        ["format", "operation", "mode"],
        "会话文件身份与受约束报告执行器；修改生成新版本，原生不可用不回退",
    ),
    "rwb_record_method_use": (
        "记录推理方法采用",
        "runtime/research-tools.mjs",
        {"method_id": "string", "version": "string", "source": "string"},
        ["method_id", "version", "source"],
        "仅记录当前会话的稳定方法 ID、版本和采用来源；内部控制，不授予权限",
    ),
    "research_run_script": (
        "研究 Python",
        "runtime/research-tools.mjs",
        {"code": "string"},
        ["code"],
        "仅本会话，严格沙箱；不允许联网或安装依赖",
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
        {"agent_id": "string", "message": "string"},
        ["agent_id", "message"],
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
SELECTABLE = {
    "research_run_script",
    "research_document_operation",
    "web_search",
    *BUSINESS_TOOLS.values(),
}

DATA_PROPERTIES = {
    "external_data": ({"dataset": "string", "arguments_json": "string", "limit": "integer"}, []),
    "search_assets": (
        {"query": "string", "market": "string", "asset_type": "string"},
        ["query"],
    ),
    "trading_calendar": (
        {"market": "string", "start_date": "string", "end_date": "string"},
        ["market", "start_date", "end_date"],
    ),
    "market_bars": (
        {
            "asset": "string",
            "asset_type": "string",
            "start_date": "string",
            "end_date": "string",
            "frequency": "string",
            "adjustment": "string",
        },
        ["asset", "start_date", "end_date"],
    ),
    "market_snapshot": (
        {"assets": "array", "asset_type": "string", "fields": "array"},
        ["assets"],
    ),
    "index_data": (
        {"index": "string", "dataset": "string", "date": "string"},
        ["index", "dataset"],
    ),
    "financials": (
        {"asset": "string", "statements": "array", "periods": "array"},
        ["asset"],
    ),
    "market_activity": (
        {
            "asset": "string",
            "dataset": "string",
            "start_date": "string",
            "end_date": "string",
        },
        ["asset", "dataset"],
    ),
    "factor_macro": (
        {
            "series": "array",
            "assets": "array",
            "start_date": "string",
            "end_date": "string",
        },
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
        {
            "query": "string",
            "limit": "integer",
            "start_date": "string",
            "end_date": "string",
        },
        [],
    ),
    "search_announcements": (
        {
            "asset": "string",
            "query": "string",
            "start_date": "string",
            "end_date": "string",
        },
        [],
    ),
    "search_research": (
        {"query": "string", "document_type": "string", "limit": "integer"},
        ["query"],
    ),
    "search_web": ({"query": "string", "limit": "integer"}, ["query"]),
    "database_schema": ({"database": "string", "table": "string"}, []),
    "table_query": (
        {
            "database": "string",
            "table": "string",
            "columns": "array",
            "filters": "array",
            "order_by": "array",
            "offset": "integer",
            "limit": "integer",
        },
        ["database", "table", "columns"],
    ),
}

WORKFLOW_TOOL_DECLARATIONS = {
    "report_workbook_refresh": (
        "刷新报告底稿",
        "复制锁定版本的 Excel 母版，串行调用声明的 Wind／iFinD Provider，完整重算并保存刷新清单。",
        {"run_id": "string", "workbook": "string"},
    ),
    "report_workbook_extract": (
        "提取报告底稿",
        "从本次运行的已刷新底稿生成结构化快照、数据日期和口径说明。",
        {"run_id": "string", "workbook": "string"},
    ),
    "report_template_inspect": (
        "检查报告模板",
        "读取锁定的 Word／PPT 模板并核对命名占位符、报告区块和映射。",
        {"workflow_id": "string", "version": "integer"},
    ),
    "report_chart_render": (
        "渲染报告图表",
        "根据锁定映射和共享快照生成报告图表资源，不访问外部数据源。",
        {"run_id": "string", "block_id": "string"},
    ),
    "report_docx_assemble": (
        "组装 Word 报告",
        "将结构化报告区块、图表和表格填入本次运行的 Word 模板副本。",
        {"run_id": "string", "payload": "string"},
    ),
    "report_pptx_assemble": (
        "组装 PPT 报告",
        "按占位符映射替换本次运行的 PPT 模板副本并保留模板版式。",
        {"run_id": "string", "payload": "string"},
    ),
    "report_delivery_validate": (
        "检查报告交付",
        "重开本次产物并检查格式、非空内容、未替换占位符、数据日期和文件哈希。",
        {"run_id": "string"},
    ),
}


def tool_catalog(data_root: Path | None = None):
    guard = (Path(__file__).parents[1] / "runtime/guard.mjs").read_text(encoding="utf-8")
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
        parameters: dict[str, Any] = {
            "type": "object",
            "properties": {key: {"type": value} for key, value in fields.items()},
            "required": required,
        }
        if name == "web_search":
            parameters["properties"]["queries"]["items"] = {"type": "string"}
        items.append(
            {
                "id": name,
                "name": label,
                "kind": "tool",
                "description": condition,
                "selectable": name in SELECTABLE,
                "read_only": name
                not in {
                    "research_document_operation",
                    "specialist_plan",
                    "specialist_run",
                    "specialist_cancel",
                },
                "parameters": parameters,
                "source": source,
                "source_commit": PIN if source.startswith("packages/") else None,
                "approval": "native-policy-unchanged",
                "conditions": [
                    "需专属研究工具 preset，目录声明不代表实例在线或授权",
                    condition,
                ],
                "availability": "declared",
                "execution_surface": "dsh_native",
                "data_sources": {},
            }
        )
    statuses = MySQLConnectionStore(data_root).statuses() if data_root is not None else None
    data_catalog = build_catalog(connection_statuses=statuses)
    capabilities = {item["id"]: item for item in data_catalog["capabilities"]}
    for capability_id, tool_id in BUSINESS_TOOLS.items():
        if tool_id not in allowed:
            continue
        capability = capabilities[capability_id]
        fields, required = DATA_PROPERTIES[capability_id]
        properties = {key: {"type": value} for key, value in fields.items()}
        for key in ("assets", "fields", "statements", "periods", "series", "columns"):
            if key in properties:
                properties[key]["items"] = {"type": "string"}
        properties.update(
            source={"type": "string", "description": "目录来源 ID；默认 auto"},
            allow_fallback={"type": "boolean"},
            refresh={"type": "boolean"},
        )
        if capability_id == "fund_data":
            properties["dataset"]["enum"] = [
                "nav",
                "profile",
                "distributions",
                "holdings",
            ]
        elif capability_id in {"market_bars", "market_snapshot"}:
            properties["asset_type"]["enum"] = ["stock", "index", "etf"]
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
                "approval": "automatic",
                "conditions": [
                    "已配置且可用的 DataHub 来源自动执行，无逐次确认",
                    "无可调用来源的能力不会注册到 Runtime",
                ],
                "availability": "ready" if selectable else "blocked_no_provider",
                "execution_surface": "dsh_native",
                "data_sources": {
                    binding["source_id"]: binding["datasets"]
                    for binding in data_catalog["bindings"]
                    if binding["capability_id"] == capability_id
                },
            }
        )
    for tool_id, (name, description, fields) in WORKFLOW_TOOL_DECLARATIONS.items():
        items.append(
            {
                "id": tool_id,
                "name": name,
                "kind": "tool",
                "description": description,
                "selectable": False,
                "read_only": tool_id in {"report_workbook_extract", "report_template_inspect"},
                "parameters": {
                    "type": "object",
                    "properties": {key: {"type": value} for key, value in fields.items()},
                    "required": list(fields),
                    "additionalProperties": False,
                },
                "source": "app/research_web/report_workflows",
                "source_commit": None,
                "approval": "workflow-locked-version",
                "conditions": [
                    "仅由已发布的 Report Workflow 在自己的 Run 目录内调用",
                    "不能由聊天输入直接选择，也不会获得额外宿主权限",
                ],
                "availability": "ready",
                "execution_surface": "workflow_backend",
                "data_sources": {},
            }
        )
    return {"items": items, "read_only": True, "runtime_checked": False}
