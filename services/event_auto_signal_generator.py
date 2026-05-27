"""
事件自动生成信号服务
已批准的事件自动生成候选信号，不需要手动触发流水线
"""

from core.observability import get_logger
from data_layer.repositories.event_repository import EventRepositoryImpl
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from services.signal_generator_service import SignalGeneratorService

logger = get_logger(__name__)


class EventAutoSignalGenerator:
    """
    事件自动信号生成器
    监听已批准的事件，自动生成候选信号
    """

    def __init__(self, event_repo=None, signal_repo=None, signal_generator=None):
        self.event_repo = event_repo or EventRepositoryImpl()
        self.signal_repo = signal_repo or SignalRepositoryImpl()
        self.signal_generator = signal_generator or SignalGeneratorService()

    def process_approved_events(self) -> int:
        """
        处理所有已批准但未生成信号的事件，自动生成候选信号
        返回生成的信号数量
        """
        logger.info("Starting auto signal generation from approved events")

        # 查询所有已批准且未生成信号的事件
        approved_events = self.event_repo.list_approved_pending_signal()
        generated_count = 0

        for event in approved_events:
            try:
                logger.info(
                    f"Generating signal for approved event: {event.event_id} - {event.title}"
                )

                # 自动生成信号
                signals = self.signal_generator.generate_from_event(event)

                # 保存生成的信号
                for signal in signals:
                    signal.status = "candidate"  # 标记为候选信号，待审核
                    signal.generated_auto = True  # 标记为自动生成
                    signal.generated_from_event_id = event.event_id
                    self.signal_repo.save(signal)
                    generated_count += 1

                # 标记事件已生成信号
                self.event_repo.mark_signal_generated(event.event_id)

                logger.info(
                    f"Successfully generated {len(signals)} signals for event {event.event_id}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to generate signals for event {event.event_id}: {str(e)}",
                    exc_info=True,
                )

        logger.info(f"Auto signal generation completed, total generated: {generated_count}")
        return generated_count

    def on_event_approved(self, event_id: str):
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
            for signal in signals:
                signal.status = "candidate"
                signal.generated_auto = True
                signal.generated_from_event_id = event_id
                self.signal_repo.save(signal)

            self.event_repo.mark_signal_generated(event_id)
            logger.info(f"Generated {len(signals)} signals from approved event {event_id}")
        except Exception as e:
            logger.error(f"Failed to process approved event {event_id}: {str(e)}", exc_info=True)
