"""
事件自动生成信号服务
已批准的事件自动生成候选信号，不需要手动触发流水线
"""

from collections.abc import Sequence
from types import TracebackType
from typing import Optional, Protocol

from sqlalchemy.orm import Session

from core.contracts import AlphaSignal, CanonicalEvent
from core.observability import get_logger
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.event_repository import EventRepositoryImpl
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from services.signal_generator_service import SignalGeneratorService

logger = get_logger(__name__)


class EventRepositoryProtocol(Protocol):
    """事件仓储所需接口。"""

    def get(self, id: str) -> Optional[CanonicalEvent]:
        """根据 ID 获取事件。"""
        ...

    def list_approved_pending_signal(self, limit: int = 100) -> list[CanonicalEvent]:
        """列出已批准且尚未生成信号的事件。"""
        ...

    def mark_signal_generated(self, event_id: str) -> None:
        """标记事件已完成自动信号生成。"""
        ...


class SignalRepositoryProtocol(Protocol):
    """信号仓储所需接口。"""

    def save(self, signal: AlphaSignal) -> AlphaSignal:
        """保存信号。"""
        ...


class SignalGeneratorProtocol(Protocol):
    """信号生成器所需接口。"""

    def generate_from_event(self, event: CanonicalEvent) -> Sequence[AlphaSignal]:
        """从事件生成信号。"""
        ...


class EventAutoSignalGenerator:
    """
    事件自动信号生成器
    监听已批准的事件，自动生成候选信号
    """

    def __init__(
        self,
        event_repo: Optional[EventRepositoryProtocol] = None,
        signal_repo: Optional[SignalRepositoryProtocol] = None,
        signal_generator: Optional[SignalGeneratorProtocol] = None,
        db_session: Optional[Session] = None,
    ) -> None:
        self._owned_session: Optional[Session] = None
        if event_repo is None or signal_repo is None:
            self._owned_session = SessionLocal()

        self._transaction_session = self._owned_session or db_session
        self.event_repo = event_repo or EventRepositoryImpl(self._owned_session)
        self.signal_repo = signal_repo or SignalRepositoryImpl(self._owned_session)
        self.signal_generator = signal_generator or SignalGeneratorService()

    def process_approved_events(self) -> int:
        """
        处理所有已批准但未生成信号的事件，自动生成候选信号
        返回生成的信号数量
        """
        logger.info("Starting auto signal generation from approved events")

        approved_events = self.event_repo.list_approved_pending_signal()
        generated_count = 0

        for event in approved_events:
            try:
                logger.info(
                    f"Generating signal for approved event: {event.event_id} - {event.title}"
                )
                signals = self.signal_generator.generate_from_event(event)
                saved_count = self._save_generated_signals(event, signals)
                self.event_repo.mark_signal_generated(event.event_id)
                self._commit_transaction_session()
                generated_count += saved_count
                logger.info(
                    f"Successfully generated {len(signals)} signals for event {event.event_id}"
                )
            except Exception as e:
                self._rollback_transaction_session()
                logger.error(
                    f"Failed to generate signals for event {event.event_id}: {str(e)}",
                    exc_info=True,
                )

        logger.info(f"Auto signal generation completed, total generated: {generated_count}")
        return generated_count

    def on_event_approved(self, event_id: str) -> None:
        """
        事件审批通过后的钩子，立即触发信号生成
        """
        logger.info(f"Event {event_id} approved, triggering auto signal generation")
        try:
            event = self.event_repo.get(event_id)
            if not event:
                logger.warning(f"Event {event_id} not found")
                return

            signals = self.signal_generator.generate_from_event(event)
            self._save_generated_signals(event, signals)
            self.event_repo.mark_signal_generated(event_id)
            self._commit_transaction_session()
            logger.info(f"Generated {len(signals)} signals from approved event {event_id}")
        except Exception as e:
            self._rollback_transaction_session()
            logger.error(f"Failed to process approved event {event_id}: {str(e)}", exc_info=True)

    def __enter__(self) -> "EventAutoSignalGenerator":
        """进入自动信号生成上下文。"""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """退出自动信号生成上下文并释放自有会话。"""
        self.close()

    def close(self) -> None:
        """关闭自动创建的数据库会话。"""
        if self._owned_session is not None:
            self._owned_session.close()
            self._owned_session = None

    def _commit_transaction_session(self) -> None:
        """提交自动信号生成事务会话。"""
        if self._transaction_session is not None:
            self._transaction_session.commit()

    def _rollback_transaction_session(self) -> None:
        """回滚自动信号生成事务会话。"""
        if self._transaction_session is not None:
            self._transaction_session.rollback()

    def _save_generated_signals(self, event: CanonicalEvent, signals: Sequence[AlphaSignal]) -> int:
        """保存生成的候选信号。"""
        for signal in signals:
            signal_data = signal.model_dump()
            signal_data.update(
                {
                    "status": "candidate",
                    "metadata": {
                        **signal.metadata,
                        "generated_auto": True,
                        "generated_from_event_id": event.event_id,
                    },
                }
            )
            updated = signal.__class__(**signal_data)
            self.signal_repo.save(updated)
        return len(signals)
