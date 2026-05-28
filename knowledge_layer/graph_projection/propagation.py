from typing import List

from core.contracts.events import CanonicalEvent
from core.contracts.industry_chain import PropagationPath as CorePropagationPath
from core.contracts.industry_chain import PropagationStep
from core.observability import get_logger

from .contracts import SupplyChainPosition
from .graph_store import IndustryGraphStore

logger = get_logger(__name__)


class PropagationAnalyzer:
    """分析事件在产业链中的影响传播路径

    输出 core.contracts.industry_chain.PropagationPath，
    与 knowledge_layer 自身的 PropagationPath (deprecated) 不同。
    """

    def analyze_impact_propagation(
        self,
        graph_store: IndustryGraphStore,
        event: CanonicalEvent,
        chain_id: str | None = None,
    ) -> CorePropagationPath:
        """
        基于事件类型和产业链拓扑推导事件影响的传播路径。
        默认按照从上游到下游的顺序传播。

        Returns:
            core.contracts.industry_chain.PropagationPath
        """
        steps: list[PropagationStep] = []

        target_chain = None
        if chain_id:
            target_chain = graph_store.get_chain(chain_id)

        affected_entities = [e["entity_id"] for e in event.entities if "entity_id" in e]

        if target_chain:
            for idx, entity_id in enumerate(target_chain.nodes):
                if idx == 0:
                    position = SupplyChainPosition.UPSTREAM
                    expected_lag_days = 2
                elif idx == len(target_chain.nodes) - 1:
                    position = SupplyChainPosition.DOWNSTREAM
                    expected_lag_days = 10
                else:
                    position = SupplyChainPosition.MIDSTREAM
                    expected_lag_days = 5

                mapping_strength = max(0.2, 1.0 - expected_lag_days * 0.05)
                steps.append(
                    PropagationStep(
                        node_id=entity_id,
                        node_name=entity_id,
                        impact=f"{position.value}: {event.impact_direction}, lag {expected_lag_days}d",
                        mapping_strength=mapping_strength,
                    )
                )
        else:
            processed: set[str] = set()
            current_level = affected_entities
            day_offset = 0

            while current_level and len(steps) < 20:
                for entity_id in current_level:
                    if entity_id in processed:
                        continue
                    processed.add(entity_id)

                    if day_offset == 0:
                        position = SupplyChainPosition.UPSTREAM
                        lag = 1
                    elif day_offset < 3:
                        position = SupplyChainPosition.MIDSTREAM
                        lag = 3 + day_offset * 2
                    else:
                        position = SupplyChainPosition.DOWNSTREAM
                        lag = 5 + day_offset * 3

                    mapping_strength = max(0.2, 1.0 - lag * 0.05)
                    steps.append(
                        PropagationStep(
                            node_id=entity_id,
                            node_name=entity_id,
                            impact=f"{position.value}: {event.impact_direction}, lag {lag}d",
                            mapping_strength=mapping_strength,
                        )
                    )

                next_level = []
                for entity_id in current_level:
                    relations = graph_store.get_downstream(entity_id)
                    for rel in relations:
                        if rel.to_entity_id not in processed:
                            next_level.append(rel.to_entity_id)

                current_level = next_level
                day_offset += 1

        result = CorePropagationPath(steps=steps)
        result.overall_strength = result.calculate_overall_strength()

        # 发布传播分析完成事件
        try:
            import asyncio

            from services.pipeline_monitor import pipeline_monitor
            from services.system_event_bus import event_bus

            payload = {
                "event_id": event.event_id,
                "chain_id": chain_id,
                "steps": len(steps),
                "overall_strength": result.overall_strength,
            }
            asyncio.run(event_bus.publish("knowledge.propagation_analyzed", payload))
            pipeline_monitor.record_event("knowledge.propagation_analyzed", payload)
        except Exception:
            pass

        return result

    def find_similar_historical_paths(
        self,
        graph_store: IndustryGraphStore,
        event_type: str,
        industry: str,
    ) -> List[CorePropagationPath]:
        """查找历史上相似事件类型的传播路径（当前返回空列表）"""
        logger.info(
            "Looking for similar historical propagation paths",
            event_type=event_type,
            industry=industry,
        )
        return []
