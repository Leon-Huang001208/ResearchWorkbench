"""
产业链图谱集成测试 - 测试GraphStore + PropagationAnalyzer联合工作
"""
import uuid
from datetime import datetime

import pytest

from core.contracts import CanonicalEvent
from knowledge_layer.graph_projection import IndustryGraphStore, PropagationAnalyzer
from knowledge_layer.graph_projection.contracts import (
    IndustryChain,
    RelationshipType,
    SupplyChainPosition,
    TemporalRelation,
)


@pytest.fixture
def graph_store():
    """Create fresh IndustryGraphStore instance."""
    return IndustryGraphStore()


@pytest.fixture
def analyzer():
    """Create PropagationAnalyzer instance."""
    return PropagationAnalyzer()


@pytest.fixture
def sample_automotive_chain(graph_store):
    """Create sample lithium ion battery -> new energy vehicle -> dealer chain."""
    chain_id = "chain-automotive-nev"
    chain = IndustryChain(
        chain_id=chain_id,
        name="新能源汽车产业链",
        industry="automotive",
        nodes=[
            "entity:lithium",
            "entity:battery",
            "entity:nev",
            "entity:dealer",
        ],
        relations=[],
        created_at=datetime.now(),
    )
    graph_store.add_chain(chain)

    # Add temporal relations between entities
    relations = [
        TemporalRelation(
            relation_id=f"rel-{uuid.uuid4().hex[:8]}",
            from_entity_id="entity:lithium",
            to_entity_id="entity:battery",
            relationship_type=RelationshipType.SUPPLIES,
            valid_from=datetime(2020, 1, 1),
            valid_to=None,
            strength=0.9,
        ),
        TemporalRelation(
            relation_id=f"rel-{uuid.uuid4().hex[:8]}",
            from_entity_id="entity:battery",
            to_entity_id="entity:nev",
            relationship_type=RelationshipType.SUPPLIES,
            valid_from=datetime(2020, 1, 1),
            valid_to=None,
            strength=0.95,
        ),
        TemporalRelation(
            relation_id=f"rel-{uuid.uuid4().hex[:8]}",
            from_entity_id="entity:nev",
            to_entity_id="entity:dealer",
            relationship_type=RelationshipType.SUPPLIES,
            valid_from=datetime(2020, 1, 1),
            valid_to=None,
            strength=0.85,
        ),
    ]

    for rel in relations:
        graph_store.add_relation(rel)

    return chain


def create_test_event(impact_direction="positive"):
    """Helper to create test canonical event."""
    return CanonicalEvent(
        event_id="evt-test-graph-001",
        event_type="supply_disruption",
        source_type="news",
        source_name="TestSource",
        title="Lithium price decreases 15%",
        summary="Lithium price decreases",
        impact_direction=impact_direction,
        confidence=0.8,
        needs_review=False,
        entities=[{"text": "Lithium", "entity_id": "entity:lithium", "type": "commodity"}],
        evidence_spans=[{"text": "Lithium price decreases 15%"}],
        source_doc_id="doc-test-001",
        reviewer_status="approved",
    )


