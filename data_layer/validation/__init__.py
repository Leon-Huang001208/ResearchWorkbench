"""
数据验证模块

提供双源校验、复权对齐、时间窗口策略等功能。
"""
from data_layer.validation.adjustment_normalizer import (
    AdjustmentInfo,
    AdjustmentNormalizer,
    AdjustmentType,
    NormalizationResult,
)
from data_layer.validation.alerts import (
    Alert,
    AlertChannel,
    AlertLevel,
    AlertManager,
    ConsoleAlertChannel,
    LogAlertChannel,
    get_alert_manager,
)
from data_layer.validation.audit_log import AuditEntry, AuditLogger, get_audit_logger
from data_layer.validation.dual_source_validator import (
    Discrepancy,
    DualSourceValidator,
    ValidationResult,
    ValidationStatus,
)
from data_layer.validation.time_window_strategy import (
    FetchPlan,
    TimeWindowConfig,
    TimeWindowDecision,
    TimeWindowMode,
    TimeWindowStrategy,
)

__all__ = [
    # Adjustment Normalizer
    "AdjustmentNormalizer",
    "AdjustmentType",
    "AdjustmentInfo",
    "NormalizationResult",
    # Alerts
    "AlertManager",
    "Alert",
    "AlertLevel",
    "AlertChannel",
    "LogAlertChannel",
    "ConsoleAlertChannel",
    "get_alert_manager",
    # Audit Log
    "AuditLogger",
    "AuditEntry",
    "get_audit_logger",
    # Dual Source Validator
    "DualSourceValidator",
    "ValidationResult",
    "ValidationStatus",
    "Discrepancy",
    # Time Window Strategy
    "TimeWindowStrategy",
    "TimeWindowConfig",
    "TimeWindowDecision",
    "TimeWindowMode",
    "FetchPlan",
]
