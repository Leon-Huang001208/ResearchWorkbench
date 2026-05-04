"""日期标准化器"""
import re
from datetime import date, datetime
from typing import Optional, Union

from core.observability import get_logger

logger = get_logger(__name__)


class DateNormalizer:
    """日期标准化器"""

    # 日期格式模式
    DATE_PATTERNS = [
        # 标准格式
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", "%Y-%m-%d"),
        (r"(\d{4})/(\d{1,2})/(\d{1,2})", "%Y/%m/%d"),
        (r"(\d{4})\.(\d{1,2})\.(\d{1,2})", "%Y.%m.%d"),
        # 中文格式
        (r"(\d{4})年(\d{1,2})月(\d{1,2})日", "%Y年%m月%d日"),
        (r"(\d{4})年(\d{1,2})月", "%Y年%m月"),
        # 其他常见格式
        (r"(\d{2})/(\d{2})/(\d{4})", "%d/%m/%Y"),
        (r"(\d{2})-(\d{2})-(\d{4})", "%d-%m-%Y"),
        # 年月简写
        (r"(\d{4})(\d{2})(\d{2})", "%Y%m%d"),
        (r"(\d{4})-(\d{2})", "%Y-%m"),
    ]

    # 相对日期
    RELATIVE_PATTERNS = {
        r"今天": 0,
        r"昨天": -1,
        r"前天": -2,
        r"明天": 1,
        r"后天": 2,
    }

    def __init__(self, default_year: Optional[int] = None):
        self.default_year = default_year or datetime.now().year

    def normalize(self, date_str: str, *, strict: bool = False) -> Optional[date]:
        """
        标准化日期字符串为 date 对象

        Args:
            date_str: 日期字符串
            strict: 是否严格模式，严格模式下失败会抛出异常

        Returns:
            标准化后的 date 对象，失败返回 None
        """
        if not date_str:
            return None

        date_str = date_str.strip()

        # 尝试相对日期
        result = self._try_relative_date(date_str)
        if result:
            return result

        # 尝试各种日期格式
        for pattern, fmt in self.DATE_PATTERNS:
            result = self._try_parse_pattern(date_str, pattern, fmt)
            if result:
                return result

        if strict:
            raise ValueError(f"Could not parse date: {date_str}")

        logger.debug(f"Could not parse date: {date_str}")
        return None

    def normalize_to_str(
        self, date_str: str, *, strict: bool = False, format: str = "%Y-%m-%d"
    ) -> Optional[str]:
        """
        标准化日期为字符串

        Args:
            date_str: 日期字符串
            strict: 是否严格模式
            format: 输出格式

        Returns:
            格式化后的日期字符串
        """
        d = self.normalize(date_str, strict=strict)
        return d.strftime(format) if d else None

    def _try_relative_date(self, date_str: str) -> Optional[date]:
        """尝试解析相对日期"""
        today = date.today()
        for pattern, delta in self.RELATIVE_PATTERNS.items():
            if re.fullmatch(pattern, date_str):
                return date.fromordinal(today.toordinal() + delta)
        return None

    def _try_parse_pattern(self, date_str: str, pattern: str, fmt: str) -> Optional[date]:
        """尝试用特定模式解析日期"""
        match = re.search(pattern, date_str)
        if not match:
            return None

        try:
            parsed = datetime.strptime(match.group(0), fmt).date()
            # 处理两位年份的情况（假设是 2000 年后）
            if parsed.year < 100:
                parsed = parsed.replace(year=parsed.year + 2000)
            return parsed
        except ValueError:
            return None
