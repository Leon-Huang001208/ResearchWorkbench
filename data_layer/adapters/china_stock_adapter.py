"""China Stock 数据适配器 - 基于 openclaw-data-china-stock 插件"""
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from core.contracts import DocumentEnvelope
from core.contracts.assets import AssetAnalysisSnapshot
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter
from data_layer.adapters.china_stock import ChinaStockMapper, ChinaStockPluginError

logger = get_logger(__name__)


class ChinaStockAdapter(BaseDataAdapter):
    """
    China Stock 数据适配器 - 统一入口
    使用 openclaw-data-china-stock 插件提供中国 A 股市场数据
    """

    def __init__(self):
        super().__init__(source_type="china_stock")
        self._mapper = ChinaStockMapper()

    def _call_plugin_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """
        调用 openclaw-data-china-stock 插件工具
        
        Args:
            tool_name: 插件工具名称
            args: 工具参数
            
        Returns:
            插件返回的字典数据
            
        Raises:
            ChinaStockPluginError: 插件调用失败
        """
        # TODO: 这里暂时使用子进程调用，后续可替换为 OpenClaw Tool API 调用
        # 假设插件的 tool_runner.py 在某个路径下，或者已安装到环境中
        # 这里使用一个模拟实现，实际使用时需要根据插件的实际调用方式调整
        args_json = json.dumps(args, ensure_ascii=False)
        try:
            # 示例调用：python -m openclaw_data_china_stock.tool_runner <tool_name> <args_json>
            # 实际路径需要根据插件安装位置调整
            result = subprocess.run(
                ["python", "-m", "openclaw_data_china_stock.tool_runner", tool_name, args_json],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Failed to call plugin tool {tool_name}: {e}", exc_info=True)
            raise ChinaStockPluginError(f"Plugin tool call failed: {tool_name}") from e

    async def fetch_stock_quotes(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取股票行情数据"""
        logger.info(f"Fetching stock quotes (china_stock): codes={codes}, start={start_date}, end={end_date}")
        # 调用插件工具
        raw_result = self._call_plugin_tool(
            "tool_fetch_market_data",
            {
                "codes": codes,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        if not raw_result.get("success"):
            raise ChinaStockPluginError(f"Plugin returned error: {raw_result.get('message')}")
        
        raw_data = raw_result.get("data", {}).get("items", [])
        snapshots = []
        as_of = datetime.now()
        # 按 code 分组处理
        code_groups: dict[str, list[dict]] = {}
        for item in raw_data:
            code = item.get("code")
            if code not in code_groups:
                code_groups[code] = []
            code_groups[code].append(item)
        
        for code, group in code_groups.items():
            snapshots.extend(self._mapper.map_market_data(code, group, as_of))
        return snapshots

    async def fetch_financial_report(
        self, code: str, report_type: str = "annual"
    ) -> list[AssetAnalysisSnapshot]:
        """获取财务报告数据"""
        logger.info(f"Fetching financial report (china_stock): code={code}, report_type={report_type}")
        raw_result = self._call_plugin_tool(
            "tool_fetch_stock_financials",
            {
                "code": code,
                "report_type": report_type,
            },
        )
        if not raw_result.get("success"):
            raise ChinaStockPluginError(f"Plugin returned error: {raw_result.get('message')}")
        
        raw_data = raw_result.get("data", {}).get("items", [])
        as_of = datetime.now()
        return self._mapper.map_financials(code, raw_data, as_of)

    async def fetch_fund_flow(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取资金流向数据"""
        logger.info(f"Fetching fund flow (china_stock): codes={codes}, start={start_date}, end={end_date}")
        raw_result = self._call_plugin_tool(
            "tool_fetch_a_share_fund_flow",
            {
                "codes": codes,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        if not raw_result.get("success"):
            raise ChinaStockPluginError(f"Plugin returned error: {raw_result.get('message')}")
        
        raw_data = raw_result.get("data", {}).get("items", [])
        snapshots = []
        as_of = datetime.now()
        code_groups: dict[str, list[dict]] = {}
        for item in raw_data:
            code = item.get("code")
            if code not in code_groups:
                code_groups[code] = []
            code_groups[code].append(item)
        
        for code, group in code_groups.items():
            snapshots.extend(self._mapper.map_fund_flow(code, group, as_of))
        return snapshots

    async def fetch_valuation(
        self, code: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取估值数据"""
        logger.info(f"Fetching valuation (china_stock): code={code}")
        raw_result = self._call_plugin_tool(
            "tool_l4_valuation_context",
            {
                "code": code,
            },
        )
        if not raw_result.get("success"):
            raise ChinaStockPluginError(f"Plugin returned error: {raw_result.get('message')}")
        
        raw_data = raw_result.get("data", {})
        as_of = datetime.now()
        return self._mapper.map_valuation(code, raw_data, as_of)

    async def fetch_technical_indicators(
        self, code: str, indicators: list[str] | None = None
    ) -> list[AssetAnalysisSnapshot]:
        """获取技术指标数据"""
        logger.info(f"Fetching technical indicators (china_stock): code={code}")
        raw_result = self._call_plugin_tool(
            "tool_calculate_technical_indicators",
            {
                "code": code,
                "indicators": indicators or [],
            },
        )
        if not raw_result.get("success"):
            raise ChinaStockPluginError(f"Plugin returned error: {raw_result.get('message')}")
        
        raw_data = raw_result.get("data", {})
        as_of = datetime.now()
        return self._mapper.map_technical_indicators(code, raw_data, as_of)

    async def fetch_macro_indicators(
        self, indicators: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取宏观经济指标"""
        logger.info(
            f"Fetching macro indicators (china_stock): indicators={indicators}, start={start_date}, end={end_date}"
        )
        raw_result = self._call_plugin_tool(
            "tool_fetch_macro_data",
            {
                "indicators": indicators,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        if not raw_result.get("success"):
            raise ChinaStockPluginError(f"Plugin returned error: {raw_result.get('message')}")
        
        raw_data = raw_result.get("data", {})
        as_of = datetime.now()
        return self._mapper.map_macro(raw_data, as_of)

    async def fetch_sentiment(
        self, codes: list[str] | None = None
    ) -> list[AssetAnalysisSnapshot]:
        """获取情绪数据"""
        logger.info(f"Fetching sentiment (china_stock): codes={codes}")
        raw_result = self._call_plugin_tool(
            "tool_fetch_market_sentiment",
            {
                "codes": codes or [],
            },
        )
        if not raw_result.get("success"):
            raise ChinaStockPluginError(f"Plugin returned error: {raw_result.get('message')}")
        
        raw_data = raw_result.get("data", {})
        as_of = datetime.now()
        if codes:
            snapshots = []
            for code in codes:
                snapshots.extend(self._mapper.map_sentiment(code, raw_data, as_of))
            return snapshots
        else:
            return self._mapper.map_sentiment(None, raw_data, as_of)

    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """
        获取 China Stock 数据

        kwargs:
            data_type: str - 数据类型：stock, financial, fund_flow, valuation, technical, macro
            codes: list[str] - 证券代码列表
            start_date: str - 开始日期
            end_date: str - 结束日期
        """
        # 注意：此方法为同步方法，实际使用时建议使用异步方法
        import asyncio
        data_type = kwargs.get("data_type", "stock")
        codes = kwargs.get("codes", [])
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")

        async def _fetch():
            if data_type == "stock":
                return await self.fetch_stock_quotes(codes, start_date, end_date)
            elif data_type == "financial":
                snapshots = []
                for code in codes:
                    snapshots.extend(await self.fetch_financial_report(code))
                return snapshots
            elif data_type == "fund_flow":
                return await self.fetch_fund_flow(codes, start_date, end_date)
            elif data_type == "valuation":
                snapshots = []
                for code in codes:
                    snapshots.extend(await self.fetch_valuation(code))
                return snapshots
            elif data_type == "technical":
                snapshots = []
                for code in codes:
                    snapshots.extend(await self.fetch_technical_indicators(code))
                return snapshots
            elif data_type == "macro":
                return await self.fetch_macro_indicators(codes, start_date, end_date)
            else:
                raise ValueError(f"Unknown data type: {data_type}")

        snapshots = asyncio.run(_fetch())
        # 转换为 DocumentEnvelope
        envelopes = []
        for snapshot in snapshots:
            envelope = DocumentEnvelope(
                doc_id=snapshot.canonical_id,
                title=f"China Stock Snapshot: {snapshot.canonical_id}",
                source_type="vendor_snapshot",
                source_name="openclaw-data-china-stock",
                raw_text=snapshot.model_dump_json(),
                canonical_text=snapshot.model_dump_json(),
                metadata={
                    "as_of": snapshot.as_of.isoformat(),
                },
            )
            envelopes.append(envelope)
        return envelopes

    def parse(self, source: Path | bytes | str, **kwargs: Any) -> DocumentEnvelope:
        """解析 China Stock 原始数据"""
        raise NotImplementedError("Parse method not implemented for China Stock adapter")
