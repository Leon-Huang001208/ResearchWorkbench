"""Test for industry chain mapping and thesis generation"""

import pytest

from core.contracts.events import CanonicalEvent
from core.contracts.industry_chain import (
    IndustryGraph,
    IndustryNode,
    MappingStrength,
    PropagationPath,
    ThesisCard,
)
from services.thesis_generator_service import DATA_DIR, ThesisGeneratorService


@pytest.fixture
def industry_graph_assets() -> None:
    """Require the local industry graph dataset for data-backed service tests."""
    if not DATA_DIR.is_dir():
        pytest.skip("requires the unversioned data/industry_graphs dataset")


def test_mapping_strength_values():
    """Test that mapping strength values are correct"""
    assert MappingStrength.DIRECT_IMPACT == 0.9
    assert MappingStrength.STRONG_LINKAGE == 0.7
    assert MappingStrength.SECONDARY_LINKAGE == 0.5
    assert MappingStrength.THEMATIC_ASSOCIATION == 0.3


def test_industry_graph_get_node():
    """Test getting node from graph"""
    node1 = IndustryNode(node_id="n1", name="Node 1", industry="test")
    node2 = IndustryNode(node_id="n2", name="Node 2", industry="test")

    graph = IndustryGraph(
        graph_id="test",
        name="Test Graph",
        description="Test",
        nodes=[node1, node2],
        edges=[],
    )

    assert graph.get_node("n1") == node1
    assert graph.get_node("n2") == node2
    assert graph.get_node("n3") is None


def test_propagation_path_calculate_overall_strength():
    """Test overall strength calculation"""
    from core.contracts.industry_chain import PropagationStep

    path = PropagationPath()
    path.steps = [
        PropagationStep(
            node_id="n1", node_name="N1", impact="start", mapping_strength=0.9, symbol=None
        ),
        PropagationStep(
            node_id="n2", node_name="N2", impact="test", mapping_strength=0.8, symbol="123"
        ),
    ]

    # 0.9 * 0.8 = 0.72 → sqrt(0.72) ≈ 0.8485
    overall = path.calculate_overall_strength()
    assert 0.84 < overall < 0.85


def test_service_loads_graphs(industry_graph_assets):
    """Test that service loads predefined graphs correctly"""
    service = ThesisGeneratorService()
    graphs = service.list_graphs()

    assert len(graphs) == 3
    graph_ids = [g["graph_id"] for g in graphs]
    assert "ai_compute_chain" in graph_ids
    assert "semiconductor_localization" in graph_ids
    assert "new_energy_upstream" in graph_ids

    # Check each graph has nodes
    for g in graphs:
        assert g["node_count"] > 0


def test_generate_theses_from_event(industry_graph_assets):
    """Test generating theses from an event"""
    service = ThesisGeneratorService()

    # Create test event
    event = CanonicalEvent(
        event_id="test_event_001",
        event_type="industry_shock",
        source_type="news",
        source_name="Test Source",
        title="AI demand surges",
        confidence=0.8,
        impacted_industries=["AI", "服务器"],
        summary="AI大模型需求爆发带动GPU服务器需求增长",
        impact_direction="positive",
    )

    theses = service.generate_theses_from_event(event, graph_id="ai_compute_chain")

    assert len(theses) > 0

    # Check that all theses have required fields
    for thesis in theses:
        assert isinstance(thesis, ThesisCard)
        assert thesis.thesis_id
        assert thesis.event_summary
        assert thesis.target_symbol
        assert thesis.target_name
        assert 0 <= thesis.overall_confidence <= 1
        assert len(thesis.propagation_path.steps) > 0


def test_ai_chain_has_company_nodes(industry_graph_assets):
    """Test that AI compute chain has expected companies"""
    service = ThesisGeneratorService()
    graph = service.get_graph("ai_compute_chain")

    assert graph is not None

    # Count company nodes
    company_nodes = [n for n in graph.nodes if n.is_company]
    assert len(company_nodes) == 4

    symbols = [n.symbol for n in company_nodes]
    assert "603019" in symbols  # 中科曙光
    assert "002158" in symbols  # 汉钟精机
