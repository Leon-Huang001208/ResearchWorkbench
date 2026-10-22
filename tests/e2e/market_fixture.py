"""Loopback-only market browser fixture; no supplier, model or account credentials.

The real MarketService and market_routes consume explicit offline provider records.
The cookie below exercises same-origin browser propagation, not production auth.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import socket
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.research_web.datahub.providers_market import INDEXES, MarketProvider
from app.research_web.market_routes import router
from app.research_web.market_service import MarketService
from core.observability import get_logger

log = get_logger(__name__)
PROJECT = Path(__file__).resolve().parents[2]
STAMP = "2026-10-22T02:00:00+00:00"
COOKIE = "rwb_market_fixture"


class OfflineProvider:
    """Deterministic 6,001-stock records, explicitly never real market evidence."""

    def __init__(self, mode="normal"):
        self.mode = mode
        self.calls = []
        self.closed = False
        self.rows = []
        for index in range(6001):
            exchange = ("SH", "SZ", "BJ")[index % 3]
            ordinal = index // 3
            if exchange == "SH":
                board = "star" if ordinal % 10 == 0 else "main"
                code = str((688000 if board == "star" else 600000) + ordinal)
            elif exchange == "SZ":
                board = "chinext" if ordinal % 10 == 0 else "main"
                code = f"{(300000 if board == 'chinext' else 1) + ordinal:06d}"
            else:
                board, code = "beijing", str(920000 + ordinal)
            change = round((index % 251 - 125) / 10, 2)
            self.rows.append(
                {
                    "asset": f"{code}.{exchange}",
                    "code": code,
                    "name": f"离线夹具股票{index:04d}",
                    "exchange": exchange,
                    "board": board,
                    "price": None if index == 6000 else round(10 + index / 1000, 2),
                    "change": None if index == 6000 else round(change / 10, 2),
                    "change_pct": None if index == 6000 else change,
                    "volume": index * 100,
                    "amount": index * 10000,
                    "amplitude_pct": 0 if not index else 2.5,
                    "turnover_rate_pct": 1.2,
                    "volume_ratio": 1.1,
                    "pe_dynamic": 12.5,
                    "pb": 0 if not index else 1.4,
                    "total_market_cap": 100000000 + index * 100000,
                    "float_market_cap": 80000000 + index * 100000,
                    "change_5m_pct": 0.2,
                    "change_60d_pct": 2.1,
                    "change_ytd_pct": 3.2,
                    "as_of": STAMP,
                }
            )

    async def fetch(self, section, *, board_id=None, kind="industry", period="today"):
        if self.closed:
            raise RuntimeError("offline provider is closed")
        self.calls.append(
            {"section": section, "board_id": board_id, "kind": kind, "period": period}
        )
        await asyncio.sleep(0.03)
        rows, summary = [], {}
        if section == "quotes":
            rows = self.rows[:] if self.mode == "normal" else self.rows[:-73]
            if self.mode == "normal":
                summary = MarketProvider._statistics(rows, "2026-10-22")
                summary.update(quote_trade_date="2026-10-22", temporal_complete=True)
        elif section == "indices":
            rows = [
                {
                    "asset": asset,
                    "name": name,
                    "price": 3000 + index * 100,
                    "change": index - 4,
                    "change_pct": round(index / 10 - 0.4, 2),
                    "as_of": STAMP,
                    "series": [
                        {
                            "time": f"{9 + (30 + minute) // 60:02d}:{(30 + minute) % 60:02d}",
                            "change_pct": round(math.sin(minute / 15 + index) / 2 + index / 20, 3),
                        }
                        for minute in range(61)
                    ],
                }
                for index, (asset, name, _) in enumerate(INDEXES)
            ]
        elif section in {"industry", "concept", "flows"}:
            actual_kind = kind if section == "flows" else section
            start = 1 if actual_kind == "industry" else 1001
            rows = [
                {
                    "board_id": f"BK{start + index:04d}",
                    "name": f"离线{'行业' if actual_kind == 'industry' else '概念'}{index + 1}",
                    "change_pct": round((index - 3) / 3, 2),
                    "amount": (index + 1) * 100000000,
                    "total_market_cap": (index + 1) * 1000000000,
                    "up_count": index * 10,
                    "down_count": 90 - index * 10,
                    "leader_name": self.rows[index]["name"],
                    "leader_change_pct": index / 2,
                    "main_net": (index - 3) * 100000000,
                    "main_ratio_pct": index - 3,
                    "super_net": (index - 3) * 40000000,
                    "large_net": (index - 3) * 60000000,
                    "medium_net": -(index - 3) * 70000000,
                    "small_net": -(index - 3) * 30000000,
                    "as_of": STAMP,
                }
                for index in range(8)
            ]
            if section == "flows":
                summary["market_flow"] = {
                    "scope": "SH+SZ",
                    "frequency": "daily",
                    "rows": [
                        {"date": f"2026-10-{day:02d}", "main_net": (day - 15) * 100000000}
                        for day in range(12, 23)
                    ],
                }
        elif section == "calendar":
            summary = {
                "trading_dates": ["2026-10-21", "2026-10-22", "2026-10-23"],
                "valid_until": "2026-10-23",
            }
            rows = [{"trade_date": day} for day in summary["trading_dates"]]
        elif section == "members":
            rows = [
                {"code": row["code"], "market": 1 if row["exchange"] == "SH" else 0}
                for row in self.rows[:3]
            ]
            summary = {"board_id": board_id, "kind": kind}
        else:
            raise ValueError("unsupported offline section")
        complete = not (section == "quotes" and self.mode == "partial")
        log.info("market_browser_fixture_fetch", section=section, rows=len(rows))
        return {
            "rows": rows,
            "summary": summary,
            "provider": "offline-fixture",
            "source_url": "http://127.0.0.1/fixture/offline",
            "as_of": STAMP,
            "retrieved_at": STAMP,
            "started_at": STAMP,
            "provider_total": 6001 if section == "quotes" else len(rows),
            "pages_fetched": 61 if section == "quotes" else 1,
            "pagination_complete": complete,
            "complete": complete,
            "missing": {"pages": 1} if not complete else {},
            "limitations": ["离线浏览器夹具，非真实行情；fixture cookie 不是生产认证。"]
            + (["离线故障：缺失末页73只股票。"] if not complete else []),
        }

    async def close(self):
        self.closed = True


def fixture_app(data_root):
    state = {"reads": [], "session_creates": 0, "mode": "normal", "clock": 0.0, "profile": 0}

    def build_market(mode):
        provider = OfflineProvider(mode)
        market = MarketService(
            data_root / f"profile-{state['profile']}",
            provider,
            clock=lambda: state["clock"],
            now=lambda: datetime.fromisoformat(STAMP).astimezone(UTC),
        )
        return market

    @asynccontextmanager
    async def lifespan(app):
        app.state.research = SimpleNamespace(market=build_market("normal"))
        try:
            yield
        finally:
            await app.state.research.market.close()
            print(
                json.dumps(
                    {
                        "fixture_shutdown": True,
                        "active_collectors": len(app.state.research.market._collectors),
                    }
                ),
                flush=True,
            )

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)

    @app.middleware("http")
    async def fixture_boundary(request, call_next):
        path = request.url.path
        if path.startswith("/api/"):
            state["reads"].append(
                {"method": request.method, "path": path, "query": str(request.url.query)}
            )
            state["reads"] = state["reads"][-2000:]
        if (
            path.startswith(("/api/research/market", "/fixture/"))
            and request.cookies.get(COOKIE) != "local-only"
        ):
            return JSONResponse(
                {
                    "error": {
                        "code": "fixture_auth_required",
                        "message": "Offline fixture cookie required",
                    }
                },
                status_code=401,
            )
        if request.method == "POST" and path.startswith("/api/research/sessions"):
            state["session_creates"] += 1
            return JSONResponse(
                {"error": {"message": "Fixture prohibits research creation"}}, status_code=409
            )
        response = await call_next(request)
        response.headers["X-Research-Fixture"] = "offline-market-browser-only"
        return response

    @app.get("/")
    async def index():
        html = (PROJECT / "app/research_web/ui/index.html").read_text()
        html = html.replace(
            "</head>",
            '<script>window.__RWB_USER_ID__="offline-market-user";window.__RWB_ACCOUNT__={name:"离线市场浏览器夹具",role:"user"};</script></head>',
        )
        html = html.replace("<title>", "<title>[OFFLINE FIXTURE] ")
        response = HTMLResponse(html)
        response.set_cookie(COOKIE, "local-only", httponly=True, samesite="strict")
        return response

    @app.get("/health")
    async def health():
        return {"status": "offline-fixture", "not_production_auth": True}

    @app.get("/fixture/state")
    async def inspect():
        market = app.state.research.market
        return {
            **state,
            "provider_calls": market.provider.calls,
            "inflight": len(market._collectors),
            "sections": {
                key: {
                    "snapshot_id": value.get("snapshot_id"),
                    "row_count": value.get("row_count"),
                    "complete": value.get("complete"),
                }
                for key, value in market.overview()["sections"].items()
            },
        }

    @app.post("/fixture/control")
    async def control(request: Request):
        body = await request.json()
        mode = body.get("mode", state["mode"])
        if mode not in {"normal", "partial"}:
            return JSONResponse({"error": "invalid fixture mode"}, status_code=400)
        state["clock"] += 120
        if mode != state["mode"] or body.get("reset"):
            await app.state.research.market.close()
            state["mode"] = mode
            state["profile"] += 1
            app.state.research.market = build_market(mode)
        return {"mode": mode, "clock": state["clock"]}

    @app.post("/fixture/shutdown")
    async def shutdown():
        app.state.fixture_server.should_exit = True
        return {"status": "closing"}

    @app.get("/api/research/{path:path}")
    async def catalogs(path: str):
        if path == "runtime":
            return {
                "connected": True,
                "provider": "offline-fixture",
                "model": "offline-fixture",
                "credential_configured": False,
            }
        if path == "models":
            return {"groups": [], "failures": []}
        if path in {
            "workspaces",
            "sessions",
            "capabilities",
            "tools",
            "report-workflows",
            "assets/observations",
            "watchlists",
            "asset-notes",
            "asset-alerts",
            "asset-notifications",
        }:
            return {"items": []}
        if path == "data/catalog":
            return {"summary": {}, "capabilities": [], "sources": [], "bindings": []}
        log.warning("market_fixture_unexpected_route", route=path)
        return JSONResponse(
            {"error": {"code": "fixture_unexpected_route", "message": "Unexpected fixture route"}},
            status_code=404,
        )

    app.mount("/static", StaticFiles(directory=PROJECT / "app/research_web/ui"), name="static")
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    args.data_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(128)
    print(json.dumps({"fixture_port": server_socket.getsockname()[1]}), flush=True)
    try:
        app = fixture_app(args.data_root)
        config = uvicorn.Config(
            app, host="127.0.0.1", port=0, log_level="warning", timeout_graceful_shutdown=10
        )
        server = uvicorn.Server(config)
        app.state.fixture_server = server
        server.run(sockets=[server_socket])
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
