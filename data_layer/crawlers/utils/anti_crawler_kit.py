"""
通用反爬虫工具包

提供多种反爬虫规避策略，供所有爬虫使用：
- User-Agent 轮换（支持多种来源）
- 请求头随机化
- 智能延迟策略（带抖动）
- 指数退避重试
- 速率限制
- 自适应请求间隔

使用示例:

```python
from data_layer.crawlers.utils import AntiScrapeKit, AntiScrapeConfig, retry_with_backoff

# 配置反爬
config = AntiScrapeConfig(
    base_delay=2.0,
    jitter_range=1.0,
    max_requests_per_minute=60,
    enable_rate_limit=True,
)

# 创建反爬工具
kit = AntiScrapeKit(config)

# 发送请求
headers = kit.get_headers()
kit.before_request()
response = requests.get(url, headers=headers)
kit.after_success()

# 使用重试装饰器
@retry_with_backoff(max_retries=5)
def fetch_data(url):
    return requests.get(url)
```
"""
import logging
import random
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

T = TypeVar("T")


@dataclass
class RetryConfig:
    """重试策略配置"""

    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_exceptions: Tuple[Type[Exception], ...] = field(default_factory=lambda: (Exception,))


@dataclass
class AntiScrapeConfig:
    """反爬虫配置"""

    # 基础延迟配置
    base_delay: float = 1.5
    jitter_range: float = 0.8
    min_delay: float = 0.3
    max_delay: float = 10.0

    # User-Agent 轮换
    enable_ua_rotation: bool = True
    custom_user_agents: Optional[List[str]] = None

    # Referer 配置
    enable_referer_rotation: bool = True
    default_referer: str = "https://www.google.com"
    custom_referers: Optional[List[str]] = None

    # 请求头随机化
    enable_header_randomization: bool = True

    # 速率限制
    enable_rate_limit: bool = True
    max_requests_per_minute: int = 80
    max_requests_per_hour: int = 2000

    # 指数退避
    backoff_base: float = 2.0
    backoff_max: float = 120.0

    # 自适应延迟
    enable_adaptive_delay: bool = True
    success_streak_threshold: int = 5
    success_speedup_factor: float = 0.8
    failure_slowdown_factor: float = 2.0


class RequestTiming:
    """请求时序追踪器"""

    def __init__(self) -> None:
        self.requests_minute: List[float] = []
        self.requests_hour: List[float] = []
        self.last_request_time: float = 0.0
        self._lock = None

    def record_request(self) -> None:
        """记录一次请求"""
        now = time.time()
        self.last_request_time = now
        self.requests_minute.append(now)
        self.requests_hour.append(now)
        self._cleanup()

    def _cleanup(self) -> None:
        """清理过期记录"""
        now = time.time()
        self.requests_minute = [t for t in self.requests_minute if now - t < 60]
        self.requests_hour = [t for t in self.requests_hour if now - t < 3600]

    def get_minute_count(self) -> int:
        """获取最近一分钟请求数"""
        self._cleanup()
        return len(self.requests_minute)

    def get_hour_count(self) -> int:
        """获取最近一小时请求数"""
        self._cleanup()
        return len(self.requests_hour)

    def time_since_last_request(self) -> float:
        """获取距离上次请求的时间"""
        if self.last_request_time == 0:
            return float("inf")
        return time.time() - self.last_request_time


