"""回放服务 — 历史事件批量回放 & 信号校准。

核心逻辑：
1. 从基准数据集（benchmarks/datasets/）或数据库加载历史事件
2. 逐一通过 Golden Path（EventExtractor → 信号构建 → 择时评估）
3. 模拟评估：基于事件类型和信号特征生成模拟 outcome
4. 保存结果，聚合分析，校准分析
"""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from core.contracts.events import CanonicalEvent
from core.contracts.replay import ReplayAggregate, ReplayJob, ReplayResult
from core.observability import get_logger
from data_layer.repositories.replay_repository import ReplayRepositoryImpl
from services.event_extractor import EventExtractor

logger = get_logger(__name__)

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 模拟 outcome 参数：按事件类型给出不同的收益率分布
_OUTCOME_PROFILES: dict[str, dict] = {
    "earnings": {
        "mean_return": 0.02,
        "mean_excess": 0.015,
        "mean_drawdown": -0.04,
        "mean_decay": 0.12,
    },
    "policy": {
        "mean_return": 0.03,
        "mean_excess": 0.025,
        "mean_drawdown": -0.03,
        "mean_decay": 0.10,
    },
    "product": {
        "mean_return": 0.04,
        "mean_excess": 0.035,
        "mean_drawdown": -0.05,
        "mean_decay": 0.15,
    },
    "merger_acquisition": {
        "mean_return": 0.05,
        "mean_excess": 0.04,
        "mean_drawdown": -0.06,
        "mean_decay": 0.08,
    },
    "rating_change": {
        "mean_return": 0.01,
        "mean_excess": 0.008,
        "mean_drawdown": -0.02,
        "mean_decay": 0.20,
    },
    "supply_chain": {
        "mean_return": 0.02,
        "mean_excess": 0.015,
        "mean_drawdown": -0.05,
        "mean_decay": 0.18,
    },
    "macro": {
        "mean_return": 0.015,
        "mean_excess": 0.01,
        "mean_drawdown": -0.03,
        "mean_decay": 0.10,
    },
    "other": {
        "mean_return": 0.01,
        "mean_excess": 0.005,
        "mean_drawdown": -0.04,
        "mean_decay": 0.15,
    },
}


