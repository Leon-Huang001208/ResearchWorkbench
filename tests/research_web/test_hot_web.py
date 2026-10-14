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


class FollowBoundaryTests(unittest.TestCase):
    def test_source_catalog_activation_requires_typed_action_and_reason(self):
        seen = []
        class Bridge:
            async def call(self, operation, *args, **kwargs):
                seen.append((operation, args))
                return {"saved": True}
        app = FastAPI();app.include_router(router);app.state.hot = Bridge()
        @app.exception_handler(HotWebError)
        async def error(request, exc):
            return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status)
        body = {"sourceId": "fed", "expectedRevision": "4", "useCatalog": True,
                "reason": "resume", "requestId": "11111111-1111-4111-8111-111111111111"}
        url = "/api/research/hot/sources/configure"
        with TestClient(app) as client:
            self.assertEqual(client.post(url, json=body).status_code, 403)
            headers = {"X-Research-User-Action": "?1"}
            for invalid in [{**body, "reason": None}, {**body, "reason": " "}, {**body, "useCatalog": 1}, {**body, "url": "https://untrusted.invalid"}]:
                self.assertEqual(client.post(url, json=invalid, headers=headers).status_code, 400)
            self.assertEqual(client.post(url, json=body, headers=headers).status_code, 200)
            self.assertEqual(seen, [("configure_source", ("fed", "4", None, None, body["requestId"], True, "resume"))])

    def test_automation_periodic_adapter_is_readonly_and_preserves_explicit_write_contract(self):
        from app.research_web.automation.routes import router as automation_router
        seen = []
        class Bridge:
            async def call(self, operation, *args, **kwargs):
                seen.append((operation, args, kwargs))
                return {"items": []}
        app = FastAPI();app.include_router(router);app.include_router(automation_router)
        app.state.hot = Bridge();app.state.research = SimpleNamespace(automations=object())
        @app.exception_handler(HotWebError)
        async def error(request, exc):
            return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status)
        identifier = "11111111-1111-4111-8111-111111111111"
        config = {"name": "Macro", "channelId": "macro", "enabled": False, "firstRunAt": "2026-10-14T08:00:00Z", "intervalSeconds": 86400, "windowSeconds": 86400, "maxEvents": 10, "timezone": "Asia/Shanghai", "sort": "importance"}
        body = {"planId": identifier, "expectedVersion": 0, "config": config, "reason": "test", "requestId": identifier}
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/research/automations/hot-brief-plans").status_code, 200)
            self.assertEqual(seen[-1][0], "periodic_plans")
            self.assertEqual(client.get(f"/api/research/automations/hot-brief-plans/{identifier}/runs").status_code, 200)
            self.assertEqual(seen[-1][0], "periodic_runs")
            url = "/api/research/automations/hot-brief-plans/configure"
            self.assertEqual(client.post(url, json=body).status_code, 403)
            headers = {"X-Research-User-Action": "?1"}
            self.assertEqual(client.post(url, json={**body, "config": {**config, "intervalSeconds": True}}, headers=headers).status_code, 400)
            self.assertEqual(client.post(url, json={**body, "config": {**config, "model": "paid"}}, headers=headers).status_code, 400)
            self.assertEqual(client.post(url, json=body, headers=headers).status_code, 200)
            self.assertEqual(seen[-1][0], "configure_periodic_plan")
            self.assertEqual(seen[-1][2]["request_id"], identifier)
            self.assertNotIn("requestId", seen[-1][1][0])

    def test_follows_read_never_mutates_and_writes_require_action_and_strict_revision(self):
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
        identifier = "11111111-1111-4111-8111-111111111111"
        body = {"followId": identifier, "expectedVersion": 0, "config": {"kind": "channel", "target": "macro", "name": "宏观", "enabled": True}, "reason": "关注", "requestId": identifier}
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/research/hot/follows").status_code, 200)
            self.assertEqual(seen[-1][0], "follows")
            self.assertEqual(client.get("/api/research/hot/follows?sql=bad").status_code, 400)
            self.assertEqual(client.post("/api/research/hot/follows/configure", json=body).status_code, 403)
            headers = {"X-Research-User-Action": "?1"}
            self.assertEqual(client.post("/api/research/hot/follows/configure", json={**body, "expectedVersion": True}, headers=headers).status_code, 400)
            self.assertEqual(client.post("/api/research/hot/follows/configure", json=body, headers=headers).status_code, 200)
            self.assertEqual(seen[-1][0], "configure_follow")
            self.assertNotIn("requestId", seen[-1][1][0])
            self.assertEqual(seen[-1][2]["request_id"], identifier)

    def test_manager_rejects_untyped_targets_before_control_and_normalizes_event_ids(self):
        from research_workbench_entrypoint.hot_manager import HotManager
        manager = object.__new__(HotManager)
        calls = []
        manager._control_projection = lambda op, params, request, valid: calls.append((op, params)) or params
        identifier = "a1111111-1111-4111-8111-111111111111"
        body = {"followId": identifier, "expectedVersion": 0, "config": {"kind": "event", "target": identifier.upper(), "name": "政策", "enabled": True}, "reason": "关注"}
        result = manager.configure_follow(body, identifier)
        self.assertEqual(result["config"]["target"], identifier)
        self.assertEqual(body["config"]["target"], identifier.upper())
        for config in [{**body["config"], "kind": []}, {**body["config"], "enabled": 1}, {**body["config"], "target": "bad"}, {**body["config"], "secret": "bad"}]:
            with self.assertRaisesRegex(RuntimeError, "hot_"):
                manager.configure_follow({**body, "config": config}, identifier)
        self.assertEqual(len(calls), 1)


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
    def test_brief_post_requires_action_and_markdown_only_reads_saved_version(self):
        seen = []
        brief = "22222222-2222-4222-8222-222222222222"
        request_id = "11111111-1111-4111-8111-111111111111"
        class Bridge:
            async def call(self, operation, *args, **kwargs):
                seen.append((operation, args, kwargs))
                if operation == "brief_export":
                    return {"briefId": brief, "version": 2, "contentHash": "a" * 64, "text": "# Frozen brief\n"}
                return {"requestId": request_id, "version": 1}
        app = FastAPI()
        app.include_router(router)
        app.state.hot = Bridge()
        @app.exception_handler(HotWebError)
        async def error(request, exc):
            return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status)
        params = {"briefId": brief, "eventIds": [brief], "expectedVersion": 0, "channelId": "macro", "cutoff": "2026-10-08T00:00:00Z", "requestId": request_id}
        with TestClient(app) as client:
            self.assertEqual(client.post("/api/research/hot/briefs", json=params).status_code, 403)
            self.assertEqual(seen, [])
            headers = {"X-Research-User-Action": "?1"}
            self.assertEqual(client.post("/api/research/hot/briefs", json={**params, "expectedVersion": True}, headers=headers).status_code, 400)
            self.assertEqual(client.post("/api/research/hot/briefs", json=params, headers=headers).status_code, 200)
            self.assertEqual(seen[-1][2]["request_id"], request_id)
            self.assertNotIn("requestId", seen[-1][1][0])
            response = client.get(f"/api/research/hot/briefs/{brief}/markdown?version=2")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.text, "# Frozen brief\n")
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertIn("-v2.md", response.headers["content-disposition"])
            self.assertEqual(seen[-1][0], "brief_export")
            self.assertEqual(seen[-1][1], (brief, 2))
            self.assertEqual(client.get(f"/api/research/hot/briefs/{brief}/markdown?sql=bad").status_code, 400)

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
