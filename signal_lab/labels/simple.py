"""
简单标签函数

提供基础的标签计算函数。
"""


def compute_relative_return_label(asset_return: float, benchmark_return: float) -> float:
    """
    计算相对收益标签

    Args:
        asset_return: 资产收益率
        benchmark_return: 基准收益率

    Returns:
        相对收益率
    """
    return round(asset_return - benchmark_return, 10)
