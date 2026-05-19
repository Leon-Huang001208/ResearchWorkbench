"""System event bus — 轻量级内存事件总线，用于 SSE 实时推送"""

import asyncio
import json
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from core.observability import get_logger

logger = get_logger(__name__)

MAX_EVENTS = 500


@dataclass
class SystemEvent:
    event_id: str
    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    id: int = 0

    def to_sse_dict(self) -> Dict[str, Any]:
        return {
            "id": self.event_id,
            "type": self.event_type,
            "payload": self.payload,
            "timestamp": self.created_at,
        }


class SystemEventBus:
    """轻量级内存事件总线，用于 SSE 实时推送和 worker heartbeat 记录

    支持可选的 JSONL 文件持久化：设置 log_path 后，事件会追加写入磁盘，
    启动时自动回放最近 MAX_EVENTS 条事件。
    """

    def __init__(self, log_path: Optional[str] = None) -> None:
        self._events: Deque[SystemEvent] = deque(maxlen=MAX_EVENTS)
        self._counter: int = 0
        self._lock: asyncio.Lock = asyncio.Lock()
        self._subscribers: List[asyncio.Queue] = []
        self._worker_heartbeat: Dict[str, float] = {}
        self._log_path: Optional[str] = log_path
        if log_path:
            self._load_history()

    # ── persistence ──────────────────────────────────────────────

    def _load_history(self) -> None:
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:  # type: ignore[arg-type]
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        event = SystemEvent(
                            event_id=data["id"],
                            event_type=data["type"],
                            payload=data.get("payload", {}),
                            created_at=data.get("timestamp", 0),
                            id=data.get("_seq", 0),
                        )
                        self._events.append(event)
                        if event.id > self._counter:
                            self._counter = event.id
                    except (json.JSONDecodeError, KeyError):
                        continue
            logger.info("Event log replayed", count=len(self._events))
        except (FileNotFoundError, OSError):
            pass

    def _append_to_log(self, event: SystemEvent) -> None:
        if not self._log_path:
            return
        try:
            os.makedirs(os.path.dirname(self._log_path), exist_ok=True)
            record = event.to_sse_dict()
            record["_seq"] = event.id
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ── public API ───────────────────────────────────────────────

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> SystemEvent:
        async with self._lock:
            self._counter += 1
            event = SystemEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                payload=payload,
                id=self._counter,
            )
            self._events.append(event)
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass
        self._append_to_log(event)
        return event

    async def get_events_after(self, after_id: Optional[str] = None) -> List[SystemEvent]:
        async with self._lock:
            if after_id is None:
                return list(self._events)[-50:]
            after_found = False
            result = []
            for e in self._events:
                if after_found:
                    result.append(e)
                elif e.event_id == after_id:
                    after_found = True
            return result

    async def subscribe(self) -> "asyncio.Queue[SystemEvent]":
        q: asyncio.Queue[SystemEvent] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.append(q)
        logger.info("SSE subscriber added", total_subscribers=len(self._subscribers))
        return q

    async def unsubscribe(self, q: "asyncio.Queue[SystemEvent]") -> None:
        async with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)
        logger.info("SSE subscriber removed", total_subscribers=len(self._subscribers))

    def record_worker_heartbeat(self, worker_name: str) -> None:
        self._worker_heartbeat[worker_name] = time.time()

    def get_worker_heartbeats(self) -> Dict[str, float]:
        return dict(self._worker_heartbeat)


event_bus = SystemEventBus(
    log_path=str(Path(__file__).resolve().parent.parent.parent / ".data" / "event_log.jsonl")
)
