"""Private Host model accounting cannot be authorized by browser action headers."""
import unittest
import base64
import hashlib
import hmac
import json
import socketserver
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.research_web.hot_routes import private_router
from app.research_web.hot_service import HotWebError
from research_workbench_entrypoint.hot_manager import HotManager, rpc
from research_workbench_entrypoint.hot import HotError

SID = "00000000-0000-0000-0000-000000000001"
RUN = "00000000-0000-0000-0000-000000000002"


@contextmanager
def signed_peer(result=None, code=None, bad_proof=False):
    key = "synthetic-test-key" * 4
    captured = []
    class Peer(socketserver.BaseRequestHandler):
        def handle(self):
            raw = b""
            while b"\n" not in raw:
                raw += self.request.recv(65536)
                if len(raw) > 2097152:
                    return
            frame = json.loads(raw)
            if frame["proof"] != hmac.new(key.encode(), frame["data"].encode(), hashlib.sha256).hexdigest():
                return
            request = json.loads(base64.urlsafe_b64decode(frame["data"] + "=" * (-len(frame["data"]) % 4)))
            captured.append(request)
            response = {"protocol": "rwb-hot/v1", "id": request["id"], "ok": code is None, **({"result": result} if code is None else {"code": code})}
            data = base64.urlsafe_b64encode(json.dumps(response, separators=(",", ":")).encode()).decode().rstrip("=")
            proof = "0" * 64 if bad_proof else hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()
            self.request.sendall(json.dumps({"data": data, "proof": proof}).encode() + b"\n")
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), Peer) as server:
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
        thread.start()
        try:
            yield server.server_address[1], key, captured
        finally:
            server.shutdown()
            thread.join(timeout=1)


class HotModelBridgeTests(unittest.TestCase):
    def setUp(self):
        self.row = {"purpose": "hot_research", "hot_origin": {"runId": RUN, "instanceId": "instance", "manifestHash": "manifest"}}
        self.hot = SimpleNamespace(call=AsyncMock(return_value={"sessionId": SID, "instanceId": "instance", "evidenceManifestHash": "manifest"}))
        app = FastAPI()
        app.include_router(private_router)
        app.state.hot = self.hot
        app.state.research = SimpleNamespace(ensure_owned=AsyncMock(), store=SimpleNamespace(session=Mock(side_effect=lambda _: self.row)), datahub=SimpleNamespace(authenticate=lambda key: key == "private-test-key"))
        @app.exception_handler(HotWebError)
        async def failed(_request, error):
            return JSONResponse({"error": error.code}, status_code=error.status)
        self.client = TestClient(app)

    def test_browser_headers_cannot_reserve_and_private_binding_requires_owned_hot_session(self):
        data = {"operation": "binding", "params": {"sessionId": SID}}
        denied = self.client.post("/api/research/internal/data/hot-model", json=data, headers={"X-Research-User-Action": "?1"})
        self.assertEqual(denied.status_code, 403)
        self.hot.call.assert_not_called()
        allowed = self.client.post("/api/research/internal/data/hot-model", json=data, headers={"X-Research-Data-Key": "private-test-key"})
        self.assertEqual(allowed.json(), {"runId": RUN, "sessionId": SID})
        self.row["purpose"] = "research"
        self.assertEqual(self.client.post("/api/research/internal/data/hot-model", json=data, headers={"X-Research-Data-Key": "private-test-key"}).status_code, 403)

    def test_cross_run_is_rejected_before_budget_control(self):
        response = self.client.post("/api/research/internal/data/hot-model", json={"operation": "dispatch", "params": {"sessionId": SID, "runId": SID}}, headers={"X-Research-Data-Key": "private-test-key"})
        self.assertEqual(response.status_code, 403)
        self.hot.call.assert_not_called()

    def test_foreign_manifest_and_instance_do_not_reach_budget_control(self):
        for field in ["instanceId", "evidenceManifestHash"]:
            self.hot.call.reset_mock()
            self.hot.call.return_value = {"sessionId": SID, "instanceId": "instance", "evidenceManifestHash": "manifest", field: "foreign"}
            response = self.client.post("/api/research/internal/data/hot-model", json={"operation": "dispatch", "params": {"sessionId": SID, "runId": RUN}}, headers={"X-Research-Data-Key": "private-test-key"})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(self.hot.call.call_count, 1)

    def test_private_receipt_forwards_after_all_ownership_checks(self):
        run = {"sessionId": SID, "instanceId": "instance", "evidenceManifestHash": "manifest"}
        self.hot.call.side_effect = [run, {"state": "received"}]
        params = {"sessionId": SID, "runId": RUN, "chunks": []}
        response = self.client.post("/api/research/internal/data/hot-model", json={"operation": "receipt", "params": params}, headers={"X-Research-Data-Key": "private-test-key"})
        self.assertEqual(response.json(), {"state": "received"})
        self.assertEqual(self.hot.call.call_args.args, ("research_model", "receipt", params))

    def test_large_receipt_keeps_private_manager_control_operation(self):
        manager = HotManager(Path.cwd(), Path("/private-test-home"), object())
        with patch.object(manager, "_state", return_value={"port": 12345, "owner": {}}), patch.object(manager, "_secret", return_value="private-test-key"), patch("research_workbench_entrypoint.hot_manager.rpc", return_value={"state": "received"}) as rpc:
            value = manager.research_model("receipt", {"sessionId": SID, "runId": RUN, "chunks": [{"text": "x" * 100000}]})
            self.assertEqual(value["state"], "received")
            self.assertEqual(rpc.call_args.args[3], "research.model.receipt")
        with self.assertRaisesRegex(HotError, "hot_research_model_invalid"):
            manager.research_model("authorize", {})

    def test_real_signed_large_frames_and_hmac_boundary(self):
        owner = {"instanceId": RUN, "mode": "native", "generation": "1"}
        receipt = {"chunks": [{"type": "text-delta", "text": "x" * 100000}]}
        with signed_peer({"state": "received"}) as (port, key, captured):
            self.assertEqual(rpc(port, owner, key, "research.model.receipt", receipt), {"state": "received"})
            self.assertEqual(captured[0]["params"], receipt)
            with self.assertRaisesRegex(HotError, "request_limit"):
                rpc(port, owner, key, "ordinary", receipt)
            with self.assertRaisesRegex(HotError, "request_limit"):
                rpc(port, owner, key, "research.model.receipt", {"text": "x" * 2097152})
        saved = {"state": "reused", "response": {"chunks": [{"type": "text-delta", "text": "x" * 950000}]}}
        with signed_peer(saved) as (port, key, _):
            self.assertEqual(rpc(port, owner, key, "research.model.reserve", {}), saved)
        with signed_peer({"state": "received"}, bad_proof=True) as (port, key, _):
            with self.assertRaisesRegex(HotError, "untrusted"):
                rpc(port, owner, key, "research.model.receipt", {})

    def test_budget_error_survives_signed_manager_bridge_without_arbitrary_error_text(self):
        manager = HotManager(Path.cwd(), Path("/private-test-home"), object())
        owner = {"instanceId": RUN, "mode": "native", "generation": "1"}
        for code, expected in [("hot_model_budget_exhausted", "hot_model_budget_exhausted"), ("untrusted_vendor_text", "hot_rpc_unavailable")]:
            with signed_peer(code=code) as (port, key, _), patch.object(manager, "_state", return_value={"port": port, "owner": owner}), patch.object(manager, "_secret", return_value=key):
                with self.assertRaisesRegex(HotError, expected):
                    manager.research_model("reserve", {})
