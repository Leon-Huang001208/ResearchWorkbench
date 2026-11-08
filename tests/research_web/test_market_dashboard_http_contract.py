"""Real dashboard request paths meet real routers; these are not auth/live tests."""

import asyncio
import hashlib
import json
import shutil
import subprocess
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research_web.event_timeline import TimelineService
from app.research_web.event_timeline import storage as timeline_storage
from app.research_web.event_timeline.routes import router as timeline_router
from app.research_web.market_routes import router as market_router
from app.research_web.market_scoring import ScoreService
from app.research_web.market_scoring.routes import router as scoring_router
from app.research_web.market_service import MarketService
from app.research_web.store import Store
from core.observability import get_logger

log = get_logger(__name__)
PROJECT = Path(__file__).resolve().parents[2]


def _application(tmp_path):
    # Only the Host activity context is stubbed. Real account-local services
    # and real route validation are used, without a gateway/auth claim.
    research = SimpleNamespace(store=Store(tmp_path / "personal"))
    research.market = MarketService(research.store.root)
    research.event_timeline = TimelineService(research)
    research.market_scores = ScoreService(research)
    research.event_inputs = SimpleNamespace(activity=nullcontext)
    app = FastAPI()
    app.state.research = research
    for router in (market_router, scoring_router, timeline_router):
        app.include_router(router)
    return app, research


def _file_hashes(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def _activate_actual_dashboard(profiles):
    node = shutil.which("node")
    assert node is not None, "Node is required for the dashboard HTTP contract"
    script = r"""
import { createMarketDashboard } from './app/research_web/ui/market-dashboard.mjs';
let input = ''; for await (const chunk of process.stdin) input += chunk;
const profiles = JSON.parse(input), calls = [];
const api = { async request(path, options = {}) {
  calls.push({ path, method: options.method || 'GET' });
  const url = new URL(path, 'http://contract.invalid');
  if (url.pathname === '/market') return { sections: {} };
  if (url.pathname === '/market-scores/profiles') return profiles;
  if (url.pathname === '/market-scores/runs') return { items: [], next_cursor: null, historical_only: true, production_enabled: false };
  if (url.pathname === '/market-scores/initial-evidence') return { items: [], production_enabled: false };
  if (url.pathname === '/events/timeline') return { items: [], next_cursor: null, sources: [], coverage: 'not_loaded' };
  if (url.pathname === '/events/coverage') return { items: [], complete: false };
  throw new Error('Unexpected dashboard read: ' + path);
}};
const dashboard = createMarketDashboard({ api, documentRef: null,
  getIdentity: () => 'isolated-contract-user', now: () => new Date('2026-11-06T12:00:00Z'),
  setTimer: () => { throw new Error('Mount must not start a poll timer'); }, clearTimer: () => {} });
await dashboard.activate();
const result = { calls, errors: dashboard.state.errors, profiles: dashboard.state.profiles,
  scoreCoverage: dashboard.state.scoreCoverage };
dashboard.cancel();
console.log('DASHBOARD_HTTP_CONTRACT:' + JSON.stringify(result));
"""
    process = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=PROJECT,
        input=json.dumps(profiles),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 0, process.stderr[-2000:]
    assert len(process.stdout) < 32 * 1024
    lines = [
        line for line in process.stdout.splitlines() if line.startswith("DASHBOARD_HTTP_CONTRACT:")
    ]
    assert len(lines) == 1, process.stdout[-2000:]
    return json.loads(lines[0].split(":", 1)[1])


def test_actual_dashboard_mount_get_paths_pass_real_fastapi_without_store_writes(tmp_path):
    app, research = _application(tmp_path)
    before_files = _file_hashes(research.store.root)
    before_store = deepcopy(research.store.data)
    try:
        captured = _activate_actual_dashboard(research.market_scores.profiles())
        assert captured["errors"] == {}
        assert len(captured["profiles"]) == 9
        assert captured["scoreCoverage"]["complete"] is True
        assert captured["scoreCoverage"]["rows"] == 0
        calls = captured["calls"]
        assert calls and all(call["method"] == "GET" for call in calls)
        assert any(call["path"] == "/market-scores/profiles" for call in calls)
        assert any(call["path"].startswith("/market-scores/runs?") for call in calls)
        assert any(call["path"].startswith("/events/timeline?") for call in calls)
        assert any(call["path"] == "/market-scores/initial-evidence" for call in calls)
        assert any(call["path"] == "/events/coverage" for call in calls)
        with TestClient(app) as client:
            for call in calls:
                response = client.request(call["method"], "/api/research" + call["path"])
                assert response.status_code == 200, (call["path"], response.text)
                if call["path"] == "/market-scores/initial-evidence":
                    assert response.json()["production_enabled"] is False
                    assert {item["index_id"] for item in response.json()["items"]} == {
                        "SSE",
                        "SP500",
                        "HSI",
                    }
                elif call["path"] == "/events/coverage":
                    assert response.json()["complete"] is False
                    assert response.json()["items"] == []
        assert research.store.data == before_store
        assert _file_hashes(research.store.root) == before_files
        assert research.market.overview()["inflight"] == []
        log.info("market_dashboard_http_contract_verified", reads=len(calls))
    finally:
        asyncio.run(research.market.close())
        asyncio.run(research.event_timeline.close())


def test_real_score_record_pagination_is_oldest_first_and_http_limit_is_enforced(
    tmp_path, monkeypatch
):
    app, research = _application(tmp_path)
    records = research.event_timeline.records
    try:
        created = []
        for number in range(3):
            monkeypatch.setattr(
                timeline_storage, "now", lambda n=number: f"2026-10-{20+n:02d}T12:00:00+00:00"
            )
            created.append(
                records.create(
                    "score",
                    {"request": {"index_id": "SSE"}, "fixture_order": number},
                    f"score-pagination-{number}",
                )
            )
        before = deepcopy(research.store.data)
        with TestClient(app) as client:
            first = client.get("/api/research/market-scores/runs?limit=2")
            assert first.status_code == 200
            page = first.json()
            assert [row["id"] for row in page["items"]] == [row["id"] for row in created[:2]]
            assert page["historical_only"] is True and page["production_enabled"] is False
            assert page["next_cursor"] is not None
            second = client.get(
                "/api/research/market-scores/runs",
                params={"limit": 2, "cursor": page["next_cursor"]},
            )
            assert second.status_code == 200
            assert [row["id"] for row in second.json()["items"]] == [created[-1]["id"]]
            assert second.json()["next_cursor"] is None
            assert client.get("/api/research/market-scores/runs?limit=200").status_code == 422
        assert research.store.data == before
        log.info("market_dashboard_score_pagination_contract_verified", rows=len(created))
    finally:
        asyncio.run(research.market.close())
        asyncio.run(research.event_timeline.close())