class UserAgentRotator:
    """User-Agent 轮换器"""

    # 现代浏览器 User-Agent 池
    DEFAULT_DESKTOP_UAS = [
        # Chrome Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        # Chrome Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        # Firefox Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
        # Firefox Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0",
        # Edge Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
        # Safari Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    ]

    def __init__(self, custom_uas: Optional[List[str]] = None):
        self.user_agents = custom_uas or self.DEFAULT_DESKTOP_UAS
        self._last_ua: Optional[str] = None

    def get_random(self) -> str:
        """获取随机 User-Agent（避免连续重复）"""
        ua = random.choice(self.user_agents)
        while ua == self._last_ua and len(self.user_agents) > 1:
            ua = random.choice(self.user_agents)
        self._last_ua = ua
        return ua


class SmartDelayer:
    """智能延迟器"""

    def __init__(self, config: AntiScrapeConfig):
        self.config = config
        self.failure_count = 0
        self.success_streak = 0
        self.timing = RequestTiming()
        self._logger = logging.getLogger(__name__)

    def record_success(self) -> None:
        """记录成功请求"""
        self.failure_count = 0
        self.success_streak += 1
        self.timing.record_request()

    def record_failure(self) -> None:
        """记录失败请求"""
        self.failure_count += 1
        self.success_streak = 0

    def get_delay(self, is_heavy_request: bool = False) -> float:
        """
        计算下次请求的延迟时间

        Args:
            is_heavy_request: 是否为重量级请求（如 AI 调用、PDF 下载等）

        Returns:
            延迟秒数
        """
        base = self.config.base_delay

        if is_heavy_request:
            base *= 2.0

        if self.config.enable_adaptive_delay:
            if self.success_streak >= self.config.success_streak_threshold:
                base *= self.config.success_speedup_factor
            if self.failure_count > 0:
                base *= self.config.failure_slowdown_factor**self.failure_count

        if self.failure_count > 0:
            backoff = min(self.config.backoff_base**self.failure_count, self.config.backoff_max)
            base = max(base, backoff)
            self._logger.debug(f"检测到 {self.failure_count} 次失败，使用退避延迟: {base:.1f}s")

        if self.config.enable_rate_limit:
            minute_count = self.timing.get_minute_count()
            hour_count = self.timing.get_hour_count()

            if minute_count >= self.config.max_requests_per_minute:
                base = max(base, 10.0)
                self._logger.warning(f"速率限制: 每分钟 {minute_count} 次请求，增加延迟")

            if hour_count >= self.config.max_requests_per_hour:
                base = max(base, 30.0)
                self._logger.warning(f"速率限制: 每小时 {hour_count} 次请求，增加延迟")

        jitter = random.uniform(-self.config.jitter_range * 0.5, self.config.jitter_range * 0.5)
        delay = max(base + jitter, self.config.min_delay)
        delay = min(delay, self.config.max_delay)

        return delay

    def sleep(self, is_heavy_request: bool = False) -> None:
        """执行延迟"""
        delay = self.get_delay(is_heavy_request)
        self._logger.debug(f"等待 {delay:.1f}s...")
        time.sleep(delay)


class HeaderRandomizer:
    """请求头随机化器"""

    ACCEPT_LANGUAGES = [
        "zh-CN,zh;q=0.9,en;q=0.8",
        "zh-CN,zh;q=0.9",
        "zh-CN,zh;q=0.8,en-US;q=0.7,en;q=0.6",
    ]

    ACCEPT_VALUES = [
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    ]

    CACHE_CONTROLS = [
        "max-age=0",
        "no-cache",
        "",
    ]

    def get_random_headers(self, base_headers: Optional[Dict] = None) -> Dict[str, str]:
        """获取随机化的请求头"""
        headers = base_headers.copy() if base_headers else {}

        if "Accept-Language" not in headers:
            headers["Accept-Language"] = random.choice(self.ACCEPT_LANGUAGES)
        if "Accept" not in headers:
            headers["Accept"] = random.choice(self.ACCEPT_VALUES)

        cache_control = random.choice(self.CACHE_CONTROLS)
        if cache_control and "Cache-Control" not in headers:
            headers["Cache-Control"] = cache_control

        if random.random() > 0.5:
            headers[
                "Sec-CH-UA"
            ] = '"Chromium";v="130", "Not=A?Brand";v="24", "Google Chrome";v="130"'
            headers["Sec-CH-UA-Mobile"] = "?0"
            headers["Sec-CH-UA-Platform"] = '"Windows"'

        if random.random() > 0.7:
            headers["DNT"] = "1"

        if random.random() > 0.5:
            headers["Upgrade-Insecure-Requests"] = "1"

        return headers


class AntiScrapeKit:
    """反爬虫工具包 - 统一入口"""

    def __init__(self, config: Optional[AntiScrapeConfig] = None):
        self.config = config or AntiScrapeConfig()
        self.ua_rotator = UserAgentRotator(self.config.custom_user_agents)
        self.header_randomizer = HeaderRandomizer()
        self.delayer = SmartDelayer(self.config)
        self._logger = logging.getLogger(__name__)

    def get_headers(
        self,
        base_headers: Optional[Dict] = None,
        referer: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        获取完整的请求头

        Args:
            base_headers: 基础请求头
            referer: 指定的 Referer

        Returns:
            请求头字典
        """
        headers = base_headers.copy() if base_headers else {}

        if self.config.enable_ua_rotation:
            headers["User-Agent"] = self.ua_rotator.get_random()

        if self.config.enable_referer_rotation:
            headers["Referer"] = referer or self.config.default_referer

        if self.config.enable_header_randomization:
            headers = self.header_randomizer.get_random_headers(headers)

        return headers

    def before_request(self, is_heavy_request: bool = False) -> None:
        """请求前的处理（延迟等）"""
        self.delayer.sleep(is_heavy_request)

    def after_success(self) -> None:
        """成功后的处理"""
        self.delayer.record_success()

    def after_failure(self) -> None:
        """失败后的处理"""
        self.delayer.record_failure()

    def get_current_stats(self) -> Dict[str, Any]:
        """获取当前统计信息"""
        return {
            "minute_requests": self.delayer.timing.get_minute_count(),
            "hour_requests": self.delayer.timing.get_hour_count(),
            "failure_count": self.delayer.failure_count,
            "success_streak": self.delayer.success_streak,
            "current_delay": self.delayer.get_delay(),
        }


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    max_retries: Optional[int] = None,
    base_delay: Optional[float] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    指数退避重试装饰器

    Args:
        config: 重试配置对象
        max_retries: 最大重试次数（覆盖配置）
        base_delay: 基础延迟（覆盖配置）
        on_retry: 重试回调函数，参数为 (重试次数, 异常)

    使用示例:
        @retry_with_backoff(max_retries=5)
        def fetch_url(url):
            return requests.get(url)
    """
    if config is None:
        config = RetryConfig()
    if max_retries is not None:
        config.max_retries = max_retries
    if base_delay is not None:
        config.base_delay = base_delay

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            logger = logging.getLogger(func.__module__)

            for attempt in range(config.max_retries):
                try:
                    return func(*args, **kwargs)
                except config.retry_exceptions as e:
                    last_exception = e
                    remaining_attempts = config.max_retries - attempt - 1

                    if remaining_attempts <= 0:
                        logger.error(f"重试次数已用尽，最后异常: {e}")
                        break

                    delay = config.base_delay * (config.exponential_base**attempt)
                    if config.jitter:
                        delay *= 0.5 + random.random()
                    delay = min(delay, config.max_delay)

                    logger.warning(
                        f"操作失败 (尝试 {attempt + 1}/{config.max_retries}): {e}. "
                        f"等待 {delay:.1f}s 后重试..."
                    )

                    if on_retry:
                        on_retry(attempt + 1, e)

                    time.sleep(delay)

            raise last_exception or Exception("未知错误")

        return wrapper

    return decorator


def random_delay(
    base: float = 1.0,
    jitter: float = 0.5,
    min_delay: float = 0.1,
    max_delay: float = 5.0,
) -> None:
    """
    简单随机延迟函数

    Args:
        base: 基础延迟
        jitter: 抖动范围
        min_delay: 最小延迟
        max_delay: 最大延迟
    """
    delay = base + random.uniform(-jitter * 0.5, jitter * 0.5)
    delay = max(min_delay, delay)
    delay = min(max_delay, delay)
    time.sleep(delay)
