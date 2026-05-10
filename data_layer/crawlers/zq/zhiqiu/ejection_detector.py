"""
账号顶出检测器 - 检测账号是否被顶出
"""
import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DetectionConfig:
    """检测配置"""

    check_responses: bool = True
    error_keywords: List[str] = field(
        default_factory=lambda: [
            "登录已失效",
            "请重新登录",
            "token过期",
            "未授权",
            "401 Unauthorized",
            "login expired",
            "please login again",
        ]
    )
    max_consecutive_errors: int = 3
    check_status_code: bool = True
    unauthorized_codes: List[int] = field(default_factory=lambda: [401, 403])


class AccountEjectionDetector:
    """账号顶出检测器"""

    def __init__(self, config: Optional[DetectionConfig] = None):
        self.config = config or DetectionConfig()
        self.consecutive_errors = 0
        self._custom_checkers: List[Callable] = []

    def add_checker(self, checker: Callable):
        """添加自定义检测器"""
        self._custom_checkers.append(checker)

    def reset(self):
        """重置错误计数"""
        self.consecutive_errors = 0

    def check_response(
        self,
        response_text: str = "",
        status_code: Optional[int] = None,
        exception: Optional[Exception] = None,
    ) -> bool:
        """
        检查响应是否表明账号被顶出

        Returns:
            True 表示账号被顶出
        """
        # 检查异常
        if exception:
            if self._check_exception(exception):
                self.consecutive_errors += 1
                return self._check_threshold()

        # 检查状态码
        if self.config.check_status_code and status_code:
            if status_code in self.config.unauthorized_codes:
                logger.warning(f"检测到未授权状态码: {status_code}")
                self.consecutive_errors += 1
                return self._check_threshold()

        # 检查响应文本
        if self.config.check_responses and response_text:
            if self._check_response_text(response_text):
                self.consecutive_errors += 1
                return self._check_threshold()

        # 运行自定义检查器
        for checker in self._custom_checkers:
            try:
                if checker(response_text, status_code, exception):
                    self.consecutive_errors += 1
                    return self._check_threshold()
            except Exception as e:
                logger.error(f"自定义检查器出错: {e}")

        # 没有检测到问题，重置计数
        self.consecutive_errors = 0
        return False

    def _check_response_text(self, text: str) -> bool:
        """检查响应文本中的关键词"""
        text_lower = text.lower()
        for keyword in self.config.error_keywords:
            if keyword.lower() in text_lower:
                logger.warning(f"检测到账号失效关键词: {keyword}")
                return True
        return False

    def _check_exception(self, exception: Exception) -> bool:
        """检查异常是否表明账号问题"""
        exc_str = str(exception).lower()
        for keyword in self.config.error_keywords:
            if keyword.lower() in exc_str:
                logger.warning(f"异常中检测到账号失效关键词: {keyword}")
                return True
        return False

    def _check_threshold(self) -> bool:
        """检查是否达到阈值"""
        if self.consecutive_errors >= self.config.max_consecutive_errors:
            logger.error(
                f"连续错误达到阈值 ({self.consecutive_errors}/{self.config.max_consecutive_errors}), "
                f"判定账号已被顶出"
            )
            return True
        logger.warning(f"连续错误计数: {self.consecutive_errors}/{self.config.max_consecutive_errors}")
        return False

    def should_try_recovery(self) -> bool:
        """是否应该尝试恢复"""
        return (
            self.consecutive_errors > 0
            and self.consecutive_errors < self.config.max_consecutive_errors
        )
