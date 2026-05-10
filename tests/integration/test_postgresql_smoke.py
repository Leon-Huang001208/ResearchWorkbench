"""
Smoke test for PostgreSQL initialization and basic CRUD operations.
Skips automatically if not running against PostgreSQL.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.settings import settings
from data_layer.repositories.base import check_database_connection, ensure_schema
from data_layer.repositories.models import Entity


@pytest.mark.integration
def test_postgresql_initialization():
    """Test that we can initialize schema and do basic CRUD on PostgreSQL."""
    if not settings.DATABASE_URL.startswith("postgresql"):
        pytest.skip("Skipping PostgreSQL smoke test: not using PostgreSQL")
    
    # Check connection
    check_database_connection()
    
    # Ensure schema exists
    ensure_schema()
    
    # Create a test entity
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        # Create
        test_entity = Entity(
            entity_id="test-entity-001",
            canonical_id="TEST001",
            entity_type="stock",
            canonical_name="Test Company Inc.",
            aliases=["Test", "TC"],
            properties={"sector": "Technology"},
        )
        session.add(test_entity)
        session.commit()
        
        # Read
        found = session.get(Entity, "test-entity-001")
        assert found is not None
        assert found.canonical_name == "Test Company Inc."
        assert found.aliases == ["Test", "TC"]
        assert found.properties["sector"] == "Technology"
        
        # Update
        found.canonical_name = "Updated Test Company Inc."
        session.commit()
        
        updated = session.get(Entity, "test-entity-001")
        assert updated.canonical_name == "Updated Test Company Inc."
        
        # Delete
        session.delete(updated)
        session.commit()
        
        deleted = session.get(Entity, "test-entity-001")
        assert deleted is None
        
    print("PostgreSQL smoke test passed: all CRUD operations work correctly.")
