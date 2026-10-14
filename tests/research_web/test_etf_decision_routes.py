"""Real local HTTP/SQLite boundary tests; no data-provider acceptance claim."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research_web.portfolio_decisions.routes import router
from tests.research_web.test_etf_decisions import sample


class RouteAcceptance(unittest.TestCase):
    def test_explicit_action_bounded_input_retry_and_invalid_admission(self):
        with TemporaryDirectory() as directory:
            app = FastAPI()
            app.include_router(router)
            app.state.research = SimpleNamespace(store=SimpleNamespace(root=Path(directory)))
            with TestClient(app) as client:
                self.assertEqual(
                    client.get("/api/research/portfolio-decisions/runs").json(), {"items": []}
                )
                self.assertFalse((Path(directory) / "portfolio-decisions").exists())
                body = sample()
                headers = {"Idempotency-Key": "fixture-key"}
                response = client.post(
                    "/api/research/portfolio-decisions/runs", json=body, headers=headers
                )
                self.assertEqual(response.status_code, 403)
                headers["X-Research-User-Action"] = "?1"
                response = client.post(
                    "/api/research/portfolio-decisions/runs", json=body, headers=headers
                )
                self.assertEqual(response.status_code, 201, response.text)
                first = response.json()
                self.assertEqual(first["real_chain"]["status"], "BLOCKED")
                self.assertEqual(
                    client.post(
                        "/api/research/portfolio-decisions/runs", json=body, headers=headers
                    ).json(),
                    first,
                )
                self.assertEqual(
                    client.get(f"/api/research/portfolio-decisions/runs/{first['id']}").json(),
                    first,
                )
                body["snapshot"]["provenance"] = "verified_real"
                self.assertEqual(
                    client.post(
                        "/api/research/portfolio-decisions/runs", json=body, headers=headers
                    ).status_code,
                    422,
                )
                self.assertEqual(
                    len(client.get("/api/research/portfolio-decisions/runs").json()["items"]), 1
                )
