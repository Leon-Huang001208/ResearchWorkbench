"""研究流水线服务"""
import uuid
from typing import Any, List, Optional

from cognitive_agents.blackboard import CognitiveBlackboard
from core.contracts import AssetAnalysisSnapshot, CanonicalEvent, EventAlphaSignal, ScenarioSet
from core.interfaces.model_gateway import ModelGateway
from core.interfaces.reasoning_engine import ReasoningEngine
from core.observability import get_logger
from core.services.event_extractor import EventExtractor, ExtractedSignalParams
from core.services.signal_service import SignalService
from memory_learning.contracts import FailureMemory, MarketEpisode
from memory_learning.journal import LearningJournal
from timing_engine import MetaTimingEngine, TimingContext, TimingModelRegistry
from timing_engine.contracts import TimingDecision

logger = get_logger(__name__)


class ResearchPipeline:
    """端到端研究流水线"""

    def __init__(
        self,
        data_router: Optional[Any] = None,
        knowledge_extractor: Optional[Any] = None,
        reasoning_engine: Optional[ReasoningEngine] = None,
        blackboard: Optional[CognitiveBlackboard] = None,
        signal_service: Optional[SignalService] = None,
        timing_engine: Optional[MetaTimingEngine] = None,
        timing_registry: Optional[TimingModelRegistry] = None,
        model_gateway: Optional[ModelGateway] = None,
        learning_journal: Optional[LearningJournal] = None,
        event_extractor: Optional[EventExtractor] = None,
        timing_repository: Optional[Any] = None,
    ):
        self.data_router = data_router
        self.knowledge_extractor = knowledge_extractor
        self.reasoning_engine = reasoning_engine
        self.blackboard = blackboard
        self.signal_service = signal_service
        self.timing_engine = timing_engine or MetaTimingEngine()
        self.timing_registry = timing_registry or TimingModelRegistry()
        self.model_gateway = model_gateway
        self.learning_journal = learning_journal
        self.timing_repository = timing_repository
        # 构建 EventExtractor：优先用传入的，否则基于 model_gateway 创建
        if event_extractor is not None:
            self.event_extractor = event_extractor
        else:
            self.event_extractor = EventExtractor(model_gateway=model_gateway)

    async def run_asset_analysis(self, asset_id: str) -> AssetAnalysisSnapshot:
        """资产分析完整流水线"""
        logger.info(f"Running asset analysis for {asset_id}")
        # TODO: implement full pipeline steps
        # For now, return a placeholder
        from datetime import datetime, timezone

        return AssetAnalysisSnapshot(
            snapshot_id="placeholder",
            canonical_id=asset_id,
            as_of=datetime.now(timezone.utc),
        )

    async def run_event_signal(self, event: CanonicalEvent) -> EventAlphaSignal:
        """事件型 Alpha 信号流水线 — Golden Path。

        完整流程：
        1. 从事件摘要提取信号参数（LLM / 关键词 fallback）
        2. 生成 EventAlphaSignal（非 placeholder）
        3. 通过 SignalService 持久化信号
        4. 运行择时评估
        5. 持久化择时结果
        6. 记录到 LearningJournal
        7. 返回完整信号（含 timing_decision）
        """
        logger.info("Running Golden Path event signal pipeline", event_id=event.event_id)

        # ── Step 1: 事件提取 ──────────────────────────────
        extracted = await self._extract_signal_params(event)

        # ── Step 2: 生成 EventAlphaSignal ─────────────────
        signal = self._build_signal(event, extracted)

        # ── Step 3: 持久化信号 ───────────────────────────
        signal = self._persist_signal(signal)

        # ── Step 4: 择时评估 ─────────────────────────────
        timing_decision = self._evaluate_timing(signal)
        if timing_decision is not None:
            signal.timing_decision = timing_decision

        # ── Step 5: 持久化择时结果 ───────────────────────
        if timing_decision is not None:
            self._persist_timing_decision(timing_decision)

        # ── Step 6: 记录到 LearningJournal ────────────────
        self._record_to_journal(event, signal, timing_decision)

        logger.info(
            "Golden Path complete",
            signal_id=signal.signal_id,
            event_id=event.event_id,
            timing_action=timing_decision.action if timing_decision else None,
        )

        # ── Step 7: 返回完整信号 ─────────────────────────
        return signal

    # ── Golden Path 内部方法 ───────────────────────────────

    async def _extract_signal_params(self, event: CanonicalEvent) -> ExtractedSignalParams:
        """从事件中提取信号参数。"""
        # 将事件摘要 + 断言拼接为提取文本
        text_parts = [event.summary]
        for assertion in event.assertions:
            if isinstance(assertion, dict):
                text_parts.append(assertion.get("content", str(assertion)))
            else:
                text_parts.append(str(assertion))
        for entity in event.entities:
            if isinstance(entity, dict):
                text_parts.append(entity.get("name", str(entity)))
            else:
                text_parts.append(str(entity))

        text = "\n".join(text_parts)
        if not text.strip():
            logger.warning(
                "No text content in event, using default params",
                event_id=event.event_id,
            )
            return ExtractedSignalParams(
                event_type=event.event_type,
                confidence=event.confidence,
            )

        try:
            return await self.event_extractor.extract(text)
        except Exception as exc:
            logger.error(
                "Event extraction failed, using event defaults",
                event_id=event.event_id,
                error=str(exc),
            )
            return ExtractedSignalParams(
                event_type=event.event_type,
                confidence=event.confidence,
            )

    def _build_signal(
        self,
        event: CanonicalEvent,
        extracted: ExtractedSignalParams,
    ) -> EventAlphaSignal:
        """构建 EventAlphaSignal。"""
        # 优先使用提取的 subject_ids，否则从事件 entities 中尝试获取
        subject_id = "unknown"
        if extracted.subject_ids:
            subject_id = extracted.subject_ids[0]
        elif event.entities:
            for entity in event.entities:
                if isinstance(entity, dict) and entity.get("canonical_id"):
                    subject_id = entity["canonical_id"]
                    break

        signal = EventAlphaSignal(
            signal_id=str(uuid.uuid4()),
            subject_id=subject_id,
            horizon="20d",
            thesis=extracted.thesis or f"基于{event.event_type}事件的投资逻辑",
            score=extracted.score,
            confidence=extracted.confidence,
            event_id=event.event_id,
            event_type=extracted.event_type or event.event_type,
            event_time=event.event_time,
            impact_path=extracted.impact_path,
            industry_impacts=extracted.industry_impacts,
            bullish_companies=extracted.bullish_companies,
            bearish_companies=extracted.bearish_companies,
            diffusion_stage=extracted.diffusion_stage,  # type: ignore[arg-type]
            market_regime=extracted.market_regime,
            evidence_refs=[
                span.get("ref", "")
                for span in event.evidence_spans
                if isinstance(span, dict) and span.get("ref")
            ],
        )
        return signal

    def _persist_signal(self, signal: EventAlphaSignal) -> EventAlphaSignal:
        """通过 SignalService 持久化信号。"""
        if self.signal_service is None:
            logger.debug("No SignalService, skipping signal persistence")
            return signal

        try:
            persisted = self.signal_service.create_event_signal(
                event_id=signal.event_id,
                event_type=signal.event_type,
                subject_id=signal.subject_id,
                thesis=signal.thesis,
                horizon=signal.horizon,
                score=signal.score,
                confidence=signal.confidence,
                event_time=signal.event_time,
                impact_path=signal.impact_path,
                industry_impacts=signal.industry_impacts,
                bullish_companies=signal.bullish_companies,
                bearish_companies=signal.bearish_companies,
                evidence_refs=signal.evidence_refs,
            )
            # 保留原始 signal_id（create_event_signal 会生成新的）
            logger.info(
                "Signal persisted via SignalService",
                signal_id=signal.signal_id,
                persisted_id=persisted.signal_id,
            )
            return signal
        except Exception as exc:
            logger.error(
                "Failed to persist signal via SignalService",
                signal_id=signal.signal_id,
                error=str(exc),
            )
            return signal

    def _evaluate_timing(self, signal: EventAlphaSignal) -> Optional[TimingDecision]:
        """运行择时评估。"""
        if self.timing_registry is None or self.timing_engine is None:
            logger.debug("Timing engine/registry not available, skipping timing evaluation")
            return None

        try:
            context = TimingContext(
                signal_id=signal.signal_id,
                event_signal=signal.model_dump(),
                market_regime=signal.market_regime or "unknown",
            )
            model_scores = self.timing_registry.score_all(context)
            if not model_scores:
                logger.warning(
                    "No timing model scores returned",
                    signal_id=signal.signal_id,
                )
                return None

            timing_decision = self.timing_engine.evaluate(
                model_scores,
                signal_id=signal.signal_id,
                market_regime=signal.market_regime or "unknown",
            )
            logger.info(
                "Timing evaluation complete",
                signal_id=signal.signal_id,
                action=timing_decision.action,
                readiness_score=timing_decision.readiness_score,
            )
            return timing_decision
        except Exception as exc:
            logger.error(
                "Failed to run timing evaluation",
                signal_id=signal.signal_id,
                error=str(exc),
            )
            return None

    def _persist_timing_decision(self, decision: TimingDecision) -> None:
        """持久化择时结果。"""
        if self.timing_repository is None:
            logger.debug("No TimingRepository, skipping timing persistence")
            return

        try:
            self.timing_repository.save(decision)
            logger.info(
                "Timing decision persisted",
                decision_id=decision.decision_id,
                signal_id=decision.signal_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to persist timing decision",
                decision_id=decision.decision_id,
                error=str(exc),
            )

    def _record_to_journal(
        self,
        event: CanonicalEvent,
        signal: EventAlphaSignal,
        timing_decision: Optional[TimingDecision],
    ) -> None:
        """记录到 LearningJournal。"""
        if self.learning_journal is None:
            return

        try:
            # 记录 MarketEpisode（如果有 timing decision 且为 enter/wait）
            if timing_decision and timing_decision.action in ("enter", "wait"):
                episode_id = str(uuid.uuid4())
                episode = MarketEpisode(
                    episode_id=episode_id,
                    event_id=event.event_id,
                    event_type=event.event_type,
                    market_regime=timing_decision.market_regime,
                    initial_reaction="unknown",
                    outcome_horizon=signal.horizon,  # type: ignore[arg-type]
                    outcome_return=0.0,
                    outcome_excess_return=0.0,
                    timing_action=timing_decision.action,  # type: ignore[arg-type]
                    signal_id=signal.signal_id,
                    timing_decision_id=timing_decision.decision_id,
                )
                self.learning_journal.record_episode(episode)
                logger.info(
                    "Recorded market episode",
                    episode_id=episode_id,
                    signal_id=signal.signal_id,
                )

            # 记录 FailureMemory（如果有 blockers）
            if timing_decision and timing_decision.blockers:
                failure_id = str(uuid.uuid4())
                failure_type = "unknown"
                blockers_lower = [b.lower() for b in timing_decision.blockers]
                if "timing" in blockers_lower:
                    failure_type = "timing_error"
                elif "crowding" in blockers_lower:
                    failure_type = "crowding_error"

                failure = FailureMemory(
                    failure_id=failure_id,
                    source_id=signal.signal_id,
                    failure_type=failure_type,  # type: ignore[arg-type]
                    root_cause=f"Blockers: {', '.join(timing_decision.blockers)}",
                    corrective_action="Review timing and crowding models",
                )
                self.learning_journal.record_failure(failure)
                logger.info(
                    "Recorded failure memory",
                    failure_id=failure_id,
                    signal_id=signal.signal_id,
                )
        except Exception as exc:
            logger.error(
                "Failed to record to learning journal",
                signal_id=signal.signal_id,
                error=str(exc),
                exc_info=True,
            )

    async def record_outcome(
        self,
        episode_id: str,
        outcome_return: float,
        outcome_excess_return: float,
        lesson: Optional[str] = None,
    ) -> Optional[MarketEpisode]:
        """记录事件后续收益结果（供外部回测后回调）"""
        if not self.learning_journal:
            logger.warning("Learning journal not available, skipping outcome record")
            return None

        episode = self.learning_journal.get_episode(episode_id)
        if not episode:
            logger.warning(f"Episode not found: {episode_id}")
            return None

        # Update the episode
        updated_episode = MarketEpisode(
            episode_id=episode.episode_id,
            event_id=episode.event_id,
            event_type=episode.event_type,
            market_regime=episode.market_regime,
            initial_reaction=episode.initial_reaction,
            outcome_horizon=episode.outcome_horizon,
            outcome_return=outcome_return,
            outcome_excess_return=outcome_excess_return,
            timing_action=episode.timing_action,
            signal_id=episode.signal_id,
            timing_decision_id=episode.timing_decision_id,
            failed_reason=episode.failed_reason,
            lesson=lesson or episode.lesson,
            evidence_refs=episode.evidence_refs,
            metadata=episode.metadata,
        )
        self.learning_journal.record_episode(updated_episode)
        logger.info(
            "Updated episode outcome",
            episode_id=episode_id,
            outcome_return=outcome_return,
            outcome_excess_return=outcome_excess_return,
        )
        return updated_episode

    async def run_scenario_analysis(self, question: str, subject_ids: List[str]) -> ScenarioSet:
        """情景分析流水线"""
        logger.info(f"Running scenario analysis for question: {question}")
        # TODO: implement full pipeline steps
        return ScenarioSet(set_id="placeholder", question=question, hypotheses=[])
