"""
审计日志系统

记录所有校验结果，用于后续分析和回溯。
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import json

from core.observability import get_logger
from data_layer.validation.dual_source_validator import ValidationResult

logger = get_logger("audit_log")


@dataclass
class AuditEntry:
    """审计记录"""

    symbol: str
    timestamp: datetime
    operation: str  # "fetch", "validate", "merge"
    sources: List[str]
    result_summary: str
    validation_result: Optional[Dict] = None
    data_count: Optional[int] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation,
            "sources": self.sources,
            "result_summary": self.result_summary,
            "validation_result": self.validation_result,
            "data_count": self.data_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AuditEntry":
        """从字典创建"""
        return cls(
            symbol=d["symbol"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            operation=d["operation"],
            sources=d["sources"],
            result_summary=d["result_summary"],
            validation_result=d.get("validation_result"),
            data_count=d.get("data_count"),
            metadata=d.get("metadata", {}),
        )


class AuditLogger:
    """
    审计日志记录器

    将校验和数据操作记录到持久化存储。
    """

    def __init__(self, log_dir: Optional[Path] = None):
        """
        初始化审计日志记录器

        Args:
            log_dir: 日志目录（默认 .ai/audit_logs）
        """
        if log_dir is None:
            log_dir = Path.cwd() / ".ai" / "audit_logs"

        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger("audit_logger")

    def log_validation(self, result: ValidationResult) -> AuditEntry:
        """
        记录校验结果

        Args:
            result: 校验结果

        Returns:
            审计记录
        """
        entry = AuditEntry(
            symbol=result.symbol,
            timestamp=result.validation_time,
            operation="validate",
            sources=[result.source1_name, result.source2_name],
            result_summary=result.summary,
            validation_result={
                "status": result.status.value,
                "data_points_compared": result.data_points_compared,
                "max_relative_diff_pct": result.max_relative_diff_pct,
                "avg_relative_diff_pct": result.avg_relative_diff_pct,
                "discrepancy_count": len(result.discrepancies),
                "recommended_source": result.recommended_source,
            },
        )

        self._append_entry(entry)
        return entry

    def log_fetch(
        self,
        symbol: str,
        source: str,
        data_count: int,
        success: bool,
        error: Optional[str] = None,
    ) -> AuditEntry:
        """
        记录数据拉取操作

        Args:
            symbol: 股票代码
            source: 数据源
            data_count: 数据点数
            success: 是否成功
            error: 错误信息（如有）

        Returns:
            审计记录
        """
        summary = f"Fetched {data_count} records" if success else f"Fetch failed: {error}"

        entry = AuditEntry(
            symbol=symbol,
            timestamp=datetime.now(),
            operation="fetch",
            sources=[source],
            result_summary=summary,
            data_count=data_count,
            metadata={"success": success, "error": error},
        )

        self._append_entry(entry)
        return entry

    def log_merge(
        self,
        symbol: str,
        sources: List[str],
        final_data_count: int,
        selected_source: str,
        validation_passed: bool,
    ) -> AuditEntry:
        """
        记录数据合并操作

        Args:
            symbol: 股票代码
            sources: 所有数据源
            final_data_count: 最终数据点数
            selected_source: 选择的数据源
            validation_passed: 校验是否通过

        Returns:
            审计记录
        """
        entry = AuditEntry(
            symbol=symbol,
            timestamp=datetime.now(),
            operation="merge",
            sources=sources,
            result_summary=f"Merged data from {len(sources)} sources, selected {selected_source}",
            data_count=final_data_count,
            metadata={
                "selected_source": selected_source,
                "validation_passed": validation_passed,
            },
        )

        self._append_entry(entry)
        return entry

    def query_recent(
        self,
        symbol: Optional[str] = None,
        operation: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """
        查询最近的审计记录

        Args:
            symbol: 股票代码过滤
            operation: 操作类型过滤
            limit: 返回数量限制

        Returns:
            审计记录列表
        """
        entries: List[AuditEntry] = []

        # 遍历日志文件
        for log_file in sorted(self.log_dir.glob("*.jsonl"), reverse=True):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            d = json.loads(line.strip())
                            entry = AuditEntry.from_dict(d)

                            # 应用过滤
                            if symbol and entry.symbol != symbol:
                                continue
                            if operation and entry.operation != operation:
                                continue

                            entries.append(entry)

                            if len(entries) >= limit:
                                return entries

                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                self.logger.warning(f"Error reading audit log {log_file}: {e}")

        return entries

    def _append_entry(self, entry: AuditEntry) -> None:
        """追加记录到日志文件"""
        # 按天分割日志文件
        date_str = entry.timestamp.strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit_{date_str}.jsonl"

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False))
                f.write("\n")
        except Exception as e:
            self.logger.error(f"Failed to write audit log: {e}")


# 全局审计日志记录器实例
_default_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """
    获取全局审计日志记录器实例

    Returns:
        审计日志记录器
    """
    global _default_audit_logger

    if _default_audit_logger is None:
        _default_audit_logger = AuditLogger()

    return _default_audit_logger

