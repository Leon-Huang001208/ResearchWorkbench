"""
双源校验引擎

核心功能：
1. 对齐两个数据源的数据
2. 计算收盘价差异
3. 判断是否通过校验
4. 生成详细报告
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from core.observability import get_logger
from data_layer.crawlers.akshare.base import MarketData

logger = get_logger("dual_source_validator")


class ValidationStatus(Enum):
    """校验状态"""

    PASSED = "passed"  # 通过
    WARNING = "warning"  # 警告（差异在可接受范围）
    FAILED = "failed"  # 失败（差异超过阈值）
    INSUFFICIENT_DATA = "insufficient_data"  # 数据不足


@dataclass
class Discrepancy:
    """差异记录"""

    date: datetime
    field: str
    value_source1: Optional[float]
    value_source2: Optional[float]
    absolute_diff: Optional[float]
    relative_diff_pct: Optional[float]


@dataclass
class ValidationResult:
    """校验结果"""

    status: ValidationStatus
    symbol: str
    source1_name: str
    source2_name: str
    data_points_compared: int = 0
    discrepancies: List[Discrepancy] = field(default_factory=list)
    max_relative_diff_pct: Optional[float] = None
    avg_relative_diff_pct: Optional[float] = None
    threshold_pct: float = 0.5
    summary: str = ""
    recommended_source: Optional[str] = None
    validation_time: datetime = field(default_factory=datetime.now)


class DualSourceValidator:
    """
    双源校验引擎

    对比两个数据源的数据，检测差异。
    """

    def __init__(self, threshold_pct: float = 0.5, warning_threshold_pct: float = 0.2):
        """
        初始化校验器

        Args:
            threshold_pct: 失败阈值（默认 0.5%）
            warning_threshold_pct: 警告阈值（默认 0.2%）
        """
        self.threshold_pct = threshold_pct
        self.warning_threshold_pct = warning_threshold_pct
        self.logger = get_logger("dual_source_validator")

    def validate(
        self,
        symbol: str,
        data_source1: List[MarketData],
        data_source2: List[MarketData],
        source1_name: str = "akshare",
        source2_name: str = "baostock",
        fields_to_check: Optional[List[str]] = None,
    ) -> ValidationResult:
        """
        执行双源校验

        Args:
            symbol: 股票代码
            data_source1: 数据源1的数据
            data_source2: 数据源2的数据
            source1_name: 数据源1名称
            source2_name: 数据源2名称
            fields_to_check: 要检查的字段列表（默认仅 close）

        Returns:
            校验结果
        """
        if fields_to_check is None:
            fields_to_check = ["close"]

        # 基础检查
        if not data_source1 or not data_source2:
            return ValidationResult(
                status=ValidationStatus.INSUFFICIENT_DATA,
                symbol=symbol,
                source1_name=source1_name,
                source2_name=source2_name,
                summary=f"Insufficient data: source1={len(data_source1)}, source2={len(data_source2)}",
            )

        # 按日期对齐数据
        aligned_data = self._align_data_by_date(data_source1, data_source2)

        if len(aligned_data) == 0:
            return ValidationResult(
                status=ValidationStatus.INSUFFICIENT_DATA,
                symbol=symbol,
                source1_name=source1_name,
                source2_name=source2_name,
                summary="No overlapping dates between data sources",
            )

        # 计算差异
        discrepancies: List[Discrepancy] = []
        close_diffs: List[float] = []

        for date, (d1, d2) in aligned_data.items():
            for field_name in fields_to_check:
                v1 = self._get_field_value(d1, field_name)
                v2 = self._get_field_value(d2, field_name)

                if v1 is not None and v2 is not None:
                    abs_diff = abs(v1 - v2)
                    rel_diff = (abs_diff / v1) * 100 if v1 != 0 else None

                    if rel_diff and rel_diff > self.warning_threshold_pct:
                        discrepancies.append(
                            Discrepancy(
                                date=date,
                                field=field_name,
                                value_source1=v1,
                                value_source2=v2,
                                absolute_diff=abs_diff,
                                relative_diff_pct=rel_diff,
                            )
                        )

                    if field == "close" and rel_diff is not None:
                        close_diffs.append(rel_diff)

        # 计算统计指标
        max_diff = max(close_diffs) if close_diffs else None
        avg_diff = sum(close_diffs) / len(close_diffs) if close_diffs else None

        # 判断状态
        status = ValidationStatus.PASSED
        if max_diff and max_diff > self.threshold_pct:
            status = ValidationStatus.FAILED
        elif max_diff and max_diff > self.warning_threshold_pct:
            status = ValidationStatus.WARNING

        # 确定推荐源
        recommended_source = self._recommend_source(
            data_source1,
            data_source2,
            discrepancies,
            source1_name,
            source2_name,
        )

        # 生成摘要
        summary = self._generate_summary(
            status,
            len(aligned_data),
            len(discrepancies),
            max_diff,
            avg_diff,
            source1_name,
            source2_name,
        )

        return ValidationResult(
            status=status,
            symbol=symbol,
            source1_name=source1_name,
            source2_name=source2_name,
            data_points_compared=len(aligned_data),
            discrepancies=discrepancies,
            max_relative_diff_pct=max_diff,
            avg_relative_diff_pct=avg_diff,
            threshold_pct=self.threshold_pct,
            summary=summary,
            recommended_source=recommended_source,
        )

    def _align_data_by_date(
        self,
        data1: List[MarketData],
        data2: List[MarketData],
    ) -> Dict[datetime, Tuple[MarketData, MarketData]]:
        """
        按日期对齐两个数据源

        Args:
            data1: 数据源1
            data2: 数据源2

        Returns:
            对齐后的数据字典: {date: (data1_point, data2_point)}
        """
        # 构建日期索引
        idx1 = {d.timestamp: d for d in data1}
        idx2 = {d.timestamp: d for d in data2}

        # 找共同日期
        common_dates = set(idx1.keys()) & set(idx2.keys())

        # 构建对齐结果
        result: Dict[datetime, Tuple[MarketData, MarketData]] = {}
        for date in sorted(common_dates):
            result[date] = (idx1[date], idx2[date])

        return result

    def _get_field_value(self, data: MarketData, field: str) -> Optional[float]:
        """
        从 MarketData 中获取字段值

        Args:
            data: 市场数据
            field: 字段名

        Returns:
            字段值
        """
        if field == "open":
            return data.open
        elif field == "high":
            return data.high
        elif field == "low":
            return data.low
        elif field == "close":
            return data.close
        elif field == "volume":
            return float(data.volume) if data.volume else None
        elif field == "amount":
            return data.amount
        else:
            return None

    def _recommend_source(
        self,
        data1: List[MarketData],
        data2: List[MarketData],
        discrepancies: List[Discrepancy],
        name1: str,
        name2: str,
    ) -> Optional[str]:
        """
        推荐使用哪个数据源

        策略：
        1. 如果一个源的数据多很多，优先选择数据多的
        2. 否则，统计哪个源在差异中更接近均值
        3. 默认优先 AkShare
        """
        # 先看数据量
        len1, len2 = len(data1), len(data2)
        if len1 > len2 * 1.5:
            return name1
        if len2 > len1 * 1.5:
            return name2

        # 统计差异偏向

        for disc in discrepancies:
            if disc.relative_diff_pct is not None:
                # 这里我们可以比较与历史均值的偏离
                # 简化处理：假设两个源都同样可靠时优先 AkShare
                pass

        # 默认优先 AkShare
        if name1 == "akshare":
            return name1
        elif name2 == "akshare":
            return name2
        else:
            return name1

    def _generate_summary(
        self,
        status: ValidationStatus,
        data_points: int,
        discrepancy_count: int,
        max_diff: Optional[float],
        avg_diff: Optional[float],
        name1: str,
        name2: str,
    ) -> str:
        """生成摘要"""
        status_str = status.value.upper()
        max_diff_str = f"{max_diff:.2f}%" if max_diff is not None else "N/A"
        avg_diff_str = f"{avg_diff:.2f}%" if avg_diff is not None else "N/A"

        return (
            f"[{status_str}] Compared {data_points} data points "
            f"between {name1} and {name2}. "
            f"Found {discrepancy_count} discrepancies exceeding warning threshold. "
            f"Max diff: {max_diff_str}, Avg diff: {avg_diff_str}."
        )
