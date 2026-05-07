"""研究流水线服务"""
from typing import List, Optional, Any
import uuid

from core.contracts import AssetAnalysisSnapshot, CanonicalEvent, ScenarioSet, EventAlphaSignal
from core.observability import get_logger
from core.services.signal_service import SignalService
from core.interfaces.reasoning_engine import ReasoningEngine
from core.interfaces.model_gateway import ModelGateway
from cognitive_agents.blackboard import CognitiveBlackboard
from timing_engine import MetaTimingEngine, TimingContext, TimingModelRegistry
from memory_learning.journal import LearningJournal
from memory_learning.contracts import MarketEpisode, FailureMemory, TimingAction

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
        """事件型 Alpha 信号流水线（含 Timing + Memory 反馈）"""
        logger.info(f"Running event signal pipeline for {event.event_id}")
        # TODO: implement full pipeline steps (event understanding, propagation, etc.)
        # For now, create a placeholder EventAlphaSignal
        from core.contracts import EventAlphaSignal
        from datetime import datetime, timezone
        signal = EventAlphaSignal(
            signal_id=str(uuid.uuid4()),
            subject_id="placeholder-subject",
            horizon="20d",
            thesis="Placeholder thesis for event signal",
            score=0.7,
            confidence=0.8,
            event_id=event.event_id,
            event_type=event.event_type,
        )
        
        timing_decision = None
        blockers: list[str] = []
        # Timing evaluation step
        if self.timing_registry and self.timing_engine:
            try:
                context = TimingContext(
                    signal_id=signal.signal_id,
                    event_signal=signal.model_dump(),
                )
                model_scores = self.timing_registry.score_all(context)
                timing_decision = self.timing_engine.evaluate(
                    model_scores,
                    signal_id=signal.signal_id,
                )
                # Attach timing decision to signal (if EventAlphaSignal supports it)
                # For now, just log
                logger.info(
                    "Timing evaluation complete",
                    signal_id=signal.signal_id,
                    action=timing_decision.action,
                )
                signal.timing_decision = timing_decision  # type: ignore[attr-defined]
                blockers = timing_decision.blockers
            except Exception as e:
                logger.error(
                    "Failed to run timing evaluation",
                    signal_id=signal.signal_id,
                    error=str(e),
                )
        
        # Memory feedback step
        if self.learning_journal:
            try:
                # Record MarketEpisode if timing decision is enter/wait
                if timing_decision and timing_decision.action in ["enter", "wait"]:
                    episode_id = str(uuid.uuid4())
                    episode = MarketEpisode(
                        episode_id=episode_id,
                        event_id=event.event_id,
                        event_type=event.event_type,
                        market_regime=getattr(timing_decision, "market_regime", "unknown"),
                        initial_reaction="unknown",  # TODO: get from event analysis
                        outcome_horizon=signal.horizon,  # type: ignore[arg-type]
                        outcome_return=0.0,  # Placeholder, will be updated later
                        outcome_excess_return=0.0,  # Placeholder, will be updated later
                        timing_action=timing_decision.action,  # type: ignore[arg-type]
                        signal_id=signal.signal_id,
                        timing_decision_id=getattr(timing_decision, "decision_id", None),
                    )
                    self.learning_journal.record_episode(episode)
                    logger.info(
                        "Recorded market episode",
                        episode_id=episode_id,
                        signal_id=signal.signal_id,
                    )
                # Record FailureMemory if there are blockers
                if blockers:
                    failure_id = str(uuid.uuid4())
                    # Determine failure type based on blockers
                    failure_type = "unknown"
                    if "timing" in [b.lower() for b in blockers]:
                        failure_type = "timing_error"
                    if "crowding" in [b.lower() for b in blockers]:
                        failure_type = "crowding_error"
                    failure = FailureMemory(
                        failure_id=failure_id,
                        source_id=signal.signal_id,
                        failure_type=failure_type,  # type: ignore[arg-type]
                        root_cause=f"Blockers: {', '.join(blockers)}",
                        corrective_action="Review timing and crowding models",
                    )
                    self.learning_journal.record_failure(failure)
                    logger.info(
                        "Recorded failure memory",
                        failure_id=failure_id,
                        signal_id=signal.signal_id,
                    )
            except Exception as e:
                logger.error(
                    "Failed to record to learning journal",
                    signal_id=signal.signal_id,
                    error=str(e),
                    exc_info=True,
                )
        
        return signal

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
