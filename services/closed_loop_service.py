"""
最小可行闭环服务 - 规则驱动
真实事件 → 生成信号 → 回测验证 → 记录 Outcome
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast

from sqlalchemy import text

from core.contracts import AlphaSignal, EventAlphaSignal
from core.observability import get_logger
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import AlphaSignalDB, CanonicalEvent
from memory_learning.contracts import MarketEpisode
from memory_learning.journal import LearningJournal
from memory_learning.pattern_learner import PatternLearner

logger = get_logger(__name__)

if TYPE_CHECKING:
    import pandas as pd


def _publish_event(event_type: str, payload: Dict[str, Any]) -> None:
    """在同步代码中安全发布事件到 event_bus 并记录到 PipelineMonitor。"""
    try:
        from services.system_event_bus import event_bus

        # 使用 new_event_loop 避免在已有循环的线程上下文中嵌套调用 asyncio.run()
        # 导致 "coroutine was never awaited" RuntimeWarning
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(event_bus.publish(event_type, payload))
        finally:
            loop.close()
    except Exception:
        pass  # 事件发布失败不应影响管线执行

    try:
        from services.pipeline_monitor import pipeline_monitor

        pipeline_monitor.record_event(event_type, payload)
    except Exception:
        pass


class ClosedLoopService:
    """
    最小可行闭环服务 - 使用真实价格数据
    """

    def __init__(self, use_event_study: bool = True):
        try:
            from data_layer.adapters.multi_source_adapter import MultiSourcePriceAdapter

            self.price_adapter = MultiSourcePriceAdapter()
        except Exception as e:
            from data_layer.adapters.hybrid_price_adapter import HybridPriceAdapter

            logger.warning(f"Multi-source adapter not available, falling back: {e}")
            self.price_adapter = HybridPriceAdapter()
        self.benchmark_code = "000300.SH"  # 沪深300作为基准
        self.learning_journal = LearningJournal()
        self.pattern_learner = PatternLearner()
        self.use_event_study = use_event_study

        # Event study backtester and signal ranker
        from signal_lab.backtests.event_study import EventStudyBacktester
        from signal_lab.scoring.ranker import SignalRanker

        self.event_study_backtester = EventStudyBacktester(horizon=20)
        self.signal_ranker = SignalRanker()

    def generate_signals_from_events(
        self, event_ids: Optional[List[str]] = None
    ) -> List[EventAlphaSignal]:
        """
        从真实事件生成信号

        Args:
            event_ids: 可选，指定事件ID列表，不传则处理所有未生成信号的事件

        Returns:
            生成的信号列表
        """
        db = SessionLocal()
        try:
            # 查询事件
            query = db.query(CanonicalEvent)
            if event_ids:
                query = query.filter(CanonicalEvent.event_id.in_(event_ids))
            else:
                # 查询未生成过信号的事件
                existing_event_ids = (
                    db.query(AlphaSignalDB.event_id)
                    .filter(AlphaSignalDB.event_id.isnot(None))
                    .all()
                )
                existing_event_ids = [e[0] for e in existing_event_ids if e[0]]
                query = query.filter(~CanonicalEvent.event_id.in_(existing_event_ids))

            events = query.order_by(CanonicalEvent.created_at.desc()).all()
            logger.info(f"Found {len(events)} events to process")

            generated_signals = []
            for event in events:
                signal = self._generate_signal_from_event(event, db)
                if signal:
                    generated_signals.append(signal)

            logger.info(f"Generated {len(generated_signals)} signals from {len(events)} events")
            return generated_signals

        finally:
            db.close()

    def _generate_signal_from_event(self, event: CanonicalEvent, db) -> Optional[EventAlphaSignal]:
        """
        从单个事件生成信号（规则驱动）

        Rules:
        - earnings 财报事件: positive 影响 → 看多，confidence > 0.8 → score 0.7
        - policy 政策事件: positive 影响 → 看多相关指数
        - industry 行业事件: 看多行业内公司
        """
        try:
            # 从 event payload 提取标的
            subject_ids = event.payload.get("impacted_symbols", []) if event.payload else []

            # 清理标的列表，只保留有效的 A 股代码
            valid_subjects = []
            for s in subject_ids:
                if s.endswith((".SH", ".SZ")) and len(s.split(".")[0]) == 6:
                    valid_subjects.append(s)

            # 如果没有有效标的，根据事件类型分配默认标的
            if not valid_subjects:
                if event.event_type == "earnings":
                    valid_subjects = ["600519.SH"]  # 贵州茅台
                elif event.event_type == "policy":
                    valid_subjects = ["000001.SZ"]  # 平安银行
                elif event.event_type == "industry":
                    if "新能源" in event.summary or "比亚迪" in event.summary:
                        valid_subjects = ["002594.SZ"]  # 比亚迪
                    else:
                        valid_subjects = ["601012.SH"]  # 隆基绿能
                else:
                    valid_subjects = ["600519.SH"]

            subject_ids = valid_subjects

            # 计算分数 (规则驱动)
            base_score = 0.5
            if event.impact_direction == "positive":
                base_score += 0.2
            elif event.impact_direction == "negative":
                base_score -= 0.2

            # 置信度加成
            confidence = float(event.confidence)
            if confidence >= 0.9:
                base_score += 0.1
            elif confidence >= 0.8:
                base_score += 0.05

            # 限制在 0-1
            score = max(0.0, min(1.0, base_score))

            # 生成 thesis
            thesis = self._generate_thesis_from_event(event)

            # 生成 signal
            signal = EventAlphaSignal(
                signal_id=str(uuid.uuid4()),
                event_id=event.event_id,
                event_type=event.event_type,
                subject_id=subject_ids[0],  # 先取第一个标的
                thesis=thesis,
                horizon="20d",
                score=score,
                confidence=confidence,
                event_time=event.event_time,
                impact_path=[],
                industry_impacts=(
                    event.payload.get("impacted_industries", []) if event.payload else []
                ),
                bullish_companies=subject_ids if event.impact_direction == "positive" else [],
                bearish_companies=subject_ids if event.impact_direction == "negative" else [],
                scenario_refs=[],
                evidence_refs=[event.event_id],
                status="candidate",
            )

            # 保存到数据库
            db_signal = AlphaSignalDB(
                signal_id=signal.signal_id,
                discriminator="event_alpha_signal",
                subject_id=signal.subject_id,
                horizon=signal.horizon,
                thesis=signal.thesis,
                score=signal.score,
                confidence=signal.confidence,
                scenario_refs=signal.scenario_refs,
                evidence_refs=signal.evidence_refs,
                status=signal.status,
                event_id=signal.event_id,
                event_type=signal.event_type,
                event_time=signal.event_time,
                impact_path=signal.impact_path,
                industry_impacts=signal.industry_impacts,
                bullish_companies=signal.bullish_companies,
                bearish_companies=signal.bearish_companies,
                diffusion_stage="identified",
                market_regime="unknown",
                validation_status="pending",
                validation_metrics={},
            )
            db.add(db_signal)
            db.commit()

            logger.info(f"Generated signal {signal.signal_id} for event {event.event_id}")
            return signal

        except Exception as e:
            logger.error(f"Failed to generate signal from event {event.event_id}: {e}")
            db.rollback()
            return None

    def _generate_thesis_from_event(self, event: CanonicalEvent) -> str:
        """从事件生成 thesis"""
        direction_desc = {"positive": "利好", "negative": "利空", "neutral": "中性影响"}
        impact_direction = str(event.impact_direction or "neutral")
        event_type = str(event.event_type or "")
        summary = str(event.summary or "")
        direction = direction_desc.get(impact_direction, "中性影响")

        thesis_templates = {
            "earnings": f"{summary[:100]}...，{direction}相关标的",
            "policy": f"{summary[:100]}...，政策{direction}市场",
            "industry": f"{summary[:100]}...，行业{direction}",
        }

        return thesis_templates.get(event_type, f"{summary[:100]}...")

    def backtest_signals(
        self,
        signal_ids: Optional[List[str]] = None,
        use_event_study: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        回测信号

        Args:
            signal_ids: 可选，指定信号ID列表
            use_event_study: 若为 True，使用 EventStudyBacktester（事件窗统计）；
                             为 None 时取 self.use_event_study 的默认值。

        Returns:
            回测结果列表
        """
        use_es = use_event_study if use_event_study is not None else self.use_event_study

        db = SessionLocal()
        try:
            # 查询信号
            query = db.query(AlphaSignalDB).filter(AlphaSignalDB.event_id.isnot(None))
            if signal_ids:
                query = query.filter(AlphaSignalDB.signal_id.in_(signal_ids))

            # 只查还没有回测结果的信号
            result = db.execute(text("SELECT signal_id FROM signal_outcome"))
            existing_outcome_signal_ids = [row[0] for row in result if row[0]]
            if existing_outcome_signal_ids:
                query = query.filter(~AlphaSignalDB.signal_id.in_(existing_outcome_signal_ids))

            signals = query.order_by(AlphaSignalDB.created_at.desc()).all()
            logger.info(f"Found {len(signals)} signals to backtest")

            if use_es:
                results = self._backtest_with_event_study(signals, db)
            else:
                results = []
                for signal in signals:
                    r = self._backtest_single_signal(signal, db)
                    if r:
                        results.append(r)

            logger.info(f"Completed backtest for {len(results)} signals")
            return results

        finally:
            db.close()

    def _backtest_single_signal(self, signal: AlphaSignalDB, db) -> Optional[Dict[str, Any]]:
        """回测单个信号（规则驱动，简单买入持有收益计算）。"""
        try:
            # 确定回测时间范围
            event_time = cast(Optional[datetime], signal.event_time)
            if not event_time:
                # 用创建时间
                event_time = cast(datetime, signal.created_at)
            subject_id = str(signal.subject_id)

            # 回测未来 20 天
            horizon_days = 20
            start_date = event_time.strftime("%Y-%m-%d")
            end_date = (event_time + timedelta(days=horizon_days + 30)).strftime("%Y-%m-%d")

            # 获取标的价格
            quotes = self._get_price_data(subject_id, start_date, end_date)
            if not quotes:
                logger.warning(f"No price data for {subject_id}, skipping backtest")
                return None

            # 计算收益
            entry_price, exit_price, outcome_return, max_drawdown = self._calculate_returns(
                quotes, event_time, horizon_days
            )

            # 获取基准收益
            benchmark_return = 0.0
            try:
                benchmark_quotes = self._get_price_data(self.benchmark_code, start_date, end_date)
                if benchmark_quotes:
                    _, _, benchmark_return, _ = self._calculate_returns(
                        benchmark_quotes, event_time, horizon_days
                    )
            except Exception as e:
                logger.warning(f"Failed to get benchmark return: {e}")

            excess_return = outcome_return - benchmark_return

            # 确定方向是否正确
            direction_correct = (outcome_return > 0 and float(signal.score) >= 0.5) or (
                outcome_return < 0 and float(signal.score) < 0.5
            )

            # 生成 lesson
            lesson = self._generate_lesson(signal, outcome_return, excess_return, direction_correct)

            self._persist_outcome(
                signal,
                db,
                event_time,
                outcome_return,
                excess_return,
                max_drawdown,
                direction_correct,
                lesson,
            )

            result = {
                "signal_id": signal.signal_id,
                "event_id": signal.event_id,
                "subject_id": signal.subject_id,
                "return": outcome_return,
                "excess_return": excess_return,
                "max_drawdown": max_drawdown,
                "direction_correct": direction_correct,
            }

            logger.info(f"Backtested signal {signal.signal_id}: return {outcome_return:.2%}")
            return result

        except Exception as e:
            logger.error(f"Failed to backtest signal {signal.signal_id}: {e}")
            db.rollback()
            return None

    def _backtest_with_event_study(self, signals: List[AlphaSignalDB], db) -> List[Dict[str, Any]]:
        """使用 EventStudyBacktester 对信号批量事件研究回测。

        将价格数据转为 DataFrame，按标的+事件日对齐，计算事件窗
        超额收益、夏普比率、decay_by_day 等统计量并存入 signal_outcome。
        """
        import pandas as pd

        results: List[Dict[str, Any]] = []
        # 按标的分组，同一标的的信号共享价格数据
        by_subject: Dict[str, List[AlphaSignalDB]] = {}
        for signal in signals:
            by_subject.setdefault(str(signal.subject_id), []).append(signal)

        for subject_id, subject_signals in by_subject.items():
            # 获取价格数据
            price_data = self._fetch_price_range(subject_id)
            benchmark_data = self._fetch_price_range(self.benchmark_code)
            if price_data is None or price_data.empty:
                logger.warning(f"No price data for {subject_id}, skipping event study")
                continue

            # 构建事件 DataFrame
            event_rows = []
            for sig in subject_signals:
                event_time = cast(datetime, sig.event_time or sig.created_at)
                event_rows.append(
                    {
                        "event_date": pd.Timestamp(event_time),
                        "signal_id": sig.signal_id,
                        "event_id": sig.event_id,
                        "score": float(sig.score) if sig.score else 0.5,
                    }
                )
            events_df = pd.DataFrame(event_rows)

            # 调用 EventStudyBacktester
            try:
                bt_kwargs: Dict[str, Any] = {"events": events_df}
                if benchmark_data is not None and not benchmark_data.empty:
                    bt_kwargs["benchmark"] = benchmark_data
                bt_result = self.event_study_backtester.run(price_data, None, **bt_kwargs)

                # 为每个信号记录结果
                for sig in subject_signals:
                    direction_correct = (
                        bt_result.total_return > 0 and float(sig.score) >= 0.5
                    ) or (bt_result.total_return < 0 and float(sig.score) < 0.5)
                    lesson = self._generate_lesson(
                        sig, bt_result.total_return, bt_result.total_return, direction_correct
                    )

                    self._persist_outcome(
                        sig,
                        db,
                        cast(datetime, sig.event_time or sig.created_at),
                        bt_result.total_return,
                        bt_result.total_return,  # excess ≈ total when using event study avg
                        bt_result.max_drawdown,
                        direction_correct,
                        lesson,
                        extra_metadata={
                            "engine": "event_study",
                            "sharpe_ratio": bt_result.sharpe_ratio,
                            "volatility": bt_result.volatility,
                            "win_rate": bt_result.win_rate,
                            "decay_by_day": bt_result.metadata.get("decay_by_day", {}),
                            "event_count": bt_result.metadata.get("event_count", 0),
                        },
                    )

                    results.append(
                        {
                            "signal_id": sig.signal_id,
                            "event_id": sig.event_id,
                            "subject_id": sig.subject_id,
                            "return": bt_result.total_return,
                            "excess_return": bt_result.total_return,
                            "max_drawdown": bt_result.max_drawdown,
                            "direction_correct": direction_correct,
                            "sharpe_ratio": bt_result.sharpe_ratio,
                        }
                    )
            except Exception as exc:
                logger.error(
                    f"Event study backtest failed for {subject_id}: {exc}",
                    exc_info=True,
                )

        return results

    def _persist_outcome(
        self,
        signal: AlphaSignalDB,
        db,
        event_time: datetime,
        outcome_return: float,
        excess_return: float,
        max_drawdown: float,
        direction_correct: bool,
        lesson: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """将回测结果写入 signal_outcome 表。"""
        outcome_id = str(uuid.uuid4())
        outcome_metadata = {
            "event_type": signal.event_type,
            "signal_score": float(signal.score),
            "direction_correct": direction_correct,
        }
        if extra_metadata:
            outcome_metadata.update(extra_metadata)

        db.execute(
            text("""
            INSERT INTO signal_outcome (
                outcome_id, event_id, signal_id, subject_id, event_date,
                timing_action, entry_rule, horizon, benchmark,
                outcome_return, outcome_excess_return, max_drawdown,
                failure_reason, lesson, evaluated_at, metadata, created_at
            ) VALUES (
                :outcome_id, :event_id, :signal_id, :subject_id, :event_date,
                :timing_action, :entry_rule, :horizon, :benchmark,
                :outcome_return, :outcome_excess_return, :max_drawdown,
                :failure_reason, :lesson, :evaluated_at, :metadata, :created_at
            )
        """),
            {
                "outcome_id": outcome_id,
                "event_id": signal.event_id,
                "signal_id": signal.signal_id,
                "subject_id": signal.subject_id,
                "event_date": event_time,
                "timing_action": "enter",
                "entry_rule": (
                    "event_study"
                    if extra_metadata and "decay_by_day" in extra_metadata
                    else "rule_based"
                ),
                "horizon": "20d",
                "benchmark": self.benchmark_code,
                "outcome_return": outcome_return,
                "outcome_excess_return": excess_return,
                "max_drawdown": max_drawdown,
                "failure_reason": None if direction_correct else "direction_wrong",
                "lesson": lesson,
                "evaluated_at": datetime.now(timezone.utc),
                "metadata": json.dumps(outcome_metadata),
                "created_at": datetime.now(timezone.utc),
            },
        )
        db.commit()

    def _fetch_price_range(
        self, code: str, lookback_days: int = 252
    ) -> "pd.DataFrame | None":  # noqa: F821
        """拉取标的价格，返回以 date 为索引的 DataFrame。"""
        import pandas as pd

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        quotes = self._get_price_data(code, start_date, end_date)
        if not quotes:
            return None
        df = pd.DataFrame(quotes)
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date").sort_index()

    def _get_price_data(self, code: str, start_date: str, end_date: str) -> List[Dict]:
        """获取真实价格数据（优先在线，失败用本地缓存）"""
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            quotes = loop.run_until_complete(
                self.price_adapter.fetch_stock_quotes(code, start_date, end_date)
            )
            return quotes
        except Exception as e:
            logger.error(f"Failed to get price data for {code}: {e}")
            return []
        finally:
            # drain 任何未完成的协程，避免 "coroutine was never awaited" RuntimeWarning
            try:
                loop.run_until_complete(asyncio.sleep(0))
            except Exception:
                pass
            loop.close()

    def _calculate_returns(
        self, quotes: List[Dict], event_time: datetime, horizon_days: int
    ) -> Tuple[float, float, float, float]:
        """计算收益和最大回撤"""
        if not quotes:
            return 0.0, 0.0, 0.0, 0.0

        # 转换为 DataFrame 方便处理
        import pandas as pd

        df = pd.DataFrame(quotes)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        # 找到事件后第一个交易日作为进场点
        event_date = event_time.date()
        entry_idx = df[df["date"].dt.date >= event_date].index.min()

        if pd.isna(entry_idx):
            logger.warning(f"No entry point found after {event_date}")
            return 0.0, 0.0, 0.0, 0.0

        entry_price = df.loc[entry_idx, "close"]

        # 找到 horizon_days 后的退场点（或最后一个交易日）
        target_exit_date = df.loc[entry_idx, "date"] + timedelta(days=horizon_days)
        exit_idx = df[df["date"] >= target_exit_date].index.min()

        if pd.isna(exit_idx):
            exit_idx = df.index[-1]

        exit_price = df.loc[exit_idx, "close"]

        # 计算收益
        outcome_return = float((exit_price - entry_price) / entry_price)

        # 计算期间最大回撤
        period_df = df.loc[entry_idx:exit_idx].copy()
        period_df["cummax"] = period_df["close"].cummax()
        period_df["drawdown"] = (period_df["close"] - period_df["cummax"]) / period_df["cummax"]
        max_drawdown = float(period_df["drawdown"].min())

        return float(entry_price), float(exit_price), outcome_return, max_drawdown

    def _generate_lesson(
        self,
        signal: AlphaSignalDB,
        outcome_return: float,
        excess_return: float,
        direction_correct: bool,
    ) -> str:
        """生成学习教训"""
        if direction_correct and outcome_return > 0:
            if excess_return > 0.05:
                return (
                    f"{signal.event_type} 事件信号表现优秀，超额收益 {excess_return:.1%}，值得复用"
                )
            else:
                return f"{signal.event_type} 事件信号方向正确，但超额收益一般"
        elif direction_correct and outcome_return < 0:
            return f"{signal.event_type} 事件方向判断正确，但市场整体下跌，需要择时配合"
        else:
            return f"{signal.event_type} 事件信号方向判断错误，需要重新评估事件影响逻辑"

    def rank_and_filter_signals(
        self,
        signals: Optional[List[EventAlphaSignal]] = None,
        top_n: int = 10,
    ) -> List[EventAlphaSignal]:
        """使用 SignalRanker 对信号排序并返回前 top_n 个。

        Args:
            signals: 待排序的信号列表；不传则从事件生成。
            top_n: 返回前 N 个信号

        Returns:
            排名前 top_n 的信号。
        """
        if signals is None:
            signals = self.generate_signals_from_events()

        if not signals:
            logger.warning("No signals to rank")
            return []

        ranked = self.signal_ranker.filter_top_n(cast(List[AlphaSignal], signals), n=top_n)
        return cast(List[EventAlphaSignal], ranked)

    def run_full_loop(self) -> Dict[str, Any]:
        """
        运行完整闭环

        Returns:
            闭环结果摘要
        """
        start_time = datetime.now(timezone.utc)
        _publish_event("pipeline.closed_loop.started", {"started_at": start_time.isoformat()})

        logger.info("=" * 60)
        logger.info("Starting closed-loop pipeline")
        logger.info("=" * 60)

        try:
            # Step 1: 从事件生成信号
            logger.info("Step 1: Generating signals from events...")
            step1_start = datetime.now(timezone.utc)
            signals = self.generate_signals_from_events()
            _publish_event(
                "pipeline.signal.generated",
                {
                    "count": len(signals),
                    "duration_ms": int(
                        (datetime.now(timezone.utc) - step1_start).total_seconds() * 1000
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Step 2: 回测信号
            logger.info("Step 2: Backtesting signals...")
            step2_start = datetime.now(timezone.utc)
            results = self.backtest_signals()
            _publish_event(
                "pipeline.backtest.completed",
                {
                    "count": len(results),
                    "duration_ms": int(
                        (datetime.now(timezone.utc) - step2_start).total_seconds() * 1000
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Step 3: 记录market episodes（学习）
            logger.info("Step 3: Recording market episodes...")
            step3_start = datetime.now(timezone.utc)
            episodes_recorded = self._record_market_episodes(results)
            _publish_event(
                "pipeline.episode.recorded",
                {
                    "count": episodes_recorded,
                    "duration_ms": int(
                        (datetime.now(timezone.utc) - step3_start).total_seconds() * 1000
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Step 4: 更新pattern learner
            patterns_learned = 0
            if episodes_recorded > 0:
                logger.info("Step 4: Learning patterns from episodes...")
                step4_start = datetime.now(timezone.utc)
                all_episodes = self.learning_journal.list_episodes()
                self.pattern_learner.learn_from_episodes(all_episodes)
                patterns_learned = len(all_episodes)
                _publish_event(
                    "pipeline.pattern.learned",
                    {
                        "episodes_analyzed": patterns_learned,
                        "duration_ms": int(
                            (datetime.now(timezone.utc) - step4_start).total_seconds() * 1000
                        ),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            # Step 5: 生成摘要
            summary = self._generate_summary(signals, results, episodes_recorded)

            total_duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            logger.info("=" * 60)
            logger.info(
                "Closed-loop pipeline completed",
                duration_ms=total_duration,
                signals=len(signals),
                backtests=len(results),
                episodes=episodes_recorded,
            )
            logger.info("=" * 60)

            _publish_event(
                "pipeline.closed_loop.completed",
                {
                    **summary,
                    "duration_ms": total_duration,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            return summary

        except Exception as exc:
            logger.error("Closed-loop pipeline failed: %s", exc, exc_info=True)
            _publish_event(
                "pipeline.closed_loop.error",
                {
                    "error": str(exc),
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                    "duration_ms": int(
                        (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                    ),
                },
            )
            raise

    def _record_market_episodes(self, results: List[Dict[str, Any]]) -> int:
        """Record market episodes from backtest results."""
        recorded_count = 0

        for result in results:
            try:
                # Get signal details
                db = SessionLocal()
                try:
                    signal = (
                        db.query(AlphaSignalDB)
                        .filter(AlphaSignalDB.signal_id == result["signal_id"])
                        .first()
                    )
                    if not signal:
                        continue

                    # Create market episode
                    episode = MarketEpisode(
                        episode_id=str(uuid.uuid4()),
                        event_id=signal.event_id,
                        event_type=signal.event_type,
                        market_regime="unknown",  # We'll enhance this later
                        initial_reaction="unknown",
                        outcome_horizon="20d",
                        outcome_return=result["return"],
                        outcome_excess_return=result["excess_return"],
                        timing_action="enter",
                        signal_id=result["signal_id"],
                        failed_reason=None if result["direction_correct"] else "direction_wrong",
                        lesson=result.get("lesson", ""),
                        evidence_refs=[signal.event_id] if signal.event_id else [],
                        metadata={
                            "signal_score": float(signal.score) if signal.score else 0.5,
                            "signal_confidence": (
                                float(signal.confidence) if signal.confidence else 0.5
                            ),
                        },
                    )

                    # Record the episode
                    self.learning_journal.record_episode(episode)
                    recorded_count += 1
                finally:
                    db.close()

            except Exception as e:
                logger.error(f"Failed to record episode for signal {result.get('signal_id')}: {e}")

        logger.info(f"Recorded {recorded_count} market episodes")
        return recorded_count

    def _generate_summary(
        self, signals: List, results: List[Dict], episodes_recorded: int = 0
    ) -> Dict[str, Any]:
        """生成闭环摘要"""
        total_signals = len(signals)
        total_backtested = len(results)

        if results:
            avg_return = sum(r["return"] for r in results) / total_backtested
            avg_excess_return = sum(r["excess_return"] for r in results) / total_backtested
            win_rate = sum(1 for r in results if r["return"] > 0) / total_backtested
            correct_direction_rate = (
                sum(1 for r in results if r["direction_correct"]) / total_backtested
            )
        else:
            avg_return = 0.0
            avg_excess_return = 0.0
            win_rate = 0.0
            correct_direction_rate = 0.0

        # Get learning insights
        learning_insights = []
        if episodes_recorded > 0:
            all_episodes = self.learning_journal.list_episodes()
            if all_episodes:
                # Get insights by event type
                event_types = set(e.event_type for e in all_episodes)
                for event_type in event_types:
                    perf = self.pattern_learner.get_event_type_performance(event_type)
                    if perf:
                        learning_insights.append(
                            {
                                "event_type": event_type,
                                "win_rate": perf["win_rate"],
                                "avg_excess_return": perf["average_excess_return"],
                                "sample_size": perf["sample_size"],
                            }
                        )

        summary = {
            "signals_generated": total_signals,
            "signals_backtested": total_backtested,
            "avg_return": avg_return,
            "avg_excess_return": avg_excess_return,
            "win_rate": win_rate,
            "correct_direction_rate": correct_direction_rate,
            "results": results,
            "episodes_recorded": episodes_recorded,
            "learning_insights": learning_insights[:5],  # Top 5 insights
        }

        return summary
