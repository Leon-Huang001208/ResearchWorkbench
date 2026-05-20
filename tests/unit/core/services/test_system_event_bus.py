"""System Event Bus 单元测试"""
import asyncio

import pytest


class TestSystemEventBus:
    """测试 SystemEventBus"""

    @pytest.mark.asyncio
    async def test_publish_and_get_events(self):
        from core.services.system_event_bus import SystemEventBus

        bus = SystemEventBus()
        await bus.publish("test_type", {"k": "v1"})
        await bus.publish("test_type", {"k": "v2"})

        events = await bus.get_events_after(None)
        assert len(events) >= 2
        assert events[-1].event_type == "test_type"
        assert events[-1].payload == {"k": "v2"}

    @pytest.mark.asyncio
    async def test_worker_heartbeat(self):
        from core.services.system_event_bus import SystemEventBus

        bus = SystemEventBus()
        bus.record_worker_heartbeat("knowledge_worker")
        heartbeats = bus.get_worker_heartbeats()
        assert "knowledge_worker" in heartbeats

    @pytest.mark.asyncio
    async def test_subscribe_and_receive(self):
        from core.services.system_event_bus import SystemEventBus

        bus = SystemEventBus()
        q = await bus.subscribe()
        await bus.publish("sub_test", {"msg": "hello"})
        try:
            event = q.get_nowait()
            assert event.event_type == "sub_test"
        except asyncio.QueueEmpty:
            pytest.fail("Expected event not received")

        await bus.unsubscribe(q)

    def test_event_to_sse_dict(self):
        from core.services.system_event_bus import SystemEvent, SystemEventBus

        SystemEventBus()
        e = SystemEvent(event_id="e1", event_type="t", payload={"x": 1})
        d = e.to_sse_dict()
        assert d["id"] == "e1"
        assert d["type"] == "t"
        assert d["payload"] == {"x": 1}
