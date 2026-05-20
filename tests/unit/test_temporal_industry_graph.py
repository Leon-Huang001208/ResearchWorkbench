"""Test the temporal industry graph implementation"""
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from core.contracts.events import CanonicalEvent
from knowledge_layer.graph_projection.contracts import (
    IndustryChain,
    PropagationPath,
    RelationshipType,
    SupplyChainPosition,
    TemporalRelation,
)
from knowledge_layer.graph_projection.graph_store import IndustryGraphStore
from knowledge_layer.graph_projection.propagation import PropagationAnalyzer
from knowledge_layer.graph_projection.repository import GraphRepository


class TestTemporalRelationContract:
    """Test the Pydantic contracts"""

    def test_valid_temporal_relation(self):
        """Test that a valid temporal relation passes validation"""
        relation = TemporalRelation(
            relation_id="rel_001",
            from_entity_id="entity_001",
            to_entity_id="entity_002",
            relationship_type=RelationshipType.SUPPLIES,
            strength=0.8,
            industry="semiconductor",
        )
        assert relation.relation_id == "rel_001"
        assert relation.relationship_type == RelationshipType.SUPPLIES
        assert 0 <= relation.strength <= 1

    def test_strength_out_of_range(self):
        """Test that strength out of range is rejected by validation"""
        with pytest.raises(ValueError):
            TemporalRelation(
                relation_id="rel_001",
                from_entity_id="e1",
                to_entity_id="e2",
                relationship_type=RelationshipType.SUPPLIES,
                strength=1.5,
            )


class TestIndustryGraphStore:
    """Test the in-memory graph store"""

    def test_add_get_remove_relation(self):
        store = IndustryGraphStore()
        relation = TemporalRelation(
            relation_id="rel_001",
            from_entity_id="e1",
            to_entity_id="e2",
            relationship_type=RelationshipType.SUPPLIES,
            strength=0.7,
        )

        added = store.add_relation(relation)
        assert added == relation

        retrieved = store.get_relation("rel_001")
        assert retrieved is not None
        assert retrieved.relation_id == "rel_001"

        removed = store.remove_relation("rel_001")
        assert removed is True
        assert store.get_relation("rel_001") is None

    def test_time_filtering(self):
        store = IndustryGraphStore()
        now = datetime.now(UTC)

        # Valid from past to future
        rel1 = TemporalRelation(
            relation_id="rel_active",
            from_entity_id="e1",
            to_entity_id="e2",
            relationship_type=RelationshipType.SUPPLIES,
            strength=0.5,
            valid_from=now.replace(year=now.year - 1),
            valid_to=None,
        )
        # Expired relation
        rel2 = TemporalRelation(
            relation_id="rel_expired",
            from_entity_id="e1",
            to_entity_id="e3",
            relationship_type=RelationshipType.SUPPLIES,
            strength=0.5,
            valid_from=now.replace(year=now.year - 2),
            valid_to=now.replace(year=now.year - 1),
        )
        store.add_relation(rel1)
        store.add_relation(rel2)

        results = store.find_relations(at_time=now)
        assert len(results) == 1
        assert results[0].relation_id == "rel_active"

    def test_get_upstream_downstream(self):
        store = IndustryGraphStore()
        # e1 supplies e2, e2 supplies e3
        rel1 = TemporalRelation(
            relation_id="rel1",
            from_entity_id="e1",
            to_entity_id="e2",
            relationship_type=RelationshipType.SUPPLIES,
            strength=0.8,
        )
        rel2 = TemporalRelation(
            relation_id="rel2",
            from_entity_id="e2",
            to_entity_id="e3",
            relationship_type=RelationshipType.SUPPLIES,
            strength=0.8,
        )
        store.add_relation(rel1)
        store.add_relation(rel2)

        downstream = store.get_downstream("e1")
        assert len(downstream) == 1
        assert downstream[0].to_entity_id == "e2"

        upstream = store.get_upstream("e2")
        assert len(upstream) == 1
        assert upstream[0].from_entity_id == "e1"

    def test_shortest_path(self):
        store = IndustryGraphStore()
        # Create chain e1 -> e2 -> e3
        rel1 = TemporalRelation(
            relation_id="rel1",
            from_entity_id="e1",
            to_entity_id="e2",
            relationship_type=RelationshipType.SUPPLIES,
            strength=0.8,
        )
        rel2 = TemporalRelation(
            relation_id="rel2",
            from_entity_id="e2",
            to_entity_id="e3",
            relationship_type=RelationshipType.SUPPLIES,
            strength=0.8,
        )
        store.add_relation(rel1)
        store.add_relation(rel2)

        path = store.shortest_path("e1", "e3")
        assert path == ["e1", "e2", "e3"]


