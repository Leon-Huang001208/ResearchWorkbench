"""数据源路由器 - 实现 iFinD 优先、AKShare 其次、China Stock 降级的策略

NOTE: DataSourceRouter 已标记为 legacy。自动化爬取请使用
CrawlOrchestrator (core/services/crawl_orchestrator.py)。
"""
from datetime import datetime
from typing import Any

from core.contracts import DocumentEnvelope
from core.contracts.assets import AssetAnalysisSnapshot
from core.observability import get_logger
from data_layer.adapters import (
    AKShareAdapter,
    ChinaStockAdapter,
    CLSAdapter,
    CNStockAdapter,
    IFinDAdapter,
    ZQAdapter,
)
from data_layer.adapters.akshare.exceptions import AkShareAdapterError
from data_layer.adapters.china_stock.exceptions import ChinaStockPluginError
from data_layer.adapters.ifind.exceptions import IFinDDatasourceError


# AKShare exception placeholder for now
class AKShareAdapterError(Exception):
    pass


logger = get_logger(__name__)


class DataSourceRouter:
    """
    数据源路由器
    策略：iFinD 优先 → AkShare → China Stock 降级
    """

    def __init__(self):
        self.ifind_adapter = IFinDAdapter()
        self.akshare_adapter = AKShareAdapter()
        self.china_stock_adapter = ChinaStockAdapter()
        self.cls_adapter = CLSAdapter()
        self.cnstock_adapter = CNStockAdapter()
        self.zq_adapter = ZQAdapter()

    async def fetch_stock_quotes(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取股票行情数据，带降级策略"""
        try:
            logger.info("Trying iFinD adapter for stock quotes")
            return await self.ifind_adapter.fetch_stock_quotes(codes, start_date, end_date)
        except IFinDDatasourceError as e:
            logger.warning(f"iFinD adapter failed: {e}, falling back to AkShare adapter")
            try:
                return await self.akshare_adapter.fetch_stock_quotes(codes, start_date, end_date)
            except AkShareAdapterError as e2:
                logger.warning(f"AkShare adapter failed: {e2}, falling back to China Stock adapter")
                try:
                    return await self.china_stock_adapter.fetch_stock_quotes(
                        codes, start_date, end_date
                    )
                except ChinaStockPluginError as e3:
                    logger.error(f"China Stock adapter also failed: {e3}")
                    raise

    async def fetch_financial_report(
        self, code: str, report_type: str = "annual"
    ) -> list[AssetAnalysisSnapshot]:
        """获取财务报告数据，带降级策略"""
        try:
            logger.info("Trying iFinD adapter for financial report")
            return await self.ifind_adapter.fetch_financial_report(code, report_type)
        except IFinDDatasourceError as e:
            logger.warning(f"iFinD adapter failed: {e}, falling back to AkShare adapter")
            try:
                return await self.akshare_adapter.fetch_financial_report(code, report_type)
            except AkShareAdapterError as e2:
                logger.warning(f"AkShare adapter failed: {e2}, falling back to China Stock adapter")
                try:
                    return await self.china_stock_adapter.fetch_financial_report(code, report_type)
                except ChinaStockPluginError as e3:
                    logger.error(f"China Stock adapter also failed: {e3}")
                    raise

    async def fetch_fund_flow(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取资金流向数据，带降级策略"""
        try:
            logger.info("Trying iFinD adapter for fund flow")
            return await self.ifind_adapter.fetch_fund_flow(codes, start_date, end_date)
        except IFinDDatasourceError as e:
            logger.warning(f"iFinD adapter failed: {e}, falling back to AkShare adapter")
            try:
                return await self.akshare_adapter.fetch_fund_flow(codes, start_date, end_date)
            except AkShareAdapterError as e2:
                logger.warning(f"AkShare adapter failed: {e2}, falling back to China Stock adapter")
                try:
                    return await self.china_stock_adapter.fetch_fund_flow(
                        codes, start_date, end_date
                    )
                except ChinaStockPluginError as e3:
                    logger.error(f"China Stock adapter also failed: {e3}")
                    raise

    async def fetch_industry_classification(self, codes: list[str]) -> list[AssetAnalysisSnapshot]:
        """获取行业分类数据，仅 iFinD 支持"""
        try:
            logger.info("Trying iFinD adapter for industry classification")
            return await self.ifind_adapter.fetch_industry_classification(codes)
        except IFinDDatasourceError as e:
            logger.error(
                f"iFinD adapter failed: {e}, China Stock adapter doesn't support industry classification yet"
            )
            raise

    async def fetch_macro_indicators(
        self, indicators: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取宏观指标数据，带降级策略"""
        try:
            logger.info("Trying iFinD adapter for macro indicators")
            return await self.ifind_adapter.fetch_macro_indicators(indicators, start_date, end_date)
        except IFinDDatasourceError as e:
            logger.warning(f"iFinD adapter failed: {e}, falling back to AkShare adapter")
            try:
                return await self.akshare_adapter.fetch_macro_indicators(
                    indicators, start_date, end_date
                )
            except AkShareAdapterError as e2:
                logger.warning(f"AkShare adapter failed: {e2}, falling back to China Stock adapter")
                try:
                    return await self.china_stock_adapter.fetch_macro_indicators(
                        indicators, start_date, end_date
                    )
                except ChinaStockPluginError as e3:
                    logger.error(f"China Stock adapter also failed: {e3}")
                    raise

    async def fetch_technical_indicators(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取技术指标数据，带降级策略"""
        try:
            logger.info("Trying iFinD adapter for technical indicators")
            return await self.ifind_adapter.fetch_technical_indicators(codes, start_date, end_date)
        except IFinDDatasourceError as e:
            logger.warning(f"iFinD adapter failed: {e}, falling back to AkShare adapter")
            try:
                snapshots = []
                for code in codes:
                    snapshots.extend(await self.akshare_adapter.fetch_technical_indicators(code))
                return snapshots
            except AkShareAdapterError as e2:
                logger.warning(f"AkShare adapter failed: {e2}, falling back to China Stock adapter")
                try:
                    snapshots = []
                    for code in codes:
                        snapshots.extend(
                            await self.china_stock_adapter.fetch_technical_indicators(code)
                        )
                    return snapshots
                except ChinaStockPluginError as e3:
                    logger.error(
                        f"China Stock adapter also failed: {e3}, returning insufficient evidence"
                    )
                    as_of = datetime.now()
                    return [
                        AssetAnalysisSnapshot(
                            canonical_id=f"insufficient:{code}:{as_of.strftime('%Y%m%d')}:technical",
                            as_of=as_of,
                            evidence_refs=["insufficient_evidence"],
                        )
                        for code in codes
                    ]

    async def fetch_sentiment(
        self,
        codes: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[AssetAnalysisSnapshot]:
        """获取情绪数据，带降级策略"""
        try:
            logger.info("Trying iFinD adapter for sentiment data")
            if codes and start_date and end_date:
                return await self.ifind_adapter.fetch_sentiment(codes, start_date, end_date)
            else:
                raise IFinDDatasourceError("iFinD requires codes, start_date, end_date")
        except IFinDDatasourceError as e:
            logger.warning(f"iFinD adapter failed: {e}, falling back to AkShare adapter")
            try:
                return await self.akshare_adapter.fetch_sentiment(codes)
            except AkShareAdapterError as e2:
                logger.warning(f"AkShare adapter failed: {e2}, falling back to China Stock adapter")
                try:
                    return await self.china_stock_adapter.fetch_sentiment(codes)
                except ChinaStockPluginError as e3:
                    logger.error(
                        f"China Stock adapter also failed: {e3}, returning insufficient evidence"
                    )
                    as_of = datetime.now()
                    target_codes = codes or ["market"]
                    return [
                        AssetAnalysisSnapshot(
                            canonical_id=f"insufficient:{code}:{as_of.strftime('%Y%m%d')}:sentiment",
                            as_of=as_of,
                            evidence_refs=["insufficient_evidence"],
                        )
                        for code in target_codes
                    ]

    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """获取数据，带降级策略"""
        try:
            logger.info("Trying iFinD adapter for fetch")
            return self.ifind_adapter.fetch(**kwargs)
        except Exception as e:
            logger.warning(f"iFinD adapter failed: {e}, falling back to AkShare adapter")
            try:
                return self.akshare_adapter.fetch(**kwargs)
            except Exception as e2:
                logger.warning(f"AkShare adapter failed: {e2}, falling back to China Stock adapter")
                try:
                    return self.china_stock_adapter.fetch(**kwargs)
                except Exception as e3:
                    logger.error(f"China Stock adapter also failed: {e3}")
                    raise

    async def fetch_news_cls(self, **kwargs) -> list[DocumentEnvelope]:
        """Fetch CLS (财联社) news"""
        logger.info("Fetching CLS news via DataSourceRouter")
        return self.cls_adapter.fetch(**kwargs)

    async def fetch_news_cnstock(self, **kwargs) -> list[DocumentEnvelope]:
        """Fetch CNStock (中国证券网) news"""
        logger.info("Fetching CNStock news via DataSourceRouter")
        return self.cnstock_adapter.fetch(**kwargs)

    async def fetch_reports_zq(self, **kwargs) -> list[DocumentEnvelope]:
        """Fetch ZQ (知丘) content (reports/news/meetings)"""
        logger.info("Fetching ZQ content via DataSourceRouter")
        return self.zq_adapter.fetch(**kwargs)
