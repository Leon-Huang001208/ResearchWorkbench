"""
AkShare 配置模块
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Optional


@dataclass
class AkShareConfig:
    """AkShare 适配器配置"""

    # 通用配置
    enable_cache: bool = True
    cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=30))
    cache_dir: Optional[str] = None

    # 请求配置
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 2.0

    # 行情配置
    default_period: str = "daily"  # daily/weekly/monthly
    default_adjust: str = "qfq"  # qfq/hfq/None (前复权/后复权/不复权)

    # 新闻配置
    news_sources: List[str] = field(default_factory=lambda: ["sina", "eastmoney"])
    news_limit: int = 100

    # 宏配置
    macro_sources: List[str] = field(default_factory=lambda: ["stats", "pbc"])

    # 调试配置
    verbose: bool = False


# 默认配置实例
DEFAULT_CONFIG = AkShareConfig()
