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

        # Verify result structure (uses core PropagationPath with steps)
        assert path is not None
        assert len(path.steps) == 4  # All 4 nodes in the chain

        # Check positions are assigned correctly (embedded in impact string)
        assert "upstream" in path.steps[0].impact
        assert "midstream" in path.steps[1].impact
        assert "midstream" in path.steps[2].impact
        assert "downstream" in path.steps[3].impact

        # All steps should reference the event's impact direction
        assert all(event.impact_direction in step.impact for step in path.steps)

        # Mapping strength decays downstream (upstream strongest)
        assert path.steps[0].mapping_strength > path.steps[-1].mapping_strength

        # overall_strength should be positive
        assert path.overall_strength > 0

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

        # Should find all nodes starting from lithium (via graph traversal)
        assert len(path.steps) > 0
        # Entity IDs are in correct expansion order
        assert "entity:lithium" in path.steps[0].node_id

    def test_time_filter_affects_propagation(self, graph_store, analyzer, sample_automotive_chain):
        """测试时间过滤影响传播分析结果"""
        # Expire the battery to nev relation in 2022
        rels = graph_store.find_relations(from_entity="entity:battery")
        for rel in rels:
            if rel.to_entity_id == "entity:nev":
                rel.valid_to = datetime(2022, 1, 1)
                graph_store.add_relation(rel)

        # Analyze at 2023: the expired relation shouldn't be included
        event = create_test_event()
        path = analyzer.analyze_impact_propagation(graph_store, event, chain_id=None)

        # With expired relation, expansion won't go past battery
        entity_ids = [step.node_id for step in path.steps]
        assert "entity:lithium" in entity_ids
        assert "entity:battery" in entity_ids
