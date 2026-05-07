"""信号仓储测试"""
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.contracts import AlphaSignal, EventAlphaSignal, TradeCandidate
from data_layer.repositories.base import Base
from data_layer.repositories.signal_repository import SignalRepositoryImpl


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


def test_save_and_get_alpha_signal(db_session):
    """测试保存和获取 Alpha 信号"""
    repo = SignalRepositoryImpl(db=db_session)

    signal = AlphaSignal(
        signal_id=str(uuid.uuid4()),
        subject_id="AAPL",
        horizon="20d",
        thesis="Bullish on earnings",
        score=0.7,
        confidence=0.6,
    )

    saved = repo.save(signal)
    assert saved.signal_id == signal.signal_id

    retrieved = repo.get(signal.signal_id)
    assert retrieved is not None
    assert retrieved.subject_id == "AAPL"


def test_save_and_get_event_alpha_signal(db_session):
    """测试保存和获取事件型 Alpha 信号"""
    repo = SignalRepositoryImpl(db=db_session)

    signal = EventAlphaSignal(
        signal_id=str(uuid.uuid4()),
        event_id="evt-123",
        event_type="earnings",
        subject_id="AAPL",
        horizon="20d",
        thesis="Bullish on earnings beat",
        score=0.8,
        confidence=0.7,
        event_time=datetime.now(timezone.utc),
        impact_path=["AAPL", "MSFT"],
        industry_impacts=["tech"],
        bullish_companies=["AAPL"],
        bearish_companies=[],
    )

    saved = repo.save(signal)
    assert saved.signal_id == signal.signal_id
    assert isinstance(saved, EventAlphaSignal)

    retrieved = repo.get(signal.signal_id)
    assert retrieved is not None
    assert retrieved.event_id == "evt-123"


def test_list_signals(db_session):
    """测试列出信号"""
    repo = SignalRepositoryImpl(db=db_session)

    for i in range(5):
        signal = AlphaSignal(
            signal_id=str(uuid.uuid4()),
            subject_id=f"AAPL-{i}",
            horizon="20d",
            thesis="test",
            score=0.5,
            confidence=0.5,
            status="research_only" if i % 2 == 0 else "candidate",
        )
        repo.save(signal)

    all_signals = repo.list()
    assert len(all_signals) == 5

    candidate_signals = repo.list(status="candidate")
    assert len(candidate_signals) == 2


def test_update_status(db_session):
    """测试更新状态"""
    repo = SignalRepositoryImpl(db=db_session)

    signal = AlphaSignal(
        signal_id=str(uuid.uuid4()),
        subject_id="AAPL",
        horizon="20d",
        thesis="test",
        score=0.5,
        confidence=0.5,
        status="research_only",
    )

    repo.save(signal)
    updated = repo.update_status(signal.signal_id, "candidate")

    assert updated is not None
    assert updated.status == "candidate"


def test_save_trade_candidate(db_session):
    """测试保存交易候选"""
    repo = SignalRepositoryImpl(db=db_session)

    signal = AlphaSignal(
        signal_id=str(uuid.uuid4()),
        subject_id="AAPL",
        horizon="20d",
        thesis="test",
        score=0.5,
        confidence=0.5,
    )
    repo.save(signal)

    candidate = TradeCandidate(
        candidate_id=str(uuid.uuid4()),
        signal_id=signal.signal_id,
        action="long",
        sizing_hint=0.1,
        risk_notes=["Market risk"],
    )

    saved = repo.save_trade_candidate(candidate)
    assert saved.candidate_id == candidate.candidate_id
