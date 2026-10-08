"""Hot Host boundaries use stdlib tests; no running model or database required."""

import asyncio
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.research_web.hot_routes import router
from app.research_web.hot_service import HotWebError, HotWebService


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_status_creates_nothing_and_does_not_resolve_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve() / "absent"
            bridge = HotWebService(Path("/project"), home, manager_factory=lambda: self.fail("credentials factory called"))
            result = await bridge.call("status")
            self.assertEqual(result["state"], "disabled")
            self.assertFalse(home.exists())
            await bridge.close()

    async def test_timeout_holds_capacity_until_actual_thread_completion(self):
        release = threading.Event()
        class Manager:
            def events(self, params):
                release.wait(2)
                return {"items": []}
        bridge = HotWebService(Path("/project"), Path("/home"), manager_factory=Manager, capacity=1, deadline=0.02)
        try:
            with self.assertRaisesRegex(HotWebError, "响应超时"):
                await bridge.call("events", {})
            with self.assertRaisesRegex(HotWebError, "请求较多"):
                await bridge.call("events", {})
            release.set()
            await asyncio.sleep(0.02)
            self.assertEqual(await bridge.call("events", {}), {"items": []})
        finally:
            release.set()
            await bridge.close()

    async def test_mutation_timeout_returns_original_request_id(self):
        release = threading.Event()
        class Manager:
            def correct_event(self, *args):
                release.wait(2)
                return {"source": {}}
        bridge = HotWebService(Path("/project"), Path("/home"), manager_factory=Manager, deadline=0.02)
        try:
            value = await bridge.call("correct_event", {}, "reason", "opaque-id", request_id="opaque-id")
            self.assertEqual(value["state"], "outcome_unknown")
            self.assertEqual(value["requestId"], "opaque-id")
        finally:
            release.set()
            await bridge.close()

    async def test_waiting_mutation_is_not_admitted_after_close(self):
        entered, release = threading.Event(), threading.Event()
        writes = []
        class Manager:
            def events(self, params):
                entered.set()
                release.wait(2)
                return {"items": []}
            def start(self):
                writes.append("start")
        bridge = HotWebService(Path("/project"), Path("/home"), manager_factory=Manager, capacity=1, deadline=2)
        first = asyncio.create_task(bridge.call("events", {}))
        await asyncio.to_thread(entered.wait, 1)
        waiting = asyncio.create_task(bridge.call("start"))
        await asyncio.sleep(0.01)
        closing = asyncio.create_task(bridge.close())
        await asyncio.sleep(0.01)
        release.set()
        await first
        with self.assertRaisesRegex(HotWebError, "已关闭"):
            await waiting
        await closing
        self.assertEqual(writes, [])


class RouteTests(unittest.TestCase):
    def test_read_projection_and_explicit_control_body_are_bounded(self):
        seen = []
        class Bridge:
            async def call(self, operation, *args, **kwargs):
                seen.append((operation, args, kwargs))
                return {"items": []}
        app = FastAPI()
        app.include_router(router)
        app.state.hot = Bridge()
        @app.exception_handler(HotWebError)
        async def error(request, exc):
            return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status)
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/research/hot/events?channelId=gold&limit=5").status_code, 200)
            self.assertEqual(seen[0][1][0], {"channelId": "gold", "limit": 5})
            request_id = "11111111-1111-4111-8111-111111111111"
            payload = {"channelId": "gold", "expectedVersion": 0, "config": {}, "requestId": request_id}
            self.assertEqual(client.post("/api/research/hot/channels/configure", json=payload).status_code, 403)
            headers = {"X-Research-User-Action": "?1"}
            self.assertEqual(client.post("/api/research/hot/channels/configure", json=payload, headers=headers).status_code, 200)
            self.assertEqual(seen[-1][2]["request_id"], request_id)
            self.assertEqual(client.post("/api/research/hot/events/correct", content=b"x" * 65537, headers={**headers, "Content-Type": "application/json"}).status_code, 413)
            self.assertEqual(client.get("/api/research/hot/events?sql=select").status_code, 400)
            self.assertEqual(len(seen), 2)
