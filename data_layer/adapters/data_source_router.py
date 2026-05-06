"""数据源路由器 - 实现 iFinD 优先、China Stock 降级的策略"""
from typing import Any

from core.contracts import DocumentEnvelope
from core.contracts.assets import AssetAnalysisSnapshot
from core.observability import get_logger
from data_layer.adapters import ChinaStockAdapter, IFinDAdapter
from data_layer.adapters.china_stock.exceptions import ChinaStockPluginError
from data_layer.adapters.ifind.exceptions import IFinDDatasourceError

logger = get_logger(__name__)


class DataSourceRouter:
    """
    数据源路由器
    策略：iFinD 优先 → China Stock 降级
    """

    def __init__(self):
        self.ifind_adapter = IFinDAdapter()
        self.china_stock_adapter = ChinaStockAdapter()

    async def fetch_stock_quotes(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取股票行情数据，带降级策略"""
        try:
            logger.info("Trying iFinD adapter for stock quotes")
            return await self.ifind_adapter.fetch_stock_quotes(codes, start_date, end_date)
        except IFinDDatasourceError as e:
            logger.warning(f"iFinD adapter failed: {e}, falling back to China Stock adapter")
            try:
                return await self.china_stock_adapter.fetch_stock_quotes(codes, start_date, end_date)
            except ChinaStockPluginError as e2:
                logger.error(f"China Stock adapter also failed: {e2}")
                raise

    async def fetch_financial_report(
        self, code: str, report_type: str = "annual"
    ) -> list[AssetAnalysisSnapshot]:
        """获取财务报告数据，带降级策略"""
        try:
            logger.info("Trying iFinD adapter for financial report")
            return await self.ifind_adapter.fetch_financial_report(code, report_type)
        except IFinDDatasourceError as e:
            logger.warning(f"iFinD adapter failed: {e}, falling back to China Stock adapter")
            try:
                return await self.china_stock_adapter.fetch_financial_report(code, report_type)
            except ChinaStockPluginError as e2:
                logger.error(f"China Stock adapter also failed: {e2}")
                raise

    async def fetch_fund_flow(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取资金流向数据，带降级策略"""
        try:
            logger.info("Trying iFinD adapter for fund flow")
            return await self.ifind_adapter.fetch_fund_flow(codes, start_date, end_date)
        except IFinDDatasourceError as e:
            logger.warning(f"iFinD adapter failed: {e}, falling back to China Stock adapter")
            try:
                return await self.china_stock_adapter.fetch_fund_flow(codes, start_date, end_date)
            except ChinaStockPluginError as e2:
                logger.error(f"China Stock adapter also failed: {e2}")
                raise

    async def fetch_industry_classification(
        self, codes: list[str]
    ) -> list[AssetAnalysisSnapshot]:
        """获取行业分类数据，仅 iFinD 支持"""
        try:
            logger.info("Trying iFinD adapter for industry classification")
            return await self.ifind_adapter.fetch_industry_classification(codes)
        except IFinDDatasourceError as e:
            logger.error(f"iFinD adapter failed: {e}, China Stock adapter doesn't support industry classification yet")
            raise

    async def fetch_macro_indicators(
        self, indicators: list[str], start_date: str, end_date: str
    ) -> list[AssetAnalysisSnapshot]:
        """获取宏观指标数据，带降级策略"""
        try:
            logger.info("Trying iFinD adapter for macro indicators")
            return await self.ifind_adapter.fetch_macro_indicators(indicators, start_date, end_date)
        except IFinDDatasourceError as e:
            logger.warning(f"iFinD adapter failed: {e}, falling back to China Stock adapter")
            try:
                return await self.china_stock_adapter.fetch_macro_indicators(indicators, start_date, end_date)
            except ChinaStockPluginError as e2:
                logger.error(f"China Stock adapter also failed: {e2}")
                raise

    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """获取数据，带降级策略"""
        try:
            logger.info("Trying iFinD adapter for fetch")
            return self.ifind_adapter.fetch(**kwargs)
        except Exception as e:
            logger.warning(f"iFinD adapter failed: {e}, falling back to China Stock adapter")
            try:
                return self.china_stock_adapter.fetch(**kwargs)
            except Exception as e2:
                logger.error(f"China Stock adapter also failed: {e2}")
                raise
