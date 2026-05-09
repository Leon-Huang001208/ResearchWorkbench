"""
最小可行闭环服务 - 规则驱动
真实事件 → 生成信号 → 回测验证 → 记录 Outcome
"""
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from core.observability import get_logger
from core.contracts import EventAlphaSignal
from data_layer.repositories.models import CanonicalEvent, AlphaSignalDB
from data_layer.repositories.base import SessionLocal
from data_layer.adapters.akshare_adapter import AKShareAdapter

logger = get_logger(__name__)


class ClosedLoopService:
    """
    最小可行闭环服务 - 使用真实价格数据
    """

    def __init__(self):
        try:
            from data_layer.adapters.multi_source_adapter import MultiSourcePriceAdapter
            self.price_adapter = MultiSourcePriceAdapter()
        except Exception as e:
            from data_layer.adapters.hybrid_price_adapter import HybridPriceAdapter
            logger.warning(f"Multi-source adapter not available, falling back: {e}")
            self.price_adapter = HybridPriceAdapter()
        self.benchmark_code = "000300.SH"  # 沪深300作为基准

    def generate_signals_from_events(self, event_ids: Optional[List[str]] = None) -> List[EventAlphaSignal]:
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
                existing_event_ids = db.query(AlphaSignalDB.event_id).filter(
                    AlphaSignalDB.event_id.isnot(None)
                ).all()
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
            subject_ids = event.payload.get("subject_ids", []) if event.payload else []

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
                industry_impacts=event.payload.get("tags", []) if event.payload else [],
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
        direction_desc = {
            "positive": "利好",
            "negative": "利空",
            "neutral": "中性影响"
        }
        direction = direction_desc.get(event.impact_direction, "中性影响")

        thesis_templates = {
            "earnings": f"{event.summary[:100]}...，{direction}相关标的",
            "policy": f"{event.summary[:100]}...，政策{direction}市场",
            "industry": f"{event.summary[:100]}...，行业{direction}",
        }

        return thesis_templates.get(event.event_type, f"{event.summary[:100]}...")

    def backtest_signals(self, signal_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        回测信号

        Args:
            signal_ids: 可选，指定信号ID列表

        Returns:
            回测结果列表
        """
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

            results = []
            for signal in signals:
                result = self._backtest_single_signal(signal, db)
                if result:
                    results.append(result)

            logger.info(f"Completed backtest for {len(results)} signals")
            return results

        finally:
            db.close()

    def _backtest_single_signal(self, signal: AlphaSignalDB, db) -> Optional[Dict[str, Any]]:
        """回测单个信号"""
        try:
            # 确定回测时间范围
            event_time = signal.event_time
            if not event_time:
                # 用创建时间
                event_time = signal.created_at

            # 回测未来 20 天
            horizon_days = 20
            start_date = event_time.strftime("%Y-%m-%d")
            end_date = (event_time + timedelta(days=horizon_days + 30)).strftime("%Y-%m-%d")

            # 获取标的价格
            quotes = self._get_price_data(signal.subject_id, start_date, end_date)
            if not quotes:
                logger.warning(f"No price data for {signal.subject_id}, skipping backtest")
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
            direction_correct = (outcome_return > 0 and float(signal.score) >= 0.5) or \
                               (outcome_return < 0 and float(signal.score) < 0.5)

            # 生成 lesson
            lesson = self._generate_lesson(signal, outcome_return, excess_return, direction_correct)

            # 直接用 SQL 插入到 signal_outcome
            outcome_id = str(uuid.uuid4())
            outcome_metadata = {
                "event_type": signal.event_type,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "signal_score": float(signal.score),
                "direction_correct": direction_correct,
            }

            db.execute(text("""
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
            """), {
                "outcome_id": outcome_id,
                "event_id": signal.event_id,
                "signal_id": signal.signal_id,
                "subject_id": signal.subject_id,
                "event_date": event_time,
                "timing_action": "enter",
                "entry_rule": "rule_based",
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
            })
            db.commit()

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

    def _get_price_data(self, code: str, start_date: str, end_date: str) -> List[Dict]:
        """获取真实价格数据（优先在线，失败用本地缓存）"""
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                quotes = loop.run_until_complete(
                    self.price_adapter.fetch_stock_quotes(code, start_date, end_date)
                )
                return quotes
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Failed to get price data for {code}: {e}")
            return []

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
        outcome_return = (exit_price - entry_price) / entry_price

        # 计算期间最大回撤
        period_df = df.loc[entry_idx:exit_idx].copy()
        period_df["cummax"] = period_df["close"].cummax()
        period_df["drawdown"] = (period_df["close"] - period_df["cummax"]) / period_df["cummax"]
        max_drawdown = period_df["drawdown"].min()

        return entry_price, exit_price, outcome_return, max_drawdown

    def _generate_lesson(
        self, signal: AlphaSignalDB, outcome_return: float, excess_return: float, direction_correct: bool
    ) -> str:
        """生成学习教训"""
        if direction_correct and outcome_return > 0:
            if excess_return > 0.05:
                return f"{signal.event_type} 事件信号表现优秀，超额收益 {excess_return:.1%}，值得复用"
            else:
                return f"{signal.event_type} 事件信号方向正确，但超额收益一般"
        elif direction_correct and outcome_return < 0:
            return f"{signal.event_type} 事件方向判断正确，但市场整体下跌，需要择时配合"
        else:
            return f"{signal.event_type} 事件信号方向判断错误，需要重新评估事件影响逻辑"

    def run_full_loop(self) -> Dict[str, Any]:
        """
        运行完整闭环

        Returns:
            闭环结果摘要
        """
        logger.info("=" * 60)
        logger.info("Starting closed-loop pipeline")
        logger.info("=" * 60)

        # Step 1: 从事件生成信号
        logger.info("Step 1: Generating signals from events...")
        signals = self.generate_signals_from_events()

        # Step 2: 回测信号
        logger.info("Step 2: Backtesting signals...")
        results = self.backtest_signals()

        # Step 3: 生成摘要
        summary = self._generate_summary(signals, results)

        logger.info("=" * 60)
        logger.info("Closed-loop pipeline completed")
        logger.info("=" * 60)

        return summary

    def _generate_summary(self, signals: List, results: List[Dict]) -> Dict[str, Any]:
        """生成闭环摘要"""
        total_signals = len(signals)
        total_backtested = len(results)

        if results:
            avg_return = sum(r["return"] for r in results) / total_backtested
            avg_excess_return = sum(r["excess_return"] for r in results) / total_backtested
            win_rate = sum(1 for r in results if r["return"] > 0) / total_backtested
            correct_direction_rate = sum(1 for r in results if r["direction_correct"]) / total_backtested
        else:
            avg_return = 0.0
            avg_excess_return = 0.0
            win_rate = 0.0
            correct_direction_rate = 0.0

        summary = {
            "signals_generated": total_signals,
            "signals_backtested": total_backtested,
            "avg_return": avg_return,
            "avg_excess_return": avg_excess_return,
            "win_rate": win_rate,
            "correct_direction_rate": correct_direction_rate,
            "results": results,
        }

        return summary
