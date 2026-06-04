"""
爬取进度追踪器 - 负责保存和恢复爬取进度
"""
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReportProgress:
    """单个研报的处理进度"""

    report_id: str
    title: str
    status: str  # pending|processing|completed|failed
    processed_at: Optional[str] = None
    retry_count: int = 0


@dataclass
class CrawlProgress:
    """整体爬取进度"""

    session_id: str
    start_time: str
    last_update: str

    # 搜索参数
    start_date: str = ""
    end_date: str = ""
    search_keywords: str = ""
    brokers: str = ""

    # 进度统计
    total_reports: int = 0
    processed_reports: int = 0
    failed_reports: int = 0

    # 报告进度列表
    reports: List[ReportProgress] = field(default_factory=list)

    # 当前处理位置
    current_report_index: int = 0

    # 账号信息
    last_used_account: str = ""

    # 功能开关状态
    enabled_features: Dict[str, bool] = field(default_factory=dict)


class ProgressStateManager:
    """进度状态管理器"""

    def __init__(self, state_file: str, auto_save: bool = True, save_interval: int = 10):
        self.state_file = Path(state_file)
        self.auto_save = auto_save
        self.save_interval = save_interval
        self.save_counter = 0
        self.current_progress: Optional[CrawlProgress] = None

    def generate_session_id(self) -> str:
        """生成会话ID"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def create_new_progress(
        self,
        start_date: str,
        end_date: str,
        search_keywords: str = "",
        brokers: str = "",
        enabled_features: Optional[Dict[str, bool]] = None,
    ) -> CrawlProgress:
        """创建新的进度记录"""
        now = datetime.now().isoformat()
        self.current_progress = CrawlProgress(
            session_id=self.generate_session_id(),
            start_time=now,
            last_update=now,
            start_date=start_date,
            end_date=end_date,
            search_keywords=search_keywords,
            brokers=brokers,
            enabled_features=enabled_features or {},
        )
        if self.auto_save:
            self.save()
        return self.current_progress

    def has_saved_progress(self) -> bool:
        """检查是否有保存的进度"""
        return self.state_file.exists()

    def load(self) -> Optional[CrawlProgress]:
        """加载保存的进度"""
        if not self.has_saved_progress():
            return None

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 重建对象
            reports = [ReportProgress(**r) for r in data.get("reports", [])]
            data["reports"] = reports
            self.current_progress = CrawlProgress(**data)

            logger.info(
                f"已加载进度: 会话 {self.current_progress.session_id}, "
                f"已处理 {self.current_progress.processed_reports}/{self.current_progress.total_reports}"
            )
            return self.current_progress

        except Exception as e:
            logger.error(f"加载进度失败: {e}")
            return None

    def save(self) -> None:
        """保存当前进度"""
        if not self.current_progress:
            return

        self.current_progress.last_update = datetime.now().isoformat()

        try:
            # 确保目录存在
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # 转换为可序列化的字典
            data = asdict(self.current_progress)

            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"进度已保存到 {self.state_file}")

        except Exception as e:
            logger.error(f"保存进度失败: {e}")

    def checkpoint(self, force: bool = False) -> None:
        """检查点保存（根据间隔）"""
        if not self.auto_save:
            return

        self.save_counter += 1
        if force or self.save_counter >= self.save_interval:
            self.save()
            self.save_counter = 0

    def initialize_reports(
        self, report_ids: List[str], report_titles: Optional[List[str]] = None
    ) -> None:
        """初始化报告列表"""
        if not self.current_progress:
            return

        titles = report_titles or [""] * len(report_ids)

        self.current_progress.reports = []
        for report_id, title in zip(report_ids, titles):
            self.current_progress.reports.append(
                ReportProgress(report_id=report_id, title=title, status="pending")
            )

        self.current_progress.total_reports = len(report_ids)
        self.current_progress.current_report_index = 0

        if self.auto_save:
            self.save()

    def get_next_pending_report(self) -> Optional[ReportProgress]:
        """获取下一个待处理的报告"""
        if not self.current_progress:
            return None

        # 从当前位置开始查找
        for i in range(
            self.current_progress.current_report_index, len(self.current_progress.reports)
        ):
            report = self.current_progress.reports[i]
            if report.status == "pending":
                self.current_progress.current_report_index = i
                report.status = "processing"
                self.checkpoint()
                return report

        # 没有更多待处理
        return None

    def mark_report_completed(self, report_id: str) -> None:
        """标记报告已完成"""
        self._update_report_status(report_id, "completed")
        if self.current_progress:
            self.current_progress.processed_reports += 1
        self.checkpoint()

    def mark_report_failed(self, report_id: str, max_retries: int = 3) -> None:
        """标记报告失败"""
        report = self._find_report(report_id)
        if report:
            report.retry_count += 1
            if report.retry_count >= max_retries:
                report.status = "failed"
                if self.current_progress:
                    self.current_progress.failed_reports += 1
            else:
                report.status = "pending"  # 重试
        self.checkpoint()

    def _find_report(self, report_id: str) -> Optional[ReportProgress]:
        """查找报告"""
        if not self.current_progress:
            return None
        for report in self.current_progress.reports:
            if report.report_id == report_id:
                return report
        return None

    def _update_report_status(self, report_id: str, status: str) -> None:
        """更新报告状态"""
        report = self._find_report(report_id)
        if report:
            report.status = status
            report.processed_at = datetime.now().isoformat()

    def update_last_account(self, account_name: str) -> None:
        """更新最后使用的账号"""
        if self.current_progress:
            self.current_progress.last_used_account = account_name
            self.checkpoint()

    def is_complete(self) -> bool:
        """检查是否全部完成"""
        if not self.current_progress:
            return True
        total = self.current_progress.total_reports
        processed = self.current_progress.processed_reports
        failed = self.current_progress.failed_reports
        return (processed + failed) >= total

    def clear_progress(self) -> None:
        """清除进度"""
        if self.state_file.exists():
            self.state_file.unlink()
        self.current_progress = None
        logger.info("进度已清除")

    def get_summary(self) -> Dict[str, Any]:
        """获取进度摘要"""
        if not self.current_progress:
            return {}
        return {
            "session_id": self.current_progress.session_id,
            "start_date": self.current_progress.start_date,
            "end_date": self.current_progress.end_date,
            "total": self.current_progress.total_reports,
            "processed": self.current_progress.processed_reports,
            "failed": self.current_progress.failed_reports,
            "pending": self.current_progress.total_reports
            - self.current_progress.processed_reports
            - self.current_progress.failed_reports,
            "last_account": self.current_progress.last_used_account,
        }
