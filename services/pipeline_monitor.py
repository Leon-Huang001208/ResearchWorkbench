"""管线状态追踪服务 — 聚合各层运行状态和活动日志。

PipelineMonitor 是一个轻量级内存单例，记录管线事件的时间线，
同时提供 DB 查询的聚合状态接口。
"""
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.observability import get_logger

logger = get_logger(__name__)

MAX_ACTIVITY_ITEMS = 200

# 中文阶段名称映射
STAGE_LABELS: Dict[str, str] = {
    "ingestion": "数据采集",
    "knowledge": "知识提取",
    "entity_resolution": "实体解析",
    "signal_generation": "信号生成",
    "reasoning": "推理分析",
    "agent_swarm": "Agent 辩论",
    "timing": "择时评估",
    "backtest": "回测验证",
    "learning": "学习反馈",
}

STAGE_ORDER = [
    "ingestion",
    "knowledge",
    "entity_resolution",
    "signal_generation",
    "reasoning",
    "agent_swarm",
    "timing",
    "backtest",
    "learning",
]


@dataclass
class ActivityItem:
    timestamp: float
    event_type: str
    stage: str
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)


class PipelineMonitor:
    """管线状态追踪单例。

    维护最近 N 条活动的内存日志，并通过 DB 查询提供各阶段的聚合状态。
    """

    _instance: Optional["PipelineMonitor"] = None
    _lock = threading.Lock()
    _activities: List[ActivityItem]
    _stage_updates: Dict[str, float]
    _closed_loop_last_run: Optional[float]
    _closed_loop_last_result: Dict[str, Any]

    def __new__(cls) -> "PipelineMonitor":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._activities = []
            cls._instance._stage_updates = {}
            cls._instance._closed_loop_last_run = None
            cls._instance._closed_loop_last_result = {}
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例（仅用于测试）。"""
        cls._instance = None

    # ── 事件记录 ──────────────────────────────────────────────

    def record_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """从 event_bus 事件更新内部状态。

        由 _publish_event() 或 event_bus subscriber 调用。
        """
        stage = self._event_to_stage(event_type)
        message = self._format_message(event_type, payload)

        with self._lock:
            self._activities.append(
                ActivityItem(
                    timestamp=time.time(),
                    event_type=event_type,
                    stage=stage,
                    message=message,
                    payload=payload,
                )
            )
            # 保持上限
            while len(self._activities) > MAX_ACTIVITY_ITEMS:
                self._activities.pop(0)

            self._stage_updates[stage] = time.time()

            # 追踪闭环运行
            if event_type == "pipeline.closed_loop.completed":
                self._closed_loop_last_run = time.time()
                self._closed_loop_last_result = payload
            elif event_type == "pipeline.closed_loop.started":
                self._closed_loop_last_result = {}

    # ── 查询接口 ──────────────────────────────────────────────

    def get_recent_activity(self, limit: int = 50) -> List[Dict[str, Any]]:
        """返回最近的活动日志。"""
        with self._lock:
            items = self._activities[-limit:]
        return [
            {
                "timestamp": item.timestamp,
                "datetime": datetime.fromtimestamp(item.timestamp, tz=UTC).isoformat(),
                "event_type": item.event_type,
                "stage": item.stage,
                "label": STAGE_LABELS.get(item.stage, item.stage),
                "message": item.message,
                "payload": item.payload,
            }
            for item in reversed(items)
        ]

    def get_stage_status(self) -> List[Dict[str, Any]]:
        """返回所有阶段的聚合状态（结合 DB 查询）。"""
        stages = []
        db_stats = self._query_db_stats()

        for stage_key in STAGE_ORDER:
            status = "idle"
            last_activity: Optional[str] = None

            with self._lock:
                last_ts = self._stage_updates.get(stage_key)
                if last_ts is not None:
                    last_activity = datetime.fromtimestamp(last_ts, tz=UTC).isoformat()
                    # 如果 5 分钟内有活动，标记为 running
                    if time.time() - last_ts < 300:
                        status = "running"

            stage_info = {
                "key": stage_key,
                "label": STAGE_LABELS.get(stage_key, stage_key),
                "status": status,
                "last_activity": last_activity,
                **db_stats.get(stage_key, {}),
            }
            stages.append(stage_info)

        return stages

    def get_closed_loop_status(self) -> Dict[str, Any]:
        """返回闭环运行状态。"""
        with self._lock:
            last_run_ts = self._closed_loop_last_run
            last_result = dict(self._closed_loop_last_result)

        return {
            "last_run_at": (
                datetime.fromtimestamp(last_run_ts, tz=UTC).isoformat() if last_run_ts else None
            ),
            "last_result": last_result,
        }

    def get_full_status(self) -> Dict[str, Any]:
        """返回完整管线状态（供 API 使用）。"""
        return {
            "stages": self.get_stage_status(),
            "closed_loop": self.get_closed_loop_status(),
            "recent_activity": self.get_recent_activity(limit=20),
        }

    # ── 内部方法 ──────────────────────────────────────────────

    @staticmethod
    def _event_to_stage(event_type: str) -> str:
        """将事件类型映射到管线阶段。"""
        mapping = {
            "pipeline.closed_loop.started": "signal_generation",
            "pipeline.signal.generated": "signal_generation",
            "pipeline.backtest.completed": "backtest",
            "pipeline.episode.recorded": "learning",
            "pipeline.pattern.learned": "learning",
            "pipeline.closed_loop.completed": "backtest",
            "pipeline.closed_loop.error": "signal_generation",
            "knowledge.entity_resolved": "entity_resolution",
            "knowledge.propagation_analyzed": "entity_resolution",
            "reasoning.completed": "reasoning",
            "agent.swarm.completed": "agent_swarm",
            "timing.evaluated": "timing",
            "document_parsed": "knowledge",
            "event_created": "knowledge",
            "queue_update": "knowledge",
        }
        return mapping.get(event_type, "knowledge")

    @staticmethod
    def _format_message(event_type: str, payload: Dict[str, Any]) -> str:
        """将事件格式化为可读消息。"""
        templates = {
            "pipeline.closed_loop.started": "闭循环管线开始运行",
            "pipeline.signal.generated": f"生成 {payload.get('count', 0)} 个信号",
            "pipeline.backtest.completed": f"回测完成: {payload.get('count', 0)} 个信号",
            "pipeline.episode.recorded": f"记录 {payload.get('count', 0)} 个市场片段",
            "pipeline.pattern.learned": f"从 {payload.get('episodes_analyzed', 0)} 个片段中学习模式",
            "pipeline.closed_loop.completed": f"闭循环完成 (耗时 {payload.get('duration_ms', 0)}ms)",
            "pipeline.closed_loop.error": f"闭循环出错: {payload.get('error', '未知')}",
            "knowledge.entity_resolved": f"实体解析: {payload.get('canonical_name', '未知')}",
            "knowledge.propagation_analyzed": f"传播分析: {payload.get('steps', 0)} 步",
            "reasoning.completed": f"推理完成: {payload.get('scenario_count', 0)} 个场景",
            "agent.swarm.completed": f"Agent 辩论完成: {payload.get('views', 0)} 个观点, {payload.get('conflicts', 0)} 个冲突",
            "timing.evaluated": f"择时评估: action={payload.get('action', '?')}, readiness={payload.get('readiness_score', '?')}",
            "document_parsed": f"文档解析: {payload.get('doc_id', '?')}",
            "event_created": f"事件创建: {payload.get('event_id', '?')}",
            "queue_update": f"队列更新: {payload.get('pending', '?')} 待处理",
        }
        return templates.get(event_type, event_type)

    @staticmethod
    def _query_db_stats() -> Dict[str, Dict[str, Any]]:
        """从数据库查询各阶段的累计统计。"""
        stats: Dict[str, Dict[str, Any]] = {}
        try:
            from data_layer.repositories.base import SessionLocal
            from data_layer.repositories.models import (
                AlphaSignalDB,
                CanonicalEvent,
                DocumentV1DB,
                SignalOutcomeDB,
            )

            db = SessionLocal()
            try:
                # 使用北京时间 (Asia/Shanghai)，与爬虫/DB 时区一致
                tz_cn = timezone(timedelta(hours=8))
                today = datetime.now(tz_cn).replace(hour=0, minute=0, second=0, microsecond=0)

                # 数据采集
                doc_count = db.query(DocumentV1DB).count()
                doc_today = db.query(DocumentV1DB).filter(DocumentV1DB.created_at >= today).count()
                stats["ingestion"] = {
                    "docs_total": doc_count,
                    "docs_today": doc_today,
                }

                # 知识提取
                event_count = db.query(CanonicalEvent).count()
                event_today = (
                    db.query(CanonicalEvent).filter(CanonicalEvent.created_at >= today).count()
                )
                stats["knowledge"] = {
                    "events_total": event_count,
                    "events_today": event_today,
                }

                # 信号生成
                signal_count = db.query(AlphaSignalDB).count()
                signal_today = (
                    db.query(AlphaSignalDB).filter(AlphaSignalDB.created_at >= today).count()
                )
                stats["signal_generation"] = {
                    "signals_total": signal_count,
                    "signals_today": signal_today,
                }

                # 回测/学习
                outcome_count = db.query(SignalOutcomeDB).count()
                outcome_today = (
                    db.query(SignalOutcomeDB).filter(SignalOutcomeDB.created_at >= today).count()
                )
                if outcome_count > 0:
                    win_count = (
                        db.query(SignalOutcomeDB)
                        .filter(SignalOutcomeDB.outcome_excess_return > 0)
                        .count()
                    )
                    win_rate = win_count / outcome_count if outcome_count > 0 else 0.0
                else:
                    win_rate = 0.0
                stats["backtest"] = {
                    "outcomes_total": outcome_count,
                    "outcomes_today": outcome_today,
                    "win_rate": round(win_rate, 4),
                }
                stats["learning"] = {
                    "outcomes_total": outcome_count,
                    "win_rate": round(win_rate, 4),
                }

            finally:
                db.close()
        except Exception as exc:
            logger.warning("Failed to query DB stats for pipeline monitor: %s", exc)

        return stats


# 全局单例
pipeline_monitor = PipelineMonitor()
