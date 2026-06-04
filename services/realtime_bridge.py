"""实时行情桥接 — Cjpy subscribe() (sync thread) → SystemEventBus (async).

将 Cjpy 的同步 HTTP Streaming 订阅桥接到异步 SystemEventBus，
使浏览器可通过 SSE 接收实时行情推送。

用法:
    bridge = RealtimeBridge(codes=["SH600519"], fields=["StockName", "price"])
    bridge.start()
    # ... 行情数据通过 event_bus 以 "market.quote.cjpy" 事件推送 ...
    bridge.stop()
"""
import asyncio
import threading
import time
from typing import Any, Dict, List, Optional

from core.observability import get_logger

logger = get_logger(__name__)

# 默认订阅字段 — A 股核心行情字段
DEFAULT_QUOTE_FIELDS = [
    "StockName",
    "price",  # 最新价
    "open",
    "high",
    "low",
    "pre_close",  # 昨收
    "volume",
    "amount",
    "change",  # 涨跌额
    "changeRatio",  # 涨跌幅
    "highLimit",  # 涨停价
    "lowLimit",  # 跌停价
]


class RealtimeBridge:
    """Cjpy HTTP Streaming → async SystemEventBus 桥接器.

    在后台线程中运行 Cjpy subscribe()，通过 Subscription.get() 循环读取事件，
    经 asyncio.run_coroutine_threadsafe() 发布到 SystemEventBus。

    事件类型: market.quote.cjpy
    事件 payload: {codes, fields, data, timestamp}

    Attributes:
        codes: 订阅的证券代码列表.
        fields: 订阅的字段列表.
        running: 桥接器是否正在运行.
    """

    def __init__(
        self,
        codes: List[str],
        fields: Optional[List[str]] = None,
        poll_interval: float = 0.1,
    ):
        """初始化桥接器.

        Args:
            codes: 证券代码列表（Cjpy 格式，如 "SH600519"）.
            fields: 订阅字段列表，默认使用 DEFAULT_QUOTE_FIELDS.
            poll_interval: Subscription.get() 轮询间隔（秒）.
        """
        self.codes = codes
        self.fields = fields or DEFAULT_QUOTE_FIELDS
        self.poll_interval = poll_interval

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._subscription: Any = None
        self._error_count: int = 0
        self._event_count: int = 0
        self._started_at: Optional[float] = None
        self._last_event_at: Optional[float] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """启动实时行情桥接（后台线程）."""
        if self.running:
            logger.warning("RealtimeBridge already running")
            return

        logger.info(
            "realtime_bridge_start",
            extra={"codes": self.codes, "fields": self.fields},
        )

        self._stop_event.clear()
        self._started_at = time.time()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="realtime-bridge",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """停止实时行情桥接.

        Args:
            timeout: 等待线程结束的超时秒数.
        """
        if not self.running:
            return

        logger.info("realtime_bridge_stop", extra={"event_count": self._event_count})
        self._stop_event.set()

        # 停止 Cjpy subscription
        if self._subscription is not None:
            try:
                self._subscription.stop()
            except Exception:
                logger.debug("realtime_bridge_subscription_stop_error", exc_info=True)

        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("realtime_bridge_thread_join_timeout")

        self._thread = None

    def get_status(self) -> Dict[str, Any]:
        """获取桥接器运行状态."""
        uptime = time.time() - self._started_at if self._started_at else 0
        return {
            "running": self.running,
            "codes": self.codes,
            "fields": self.fields,
            "event_count": self._event_count,
            "error_count": self._error_count,
            "uptime_seconds": round(uptime, 1),
            "last_event_at": self._last_event_at,
            "started_at": self._started_at,
        }

    # ------------------------------------------------------------------
    # Thread loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """后台线程主循环 — 创建订阅并持续消费事件."""
        try:
            self._subscription = self._create_subscription()
            logger.info("realtime_bridge_subscription_created")

            # 消费事件循环
            while not self._stop_event.is_set():
                try:
                    event = self._subscription.get(timeout=self.poll_interval)
                    if event is not None:
                        self._handle_event(event)
                except Exception:
                    # get() 超时或其他临时错误，继续循环
                    pass

            logger.info("realtime_bridge_loop_exited")

        except Exception:
            logger.exception("realtime_bridge_thread_fatal")
        finally:
            self._subscription = None

    def _create_subscription(self) -> Any:
        """创建 Cjpy 订阅.

        Returns:
            cjpy.Subscription 对象.
        """
        from data_layer.adapters.cjpy_adapter import CjpyAdapter

        adapter = CjpyAdapter()
        return adapter.subscribe(ids=self.codes, fields=self.fields)

    def _handle_event(self, event: Any) -> None:
        """处理单个 Cjpy 行情事件，发布到 SystemEventBus.

        Args:
            event: Cjpy Subscription.get() 返回的原始事件对象.
        """
        self._last_event_at = time.time()
        self._event_count += 1

        # 序列化事件数据
        event_data = self._serialize_event(event)

        # 桥接到异步事件总线
        try:
            from services.system_event_bus import event_bus

            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    event_bus.publish(
                        event_type="market.quote.cjpy",
                        payload={
                            "codes": self.codes,
                            "fields": self.fields,
                            "data": event_data,
                            "timestamp": self._last_event_at,
                        },
                    ),
                    loop,
                )
            else:
                logger.debug("realtime_bridge_event_loop_not_running")
        except RuntimeError:
            # 没有运行中的 event loop（例如在 worker 线程中）
            logger.debug("realtime_bridge_no_event_loop", extra={"count": self._event_count})
        except Exception:
            self._error_count += 1
            if self._error_count <= 5:
                logger.exception("realtime_bridge_publish_error")
            elif self._error_count == 6:
                logger.warning(
                    "realtime_bridge_publish_errors_suppressed",
                    extra={"total_errors": self._error_count},
                )

    @staticmethod
    def _serialize_event(event: Any) -> Any:
        """将 Cjpy 事件对象序列化为 JSON 兼容结构.

        Args:
            event: Cjpy 事件对象（可能是 dict、namedtuple 或自定义对象）.

        Returns:
            JSON 兼容的 Python 对象.
        """
        if isinstance(event, dict):
            return event
        if isinstance(event, (list, tuple)):
            return list(event)
        if hasattr(event, "_asdict"):
            return event._asdict()
        if hasattr(event, "__dict__"):
            return event.__dict__
        return str(event)
