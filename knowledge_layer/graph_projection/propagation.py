import uuid
from typing import List

from core.contracts.events import CanonicalEvent
from core.observability import get_logger

from .contracts import PropagationPath, SupplyChainPosition
from .graph_store import IndustryGraphStore

logger = get_logger(__name__)


class PropagationAnalyzer:
    """分析事件在产业链中的影响传播路径"""

    def analyze_impact_propagation(
        self,
        graph_store: IndustryGraphStore,
        event: CanonicalEvent,
        chain_id: str | None = None,
    ) -> PropagationPath:
        """
        基于事件类型和产业链拓扑推导事件影响的传播路径
        默认按照从上游到下游的顺序传播，根据事件影响方向调整每个节点的影响方向
        """
        path_id = f"prop_{uuid.uuid4().hex[:8]}"
        propagation_path = []
        confidence = 0.8

        # If specific chain is provided, use it
        target_chain = None
        if chain_id:
            target_chain = graph_store.get_chain(chain_id)

        # Collect all affected entities from event
        affected_entities = [e["entity_id"] for e in event.entities if "entity_id" in e]

        if target_chain:
            # Process chain in order from upstream to downstream
            for idx, entity_id in enumerate(target_chain.nodes):
                # Determine position based on position in chain
                if idx == 0:
                    position = SupplyChainPosition.UPSTREAM
                    # Event typically hits upstream first with shorter lag
                    expected_lag_days = 2
                elif idx == len(target_chain.nodes) - 1:
                    position = SupplyChainPosition.DOWNSTREAM
                    # Downstream lags more
                    expected_lag_days = 10
                else:
                    position = SupplyChainPosition.MIDSTREAM
                    expected_lag_days = 5

                propagation_path.append(
                    {
                        "entity_id": entity_id,
                        "position": position,
                        "expected_lag_days": expected_lag_days,
                        "impact_direction": event.impact_direction,
                    }
                )
        else:
            # If no chain specified, start from affected entities and expand downstream
            processed = set()
            current_level = affected_entities
            day_offset = 0

            # Get position info based on how far from the trigger
            while current_level and len(propagation_path) < 20:
                for entity_id in current_level:
                    if entity_id in processed:
                        continue
                    processed.add(entity_id)

                    # Guess position based on distance
                    if day_offset == 0:
                        position = SupplyChainPosition.UPSTREAM
                        lag = 1
                    elif day_offset < 3:
                        position = SupplyChainPosition.MIDSTREAM
                        lag = 3 + day_offset * 2
                    else:
                        position = SupplyChainPosition.DOWNSTREAM
                        lag = 5 + day_offset * 3

                    propagation_path.append(
                        {
                            "entity_id": entity_id,
                            "position": position,
                            "expected_lag_days": lag,
                            "impact_direction": event.impact_direction,
                        }
                    )

                # Get next level (downstream)
                next_level = []
                for entity_id in current_level:
                    relations = graph_store.get_downstream(entity_id)
                    for rel in relations:
                        if rel.to_entity_id not in processed:
                            next_level.append(rel.to_entity_id)

                current_level = next_level
                day_offset += 1

        # Reduce confidence if we couldn't find a proper chain
        if not target_chain:
            confidence = 0.5

        return PropagationPath(
            path_id=path_id,
            trigger_event_type=event.event_type,
            affected_chain_id=chain_id if chain_id else "unknown",
            path=propagation_path,
            confidence=confidence,
        )

    def find_similar_historical_paths(
        self,
        graph_store: IndustryGraphStore,
        event_type: str,
        industry: str,
    ) -> List[PropagationPath]:
        """Find historically similar propagation paths for this event type and industry"""
        # This implementation just returns an empty list for now
        # In the future this can query the database of past propagation paths and outcomes
        logger.info(
            "Looking for similar historical propagation paths",
            event_type=event_type,
            industry=industry,
        )
        return []
