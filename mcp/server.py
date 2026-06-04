"""AlphaFoundry Data MCP Server — 将数据摄入 CLI/Connector 暴露为 MCP tools.

设计原则（改进.md）：
- MCP 是最外层的薄封装，核心能力由 Connector Python API 直接提供
- 不通过 subprocess 调用 CLI，而是直接调用 connector.run() / health_check()
- 每个 tool 返回结构化 JSON，Agent 可直接解析

Tools:
- list_data_sources: 列出所有可用数据源、数据集、健康状态
- data_ingest: 执行数据摄入（调用 connector.run()）
- data_health_check: 检查指定数据源或全部数据源的健康状态
- data_status: 查看数据采集状态（crawl status + connector health）

Usage:
    通过 stdio transport 注册到 Claude Code:
    ```json
    {
      "mcpServers": {
        "af-data": {
          "type": "stdio",
          "command": "python3",
          "args": ["-m", "mcp.server"]
        }
      }
    }
    ```
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from core.connectors.base import BaseConnector
from core.contracts.ingestion_record import HealthStatus
from core.observability import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Connector 注册表 — 使用 ConnectorRegistry 自动发现 + 手工注册
# ---------------------------------------------------------------------------

_registry_instance = None  # type: ignore[var-annotated]


def _ensure_registry():
    """延迟加载 connector 注册表，优先使用 ConnectorRegistry.discover_all().

    自动发现从 data_sources/ SourceSpec 注册的数据源，
    并手工补充未通过 SourceSpec 注册的 market connectors。
    """
    global _registry_instance
    if _registry_instance is not None:
        return _registry_instance

    from core.connectors.registry import get_connector_registry

    reg = get_connector_registry()
    reg.discover_all()

    # 为 "zq" 创建别名（指向 zhiqiu_reports 的 ZQDocumentConnector 实例）
    if "zq" not in reg.list_sources():
        zq_sources = ["zhiqiu_reports", "zhiqiu_wechat", "zhiqiu_transcript"]
        for zq_src in zq_sources:
            conn = reg.get_connector(zq_src)
            if conn is not None:
                reg.register("zq", conn)
                break
        else:
            try:
                from connectors.document.zq import ZQDocumentConnector

                reg.register_class("zq", ZQDocumentConnector)
            except ImportError:
                pass

    _registry_instance = reg
    return reg


def _get_connector_instance(source: str) -> BaseConnector | None:
    """获取 connector 实例."""
    reg = _ensure_registry()
    return reg.get_connector(source)


def _serialize_result(obj: Any) -> str:
    """将结果序列化为 JSON 字符串，处理 datetime 等特殊类型."""

    def _default(o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()
        if hasattr(o, "model_dump"):
            return o.model_dump()
        if hasattr(o, "__dict__"):
            return o.__dict__
        return str(o)

    return json.dumps(obj, ensure_ascii=False, default=_default, indent=2)


# =============================================================================
# MCP Tool 实现
# =============================================================================


def list_data_sources() -> str:
    """列出所有可用数据源及其元信息.

    返回每个数据源的 source 名称、支持的数据集列表、类型（document/market）、
    默认 asset_type。

    Returns:
        JSON 字符串，包含数据源列表。
    """
    reg = _ensure_registry()
    sources: List[Dict[str, Any]] = []

    for source_name, connector in sorted(reg.get_all_connectors().items()):
        try:
            sources.append(
                {
                    "source": connector.source,
                    "type": connector.asset_type,
                    "datasets": connector.datasets,
                }
            )
        except Exception as e:
            sources.append(
                {
                    "source": source_name,
                    "type": "unknown",
                    "datasets": [],
                    "error": str(e),
                }
            )

    result = {
        "total": len(sources),
        "sources": sources,
        "note": "使用 data_ingest 工具执行具体摄入任务，使用 data_health_check 检查数据源状态",
    }
    return _serialize_result(result)


def data_health_check(source: str | None = None) -> str:
    """检查数据源健康状态.

    对每个数据源调用 health_check()，返回 HEALTHY / DEGRADED / UNAVAILABLE 状态。

    Args:
        source: 数据源标识（如 "cls", "akshare"）。为 None 时检查所有数据源。

    Returns:
        JSON 字符串，包含健康检查结果。
    """
    reg = _ensure_registry()

    sources_to_check: List[str]
    if source:
        if source not in reg.list_sources():
            return _serialize_result(
                {
                    "error": f"Unknown source: {source}",
                    "available": sorted(reg.list_sources()),
                }
            )
        sources_to_check = [source]
    else:
        sources_to_check = sorted(reg.list_sources())

    results: Dict[str, Any] = {}
    healthy = 0
    degraded = 0
    unavailable = 0

    for src in sources_to_check:
        try:
            instance = _get_connector_instance(src)
            if instance is None:
                results[src] = {"status": "unavailable", "error": "Failed to instantiate connector"}
                unavailable += 1
                continue

            status = instance.health_check()
            results[src] = {
                "status": status.value,
                "datasets": instance.datasets,
            }
            if status == HealthStatus.HEALTHY:
                healthy += 1
            elif status == HealthStatus.DEGRADED:
                degraded += 1
            else:
                unavailable += 1
        except Exception as e:
            results[src] = {"status": "unavailable", "error": str(e)}
            unavailable += 1

    summary = {
        "checked_at": datetime.utcnow().isoformat(),
        "total": len(sources_to_check),
        "healthy": healthy,
        "degraded": degraded,
        "unavailable": unavailable,
        "sources": results,
    }
    return _serialize_result(summary)


def data_ingest(
    source: str,
    dataset: str,
    start_date: str | None = None,
    end_date: str | None = None,
    codes: str | None = None,
    max_items: int | None = None,
    **params: Any,
) -> str:
    """执行数据摄入任务.

    调用对应 connector 的 run() 方法执行完整的摄入生命周期：
    discover → fetch → save_raw → parse → normalize → validate → persist。

    Args:
        source: 数据源标识（必需）。如 "cls", "cnstock", "zq", "akshare", "wind", "yahoo"。
        dataset: 数据集标识（必需）。如 "news", "report", "daily_quotes", "stock_daily"。
        start_date: 开始日期 YYYY-MM-DD（可选）。
        end_date: 结束日期 YYYY-MM-DD（可选）。
        codes: 证券代码，逗号分隔（可选）。如 "600519.SH,000001.SZ"。
        max_items: 最大抓取数量（可选）。
        **params: 其他传递给 connector.run() 的参数。

    Returns:
        JSON 字符串，包含 IngestionResult（状态、统计、记录数等）。
    """
    reg = _ensure_registry()

    # 构建 run 参数
    run_params: Dict[str, Any] = {}
    if start_date:
        run_params["start_date"] = start_date
    if end_date:
        run_params["end_date"] = end_date
    if codes:
        run_params["codes"] = [c.strip() for c in codes.split(",") if c.strip()]
    if max_items:
        run_params["max_items"] = max_items
    run_params.update(params)

    # --- source="auto": 多源降级路由 ---
    if source == "auto":
        logger.info(
            "mcp_data_ingest_auto",
            extra={"dataset": dataset, "params": run_params},
        )
        try:
            result = reg.run_with_fallback(dataset, **run_params)
            result_source = result.routed_source or result.source
            logger.info(
                "mcp_data_ingest_auto_done",
                extra={
                    "dataset": dataset,
                    "routed_source": result_source,
                    "fallback_used": result.fallback_used,
                    "status": result.status.value,
                    "persisted": result.stats.persisted,
                },
            )
            return _serialize_result(
                {
                    "source": result_source,
                    "dataset": result.dataset,
                    "status": result.status.value,
                    "routed_source": result.routed_source,
                    "fallback_used": result.fallback_used,
                    "run_id": result.run_id,
                    "stats": {
                        "discovered": result.stats.discovered,
                        "fetched": result.stats.fetched,
                        "parsed": result.stats.parsed,
                        "validated": result.stats.validated,
                        "persisted": result.stats.persisted,
                        "failed": result.stats.failed,
                        "errors": result.stats.errors[:5] if result.stats.errors else [],
                    },
                    "record_count": len(result.records),
                    "error_message": result.error_message,
                }
            )
        except Exception as e:
            logger.error(
                "mcp_data_ingest_auto_failed",
                extra={"dataset": dataset, "error": str(e)},
                exc_info=True,
            )
            return _serialize_result(
                {
                    "dataset": dataset,
                    "status": "failed",
                    "error": str(e),
                }
            )

    # --- 普通单源模式 ---
    if source not in reg.list_sources():
        return _serialize_result(
            {
                "error": f"Unknown source: {source}",
                "available_sources": sorted(reg.list_sources()),
                "hint": "Use list_data_sources to see all available sources and their datasets.",
            }
        )

    connector = _get_connector_instance(source)
    if connector is None:
        return _serialize_result(
            {
                "error": f"Failed to instantiate connector for source: {source}",
            }
        )

    if dataset not in connector.datasets:
        return _serialize_result(
            {
                "error": f"Unknown dataset '{dataset}' for source '{source}'",
                "available_datasets": connector.datasets,
            }
        )

    logger.info(
        "mcp_data_ingest_start",
        extra={"source": source, "dataset": dataset, "params": run_params},
    )

    try:
        result = connector.run(dataset=dataset, **run_params)
        logger.info(
            "mcp_data_ingest_done",
            extra={
                "source": source,
                "dataset": dataset,
                "status": result.status.value,
                "discovered": result.stats.discovered,
                "persisted": result.stats.persisted,
                "failed": result.stats.failed,
            },
        )
        return _serialize_result(
            {
                "source": result.source,
                "dataset": result.dataset,
                "status": result.status.value,
                "run_id": result.run_id,
                "stats": {
                    "discovered": result.stats.discovered,
                    "fetched": result.stats.fetched,
                    "parsed": result.stats.parsed,
                    "validated": result.stats.validated,
                    "persisted": result.stats.persisted,
                    "failed": result.stats.failed,
                    "errors": result.stats.errors[:5] if result.stats.errors else [],
                },
                "record_count": len(result.records),
                "error_message": result.error_message,
            }
        )
    except Exception as e:
        logger.error(
            "mcp_data_ingest_failed",
            extra={"source": source, "dataset": dataset, "error": str(e)},
            exc_info=True,
        )
        return _serialize_result(
            {
                "source": source,
                "dataset": dataset,
                "status": "failed",
                "error": str(e),
            }
        )


def data_status(source: str | None = None) -> str:
    """查看数据采集状态.

    聚合 connector 健康状态 + 最近采集运行信息。

    Args:
        source: 数据源标识（可选）。为 None 时返回所有数据源的状态概览。

    Returns:
        JSON 字符串，包含数据源状态概览。
    """
    # 先获取 connector 级别的健康状态
    health_json = data_health_check(source=source)
    health_data = json.loads(health_json)

    # 尝试获取 crawl orchestrator 状态
    crawl_info: Dict[str, Any] = {}
    try:
        from services.crawl_orchestrator import CrawlOrchestrator

        orchestrator = CrawlOrchestrator()
        if source:
            from core.contracts import SourceType

            try:
                source_type = SourceType(source)
                crawl_status = orchestrator.get_crawl_status(source_type)
                if crawl_status:
                    crawl_info[source] = crawl_status
            except ValueError:
                pass
    except Exception:
        pass

    result = {
        "queried_at": datetime.utcnow().isoformat(),
        "health": health_data,
        "crawl_history": crawl_info if crawl_info else None,
        "note": "使用 data_ingest 执行摄入，使用 data_health_check 检查健康状态",
    }
    return _serialize_result(result)


# =============================================================================
# MCP Server 入口
# =============================================================================


def main() -> None:
    """启动 AlphaFoundry Data MCP Server (stdio transport)."""
    import sys

    try:
        from mcp.server import NotificationOptions, Server  # type: ignore[attr-defined]
        from mcp.server.models import InitializationCapabilities  # type: ignore[attr-defined]
        from mcp.server.stdio import stdio_server
        from mcp.types import TextContent, Tool
    except ImportError:
        print(
            "FATAL: mcp package not installed. Run: pip install mcp",
            file=sys.stderr,
        )
        sys.exit(1)

    server = Server("af-data")

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return [
            Tool(
                name="list_data_sources",
                description="列出 AlphaFoundry 所有可用数据源及其支持的数据集。返回每个数据源的 source 名称、类型（document/market）、可用数据集列表。使用此工具了解有哪些数据可以摄入。",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            Tool(
                name="data_health_check",
                description="检查数据源的健康状态。对每个数据源调用 health_check() 确认是否可用。返回 HEALTHY（正常）/ DEGRADED（降级）/ UNAVAILABLE（不可用）状态。在摄入数据前用此工具确认数据源可用。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "数据源标识（如 cls, akshare, wind）。不指定则检查所有数据源。",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="data_ingest",
                description="执行数据摄入任务。调用对应数据源 connector 的完整生命周期：discover → fetch → save_raw → parse → normalize → validate → persist。返回摄入统计信息（发现数、成功数、失败数等）。使用前先调用 list_data_sources 了解可用的 source 和 dataset。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "数据源标识（必需）。如 cls, cnstock, zq, akshare, wind, yahoo。",
                        },
                        "dataset": {
                            "type": "string",
                            "description": "数据集标识（必需）。如 news, report, daily_quotes, stock_daily。具体可用数据集参见 list_data_sources。",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "开始日期 YYYY-MM-DD（可选）。",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "结束日期 YYYY-MM-DD（可选）。",
                        },
                        "codes": {
                            "type": "string",
                            "description": "证券代码，逗号分隔（可选）。如 '600519.SH,000001.SZ'。",
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "最大抓取数量（可选）。",
                        },
                    },
                    "required": ["source", "dataset"],
                },
            ),
            Tool(
                name="data_status",
                description="查看数据采集的整体状态。聚合所有数据源的健康状态和最近采集运行历史。用于了解数据新鲜度和系统健康度。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "数据源标识（可选）。不指定则返回所有数据源的概览。",
                        },
                    },
                    "required": [],
                },
            ),
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "list_data_sources":
            result = list_data_sources()
        elif name == "data_health_check":
            result = data_health_check(source=arguments.get("source"))
        elif name == "data_ingest":
            result = data_ingest(
                source=arguments["source"],
                dataset=arguments["dataset"],
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
                codes=arguments.get("codes"),
                max_items=arguments.get("max_items"),
            )
        elif name == "data_status":
            result = data_status(source=arguments.get("source"))
        else:
            result = json.dumps({"error": f"Unknown tool: {name}"})

        return [TextContent(type="text", text=result)]

    async def run_server() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationCapabilities(
                    sampling=None,
                    experimental=None,
                ),
                NotificationOptions(),
            )

    import asyncio

    asyncio.run(run_server())


if __name__ == "__main__":
    main()