class TestPropagationAnalyzer:
    """Test the propagation analyzer"""

    def test_analyze_propagation_with_chain(self):
        store = IndustryGraphStore()
        analyzer = PropagationAnalyzer()

        # Create a test chain
        chain = IndustryChain(
            chain_id="chain_001",
            name="Semiconductor Supply Chain",
            industry="semiconductor",
            nodes=["mining", "wafer_fabrication", "chip_design", "devices"],
            relations=["r1", "r2", "r3"],
        )
        store.add_chain(chain)

        event = CanonicalEvent(
            event_id="event_001",
            event_type="export_restriction",
            source_type="news",
            source_name="TestSource",
            title="Export restrictions on semiconductor equipment",
            summary="Export restrictions on semiconductor equipment",
            impact_direction="negative",
            confidence=0.9,
            source_doc_id="doc_001",
        )

        result = analyzer.analyze_impact_propagation(store, event, chain_id="chain_001")
        assert isinstance(result, PropagationPath)
        assert len(result.path) == 4
        # First node should be upstream
        assert result.path[0]["position"] == SupplyChainPosition.UPSTREAM
        # Last node should be downstream
        assert result.path[-1]["position"] == SupplyChainPosition.DOWNSTREAM
        # Lag should increase along path
        assert result.path[0]["expected_lag_days"] < result.path[-1]["expected_lag_days"]


class TestGraphRepositorySQLite:
    """Test the repository with in-memory SQLite"""

    @pytest.fixture
    def repo(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine("sqlite:///:memory:")
        # Create tables manually for SQLite test
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                CREATE TABLE temporal_relation (
                    relation_id TEXT PRIMARY KEY,
                    from_entity_id TEXT NOT NULL,
                    to_entity_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    strength NUMERIC NOT NULL,
                    valid_from TIMESTAMP,
                    valid_to TIMESTAMP,
                    chain_position TEXT,
                    industry TEXT,
                    metadata JSON DEFAULT ('{}'),
                    evidence_refs JSON DEFAULT ('[]'),
                    created_at TIMESTAMP
                )
            """
                )
            )
            conn.execute(
                text(
                    """
                CREATE TABLE industry_chain (
                    chain_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    industry TEXT NOT NULL,
                    nodes JSON NOT NULL,
                    relations JSON NOT NULL,
                    as_of TIMESTAMP,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """
                )
            )
            conn.commit()

        Session = sessionmaker(bind=engine)
        session = Session()
        repository = GraphRepository(db=session)
        return repository

    def test_add_and_get_relation(self, repo):
        relation = TemporalRelation(
            relation_id=f"test_{uuid4().hex[:8]}",
            from_entity_id="e1",
            to_entity_id="e2",
            relationship_type=RelationshipType.SUPPLIES,
            strength=0.75,
            industry="chemicals",
        )

        repo.add_temporal_relation(relation)
        retrieved = repo.get_temporal_relation(relation.relation_id)

        assert retrieved is not None
        assert retrieved.relation_id == relation.relation_id
        assert retrieved.from_entity_id == relation.from_entity_id
        assert abs(retrieved.strength - 0.75) < 0.001

    def test_find_relations_by_industry(self, repo):
        relation1 = TemporalRelation(
            relation_id=f"rel1_{uuid4().hex[:8]}",
            from_entity_id="e1",
            to_entity_id="e2",
            relationship_type=RelationshipType.SUPPLIES,
            strength=0.5,
            industry="energy",
        )
        relation2 = TemporalRelation(
            relation_id=f"rel2_{uuid4().hex[:8]}",
            from_entity_id="e3",
            to_entity_id="e4",
            relationship_type=RelationshipType.SUPPLIES,
            strength=0.5,
            industry="semiconductor",
        )
        repo.add_temporal_relation(relation1)
        repo.add_temporal_relation(relation2)

        energy_rels = repo.find_relations(industry="energy")
        assert len(energy_rels) == 1
        assert energy_rels[0].industry == "energy"
