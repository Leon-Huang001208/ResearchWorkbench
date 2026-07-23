"""
告警系统

提供多通道告警功能，防止静默失败。
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

from core.observability import get_logger
from data_layer.validation.dual_source_validator import ValidationResult, ValidationStatus

logger = get_logger("alerts")


class AlertLevel(Enum):
    """告警级别"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """告警信息"""

    level: AlertLevel
    message: str
    source: str
    timestamp: datetime = None
    metadata: dict = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class AlertChannel:
    """告警通道基类"""

    def send(self, alert: Alert) -> None:
        """发送告警"""
        raise NotImplementedError()


class LogAlertChannel(AlertChannel):
    """日志告警通道"""

    def __init__(self, logger_name: str = "alerts"):
        self.logger = get_logger(logger_name)

    def send(self, alert: Alert) -> None:
        """通过日志发送告警"""
        msg = f"[{alert.level.value.upper()}] {alert.message}"

        if alert.level == AlertLevel.CRITICAL:
            self.logger.critical(msg)
        elif alert.level == AlertLevel.WARNING:
            self.logger.warning(msg)
        else:
            self.logger.info(msg)


class ConsoleAlertChannel(AlertChannel):
    """控制台告警通道"""

    def send(self, alert: Alert) -> None:
        """输出到控制台"""
        import sys

        color_code = ""
        reset_code = ""

        if sys.stdout.isatty():
            if alert.level == AlertLevel.CRITICAL:
                color_code = "\033[91m"  # 红色
            elif alert.level == AlertLevel.WARNING:
                color_code = "\033[93m"  # 黄色
            reset_code = "\033[0m"

        msg = (
            f"{color_code}[{alert.level.value.upper()}] {alert.timestamp.isoformat()} - {alert.message}"
            f"{reset_code}"
        )
        print(msg)


class AlertManager:
    """
    告警管理器

    支持多通道告警，防止告警刷屏。
    """

    def __init__(self):
        self.channels: List[AlertChannel] = []
        self.suppression_window_seconds: int = 60  # 1分钟内相同告警不重复
        self._recent_alerts: dict = {}  # 用于去重
        self.logger = get_logger("alert_manager")

    def add_channel(self, channel: AlertChannel) -> None:
        """添加告警通道"""
        self.channels.append(channel)

    def add_log_channel(self) -> None:
        """添加日志通道"""
        self.add_channel(LogAlertChannel())

    def add_console_channel(self) -> None:
        """添加控制台通道"""
        self.add_channel(ConsoleAlertChannel())

    def send(self, alert: Alert) -> None:
        """
        发送告警

        会自动去重，防止刷屏。
        """
        # 检查是否需要抑制
        alert_key = self._get_alert_key(alert)
        now = datetime.now().timestamp()

        if alert_key in self._recent_alerts:
            last_time = self._recent_alerts[alert_key]
            if now - last_time < self.suppression_window_seconds:
                self.logger.debug(f"Suppressing duplicate alert: {alert_key}")
                return

        # 记录发送时间
        self._recent_alerts[alert_key] = now

        # 清理过期记录
        self._cleanup_old_records(now)

        # 发送到所有通道
        for channel in self.channels:
            try:
                channel.send(alert)
            except Exception as e:
                self.logger.error(f"Failed to send alert via {type(channel).__name__}: {e}")

    def send_validation_alert(self, result: ValidationResult) -> None:
        """
        根据校验结果发送告警
        """
        if result.status == ValidationStatus.PASSED:
            return  # 不需要告警

        if result.status == ValidationStatus.INSUFFICIENT_DATA:
            alert = Alert(
                level=AlertLevel.WARNING,
                message=f"Insufficient data for dual validation: {result.symbol}",
                source="validation",
                metadata={
                    "symbol": result.symbol,
                    "status": result.status.value,
                },
            )
            self.send(alert)
            return

        # WARNING 或 FAILED
        level = (
            AlertLevel.CRITICAL if result.status == ValidationStatus.FAILED else AlertLevel.WARNING
        )

        alert = Alert(
            level=level,
            message=(
                f"Dual validation {result.status.value} for {result.symbol}: "
                f"max_diff={result.max_relative_diff_pct:.2f}%, "
                f"discrepancies={len(result.discrepancies)}"
            ),
            source="validation",
            metadata={
                "symbol": result.symbol,
                "status": result.status.value,
                "max_diff_pct": result.max_relative_diff_pct,
                "avg_diff_pct": result.avg_relative_diff_pct,
                "discrepancy_count": len(result.discrepancies),
                "recommended_source": result.recommended_source,
            },
        )
        self.send(alert)

    def send_data_source_error(self, source_name: str, error: Exception) -> None:
        """
        发送数据源错误告警
        """
        alert = Alert(
            level=AlertLevel.CRITICAL,
            message=f"Data source error: {source_name} - {str(error)}",
            source="data_source",
            metadata={"source": source_name, "error": str(error)},
        )
        self.send(alert)

    def _get_alert_key(self, alert: Alert) -> str:
        """生成告警去重键"""
        return f"{alert.source}:{alert.level.value}:{alert.message[:100]}"

    def _cleanup_old_records(self, now: float) -> None:
        """清理过期的告警记录"""
        cutoff = now - self.suppression_window_seconds
        old_keys = [k for k, v in self._recent_alerts.items() if v < cutoff]
        for k in old_keys:
            del self._recent_alerts[k]


# 全局告警管理器实例
_default_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """
    获取全局告警管理器实例

    Returns:
        告警管理器
    """
    global _default_alert_manager

    if _default_alert_manager is None:
        _default_alert_manager = AlertManager()
        _default_alert_manager.add_log_channel()
        _default_alert_manager.add_console_channel()

    return _default_alert_manager
