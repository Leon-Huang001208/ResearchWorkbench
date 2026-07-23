"""通用 normalizer 工具函数"""

from decimal import Decimal
from typing import Optional


def to_decimal(x: Optional[float]) -> Optional[Decimal]:
    """安全转换数值为 Decimal，处理 None 和异常值"""
    if x is None:
        return None
    try:
        return Decimal(str(x))
    except Exception:
        return None
