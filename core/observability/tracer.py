import logging
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterator

logger = logging.getLogger(__name__)


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    start_time: datetime
    end_time: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"

    @property
    def duration(self) -> timedelta | None:
        if self.end_time:
            return self.end_time - self.start_time
        return None


class Tracer:
    """分布式追踪器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> "Tracer":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._spans: dict[str, Span] = {}
        self._thread_local = threading.local()
        self._initialized = True

    def _get_current_span_id(self) -> str | None:
        """获取当前线程的 span_id 栈"""
        if not hasattr(self._thread_local, "span_stack"):
            self._thread_local.span_stack = []
        return self._thread_local.span_stack[-1] if self._thread_local.span_stack else None

    def _push_span_id(self, span_id: str) -> None:
        """推入 span_id 到栈"""
        if not hasattr(self._thread_local, "span_stack"):
            self._thread_local.span_stack = []
        self._thread_local.span_stack.append(span_id)

    def _pop_span_id(self) -> str | None:
        """从栈弹出 span_id"""
        if hasattr(self._thread_local, "span_stack") and self._thread_local.span_stack:
            result: str = self._thread_local.span_stack.pop()
            return result
        return None

    def start_span(self, name: str, trace_id: str | None = None) -> str:
        """开始一个 span"""
        span_id = str(uuid.uuid4())
        parent_span_id = self._get_current_span_id()

        if trace_id is None:
            trace_id = parent_span_id.split("-")[0] if parent_span_id else str(uuid.uuid4())

        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            start_time=datetime.utcnow(),
        )
        self._spans[span_id] = span
        self._push_span_id(span_id)

        logger.debug(
            "span started",
            extra={"span_name": name, "trace_id": trace_id, "span_id": span_id},
        )
        return span_id

    def end_span(self, span_id: str | None = None, status: str = "ok") -> None:
        """结束一个 span"""
        if span_id is None:
            span_id = self._pop_span_id()
        if span_id is None:
            return

        span = self._spans.get(span_id)
        if span:
            span.end_time = datetime.utcnow()
            span.status = status
            logger.debug(
                "span ended",
                extra={
                    "span_name": span.name,
                    "trace_id": span.trace_id,
                    "span_id": span_id,
                    "duration": span.duration,
                },
            )

    def set_attribute(self, key: str, value: Any, span_id: str | None = None) -> None:
        """设置 span 属性"""
        if span_id is None:
            span_id = self._get_current_span_id()
        if span_id is None:
            return

        span = self._spans.get(span_id)
        if span:
            span.attributes[key] = value

    def get_span(self, span_id: str) -> Span | None:
        """获取 span"""
        return self._spans.get(span_id)

    @contextmanager
    def span(self, name: str, trace_id: str | None = None) -> Iterator[Span]:
        """上下文管理器创建 span"""
        span_id = self.start_span(name, trace_id)
        span = self._spans[span_id]
        try:
            yield span
            self.end_span(span_id, "ok")
        except Exception as e:
            self.set_attribute("error", str(e), span_id)
            self.end_span(span_id, "error")
            raise
