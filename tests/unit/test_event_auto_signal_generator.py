"""事件自动信号生成测试。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.contracts import AlphaSignal, CanonicalEvent, EventAlphaSignal
from data_layer.repositories.base import Base
from data_layer.repositories.event_repository import EventRepositoryImpl
from data_layer.repositories.models import AlphaSignalDB, SourceDocument
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from services.event_auto_signal_generator import EventAutoSignalGenerator
from services.signal_generator_service import SignalGeneratorService


class FakeEventRepository:
    """自动信号生成测试用事件仓储。"""

    def __init__(self, events: list[CanonicalEvent]):
        self.events = {event.event_id: event for event in events}
        self.marked_event_ids: list[str] = []

    def get(self, id: str) -> CanonicalEvent | None:
        return self.events.get(id)

    def list_approved_pending_signal(self, limit: int = 100) -> list[CanonicalEvent]:
        return list(self.events.values())[:limit]

    def mark_signal_generated(self, event_id: str) -> None:
        self.marked_event_ids.append(event_id)


class FakeSignalRepository:
    """自动信号生成测试用信号仓储。"""

    def __init__(self) -> None:
        self.saved: list[AlphaSignal] = []

    def save(self, signal: AlphaSignal) -> AlphaSignal:
        self.saved.append(signal)
        return signal


class FakeSignalGenerator:
    """自动信号生成测试用生成器。"""

    def __init__(self, signals: list[AlphaSignal]):
        self.signals = signals

    def generate_from_event(self, event: CanonicalEvent) -> list[AlphaSignal]:
        return self.signals


class FailingMarkEventRepository(FakeEventRepository):
    """标记信号生成时失败的事件仓储。"""

    def mark_signal_generated(self, event_id: str) -> None:
        super().mark_signal_generated(event_id)
        if event_id == "evt-fail":
            raise RuntimeError("mark failed")


@pytest.fixture
def sample_event() -> CanonicalEvent:
    """构造测试用事件。"""
    return CanonicalEvent(
        event_id="evt-auto-001",
        event_type="policy",
        source_type="news",
        source_name="test-source",
        title="航天产业政策发布",
        summary="政策利好航天产业链",
        impact_direction="positive",
        confidence=0.8,
        novelty_score=0.6,
        impacted_industries=["航天"],
        impacted_symbols=["159267.SZ", "600879.SH"],
        source_doc_id="doc-auto-001",
        reviewer_status="approved",
    )


def test_signal_generator_builds_event_signals(sample_event: CanonicalEvent) -> None:
    """SignalGeneratorService 为每个受影响标的生成候选事件信号。"""
    generator = SignalGeneratorService()

    signals = generator.generate_from_event(sample_event)

    assert len(signals) == 2
    assert all(isinstance(signal, EventAlphaSignal) for signal in signals)
    assert {signal.subject_id for signal in signals} == {"159267.SZ", "600879.SH"}
    assert all(signal.status == "candidate" for signal in signals)
    assert signals[0].metadata["generated_auto"] is True
    assert signals[0].metadata["generated_from_event_id"] == "evt-auto-001"
    assert signals[0].score == pytest.approx(0.74)


def test_auto_generator_saves_candidate_signal_without_mutating_original(
    sample_event: CanonicalEvent,
) -> None:
    """自动生成器保存补充元数据后的 copy，不就地修改原信号。"""
    original_signal = AlphaSignal(
        signal_id="sig-001",
        subject_id="159267.SZ",
        horizon="20d",
        thesis="测试信号",
        score=0.5,
        confidence=0.5,
        metadata={"source": "unit-test"},
    )
    event_repo = FakeEventRepository([sample_event])
    signal_repo = FakeSignalRepository()
    generator = EventAutoSignalGenerator(
        event_repo=event_repo,
        signal_repo=signal_repo,
        signal_generator=FakeSignalGenerator([original_signal]),
    )

    generated_count = generator.process_approved_events()

    assert generated_count == 1
    assert event_repo.marked_event_ids == [sample_event.event_id]
    assert len(signal_repo.saved) == 1
    saved_signal = signal_repo.saved[0]
    assert saved_signal.status == "candidate"
    assert saved_signal.metadata == {
        "source": "unit-test",
        "generated_auto": True,
        "generated_from_event_id": sample_event.event_id,
    }
    assert original_signal.metadata == {"source": "unit-test"}


def test_auto_generator_does_not_count_failed_event(
    sample_event: CanonicalEvent,
) -> None:
    """单个事件失败时不把已回滚的信号计入生成数量。"""
    failed_event = sample_event.model_copy(update={"event_id": "evt-fail"})
    signal = AlphaSignal(
        signal_id="sig-fail",
        subject_id="159267.SZ",
        horizon="20d",
        thesis="测试信号",
        score=0.5,
        confidence=0.5,
    )
    event_repo = FailingMarkEventRepository([failed_event])
    signal_repo = FakeSignalRepository()
    generator = EventAutoSignalGenerator(
        event_repo=event_repo,
        signal_repo=signal_repo,
        signal_generator=FakeSignalGenerator([signal]),
    )

    generated_count = generator.process_approved_events()

    assert generated_count == 0
    assert len(signal_repo.saved) == 1


def test_auto_generator_preserves_event_signal_fields(
    sample_event: CanonicalEvent,
) -> None:
    """保存候选信号时保留 EventAlphaSignal 的事件字段。"""
    original_signal = SignalGeneratorService().generate_from_event(sample_event)[0]
    event_repo = FakeEventRepository([sample_event])
    signal_repo = FakeSignalRepository()
    generator = EventAutoSignalGenerator(
        event_repo=event_repo,
        signal_repo=signal_repo,
        signal_generator=FakeSignalGenerator([original_signal]),
    )

    generated_count = generator.process_approved_events()

    assert generated_count == 1
    saved_signal = signal_repo.saved[0]
    assert isinstance(saved_signal, EventAlphaSignal)
    assert saved_signal.event_id == original_signal.event_id
    assert saved_signal.event_type == original_signal.event_type
    assert saved_signal.impact_path == original_signal.impact_path
    assert saved_signal.status == "candidate"


def test_event_repository_filters_generated_approved_events(
    sample_event: CanonicalEvent,
) -> None:
    """事件仓储只返回已批准且尚未标记 signal_generated 的事件。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        session.add(
            SourceDocument(
                doc_id=sample_event.source_doc_id,
                source_type="news",
                title=sample_event.title,
                source_name="test-source",
                content_hash="hash-auto-001",
                parser_version="v1",
                object_uri="mem://doc-auto-001",
            )
        )
        session.commit()
        repo = EventRepositoryImpl(db=session)
        repo.save(sample_event)

        pending_events = repo.list_approved_pending_signal()
        assert [event.event_id for event in pending_events] == [sample_event.event_id]

        repo.mark_signal_generated(sample_event.event_id)
        assert repo.list_approved_pending_signal() == []
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_auto_generator_rolls_back_db_signal_when_mark_fails(
    sample_event: CanonicalEvent,
) -> None:
    """标记事件失败时，真实数据库会话回滚已保存信号。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        session.add(
            SourceDocument(
                doc_id=sample_event.source_doc_id,
                source_type="news",
                title=sample_event.title,
                source_name="test-source",
                content_hash="hash-auto-rollback",
                parser_version="v1",
                object_uri="mem://doc-auto-rollback",
            )
        )
        session.commit()
        failed_event = sample_event.model_copy(update={"event_id": "evt-fail"})
        event_repo = FailingMarkEventRepository([failed_event])
        generator = EventAutoSignalGenerator(
            event_repo=event_repo,
            signal_repo=SignalRepositoryImpl(session),
            signal_generator=FakeSignalGenerator(
                [
                    AlphaSignal(
                        signal_id="sig-rollback",
                        subject_id="159267.SZ",
                        horizon="20d",
                        thesis="测试信号",
                        score=0.5,
                        confidence=0.5,
                    )
                ]
            ),
            db_session=session,
        )

        generated_count = generator.process_approved_events()

        assert generated_count == 0
        assert session.query(AlphaSignalDB).filter_by(signal_id="sig-rollback").first() is None
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
