"""日期处理工具模块"""
from datetime import datetime, timedelta
from typing import Optional, Tuple


def parse_and_validate_date_range(
    start_date_str: Optional[str] = None, end_date_str: Optional[str] = None, default_days: int = 2
) -> Tuple[datetime, datetime]:
    """统一解析和验证日期范围"""
    # 设置默认结束日期
    if end_date_str is None:
        end_date = datetime.now()
    else:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        except ValueError:
            end_date = datetime.now()

    # 设置默认开始日期
    if start_date_str is None:
        start_date = end_date - timedelta(days=default_days)
    else:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError:
            start_date = end_date - timedelta(days=default_days)

    # 确保开始日期不晚于结束日期
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    return start_date, end_date
