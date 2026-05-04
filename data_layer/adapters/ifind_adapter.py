"""iFinD 数据适配器 - 占位实现"""
from datetime import datetime
from pathlib import Path
from typing import Any

from core.contracts import DocumentEnvelope
from core.observability import get_logger
from data_layer.adapters.base import BaseDataAdapter

logger = get_logger(__name__)


class IFinDAdapter(BaseDataAdapter):
    """
    iFinD 数据适配器 - 占位实现

    注意：这是一个占位实现，实际使用需要接入 iFinD 数据接口
    """

    def __init__(self):
        super().__init__(source_type="ifind")
        logger.warning("IFinDAdapter is a placeholder implementation")

    def fetch(self, **kwargs: Any) -> list[DocumentEnvelope]:
        """
        获取 iFinD 数据

        kwargs:
            data_type: str - 数据类型：stock, industry, macro, report
            codes: list[str] - 证券代码列表
            start_date: str - 开始日期
            end_date: str - 结束日期
        """
        data_type = kwargs.get("data_type", "stock")
        logger.info(f"Fetching iFinD data: type={data_type}")
        raise NotImplementedError(
            "IFinDAdapter is a placeholder. " "Please implement the actual iFinD integration."
        )

    def parse(self, source: Path | bytes | str, **kwargs: Any) -> DocumentEnvelope:
        """解析 iFinD 原始数据"""
        raise NotImplementedError(
            "IFinDAdapter is a placeholder. " "Please implement the actual iFinD integration."
        )

    def fetch_stock_basic(self, codes: list[str]) -> list[dict[str, Any]]:
        """获取股票基础数据"""
        raise NotImplementedError()

    def fetch_stock_quotes(
        self, codes: list[str], start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """获取股票行情数据"""
        raise NotImplementedError()

    def fetch_financial_report(
        self, code: str, report_type: str = "annual"
    ) -> list[dict[str, Any]]:
        """获取财务报告数据"""
        raise NotImplementedError()
