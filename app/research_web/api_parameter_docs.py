"""Reviewed OpenAPI parameter descriptions.

This module only enriches OpenAPI metadata: it never validates, coerces or
rewrites request or response values. Descriptions are keyed by location and
name so one accurate entry covers every operation that shares the parameter.
Prefix overrides handle names whose meaning depends on the route family.

Every entry must stay true to the live handler. ``tests/research_web/
test_api_parameter_docs.py`` fails when an operation parameter has no
description or when an override no longer matches a real route.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

DEFAULTS: dict[str, str] = {
    "header:Idempotency-Key": "客户端重试标识；结果复用与参数冲突规则由当前接口决定",
    "header:X-Research-MCP-Key": "内部 MCP 工具调用键",
    "header:idempotency-key": "客户端重试标识；结果复用与参数冲突规则由当前接口决定",
    "path:action": "机器人动作：run、enable、disable 或 delete",
    "path:aid": "审批 ID",
    "path:alert_id": "资产提醒 ID",
    "path:approval_id": "MCP 审批 ID",
    "path:artifact_id": "历史报告产物 ID",
    "path:automation_id": "自动化任务 ID",
    "path:batch_id": "批次 ID",
    "path:block": "资产观察区块名（overview、history、valuation 等）",
    "path:bot_id": "研究机器人 ID",
    "path:brief_id": "热点简报 ID",
    "path:capability_id": "数据能力 ID",
    "path:cid": "能力 ID",
    "path:did": "数据集 ID",
    "path:digest": "插件内容摘要（安装标识）",
    "path:dossier_id": "研究档案 ID",
    "path:draft_id": "自动化草稿 ID",
    "path:edition_date": "AI 日报期号日期（YYYY-MM-DD）",
    "path:eid": "档案证据 ID",
    "path:event_id": "事件 ID",
    "path:fact_id": "AI 事实分组 ID",
    "path:fid": "会话文件 ID",
    "path:handoff_id": "交接请求 ID",
    "path:identifier": "业务标识",
    "path:identity": "模型配置标识",
    "path:import_id": "自选导入批次 ID",
    "path:installation_id": "MCP 安装 ID",
    "path:item_id": "条目 ID（AI 资讯或集成项）",
    "path:job_id": "资产历史任务 ID",
    "path:key": "对象键",
    "path:lid": "档案关联 ID",
    "path:mode": "产品模式：claw 或 fingpt",
    "path:month": "月份（YYYY-MM）",
    "path:note_id": "资产笔记 ID",
    "path:observation_id": "资产观察 ID",
    "path:plan_id": "热点简报计划 ID",
    "path:probe_id": "数据源探测 ID",
    "path:project_id": "项目 ID",
    "path:provider_id": "报告供应商 ID",
    "path:qid": "研究会话问题 ID",
    "path:query_id": "研究台查询 ID",
    "path:registry_id": "MCP Registry ID",
    "path:report_id": "情报报告 ID",
    "path:request_id": "请求 ID",
    "path:request_key": "交接请求键",
    "path:resource_path": "版本资源相对路径",
    "path:run_id": "运行 ID",
    "path:scenario_id": "研究场景 ID",
    "path:server_name": "MCP 服务器名",
    "path:session_id": "研究会话 ID",
    "path:sha": "原始文件 SHA-256",
    "path:sid": "研究会话 ID",
    "path:skill_id": "研究机器人技能 ID",
    "path:slug": "稳定 URL slug",
    "path:source": "事件来源键（如 fed_fomc、bls_cpi）",
    "path:source_id": "数据源 ID",
    "path:source_session_id": "来源研究会话 ID",
    "path:story_id": "AI 资讯故事 ID",
    "path:study_id": "事件研究 ID",
    "path:track_id": "发现跟踪任务 ID",
    "path:verification_id": "本机集成验证 ID",
    "path:version": "版本号",
    "path:watchlist_id": "自选列表 ID",
    "path:workflow_id": "报告 Workflow ID",
    "query:admission_state": "事件准入状态筛选（如 confirmed）",
    "query:as_of": "评分时点（含时区的 ISO 8601 时间）；省略时使用当前 UTC 时间",
    "query:automation_id": "按自动化任务 ID 筛选",
    "query:before": "上一页返回的 next_before 运行 ID；返回该运行之后的较早记录",
    "query:board": "板块范围：all、main、star、chinext、beijing",
    "query:board_id": "板块 ID",
    "query:category": "分类筛选",
    "query:code": "证券代码",
    "query:cursor": "分页游标；续页时沿用上页返回的游标",
    "query:direction": "排序方向：asc 或 desc",
    "query:dossier_id": "按研究档案 ID 筛选",
    "query:dry_run": "仅预演不写入（默认 true）",
    "query:enable": "确认后是否立即启用自动化（默认 false）",
    "query:end": "结束日期（含）",
    "query:event_id": "按事件 ID 筛选",
    "query:exchange": "交易所范围：all、SH、SZ、BJ",
    "query:feed_id": "发现信息流 ID",
    "query:filter_set": "基金筛选集：all、topAum、topChAumPr",
    "query:format": "导出格式（默认 json）",
    "query:holding_type": "持仓变化类型：all、inc、dec、new、out",
    "query:horizon": "时间跨度：short、medium、long",
    "query:id": "证据对象 ID",
    "query:impact": "影响级别：all、medium_high、high",
    "query:include_archived": "是否包含已归档档案（默认 false）",
    "query:index_id": "指数标识：SSE、CSI300、CHINEXT、SP500、NASDAQ 等",
    "query:issuer": "OAuth issuer",
    "query:lifecycle": "事件生命周期：announced、occurred、ongoing 等",
    "query:limit": "返回条数上限",
    "query:market": "市场范围：all、ab、hk、us",
    "query:mode": "产品模式：claw 或 fingpt",
    "query:news_id": "新闻 ID",
    "query:observation_id": "按资产观察 ID 筛选",
    "query:offset": "跳过的记录数（从 0 开始）",
    "query:preview": "true 时 HTML/PNG 以内联方式返回；其余类型仍作为附件下载",
    "query:q": "搜索关键词",
    "query:range": "统计区间：today、7d、30d、custom",
    "query:refresh": "是否强制刷新缓存（默认按接口）",
    "query:registry_id": "按 MCP Registry ID 筛选",
    "query:revision": "事件修订号",
    "query:rule": "策略信号规则：volume_stall、sma5_close 等",
    "query:scope": "集成状态范围：all、data、local",
    "query:search": "搜索关键词",
    "query:section": "研究台查询分区：market、assets、funds 等",
    "query:session_id": "按研究会话 ID 筛选",
    "query:sha256": "证据文件 SHA-256",
    "query:snapshot_id": "行情快照 ID",
    "query:sort": "排序字段（默认 change_pct）",
    "query:start": "开始日期（含）",
    "query:state": "状态筛选",
    "query:subtype": "日历事件子类型",
    "query:theme_id": "发现主题 ID",
    "query:type": "证据类型：dataset、file、source",
    "query:version": "版本号",
}

# (location, name, path prefix, description). More specific prefixes first.
PREFIX_OVERRIDES: tuple[tuple[str, str, str, str], ...] = (
    (
        "path",
        "action",
        "/api/research/sessions/",
        "文件动作：download 或 preview",
    ),
    ("path", "did", "/api/research/dossiers/", "研究档案 ID"),
    (
        "path",
        "name",
        "/api/research/sessions/",
        "数据集文件名：rows.csv、rows.json 或 manifest.json",
    ),
    ("path", "name", "/api/research/plugins/", "插件源文件相对路径"),
    ("path", "name", "/api/research/documentation/", "架构文档文件名"),
    (
        "path",
        "key",
        "/api/research/aihot/reports/",
        "报告期号：日报 YYYY-MM-DD、周报 YYYY-Www、月报 YYYY-MM",
    ),
    ("path", "key", "/api/research/aihot/", "AI 媒体对象键"),
    ("path", "key", "/api/research/plugins/", "插件内 MCP 条目键"),
    (
        "path",
        "kind",
        "/api/research/aihot/reports/",
        "报告周期：daily、weekly、monthly",
    ),
    (
        "path",
        "kind",
        "/api/research/ai-news/feeds/",
        "订阅源类型：selected、selected-full、all、daily 等",
    ),
    ("path", "identifier", "/api/research/knowledge/", "资料证据标识"),
    ("path", "identifier", "/api/research/events/", "事件标识"),
    (
        "path",
        "project_id",
        "/api/research/report-projects/",
        "历史报告项目 ID",
    ),
    ("query", "state", "/api/research/mcp/oauth/", "OAuth state（防伪随机值）"),
    ("query", "code", "/api/research/mcp/oauth/", "OAuth 授权码"),
    ("query", "kind", "/api/research/dossiers/", "信号或时间线类型筛选"),
    ("query", "kind", "/api/research/capabilities", "能力类型筛选"),
    ("query", "page", "/api/research/aihot/topics/", "页码（从 1 开始）"),
    (
        "query",
        "page",
        "/api/research/market/financial-calendar",
        "页码（从 0 开始）",
    ),
    (
        "query",
        "horizon",
        "/api/research/market/analysis",
        "分析跨度：intraday、swing、allocation",
    ),
    (
        "query",
        "view",
        "/api/research/sessions",
        "会话视图：active、deleted、all",
    ),
    (
        "query",
        "view",
        "/api/research/market/financial-calendar",
        "日历视图：summary、events",
    ),
    (
        "query",
        "start",
        "/api/research/operations/",
        "自定义统计开始日期（YYYY-MM-DD，UTC，含当日）",
    ),
    ("query", "end", "/api/research/operations/", "自定义统计结束日期（YYYY-MM-DD，UTC，含当日）"),
    ("query", "market", "/api/research/events", "按事件关联市场筛选：CN、US、HK"),
    ("path", "probe_id", "/api/research/local-integrations/", "本机集成探测 ID"),
    ("path", "slug", "/api/research/frameworks/", "研究框架目录中的 slug"),
    ("path", "slug", "/api/research/aihot/topics/", "AI 资讯主题 slug"),
    (
        "query",
        "category",
        "/api/research/market/financial-calendar",
        "日历事件分类",
    ),
)


def parameter_description(location: str, name: str, path: str) -> str | None:
    """Return the reviewed description for one OpenAPI parameter, if any."""

    for target_location, target_name, prefix, description in PREFIX_OVERRIDES:
        if target_location == location and target_name == name and path.startswith(prefix):
            return description
    return DEFAULTS.get(f"{location}:{name}")


def _enrich(schema: dict[str, Any]) -> None:
    for path, item in (schema.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            for parameter in operation.get("parameters") or []:
                if not isinstance(parameter, dict) or parameter.get("description"):
                    continue
                description = parameter_description(
                    str(parameter.get("in") or ""),
                    str(parameter.get("name") or ""),
                    path,
                )
                if description:
                    parameter["description"] = description


def install_openapi_parameter_docs(app: FastAPI) -> None:
    """Attach the glossary to this app's lazily built OpenAPI schema."""

    original = app.openapi

    def openapi() -> dict[str, Any]:
        schema = app.openapi_schema or original()
        _enrich(schema)
        app.openapi_schema = schema
        return schema

    app.openapi = openapi  # type: ignore[method-assign]
