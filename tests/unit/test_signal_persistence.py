"""集成测试：SignalService 持久化——信号跨请求持久存续"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data_layer.repositories.base import Base
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from services.signal_service import SignalService


@pytest.fixture(scope="function")
def db_session():
    """创建 SQLite 内存数据库会话"""
    engine = create_engine("sqlite:///:memory:")
    # 确保所有 ORM 模型已注册
    import data_layer.repositories.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


class TestSignalPersistence:
    """测试 SignalService 通过 SignalRepositoryImpl 实现持久化"""

    def test_create_and_retrieve_signal_across_sessions(self, db_session):
        """创建信号后，通过新的 Service 实例（新 DB session）能获取到"""
        # 第一个 session：创建信号
        repo1 = SignalRepositoryImpl(db_session)
        service1 = SignalService(repository=repo1)
        signal = service1.create_signal(
            subject_id="600000.SH",
            thesis="黄金看涨",
            horizon="20d",
            score=0.8,
            confidence=0.7,
        )
        signal_id = signal.signal_id
        db_session.commit()

        # 模拟新请求：新 DB session
        engine = db_session.get_bind()
        new_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
        try:
            repo2 = SignalRepositoryImpl(new_session)
            service2 = SignalService(repository=repo2)
            retrieved = service2.get_signal(signal_id)
            assert retrieved is not None
            assert retrieved.signal_id == signal_id
            assert retrieved.subject_id == "600000.SH"
            assert retrieved.thesis == "黄金看涨"
            assert retrieved.score == 0.8
        finally:
            new_session.close()

    def test_list_signals_returns_persisted_signals(self, db_session):
        """list 能返回之前创建的信号"""
        repo = SignalRepositoryImpl(db_session)
        service = SignalService(repository=repo)

        # 创建多个信号
        service.create_signal(
            subject_id="600000.SH",
            thesis="黄金看涨",
            horizon="20d",
            score=0.8,
            confidence=0.7,
        )
        service.create_signal(
            subject_id="000001.SZ",
            thesis="银行看跌",
            horizon="60d",
            score=0.3,
            confidence=0.4,
        )
        db_session.commit()

        # 新 session 查询
        engine = db_session.get_bind()
        new_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
        try:
            repo2 = SignalRepositoryImpl(new_session)
            service2 = SignalService(repository=repo2)
            signals = service2.list_signals()
            assert len(signals) == 2
            subjects = {s.subject_id for s in signals}
            assert "600000.SH" in subjects
            assert "000001.SZ" in subjects
        finally:
            new_session.close()

    def test_list_signals_with_status_filter(self, db_session):
        """list 支持按状态过滤"""
        repo = SignalRepositoryImpl(db_session)
        service = SignalService(repository=repo)

        service.create_signal(
            subject_id="600000.SH",
            thesis="信号A",
            horizon="20d",
            score=0.8,
            confidence=0.7,
            status="research_only",
        )
        service.create_signal(
            subject_id="000001.SZ",
            thesis="信号B",
            horizon="60d",
            score=0.9,
            confidence=0.8,
            status="candidate",
        )
        db_session.commit()

        engine = db_session.get_bind()
        new_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
        try:
            repo2 = SignalRepositoryImpl(new_session)
            service2 = SignalService(repository=repo2)

            research_only = service2.list_signals(status="research_only")
            assert len(research_only) == 1
            assert research_only[0].status == "research_only"

            candidates = service2.list_signals(status="candidate")
            assert len(candidates) == 1
            assert candidates[0].status == "candidate"
        finally:
            new_session.close()

    def test_promote_signal_persists(self, db_session):
        """信号状态升级持久化"""
        repo = SignalRepositoryImpl(db_session)
        service = SignalService(repository=repo)

        signal = service.create_signal(
            subject_id="600000.SH",
            thesis="测试升级",
            horizon="20d",
            score=0.8,
            confidence=0.7,
            status="research_only",
        )
        signal_id = signal.signal_id
        db_session.commit()

        # 升级
        promoted = service.promote_signal(signal_id, new_status="candidate")
        assert promoted is not None
        assert promoted.status == "candidate"
        db_session.commit()

        # 新 session 验证
        engine = db_session.get_bind()
        new_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
        try:
            repo2 = SignalRepositoryImpl(new_session)
            service2 = SignalService(repository=repo2)
            retrieved = service2.get_signal(signal_id)
            assert retrieved is not None
            assert retrieved.status == "candidate"
        finally:
            new_session.close()

    def test_signal_not_found_after_no_persist(self, db_session):
        """没有 repository 的 SignalService 不持久化（回归测试）"""
        # 无 repository，使用内存 dict
        service = SignalService(repository=None)
        signal = service.create_signal(
            subject_id="600000.SH",
            thesis="内存信号",
            horizon="20d",
            score=0.5,
            confidence=0.5,
        )
        # 同一个 service 实例可以获取
        assert service.get_signal(signal.signal_id) is not None

        # 新 service 实例获取不到（内存不共享）
        service2 = SignalService(repository=None)
        assert service2.get_signal(signal.signal_id) is None
