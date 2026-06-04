"""研究流水线服务"""
import asyncio
import uuid
from typing import Any, List, Optional, cast

from cognitive_agents.agents.base import AgentContext
from cognitive_agents.agents.factory import AgentFactory
from cognitive_agents.agents.orchestrator import AgentOrchestrator
from cognitive_agents.blackboard import CognitiveBlackboard
from core.contracts import AssetAnalysisSnapshot, CanonicalEvent, EventAlphaSignal, ScenarioSet
from core.contracts.industry_chain import PropagationPath
from core.interfaces.model_gateway import ModelGateway
from core.observability import get_logger
from knowledge_layer.entity_resolution.resolver import EntityResolver
from knowledge_layer.graph_projection.graph_store import IndustryGraphStore
from knowledge_layer.graph_projection.propagation import PropagationAnalyzer
from memory_learning.contracts import FailureMemory, MarketEpisode
from memory_learning.journal import LearningJournal
from reasoning.graph import ReasoningEngine
from services.event_extractor import EventExtractor, ExtractedSignalParams
from services.signal_service import SignalService
from timing_engine import MetaTimingEngine, TimingContext, TimingModelRegistry
from timing_engine.contracts import MarketRegime, TimingDecision

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
        graph_store: Optional[IndustryGraphStore] = None,
        propagation_analyzer: Optional[PropagationAnalyzer] = None,
        entity_resolver: Optional[EntityResolver] = None,
        agent_factory: Optional[AgentFactory] = None,
        agent_orchestrator: Optional[AgentOrchestrator] = None,
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
        self.graph_store = graph_store
        self.propagation_analyzer = propagation_analyzer
        self.entity_resolver = entity_resolver
        self.agent_factory = agent_factory
        self.agent_orchestrator = agent_orchestrator
        # 最新一轮 agent swarm 的输出视图（供择时模型消费）
        self._latest_agent_views: list[dict] = []
        # 构建 EventExtractor：优先用传入的，否则基于 model_gateway 创建
        if event_extractor is not None:
            self.event_extractor = event_extractor
        else:
            self.event_extractor = EventExtractor(model_gateway=model_gateway)

    async def run_asset_analysis(self, asset_id: str) -> AssetAnalysisSnapshot:
        """资产分析完整流水线。

        流程：ReasoningEngine → Agent Swarm → Snapshot。
        """
        logger.info("Running asset analysis pipeline", asset_id=asset_id)

        # Step 1: Reasoning
        if self.reasoning_engine is None:
            logger.warning("No ReasoningEngine, returning placeholder snapshot")
            from datetime import datetime, timezone

            return AssetAnalysisSnapshot(
                snapshot_id="no-reasoning-engine",
                canonical_id=asset_id,
                as_of=datetime.now(timezone.utc),
            )

        snapshot = self.reasoning_engine.analyze_asset(asset_id)

        # Step 2: Agent Swarm (if available)
        if self.agent_orchestrator is not None and self.blackboard is not None:
            try:
                from datetime import datetime, timezone

                context = AgentContext(
                    target_id=asset_id,
                    event_id=None,
                    question=f"资产分析: {asset_id}",
                    evidence=snapshot.evidence_refs,
                    market_data={
                        "snapshot_id": snapshot.snapshot_id,
                        "as_of": snapshot.as_of.isoformat(),
                    },
                )
                views, conflicts = await self.agent_orchestrator.run_swarm(
                    context,
                    self.blackboard,
                )
                self._latest_agent_views = [
                    {
                        "agent": v.agent_name,
                        "role": v.role.value if hasattr(v.role, "value") else str(v.role),
                        "direction": v.direction.value
                        if hasattr(v.direction, "value")
                        else str(v.direction),
                        "thesis": v.thesis,
                        "score": v.score,
                    }
                    for v in views
                ]
                logger.info(
                    "Asset analysis agent swarm complete",
                    asset_id=asset_id,
                    views=len(views),
                    conflicts=len(conflicts),
                )
            except Exception as exc:
                logger.error(
                    "Agent swarm failed during asset analysis",
                    asset_id=asset_id,
                    error=str(exc),
                )

        return snapshot

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
        # ── 生成跨层 trace ID ────────────────────────────
        trace_id = str(uuid.uuid4())[:8]

        logger.info(
            "Running Golden Path event signal pipeline",
            event_id=event.event_id,
            trace_id=trace_id,
        )

        # ── Step 1: 事件提取 ──────────────────────────────
        extracted = await self._extract_signal_params(event)

        # ── Step 1.5: 实体解析 + 产业链传导 ────────────────
        self._resolve_entities(event)  # entities collected for Phase 3 agent context
        propagation_path = self._analyze_propagation(event)
        if propagation_path is not None:
            logger.info(
                "Propagation analysis complete",
                event_id=event.event_id,
                trace_id=trace_id,
                steps=len(propagation_path.steps),
                overall_strength=propagation_path.overall_strength,
            )

        # ── Step 2: 生成 EventAlphaSignal ─────────────────
        signal = self._build_signal(event, extracted, propagation_path)

        # ── Step 2.5: 推理分析 ─────────────────────────────
        self._run_reasoning(event, signal, trace_id=trace_id)

        # ── Step 2.75: Cognitive Agent Swarm ───────────────
        await self._run_agent_swarm(event, signal, trace_id=trace_id)

        # ── Step 3: 持久化信号 ───────────────────────────
        signal = self._persist_signal(signal)
        # 将 trace_id 写入 signal metadata
        signal.metadata["trace_id"] = trace_id

        # ── Step 4: 择时评估 ─────────────────────────────
        timing_decision = self._evaluate_timing(signal, trace_id=trace_id)
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

        text = "\n".join(part for part in text_parts if part is not None)
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

    def _resolve_entities(self, event: CanonicalEvent) -> list:
        """从事件中解析实体。"""
        if self.entity_resolver is None:
            logger.debug("No EntityResolver, skipping entity resolution")
            return []

        # 从事件构建文本用于实体提取
        text_parts = [event.title, event.summary]
        for entity in event.entities:
            if isinstance(entity, dict):
                text_parts.append(entity.get("text", entity.get("name", "")))
        text = "\n".join(filter(None, text_parts))

        if not text.strip():
            return []

        try:
            candidates = self.entity_resolver.extract_candidates(text)
            return [c.model_dump() for c in candidates]
        except Exception as exc:
            logger.error(
                "Entity resolution failed",
                event_id=event.event_id,
                error=str(exc),
            )
            return []

    def _analyze_propagation(
        self,
        event: CanonicalEvent,
    ) -> Optional[PropagationPath]:
        """分析事件在产业链中的传播路径。"""
        if self.propagation_analyzer is None or self.graph_store is None:
            logger.debug(
                "PropagationAnalyzer/GraphStore not available, skipping propagation analysis"
            )
            return None

        try:
            # 尝试通过事件中的行业信息匹配产业链
            industries = event.impacted_industries or []
            chain_id: Optional[str] = None
            if industries:
                for chain in self.graph_store.find_chains():
                    if chain.industry in industries or any(ind in chain.name for ind in industries):
                        chain_id = chain.chain_id
                        break

            result = self.propagation_analyzer.analyze_impact_propagation(
                self.graph_store,
                event,
                chain_id=chain_id,
            )
            try:
                from services.pipeline_monitor import pipeline_monitor
                from services.system_event_bus import event_bus

                payload = {
                    "event_id": event.event_id,
                    "steps": len(result.steps),
                    "overall_strength": result.overall_strength,
                }
                asyncio.run(event_bus.publish("knowledge.propagation_analyzed", payload))
                pipeline_monitor.record_event("knowledge.propagation_analyzed", payload)
            except Exception:
                pass
            return result
        except Exception as exc:
            logger.error(
                "Propagation analysis failed",
                event_id=event.event_id,
                error=str(exc),
            )
            return None

    def _run_reasoning(
        self,
        event: CanonicalEvent,
        signal: EventAlphaSignal,
        trace_id: str = "",
    ) -> None:
        """运行推理引擎，将生成的 hypotheses 填入 signal.scenario_refs。"""
        if self.reasoning_engine is None:
            logger.debug("No ReasoningEngine, skipping reasoning step")
            return

        try:
            from reasoning.state import RequestType

            question = f"{event.event_type}: {event.title or event.summary}"
            state = self.reasoning_engine.run(
                question,
                RequestType.SIGNAL_VALIDATION,
            )

            # 将 hypothesis IDs 写入 signal.scenario_refs
            scenario_ids = [h.scenario_id for h in state.hypotheses]
            if scenario_ids:
                signal.scenario_refs = list(set(signal.scenario_refs + scenario_ids))
                logger.info(
                    "Reasoning complete, added scenario refs",
                    signal_id=signal.signal_id,
                    trace_id=trace_id,
                    count=len(scenario_ids),
                )
            try:
                from services.pipeline_monitor import pipeline_monitor
                from services.system_event_bus import event_bus

                payload = {
                    "signal_id": signal.signal_id,
                    "trace_id": trace_id,
                    "scenario_count": len(scenario_ids),
                }
                asyncio.run(event_bus.publish("reasoning.completed", payload))
                pipeline_monitor.record_event("reasoning.completed", payload)
            except Exception:
                pass
        except Exception as exc:
            logger.error(
                "Reasoning step failed",
                signal_id=signal.signal_id,
                error=str(exc),
            )

    async def _run_agent_swarm(
        self,
        event: CanonicalEvent,
        signal: EventAlphaSignal,
        trace_id: str = "",
    ) -> None:
        """运行认知 Agent 群体辩论，将观点写入 CognitiveBlackboard。

        观点同时缓存到 self._latest_agent_views 供择时模型消费。
        """
        if self.agent_orchestrator is None:
            logger.debug("No AgentOrchestrator, skipping agent swarm")
            return

        try:
            from datetime import datetime, timezone

            blackboard = self.blackboard or CognitiveBlackboard()
            context = AgentContext(
                target_id=signal.subject_id,
                event_id=event.event_id,
                question=f"事件类型: {event.event_type}\n标题: {event.title}\n摘要: {event.summary}\n信号论点: {signal.thesis}",
                evidence=event.assertions + event.entities,
                market_data={
                    "confidence": signal.confidence,
                    "score": signal.score,
                    "impact_path": signal.impact_path,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            views, conflicts = await self.agent_orchestrator.run_swarm(
                context,
                blackboard,
            )

            # 缓存 agent views 供择时模型使用
            self._latest_agent_views = [
                {
                    "agent": v.agent_name,
                    "role": v.role.value if hasattr(v.role, "value") else str(v.role),
                    "direction": v.direction.value
                    if hasattr(v.direction, "value")
                    else str(v.direction),
                    "thesis": v.thesis,
                    "score": v.score,
                }
                for v in views
            ]

            logger.info(
                "Agent swarm complete",
                signal_id=signal.signal_id,
                trace_id=trace_id,
                views=len(views),
                conflicts=len(conflicts),
            )
            try:
                from services.pipeline_monitor import pipeline_monitor
                from services.system_event_bus import event_bus

                payload = {
                    "signal_id": signal.signal_id,
                    "trace_id": trace_id,
                    "views": len(views),
                    "conflicts": len(conflicts),
                    "bull_count": sum(
                        1
                        for v in views
                        if hasattr(v, "direction")
                        and getattr(v.direction, "value", str(v.direction)) == "bull"
                    ),
                    "bear_count": sum(
                        1
                        for v in views
                        if hasattr(v, "direction")
                        and getattr(v.direction, "value", str(v.direction)) == "bear"
                    ),
                }
                asyncio.run(event_bus.publish("agent.swarm.completed", payload))
                pipeline_monitor.record_event("agent.swarm.completed", payload)
            except Exception:
                pass
        except Exception as exc:
            logger.error(
                "Agent swarm failed",
                signal_id=signal.signal_id,
                error=str(exc),
            )

    def _build_signal(
        self,
        event: CanonicalEvent,
        extracted: ExtractedSignalParams,
        propagation_path: Optional[PropagationPath] = None,
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

        # 合并 impact_path：LLM 提取的 + 图谱传播分析的
        impact_path = list(extracted.impact_path) if extracted.impact_path else []
        if propagation_path is not None:
            for step in propagation_path.steps:
                impact_path.append(
                    f"{step.node_id}({step.node_name}): {step.impact} "
                    f"[mapping={step.mapping_strength:.2f}]"
                )

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
            impact_path=impact_path,
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

    def _evaluate_timing(
        self, signal: EventAlphaSignal, trace_id: str = ""
    ) -> Optional[TimingDecision]:
        """运行择时评估。"""
        if self.timing_registry is None or self.timing_engine is None:
            logger.debug("Timing engine/registry not available, skipping timing evaluation")
            return None

        try:
            context = TimingContext(
                signal_id=signal.signal_id,
                event_signal=signal.model_dump(),
                market_regime=signal.market_regime or "unknown",
                agent_views=self._latest_agent_views,
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
                market_regime=cast(MarketRegime, signal.market_regime or "unknown"),
            )
            logger.info(
                "Timing evaluation complete",
                signal_id=signal.signal_id,
                trace_id=trace_id,
                action=timing_decision.action,
                readiness_score=timing_decision.readiness_score,
            )
            try:
                from services.pipeline_monitor import pipeline_monitor
                from services.system_event_bus import event_bus

                payload = {
                    "signal_id": signal.signal_id,
                    "trace_id": trace_id,
                    "action": timing_decision.action,
                    "readiness_score": timing_decision.readiness_score,
                }
                asyncio.run(event_bus.publish("timing.evaluated", payload))
                pipeline_monitor.record_event("timing.evaluated", payload)
            except Exception:
                pass
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
        """情景分析流水线。

        流程：ReasoningEngine.generate_scenarios → 返回 ScenarioSet。
        """
        logger.info("Running scenario analysis pipeline", question=question)

        if self.reasoning_engine is None:
            logger.warning("No ReasoningEngine, returning placeholder ScenarioSet")
            return ScenarioSet(set_id="no-reasoning-engine", question=question, hypotheses=[])

        scenario_set = self.reasoning_engine.generate_scenarios(question)
        return scenario_set
