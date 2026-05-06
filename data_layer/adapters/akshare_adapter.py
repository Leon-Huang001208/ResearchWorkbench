
"""AkShare 数据适配器 - 基于 akshare 开源库"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any
import pandas as pd

from core.contracts import DocumentEnvelope
from core.contracts.assets import AssetAnalysisSnapshot
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter
from data_layer.adapters.akshare import (
    AkShareMapper,
    AkShareClient,
    AkShareClientError,
    AkShareDataError,
)
from data_layer.indicators import TechnicalIndicatorEngine

logger = get_logger(__name__)


class AkShareAdapter(BaseDataAdapter):
    """
    AkShare 数据适配器 - 统一入口
    使用 akshare Python 包提供中国 A 股市场数据
    """

    def __init__(self):
        super().__init__(source_type="akshare")
        self._client = AkShareClient()
        self._mapper = AkShareMapper()
        self._indicator_engine = TechnicalIndicatorEngine()

    async def fetch_stock_quotes(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取股票行情数据"""
        logger.info(f"Fetching stock quotes (akshare): codes={codes}, start={start_date}, end={end_date}")
        snapshots = []
        as_of = datetime.now()
        for code in codes:
            try:
                # 将日期格式从 YYYY-MM-DD 转换为 YYYYMMDD（akshare 要求）
                ak_start = start_date.replace("-", "") if start_date else ""
                ak_end = end_date.replace("-", "") if end_date else ""
                df = self._client.get_stock_hist(
                    symbol=code,
                    start_date=ak_start,
                    end_date=ak_end
                )
                # 准备数据用于技术指标计算
                if not df.empty:
                    df_indicators = df.rename(columns={
                        "开盘": "open",
                        "最高": "high",
                        "最低": "low",
                        "收盘": "close",
                        "成交量": "volume"
                    }).copy()
                    df_indicators["date"] = pd.to_datetime(df_indicators["日期"], format="%Y%m%d")
                    df_indicators = df_indicators.set_index("date").sort_index()
                    # 计算技术指标
                    technical_indicators = self._indicator_engine.calculate(df_indicators, code)
                else:
                    technical_indicators = None
                # 映射行情数据
                raw_data = df.to_dict("records")
                market_snapshots = self._mapper.map_market_data(code, raw_data, as_of)
                # 添加技术指标到快照
                if technical_indicators and len(market_snapshots) > 0:
                    # 假设最后一个快照是最新的，添加技术指标
                    market_snapshots[-1].technical = technical_indicators
                snapshots.extend(market_snapshots)
            except (AkShareClientError, AkShareDataError) as e:
                logger.error(f"Failed to fetch quotes for code {code}: {e}")
                raise
        return snapshots

    async def fetch_financial_report(
        self, code: str, report_type: str = "annual"
    ) -> list[AssetAnalysisSnapshot]:
        """获取财务报告数据"""
        logger.info(f"Fetching financial report (akshare): code={code}, report_type={report_type}")
        try:
            df = self._client.get_financial_report(symbol=code)
            raw_data = df.to_dict("records")
            as_of = datetime.now()
            return self._mapper.map_financials(code, raw_data, as_of)
        except (AkShareClientError, AkShareDataError) as e:
            logger.error(f"Failed to fetch financial report for code {code}: {e}")
            raise

    async def fetch_fund_flow(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取资金流向数据"""
        logger.info(f"Fetching fund flow (akshare): codes={codes}, start={start_date}, end={end_date}")
        snapshots = []
        as_of = datetime.now()
        for code in codes:
            try:
                df = self._client.get_stock_individual_fund_flow(symbol=code)
                raw_data = df.to_dict("records")
                snapshots.extend(self._mapper.map_fund_flow(code, raw_data, as_of))
            except (AkShareClientError, AkShareDataError) as e:
                logger.error(f"Failed to fetch fund flow for code {code}: {e}")
                raise
        return snapshots

    async def fetch_valuation(
        self, code: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取估值数据"""
        logger.info(f"Fetching valuation (akshare): code={code}")
        try:
            df = self._client.get_stock_a_indicator_lg(symbol=code)
            raw_data = df.to_dict("records")[0] if len(df) > 0 else {}
            as_of = datetime.now()
            return self._mapper.map_valuation(code, raw_data, as_of)
        except (AkShareClientError, AkShareDataError) as e:
            logger.error(f"Failed to fetch valuation for code {code}: {e}")
            raise

    async def fetch_technical_indicators(
        self, code: str, indicators: list[str] | None = None
    ) -> list[AssetAnalysisSnapshot]:
        """获取技术指标数据"""
        logger.info(f"Fetching technical indicators (akshare): code={code}")
        # TODO: 实现技术指标计算
        as_of = datetime.now()
        return self._mapper.map_technical_indicators(code, {}, as_of)

    async def fetch_macro_indicators(
        self, indicators: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取宏观经济指标"""
        logger.info(
            f"Fetching macro indicators (akshare): indicators={indicators}, start={start_date}, end={end_date}"
        )
        # TODO: 根据 indicators 选择对应的数据接口
        try:
            # 示例：获取 CPI
            df_cpi = self._client.get_macro_china_cpi()
            raw_data = df_cpi.to_dict("records")
            macro_data = {}
            as_of = datetime.now()
            return self._mapper.map_macro(macro_data, as_of)
        except (AkShareClientError, AkShareDataError) as e:
            logger.error(f"Failed to fetch macro indicators: {e}")
            raise

    async def fetch_sentiment(
        self, codes: list[str] | None = None
    ) -> list[AssetAnalysisSnapshot]:
        """获取情绪数据"""
        logger.info(f"Fetching sentiment (akshare): codes={codes}")
        # TODO: 获取涨停池、北向资金等情绪数据
        try:
            df_north = self._client.get_stock_hsgt_north_net_flow_in_em()
            df_zt = self._client.get_stock_zt_pool_em()
            raw_data = {
                "northbound": df_north.to_dict("records"),
                "limit_up": df_zt.to_dict("records"),
            }
            as_of = datetime.now()
            if codes:
                snapshots = []
                for code in codes:
                    snapshots.extend(self._mapper.map_sentiment(code, raw_data, as_of))
                return snapshots
            else:
                return self._mapper.map_sentiment(None, raw_data, as_of)
        except (AkShareClientError, AkShareDataError) as e:
            logger.error(f"Failed to fetch sentiment data: {e}")
            raise

    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """
        获取 AkShare 数据

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
                title=f"AkShare Snapshot: {snapshot.canonical_id}",
                source_type="vendor_snapshot",
                source_name="akshare",
                raw_text=snapshot.model_dump_json(),
                canonical_text=snapshot.model_dump_json(),
                metadata={
                    "as_of": snapshot.as_of.isoformat(),
                },
            )
            envelopes.append(envelope)
        return envelopes

    def parse(self, source: Path | bytes | str, **kwargs: Any) -> DocumentEnvelope:
        """解析 AkShare 原始数据"""
        raise NotImplementedError("Parse method not implemented for AkShare adapter")