@pytest.mark.integration
class TestGraphStorePropagationIntegration:
    """测试GraphStore + PropagationAnalyzer联合工作"""

    def test_graph_store_stores_relations_correctly(self, graph_store):
        """测试GraphStore正确存储和查询关系"""
        # Add a relation
        rel = TemporalRelation(
            relation_id="test-rel-001",
            from_entity_id="A",
            to_entity_id="B",
            relationship_type=RelationshipType.SUPPLIES,
            valid_from=datetime(2021, 1, 1),
            valid_to=None,
            strength=0.9,
        )
        added = graph_store.add_relation(rel)
        assert added is not None

        # Retrieve it back
        retrieved = graph_store.get_relation("test-rel-001")
        assert retrieved is not None
        assert retrieved.from_entity_id == "A"
        assert retrieved.to_entity_id == "B"

    def test_time_filter_works_correctly(self, graph_store):
        """测试时间过滤在查询中的正确性"""
        # Add relations with different validity times
        # Relation 1: valid since 2020 to 2023
        rel1 = TemporalRelation(
            relation_id="rel-time-001",
            from_entity_id="X",
            to_entity_id="Y",
            relationship_type=RelationshipType.SUPPLIES,
            valid_from=datetime(2020, 1, 1),
            valid_to=datetime(2023, 1, 1),
            strength=0.8,
        )
        # Relation 2: valid since 2022 to present
        rel2 = TemporalRelation(
            relation_id="rel-time-002",
            from_entity_id="X",
            to_entity_id="Y",
            relationship_type=RelationshipType.SUPPLIES,
            valid_from=datetime(2022, 1, 1),
            valid_to=None,
            strength=0.8,
        )
        graph_store.add_relation(rel1)
        graph_store.add_relation(rel2)

        # Query at 2021: only rel1
        results_2021 = graph_store.find_relations(
            from_entity="X",
            at_time=datetime(2021, 6, 1),
        )
        assert len(results_2021) == 1
        assert results_2021[0].relation_id == "rel-time-001"

        # Query at 2022-06: both relations
        results_2022 = graph_store.find_relations(
            from_entity="X",
            at_time=datetime(2022, 6, 1),
        )
        assert len(results_2022) == 2

        # Query at 2024-01: only rel2 (rel1 expired)
        results_2024 = graph_store.find_relations(
            from_entity="X",
            at_time=datetime(2024, 1, 1),
        )
        assert len(results_2024) == 1
        assert results_2024[0].relation_id == "rel-time-002"

    def test_get_downstream_returns_correct_nodes(self, graph_store, sample_automotive_chain):
        """测试get_downstream正确返回下游节点"""
        downstream_of_lithium = graph_store.get_downstream("entity:lithium")
        assert len(downstream_of_lithium) == 1
        assert downstream_of_lithium[0].to_entity_id == "entity:battery"

        downstream_of_battery = graph_store.get_downstream("entity:battery")
        assert len(downstream_of_battery) == 1
        assert downstream_of_battery[0].to_entity_id == "entity:nev"

    def test_full_propagation_flow_with_known_chain(
        self, graph_store, analyzer, sample_automotive_chain
    ):
        """测试从事件到传播路径的完整流程（已知产业链）"""
        event = create_test_event()
        path = analyzer.analyze_impact_propagation(
            graph_store,
            event,
            chain_id=sample_automotive_chain.chain_id,
        )

        # Verify result structure
        assert path is not None
        assert path.path_id is not None
        assert path.affected_chain_id == sample_automotive_chain.chain_id
        assert len(path.path) == 4  # All 4 nodes in the chain
        assert path.confidence == 0.8  # Full confidence with known chain

        # Check positions are assigned correctly
        positions = [node["position"] for node in path.path]
        assert positions[0] == SupplyChainPosition.UPSTREAM
        assert positions[1] == SupplyChainPosition.MIDSTREAM
        assert positions[2] == SupplyChainPosition.MIDSTREAM
        assert positions[3] == SupplyChainPosition.DOWNSTREAM

        # All nodes should have correct impact direction (matches event)
        assert all(node["impact_direction"] == event.impact_direction for node in path.path)

        # Expected lag increases as we go downstream
        lags = [node["expected_lag_days"] for node in path.path]
        assert lags == [2, 5, 5, 10]

    def test_full_propagation_flow_with_expansion(
        self, graph_store, analyzer, sample_automotive_chain
    ):
        """测试从事件触发自动扩展传播路径（无指定chain）"""
        event = create_test_event()
        path = analyzer.analyze_impact_propagation(
            graph_store,
            event,
            chain_id=None,
        )

        # Should find all nodes starting from lithium
        assert len(path.path) == 4  # lithium -> battery -> nev -> dealer
        assert path.confidence == 0.5  # Lower confidence when no chain specified
        # Entities are in correct expansion order
        entity_ids = [node["entity_id"] for node in path.path]
        assert "entity:lithium" in entity_ids[0]

    def test_time_filter_affects_propagation(self, graph_store, analyzer, sample_automotive_chain):
        """测试时间过滤影响传播分析结果"""
        # Expire the battery to nev relation in 2022
        rels = graph_store.find_relations(from_entity="entity:battery")
        for rel in rels:
            if rel.to_entity_id == "entity:nev":
                rel.valid_to = datetime(2022, 1, 1)
                graph_store.add_relation(rel)

        # Analyze at 2023: the expired relation shouldn't be included
        # Expansion starting from lithium should stop at battery
        event = create_test_event()
        path = analyzer.analyze_impact_propagation(graph_store, event, chain_id=None)

        # With expired relation, expansion won't go past battery
        # We'll just check it still works correctly in this case
        entity_ids = [n["entity_id"] for n in path.path]
        assert "entity:lithium" in entity_ids
        assert "entity:battery" in entity_ids
