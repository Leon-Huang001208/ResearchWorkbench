"""iFinD 数据适配器"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from core.contracts import DocumentEnvelope
from core.contracts.assets import AssetAnalysisSnapshot
from core.observability import get_logger
from core.settings.config import settings
from data_layer.adapters.base import BaseDataAdapter
from data_layer.adapters.ifind import BackendRouter, IFinDMapper

logger = get_logger(__name__)


class IFinDAdapter(BaseDataAdapter):
    """
    iFinD 数据适配器 - 统一入口
    """

    def __init__(self):
        super().__init__(source_type="ifind")
        self._router = BackendRouter(settings)
        self._mapper = IFinDMapper()
        self._client = None
        self._is_available = self._check_availability()

    def _check_availability(self) -> bool:
        """检查iFinD是否可用"""
        try:
            import iFinDPy
            # 检查账号配置是否存在
            if not settings.IFIND_USERNAME or not settings.IFIND_PASSWORD:
                logger.warning("iFinD username/password not configured")
                return False
            return True
        except ImportError:
            logger.warning("iFinD Python SDK not installed")
            return False

    def is_available(self) -> bool:
        return self._is_available

    async def _get_client(self):
        """获取后端客户端"""
        if self._client is None:
            self._client = await self._router.get_client()
        return self._client

    async def fetch_stock_quotes(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取股票行情数据"""
        logger.info(f"Fetching stock quotes: codes={codes}, start={start_date}, end={end_date}")
        client = await self._get_client()
        indicators = [
            "ths_open_stock",
            "ths_high_stock",
            "ths_low_stock",
            "ths_close_stock",
            "ths_vol_stock",
            "ths_turnover_stock",
        ]
        raw_data = await client.history(
            codes=codes,
            indicators=indicators,
            start_date=start_date,
            end_date=end_date,
        )
        snapshots = []
        as_of = datetime.now()
        for code in codes:
            code_data = [item for item in raw_data if item.get("code") == code]
            snapshots.extend(self._mapper.map_quotes(code, code_data, as_of))
        return snapshots

    async def fetch_financial_report(
        self, code: str, report_type: str = "annual"
    ) -> list[AssetAnalysisSnapshot]:
        """获取财务报告数据"""
        logger.info(f"Fetching financial report: code={code}, report_type={report_type}")
        client = await self._get_client()
        indicators = [
            "ths_eps_basic_stock",
            "ths_roe_stock",
            "ths_net_profit_stock",
            "ths_revenue_stock",
            "ths_gross_margin_stock",
            "ths_debt_ratio_stock",
            "ths_current_ratio_stock",
        ]
        raw_data = await client.financial(
            codes=[code],
            indicators=indicators,
        )
        as_of = datetime.now()
        return self._mapper.map_financial(code, raw_data, as_of)

    async def fetch_fund_flow(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取资金流向数据"""
        logger.info(f"Fetching fund flow: codes={codes}, start={start_date}, end={end_date}")
        client = await self._get_client()
        raw_data = await client.data_pool(
            report_name="资金流向",
            parameters={
                "codes": codes,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        snapshots = []
        as_of = datetime.now()
        for code in codes:
            code_data = [item for item in raw_data if item.get("code") == code]
            snapshots.extend(self._mapper.map_fund_flow(code, code_data, as_of))
        return snapshots

    async def fetch_industry_classification(
        self, codes: list[str]
    ) -> list[AssetAnalysisSnapshot]:
        """获取行业分类数据"""
        logger.info(f"Fetching industry classification: codes={codes}")
        client = await self._get_client()
        indicators = [
            "ths_industry_stock",
        ]
        raw_data = await client.basic(
            codes=codes,
            indicators=indicators,
        )
        snapshots = []
        as_of = datetime.now()
        for code in codes:
            code_data = [item for item in raw_data if item.get("code") == code]
            snapshots.extend(self._mapper.map_industry(code, code_data, as_of))
        return snapshots

    async def fetch_macro_indicators(
        self, indicators: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取宏观经济指标"""
        logger.info(
            f"Fetching macro indicators: indicators={indicators}, start={start_date}, end={end_date}"
        )
        client = await self._get_client()
        raw_data = await client.edb_query(
            indicators=indicators,
            start_date=start_date,
            end_date=end_date,
        )
        as_of = datetime.now()
        return self._mapper.map_macro(indicators, raw_data, as_of)

    async def fetch_technical_indicators(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取技术指标数据"""
        logger.info(f"Fetching technical indicators: codes={codes}, start={start_date}, end={end_date}")
        client = await self._get_client()
        indicators = [
            "ths_ma5_stock",
            "ths_ma10_stock",
            "ths_ma20_stock",
            "ths_ma60_stock",
            "ths_macd_stock",
            "ths_rsi_stock",
            "ths_kdj_stock",
            "ths_boll_stock",
        ]
        raw_data = await client.history(
            codes=codes,
            indicators=indicators,
            start_date=start_date,
            end_date=end_date,
        )
        snapshots = []
        as_of = datetime.now()
        for code in codes:
            code_data = [item for item in raw_data if item.get("code") == code]
            snapshots.extend(self._mapper.map_technical(code, code_data, as_of))
        return snapshots

    async def fetch_sentiment(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取情绪数据"""
        logger.info(f"Fetching sentiment data: codes={codes}, start={start_date}, end={end_date}")
        client = await self._get_client()
        indicators = [
            "ths_market_sentiment_stock",
            "ths_sector_sentiment_stock",
            "ths_fund_sentiment_stock",
        ]
        raw_data = await client.history(
            codes=codes,
            indicators=indicators,
            start_date=start_date,
            end_date=end_date,
        )
        snapshots = []
        as_of = datetime.now()
        for code in codes:
            code_data = [item for item in raw_data if item.get("code") == code]
            snapshots.extend(self._mapper.map_sentiment(code, code_data, as_of))
        return snapshots

    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """
        获取 iFinD 数据

        kwargs:
            data_type: str - 数据类型：stock, industry, macro, report
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
            elif data_type == "industry":
                return await self.fetch_industry_classification(codes)
            elif data_type == "macro":
                return await self.fetch_macro_indicators(codes, start_date, end_date)
            else:
                raise ValueError(f"Unknown data type: {data_type}")

        snapshots = asyncio.run(_fetch())
        # 转换为 DocumentEnvelope
        envelopes = []
        for snapshot in snapshots:
            envelope = DocumentEnvelope(
                canonical_id=snapshot.canonical_id,
                source_type=self.source_type,
                content=snapshot.model_dump_json(),
                metadata={
                    "as_of": snapshot.as_of.isoformat(),
                },
            )
            envelopes.append(envelope)
        return envelopes

    def parse(self, source: Path | bytes | str, **kwargs: Any) -> DocumentEnvelope:
        """解析 iFinD 原始数据"""
        raise NotImplementedError("Parse method not implemented for iFinD adapter")
