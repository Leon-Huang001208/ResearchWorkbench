"""Isolated read-only Research Web server for browser appearance acceptance."""

import asyncio
import os
from pathlib import Path

from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store
from core.observability import get_logger

log = get_logger(__name__)


class BrowserFixtureRuntime:
    """Expose deterministic runtime metadata without accepting research work."""

    async def rpc(self, method, payload):
        if method == "host.describe":
            return {"version": "fixture", "model": "fixture", "provider": "fixture"}
        if method == "llm.models":
            return {
                "groups": [
                    {
                        "id": "fixture",
                        "name": "Fixture",
                        "models": [{"id": "fixture", "name": "Fixture"}],
                    }
                ],
                "failures": [],
            }
        if method == "session.list":
            return {"items": []}
        if method == "subagent.list":
            return {"entries": []}
        if method == "credentials.describe":
            return {"credentials": {"RESEARCH_DSH_API_KEY": {"configured": False}}}
        if method == "skill.list":
            return {"skills": []}
        return {"accepted": False}

    async def plugin_json(self, method, path, *, params=None, payload=None):
        if method == "GET" and path == "/research/tabbit/status":
            return {
                "status": "disabled",
                "pluginVersion": "0.3.4",
                "launcherPresent": False,
                "onlineInstances": 0,
            }
        log.warning("browser_fixture_plugin_route_rejected", method=method, path=path)
        raise RuntimeError("fixture runtime does not expose mutable plugin routes")

    async def history(self, _session_id):
        return []

    async def close(self):
        return None

    async def frames(self, channel):
        yield {"type": "connected", "channel": channel}
        await asyncio.Event().wait()


os.environ.setdefault("RESEARCH_FRAMEWORK_COLLECTORS_ENABLED", "0")
data_root = Path(os.environ["RESEARCH_DATA_HOME"])
app = create_app(ResearchService(BrowserFixtureRuntime(), Store(data_root)))
