"""Agent 观点仓储测试"""
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cognitive_agents.contracts import AgentView, BlackboardConflict
from data_layer.repositories.base import Base
from data_layer.repositories.agent_view_repository import AgentViewRepositoryImpl


@pytest.fixture(scope="function")
def db_session():
    """测试数据库会话"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_save_and_list_agent_view(db_session):
    """测试保存和列出 Agent 观点"""
    repo = AgentViewRepositoryImpl(db=db_session)

    view = AgentView(
        view_id=str(uuid.uuid4()),
        agent_name="BullAgent",
        agent_role="bull",
        target_id="AAPL",
        view="bullish",
        thesis="Strong earnings",
        confidence=0.8,
    )

    saved = repo.save(view)
    assert saved.view_id == view.view_id

    views = repo.list(target_id="AAPL")
    assert len(views) == 1
    assert views[0].agent_name == "BullAgent"


def test_save_and_list_conflict(db_session):
    """测试保存和列出冲突"""
    repo = AgentViewRepositoryImpl(db=db_session)

    conflict = BlackboardConflict(
        conflict_id=str(uuid.uuid4()),
        target_id="AAPL",
        view_ids=["view-1", "view-2"],
        summary="Bull vs Bear",
        severity="high",
        confidence=0.9,
    )

    saved = repo.save_conflict(conflict)
    assert saved.conflict_id == conflict.conflict_id

    conflicts = repo.list_conflicts(target_id="AAPL")
    assert len(conflicts) == 1
    assert conflicts[0].severity == "high"
