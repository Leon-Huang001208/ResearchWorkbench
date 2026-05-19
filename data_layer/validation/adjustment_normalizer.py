"""
复权对齐器

处理不同数据源之间的复权方式差异：
- AkShare: 默认前复权 (qfq)
- BaoStock: 默认不复权 (adjustflag="3")

提供统一的数据对齐功能。
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from core.observability import get_logger
from data_layer.crawlers.akshare.base import MarketData

logger = get_logger("adjustment_normalizer")


class AdjustmentType(Enum):
    """复权类型"""

    NONE = "none"  # 不复权
    QFQ = "qfq"  # 前复权
    HFQ = "hfq"  # 后复权


@dataclass
class AdjustmentInfo:
    """复权信息"""

    source_type: str  # "akshare" or "baostock"
    adjustment_type: AdjustmentType
    # 对于 BaoStock: "1"=后复权, "2"=前复权, "3"=不复权
    # 对于 AkShare: "qfq", "hfq", None
    raw_adjustment_flag: Optional[str] = None


@dataclass
class NormalizationResult:
    """归一化结果"""

    data: List[MarketData]
    target_adjustment: AdjustmentType
    source_adjustment_info: AdjustmentInfo
    normalization_applied: bool
    warnings: List[str]


class AdjustmentNormalizer:
    """
    复权对齐器

    将不同数据源、不同复权方式的数据对齐到目标复权方式。
    """

    # 复权方式映射
    BAOSTOCK_ADJUST_MAP = {
        "1": AdjustmentType.HFQ,
        "2": AdjustmentType.QFQ,
        "3": AdjustmentType.NONE,
    }

    AKSHARE_ADJUST_MAP = {
        "qfq": AdjustmentType.QFQ,
        "hfq": AdjustmentType.HFQ,
        "": AdjustmentType.NONE,
        None: AdjustmentType.NONE,
    }

    def __init__(self):
        self.logger = get_logger("adjustment_normalizer")

    def detect_adjustment(self, data: List[MarketData]) -> AdjustmentInfo:
        """
        从 MarketData 中检测复权类型

        Args:
            data: 市场数据列表

        Returns:
            复权信息
        """
        if not data:
            return AdjustmentInfo(
                source_type="unknown",
                adjustment_type=AdjustmentType.NONE,
            )

        # 获取数据源类型
        source_type = data[0].source or "unknown"

        # 从 extra 中检测复权信息
        extra = data[0].extra or {}

        if source_type == "baostock":
            adjustflag = extra.get("adjustflag", "3")
            adj_type = self.BAOSTOCK_ADJUST_MAP.get(adjustflag, AdjustmentType.NONE)
            return AdjustmentInfo(
                source_type="baostock",
                adjustment_type=adj_type,
                raw_adjustment_flag=adjustflag,
            )

        elif source_type == "akshare":
            # AkShare 通常从数据特征推断，或者从配置知道
            # 这里我们假设如果是 AkShare 且没有明确信息，默认是前复权
            return AdjustmentInfo(
                source_type="akshare",
                adjustment_type=AdjustmentType.QFQ,
                raw_adjustment_flag="qfq",
            )

        else:
            return AdjustmentInfo(
                source_type=source_type,
                adjustment_type=AdjustmentType.NONE,
            )

    def normalize_to_qfq(
        self,
        data: List[MarketData],
        source_info: Optional[AdjustmentInfo] = None,
    ) -> NormalizationResult:
        """
        将数据对齐到前复权

        Args:
            data: 源数据
            source_info: 源数据复权信息（自动检测如果未提供）

        Returns:
            归一化结果
        """
        return self.normalize(data, target_adjustment=AdjustmentType.QFQ, source_info=source_info)

    def normalize_to_none(
        self,
        data: List[MarketData],
        source_info: Optional[AdjustmentInfo] = None,
    ) -> NormalizationResult:
        """
        将数据对齐到不复权

        Args:
            data: 源数据
            source_info: 源数据复权信息（自动检测如果未提供）

        Returns:
            归一化结果
        """
        return self.normalize(data, target_adjustment=AdjustmentType.NONE, source_info=source_info)

    def normalize(
        self,
        data: List[MarketData],
        target_adjustment: AdjustmentType = AdjustmentType.QFQ,
        source_info: Optional[AdjustmentInfo] = None,
    ) -> NormalizationResult:
        """
        归一化数据到目标复权方式

        **注意**: 真正的复权转换需要复权因子数据（分红、拆股等）。
        这里我们采用实用策略：
        1. 如果源和目标相同，直接返回
        2. 如果不同，标记警告并返回数据（不做实际转换）
        3. 建议在数据拉取时就选择正确的复权方式

        Args:
            data: 源数据
            target_adjustment: 目标复权方式
            source_info: 源数据复权信息（自动检测如果未提供）

        Returns:
            归一化结果
        """
        if not data:
            return NormalizationResult(
                data=[],
                target_adjustment=target_adjustment,
                source_adjustment_info=AdjustmentInfo(
                    source_type="unknown",
                    adjustment_type=AdjustmentType.NONE,
                ),
                normalization_applied=False,
                warnings=["No data to normalize"],
            )

        # 检测源复权信息
        if source_info is None:
            source_info = self.detect_adjustment(data)

        warnings: List[str] = []

        # 如果已经是目标复权方式，直接返回
        if source_info.adjustment_type == target_adjustment:
            return NormalizationResult(
                data=data,
                target_adjustment=target_adjustment,
                source_adjustment_info=source_info,
                normalization_applied=False,
                warnings=[],
            )

        # 如果复权方式不同，添加警告
        warnings.append(
            f"Adjustment type mismatch: source={source_info.adjustment_type.value}, "
            f"target={target_adjustment.value}. "
            f"Consider fetching data with correct adjustment type instead of converting."
        )

        # 记录警告但不修改数据
        self.logger.warning(
            f"Adjustment conversion requested: {source_info.adjustment_type.value} -> {target_adjustment.value}. "
            f"This requires corporate action data. Returning original data with warning."
        )

        # 返回原始数据，标记未应用转换
        return NormalizationResult(
            data=data,
            target_adjustment=target_adjustment,
            source_adjustment_info=source_info,
            normalization_applied=False,
            warnings=warnings,
        )

    def get_fetch_adjustment_flags(
        self,
        target_adjustment: AdjustmentType,
    ) -> Dict[str, str]:
        """
        获取各数据源在拉取时应该使用的复权参数

        这是推荐做法：在拉取时就选择正确的复权方式，而不是事后转换。

        Args:
            target_adjustment: 目标复权方式

        Returns:
            各数据源的复权参数字典
        """
        result: Dict[str, str] = {}

        # AkShare 映射
        if target_adjustment == AdjustmentType.QFQ:
            result["akshare"] = "qfq"
        elif target_adjustment == AdjustmentType.HFQ:
            result["akshare"] = "hfq"
        else:
            result["akshare"] = ""

        # BaoStock 映射
        if target_adjustment == AdjustmentType.QFQ:
            result["baostock"] = "2"
        elif target_adjustment == AdjustmentType.HFQ:
            result["baostock"] = "1"
        else:
            result["baostock"] = "3"

        return result