class ReplayService:
    """历史事件回放 & 信号校准服务"""

    def __init__(
        self,
        repository: Optional[ReplayRepositoryImpl] = None,
        event_extractor: Optional[EventExtractor] = None,
        pipeline: Optional[Any] = None,
        benchmark_path: Optional[str] = None,
    ):
        self.repository = repository
        self.event_extractor = event_extractor or EventExtractor(model_gateway=None)
        self.pipeline = pipeline
        self.benchmark_path = benchmark_path or str(
            _PROJECT_ROOT / "benchmarks" / "datasets" / "event_extraction_v1.jsonl"
        )
        # 内存 fallback 存储
        self._jobs: dict[str, ReplayJob] = {}
        self._results: dict[str, list[ReplayResult]] = defaultdict(list)

    # ── Job 管理 ──────────────────────────────────────────

    def create_job(
        self,
        name: str = "Default Replay",
        description: Optional[str] = None,
        event_filter: Optional[dict] = None,
        max_events: int = 100,
    ) -> ReplayJob:
        """创建回放任务"""
        job = ReplayJob(
            job_id=str(uuid.uuid4()),
            name=name,
            description=description,
            event_filter=event_filter,
            max_events=max_events,
            status="pending",
            created_at=datetime.now(timezone.utc),
        )

        if self.repository:
            job = self.repository.create_job(job)
        else:
            self._jobs[job.job_id] = job

        logger.info("replay job created", job_id=job.job_id, name=job.name)
        return job

    def get_job(self, job_id: str) -> Optional[ReplayJob]:
        """获取回放任务"""
        if self.repository:
            return self.repository.get_job(job_id)
        return self._jobs.get(job_id)

    # ── 回放执行 ──────────────────────────────────────────

    async def run_job(self, job_id: str) -> ReplayAggregate:
        """执行回放任务。

        流程：
        1. 加载历史事件
        2. 应用过滤条件
        3. 逐一通过 Golden Path
        4. 模拟评估
        5. 保存结果
        6. 聚合 & 校准
        """
        job = self.get_job(job_id)
        if job is None:
            raise ValueError(f"Replay job not found: {job_id}")

        # 更新状态
        self._update_job_status(job_id, "running")

        # 加载历史事件
        events = self._load_events(job)
        logger.info(
            "replay job starting",
            job_id=job_id,
            total_events=len(events),
        )

        # 逐一回放
        results: list[ReplayResult] = []
        for i, event_info in enumerate(events):
            try:
                result = await self._replay_single_event(job_id, event_info)
                results.append(result)
            except Exception as exc:
                logger.error(
                    "replay event failed",
                    job_id=job_id,
                    event_id=event_info.get("event_id", f"event_{i}"),
                    error=str(exc),
                )
                results.append(
                    ReplayResult(
                        job_id=job_id,
                        event_id=event_info.get("event_id", f"event_{i}"),
                        event_type=event_info.get("event_type", "unknown"),
                        source_type=event_info.get("source_type", "unknown"),
                        error=str(exc),
                    )
                )

        # 保存结果
        for result in results:
            self._save_result(result)

        # 更新状态
        self._update_job_status(job_id, "completed")

        # 聚合 & 校准
        aggregate = self._compute_aggregate(job_id, results)

        logger.info(
            "replay job completed",
            job_id=job_id,
            total=len(results),
            successful=aggregate.successful,
            hit_rate=aggregate.hit_rate,
        )

        return aggregate

    async def _replay_single_event(
        self,
        job_id: str,
        event_info: dict,
    ) -> ReplayResult:
        """回放单个事件。

        如果有 pipeline，使用 pipeline.run_event_signal()；
        否则直接用 EventExtractor 提取参数，构建信号，模拟评估。
        """
        event_id = event_info["event_id"]
        event_type = event_info.get("event_type", "unknown")
        source_type = event_info.get("source_type", "unknown")
        input_text = event_info.get("input_text", "")

        signal_score = None
        signal_confidence = None
        timing_action = None
        signal_id = None
        outcome_id = None
        outcome_return = None
        outcome_excess_return = None
        max_drawdown = None
        decay = None

        # 尝试通过 pipeline 执行
        if self.pipeline is not None:
            try:
                event = CanonicalEvent(
                    event_id=event_id,
                    event_type=event_type,
                    source_type="replay",
                    source_name=f"replay_{job_id}",
                    title=input_text[:200] or event_type,
                    summary=input_text,
                    impact_direction="unknown",
                    confidence=0.5,
                    source_doc_id=f"replay_{job_id}",
                )
                signal = await self.pipeline.run_event_signal(event)
                signal_id = signal.signal_id
                signal_score = signal.score
                signal_confidence = signal.confidence
                if signal.timing_decision:
                    timing_action = signal.timing_decision.action
            except Exception as exc:
                logger.warning(
                    "pipeline execution failed in replay, falling back to extractor",
                    event_id=event_id,
                    error=str(exc),
                )

        # Fallback：如果 pipeline 未执行成功，直接用关键词提取器
        if signal_score is None:
            try:
                extracted = await self.event_extractor.extract(input_text)
                signal_score = extracted.score
                signal_confidence = extracted.confidence
                event_type = (
                    extracted.event_type if extracted.event_type != "unknown" else event_type
                )
            except Exception as exc:
                logger.warning(
                    "event extraction failed in replay",
                    event_id=event_id,
                    error=str(exc),
                )
                signal_score = 0.5
                signal_confidence = 0.3

        # 模拟 outcome
        outcome = self._simulate_outcome(
            event_type,
            float(signal_score if signal_score is not None else 0.5),
            float(signal_confidence if signal_confidence is not None else 0.3),
            timing_action,
        )
        outcome_id = str(uuid.uuid4())
        outcome_return = outcome["outcome_return"]
        outcome_excess_return = outcome["outcome_excess_return"]
        max_drawdown = outcome["max_drawdown"]
        decay = outcome["decay"]

        if timing_action is None:
            timing_action = outcome["timing_action"]

        return ReplayResult(
            job_id=job_id,
            event_id=event_id,
            signal_id=signal_id,
            outcome_id=outcome_id,
            event_type=event_type,
            source_type=source_type,
            signal_score=signal_score,
            signal_confidence=signal_confidence,
            timing_action=timing_action,
            outcome_return=outcome_return,
            outcome_excess_return=outcome_excess_return,
            max_drawdown=max_drawdown,
            decay=decay,
        )

    def _simulate_outcome(
        self,
        event_type: str,
        score: float,
        confidence: float,
        timing_action: Optional[str] = None,
    ) -> dict:
        """基于事件类型和信号特征模拟 outcome。

        使用确定性的伪随机：基于 event_type 和 score 计算，
        确保同参数得到同结果（可复现）。
        """
        profile = _OUTCOME_PROFILES.get(event_type, _OUTCOME_PROFILES["other"])

        # score 和 confidence 调节收益
        score_factor = score  # 0.0 ~ 1.0
        confidence_factor = confidence  # 0.0 ~ 1.0
        combined_factor = (score_factor + confidence_factor) / 2.0

        # 高分高置信 → 更高收益、更小回撤
        outcome_return = profile["mean_return"] * (0.5 + combined_factor)
        outcome_excess_return = profile["mean_excess"] * (0.5 + combined_factor)
        max_drawdown = profile["mean_drawdown"] * (1.5 - combined_factor)
        decay = profile["mean_decay"] * (1.2 - 0.4 * combined_factor)

        # 判定 timing_action
        if timing_action is None:
            if combined_factor >= 0.6:
                timing_action = "enter"
            elif combined_factor >= 0.35:
                timing_action = "wait"
            else:
                timing_action = "skip"

        # skip 动作 → 大幅降低收益
        if timing_action == "skip":
            outcome_return *= 0.1
            outcome_excess_return *= 0.1

        return {
            "outcome_return": round(outcome_return, 6),
            "outcome_excess_return": round(outcome_excess_return, 6),
            "max_drawdown": round(max_drawdown, 6),
            "decay": round(decay, 6),
            "timing_action": timing_action,
        }

    # ── 事件加载 ──────────────────────────────────────────

    def _load_events(self, job: ReplayJob) -> list[dict]:
        """从基准数据集加载历史事件。"""
        events: list[dict] = []

        try:
            with open(self.benchmark_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        case = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # 转换为统一的 event_info 格式
                    gold = case.get("gold", {})
                    event_info = {
                        "event_id": case.get("case_id", str(uuid.uuid4())),
                        "event_type": gold.get("event_type", "unknown"),
                        "source_type": case.get("source_type", "unknown"),
                        "input_text": case.get("input_text", ""),
                        "gold": gold,
                    }

                    # 应用过滤条件
                    if not self._matches_filter(event_info, job.event_filter):
                        continue

                    events.append(event_info)

                    if len(events) >= job.max_events:
                        break
        except FileNotFoundError:
            logger.warning(
                "benchmark dataset not found, using empty event list",
                path=self.benchmark_path,
            )
        except Exception as exc:
            logger.error(
                "failed to load benchmark dataset",
                path=self.benchmark_path,
                error=str(exc),
            )

        logger.info("loaded events for replay", total=len(events), job_id=job.job_id)
        return events

    def _matches_filter(self, event_info: dict, event_filter: Optional[dict]) -> bool:
        """检查事件是否匹配过滤条件。"""
        if not event_filter:
            return True

        # event_type 过滤
        filter_event_type = event_filter.get("event_type")
        if filter_event_type and event_info.get("event_type") != filter_event_type:
            return False

        # source_type 过滤
        filter_source_type = event_filter.get("source_type")
        if filter_source_type and event_info.get("source_type") != filter_source_type:
            return False

        # date_range 过滤（基于 event_time，benchmark 数据可能没有日期，跳过）
        # 这里仅做框架预留

        return True

    # ── 聚合 & 校准 ──────────────────────────────────────

    def get_aggregate(self, job_id: str) -> Optional[ReplayAggregate]:
        """获取回放任务的聚合结果。"""
        results = self._get_all_results(job_id)
        if not results:
            return None
        return self._compute_aggregate(job_id, results)

    def calibrate(self, job_id: str) -> Optional[dict]:
        """校准分析 — 找出信号参数的最佳阈值和推荐策略。

        返回校准报告：
        - score_threshold: signal_score 阈值（高于此值的 hit_rate 显著更高）
        - confidence_threshold: confidence 阈值
        - best_timing_by_event_type: 按事件类型推荐的最佳 timing_action
        - hit_rate_by_score_bucket: 按 score 分桶的 hit_rate
        - hit_rate_by_confidence_bucket: 按 confidence 分桶的 hit_rate
        """
        results = self._get_all_results(job_id)
        if not results:
            return None

        successful = [r for r in results if r.error is None]
        if not successful:
            return {"error": "No successful results to calibrate"}

        # ── Score 阈值分析 ──
        score_buckets = self._bucket_analysis(
            successful,
            key=lambda r: r.signal_score,
            bucket_edges=[0.0, 0.3, 0.5, 0.7, 1.0],
        )

        # 找最佳 score 阈值：hit_rate 跳跃最大的点
        score_threshold = self._find_best_threshold(score_buckets)

        # ── Confidence 阈值分析 ──
        conf_buckets = self._bucket_analysis(
            successful,
            key=lambda r: r.signal_confidence,
            bucket_edges=[0.0, 0.3, 0.5, 0.7, 1.0],
        )
        confidence_threshold = self._find_best_threshold(conf_buckets)

        # ── 按事件类型推荐最佳 timing_action ──
        best_timing_by_event_type: dict[str, dict] = {}
        by_type: dict[str, list[ReplayResult]] = defaultdict(list)
        for r in successful:
            by_type[r.event_type].append(r)

        for etype, type_results in by_type.items():
            timing_stats: dict[str, dict] = {}
            by_timing: dict[str, list[ReplayResult]] = defaultdict(list)
            for r in type_results:
                action = r.timing_action or "unknown"
                by_timing[action].append(r)

            for action, action_results in by_timing.items():
                hits = sum(
                    1
                    for r in action_results
                    if r.outcome_excess_return is not None and r.outcome_excess_return > 0
                )
                total = len(action_results)
                avg_excess = (
                    sum(
                        r.outcome_excess_return
                        for r in action_results
                        if r.outcome_excess_return is not None
                    )
                    / total
                    if total > 0
                    else 0.0
                )
                timing_stats[action] = {
                    "count": total,
                    "hit_rate": round(hits / total, 4) if total > 0 else 0.0,
                    "avg_excess_return": round(avg_excess, 6),
                }

            # 推荐最佳 timing
            best_action = max(
                timing_stats.items(),
                key=lambda x: x[1].get("avg_excess_return", 0),
                default=("unknown", {}),
            )
            best_timing_by_event_type[etype] = {
                "recommended_action": best_action[0],
                "avg_excess_return": best_action[1].get("avg_excess_return", 0),
                "timing_breakdown": timing_stats,
            }

        return {
            "score_threshold": round(score_threshold, 2),
            "confidence_threshold": round(confidence_threshold, 2),
            "best_timing_by_event_type": best_timing_by_event_type,
            "hit_rate_by_score_bucket": score_buckets,
            "hit_rate_by_confidence_bucket": conf_buckets,
        }

    def _compute_aggregate(
        self,
        job_id: str,
        results: list[ReplayResult],
    ) -> ReplayAggregate:
        """计算聚合统计。"""
        successful = [r for r in results if r.error is None]
        failed = [r for r in results if r.error is not None]

        # 全局统计
        hit_count = sum(
            1
            for r in successful
            if r.outcome_excess_return is not None and r.outcome_excess_return > 0
        )
        hit_rate = hit_count / len(successful) if successful else 0.0

        avg_excess = (
            sum(r.outcome_excess_return for r in successful if r.outcome_excess_return is not None)
            / len(successful)
            if successful
            else 0.0
        )
        avg_drawdown = (
            sum(r.max_drawdown for r in successful if r.max_drawdown is not None) / len(successful)
            if successful
            else 0.0
        )
        avg_decay = (
            sum(r.decay for r in successful if r.decay is not None) / len(successful)
            if successful
            else 0.0
        )

        # 按分组统计
        by_event_type = self._group_stats(successful, key=lambda r: r.event_type)
        by_source_type = self._group_stats(successful, key=lambda r: r.source_type)
        by_timing_action = self._group_stats(successful, key=lambda r: r.timing_action or "unknown")

        # 校准
        calibration = self._compute_calibration(successful)

        return ReplayAggregate(
            job_id=job_id,
            total_events=len(results),
            successful=len(successful),
            failed=len(failed),
            hit_rate=round(hit_rate, 4),
            avg_excess_return=round(avg_excess, 6),
            avg_max_drawdown=round(avg_drawdown, 6),
            avg_decay=round(avg_decay, 4),
            by_event_type=by_event_type,
            by_source_type=by_source_type,
            by_timing_action=by_timing_action,
            calibration=calibration,
        )

    def _compute_calibration(self, results: list[ReplayResult]) -> dict:
        """计算校准指标（嵌入 aggregate 的简版）。"""
        if not results:
            return {}

        # Score 分桶
        score_buckets = self._bucket_analysis(
            results,
            key=lambda r: r.signal_score,
            bucket_edges=[0.0, 0.3, 0.5, 0.7, 1.0],
        )
        # Confidence 分桶
        conf_buckets = self._bucket_analysis(
            results,
            key=lambda r: r.signal_confidence,
            bucket_edges=[0.0, 0.3, 0.5, 0.7, 1.0],
        )

        return {
            "score_threshold": round(self._find_best_threshold(score_buckets), 2),
            "confidence_threshold": round(self._find_best_threshold(conf_buckets), 2),
            "hit_rate_by_score_bucket": score_buckets,
            "hit_rate_by_confidence_bucket": conf_buckets,
        }

    def _group_stats(
        self,
        results: list[ReplayResult],
        key: Callable[[ReplayResult], str],
    ) -> dict[str, dict]:
        """按指定 key 分组统计。"""
        groups: dict[str, list[ReplayResult]] = defaultdict(list)
        for r in results:
            groups[key(r)].append(r)

        stats: dict[str, dict] = {}
        for group_key, group_results in groups.items():
            total = len(group_results)
            hits = sum(
                1
                for r in group_results
                if r.outcome_excess_return is not None and r.outcome_excess_return > 0
            )
            avg_excess = (
                sum(
                    r.outcome_excess_return
                    for r in group_results
                    if r.outcome_excess_return is not None
                )
                / total
                if total > 0
                else 0.0
            )
            avg_score = (
                sum(r.signal_score for r in group_results if r.signal_score is not None) / total
                if total > 0
                else 0.0
            )
            stats[group_key] = {
                "count": total,
                "hit_rate": round(hits / total, 4) if total > 0 else 0.0,
                "avg_excess_return": round(avg_excess, 6),
                "avg_score": round(avg_score, 4),
            }

        return stats

    def _bucket_analysis(
        self,
        results: list[ReplayResult],
        key: Callable[[ReplayResult], float | None],
        bucket_edges: list[float],
    ) -> dict[str, dict]:
        """按数值分桶统计 hit_rate。"""
        buckets: dict[str, list[ReplayResult]] = defaultdict(list)

        for r in results:
            val = key(r)
            if val is None:
                continue
            # 找到所属桶
            bucket_idx = 0
            for i in range(len(bucket_edges) - 1):
                if val >= bucket_edges[i]:
                    bucket_idx = i
            bucket_label = f"{bucket_edges[bucket_idx]:.1f}-{bucket_edges[bucket_idx + 1]:.1f}"
            buckets[bucket_label].append(r)

        result: dict[str, dict] = {}
        for i in range(len(bucket_edges) - 1):
            label = f"{bucket_edges[i]:.1f}-{bucket_edges[i + 1]:.1f}"
            bucket_results = buckets.get(label, [])
            total = len(bucket_results)
            hits = sum(
                1
                for r in bucket_results
                if r.outcome_excess_return is not None and r.outcome_excess_return > 0
            )
            avg_excess = (
                sum(
                    r.outcome_excess_return
                    for r in bucket_results
                    if r.outcome_excess_return is not None
                )
                / total
                if total > 0
                else 0.0
            )
            result[label] = {
                "count": total,
                "hit_rate": round(hits / total, 4) if total > 0 else 0.0,
                "avg_excess_return": round(avg_excess, 6),
            }

        return result

    def _find_best_threshold(self, buckets: dict[str, dict]) -> float:
        """从分桶中找出 hit_rate 跳跃最大的阈值。

        策略：找到相邻桶 hit_rate 差异最大的分界点。
        """
        if not buckets:
            return 0.5

        sorted_labels = sorted(buckets.keys())
        best_threshold = 0.5
        max_jump = 0.0

        for i in range(len(sorted_labels) - 1):
            current = buckets[sorted_labels[i]]
            next_bucket = buckets[sorted_labels[i + 1]]

            if current["count"] == 0 or next_bucket["count"] == 0:
                continue

            jump = next_bucket["hit_rate"] - current["hit_rate"]
            if jump > max_jump:
                max_jump = jump
                # 阈值 = 当前桶的上界
                upper = float(sorted_labels[i].split("-")[1])
                best_threshold = upper

        return best_threshold

    # ── 内部辅助 ──────────────────────────────────────────

    def _update_job_status(
        self,
        job_id: str,
        status: str,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """更新任务状态。"""
        if self.repository:
            self.repository.update_job_status(job_id, status, completed_at)
        elif job_id in self._jobs:
            job = self._jobs[job_id]
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": status,
                    "completed_at": completed_at
                    or (datetime.now(timezone.utc) if status in ("completed", "failed") else None),
                }
            )

    def _save_result(self, result: ReplayResult) -> None:
        """保存回放结果。"""
        if self.repository:
            self.repository.save_result(result)
        else:
            self._results[result.job_id].append(result)

    def _get_all_results(self, job_id: str) -> list[ReplayResult]:
        """获取回放任务的所有结果。"""
        if self.repository:
            return self.repository.get_results(job_id)
        return self._results.get(job_id, [])
