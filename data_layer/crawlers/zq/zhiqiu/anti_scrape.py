"""
反爬措施模块

提供多种反爬虫规避策略：
- User-Agent 轮换
- Referer 轮换
- 请求头随机化
- 智能延迟策略
- 指数退避重试
- 请求指纹伪装
"""

import logging
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class AntiScrapeConfig:
    """反爬配置"""

    # User-Agent 轮换
    enable_ua_rotation: bool = True
    # Referer 轮换
    enable_referer_rotation: bool = True
    # 请求头随机化
    enable_header_randomization: bool = True
    # 请求间隔（基础秒数）
    base_delay: float = 1.0
    # 随机抖动范围
    jitter_range: float = 0.5
    # 最小延迟
    min_delay: float = 0.5
    # 最大延迟
    max_delay: float = 3.0
    # 指数退避基础
    backoff_base: float = 2.0
    # 指数退避最大延迟
    backoff_max: float = 60.0
    # 启用速率限制
    enable_rate_limit: bool = True
    # 每分钟最大请求数
    max_requests_per_minute: int = 100
    # 每小时最大请求数
    max_requests_per_hour: int = 10000


class RequestTiming:
    """请求时序追踪器"""

    def __init__(self) -> None:
        self.requests_minute: List[float] = []
        self.requests_hour: List[float] = []
        self.last_request_time: float = 0.0

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
    DESKTOP_UAS = [
        # Chrome Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        # Chrome Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        # Firefox Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
        # Firefox Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0",
        # Edge Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
        # Safari Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    ]

    def __init__(self) -> None:
        self._last_ua: Optional[str] = None

    def get_random(self) -> str:
        """获取随机 User-Agent（避免连续重复）"""
        ua = random.choice(self.DESKTOP_UAS)
        # 避免连续使用相同的 UA
        while ua == self._last_ua and len(self.DESKTOP_UAS) > 1:
            ua = random.choice(self.DESKTOP_UAS)
        self._last_ua = ua
        return ua


class RefererRotator:
    """Referer 轮换器"""

    BASE_REFERERS = [
        "https://www.kanzhiqiu.com/newreport/index.htm",
        "https://www.kanzhiqiu.com/newreport/newReportSearch.htm",
        "https://www.kanzhiqiu.com/",
    ]

    def __init__(self) -> None:
        self._last_referer: Optional[str] = None

    def get_random(self) -> str:
        """获取随机 Referer"""
        referer = random.choice(self.BASE_REFERERS)
        while referer == self._last_referer and len(self.BASE_REFERERS) > 1:
            referer = random.choice(self.BASE_REFERERS)
        self._last_referer = referer
        return referer

    def get_for_pdf(self, obj_id: str) -> str:
        """获取 PDF 页面的 Referer"""
        return f"https://www.kanzhiqiu.com/newweb/zqpdf/pdf.html?fileid={obj_id}&docType=REPORT"


class HeaderRandomizer:
    """请求头随机化器"""

    # 可选的 Accept-Language 值
    ACCEPT_LANGUAGES = [
        "zh-CN,zh;q=0.9,en;q=0.8",
        "zh-CN,zh;q=0.9",
        "zh-CN,zh;q=0.8,en-US;q=0.7,en;q=0.6",
        "zh,en;q=0.9,zh-CN;q=0.8",
    ]

    # 可选的 Accept 值
    ACCEPT_VALUES = [
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    ]

    # 可选的 Cache-Control
    CACHE_CONTROLS = [
        "max-age=0",
        "no-cache",
        "",
    ]

    def __init__(self) -> None:
        pass

    def get_random_headers(self, base_headers: Optional[Dict] = None) -> Dict[str, str]:
        """获取随机化的请求头"""
        headers = base_headers.copy() if base_headers else {}

        # 随机化 Accept-Language
        headers["Accept-Language"] = random.choice(self.ACCEPT_LANGUAGES)

        # 随机化 Accept（如果没有指定）
        if "Accept" not in headers:
            headers["Accept"] = random.choice(self.ACCEPT_VALUES)

        # 随机化 Cache-Control
        cache_control = random.choice(self.CACHE_CONTROLS)
        if cache_control:
            headers["Cache-Control"] = cache_control

        # 随机添加 Sec-CH-UA 相关头（现代浏览器）
        if random.random() > 0.5:
            headers[
                "Sec-CH-UA"
            ] = '"Chromium";v="129", "Not=A?Brand";v="24", "Google Chrome";v="129"'
            headers["Sec-CH-UA-Mobile"] = "?0"
            headers["Sec-CH-UA-Platform"] = '"Windows"'

        # 随机添加 DNT
        if random.random() > 0.7:
            headers["DNT"] = "1"

        # 随机添加 Upgrade-Insecure-Requests
        if random.random() > 0.5:
            headers["Upgrade-Insecure-Requests"] = "1"

        return headers


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

    def get_delay(self, is_ai_request: bool = False) -> float:
        """
        计算下次请求的延迟时间

        Args:
            is_ai_request: 是否为 AI 请求（通常需要更长延迟）

        Returns:
            延迟秒数
        """
        # 基础延迟
        base = self.config.base_delay
        if is_ai_request:
            base *= 1.5  # AI 请求增加 50% 延迟

        # 指数退避（根据失败次数）
        if self.failure_count > 0:
            backoff = min(self.config.backoff_base**self.failure_count, self.config.backoff_max)
            base = max(base, backoff)
            self._logger.info(f"检测到 {self.failure_count} 次失败，使用退避延迟: {base:.1f}s")

        # 成功率调整（连续成功时稍微加快）
        if self.success_streak > 5:
            base *= 0.8  # 连续成功 5 次后，减少 20% 延迟

        # 速率限制检查
        if self.config.enable_rate_limit:
            minute_count = self.timing.get_minute_count()
            hour_count = self.timing.get_hour_count()

            if minute_count >= self.config.max_requests_per_minute:
                # 超过分钟限制，等待更长时间
                base = max(base, 10.0)
                self._logger.warning(f"速率限制: 每分钟 {minute_count} 次请求，增加延迟")

            if hour_count >= self.config.max_requests_per_hour:
                base = max(base, 30.0)
                self._logger.warning(f"速率限制: 每小时 {hour_count} 次请求，增加延迟")

        # 随机抖动
        jitter = random.uniform(-self.config.jitter_range, self.config.jitter_range)
        delay = max(base + jitter, self.config.min_delay)
        delay = min(delay, self.config.max_delay)

        return delay

    def sleep(self, is_ai_request: bool = False) -> None:
        """执行延迟"""
        delay = self.get_delay(is_ai_request)
        self._logger.debug(f"等待 {delay:.1f}s...")
        time.sleep(delay)


class AntiScrapeManager:
    """反爬管理器 - 统一入口"""

    def __init__(self, config: Optional[AntiScrapeConfig] = None) -> None:
        self.config = config or AntiScrapeConfig()
        self.ua_rotator = UserAgentRotator()
        self.referer_rotator = RefererRotator()
        self.header_randomizer = HeaderRandomizer()
        self.delayer = SmartDelayer(self.config)
        self._logger = logging.getLogger(__name__)

    def get_headers(
        self,
        base_headers: Optional[Dict] = None,
        obj_id: Optional[str] = None,
        is_pdf: bool = False,
    ) -> Dict[str, str]:
        """
        获取完整的请求头

        Args:
            base_headers: 基础请求头
            obj_id: 文档 ID（用于 PDF Referer）
            is_pdf: 是否为 PDF 请求

        Returns:
            请求头字典
        """
        headers = base_headers.copy() if base_headers else {}

        # User-Agent
        if self.config.enable_ua_rotation:
            headers["User-Agent"] = self.ua_rotator.get_random()

        # Referer
        if self.config.enable_referer_rotation:
            if is_pdf and obj_id:
                headers["Referer"] = self.referer_rotator.get_for_pdf(obj_id)
            else:
                headers["Referer"] = self.referer_rotator.get_random()

        # 其他头部随机化
        if self.config.enable_header_randomization:
            headers = self.header_randomizer.get_random_headers(headers)

        return headers

    def before_request(self, is_ai_request: bool = False) -> None:
        """请求前的处理（延迟等）"""
        self.delayer.sleep(is_ai_request)

    def after_success(self) -> None:
        """成功后的处理"""
        self.delayer.record_success()

    def after_failure(self) -> None:
        """失败后的处理"""
        self.delayer.record_failure()

    def get_current_stats(self) -> Dict[str, int]:
        """获取当前统计信息"""
        return {
            "minute_requests": self.delayer.timing.get_minute_count(),
            "hour_requests": self.delayer.timing.get_hour_count(),
            "failure_count": self.delayer.failure_count,
            "success_streak": self.delayer.success_streak,
        }


# 全局便捷函数
_default_manager: Optional[AntiScrapeManager] = None


def get_manager(config: Optional[AntiScrapeConfig] = None) -> AntiScrapeManager:
    """获取全局反爬管理器实例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = AntiScrapeManager(config)
    return _default_manager


def reset_manager() -> None:
    """重置全局管理器"""
    global _default_manager
    _default_manager = None
