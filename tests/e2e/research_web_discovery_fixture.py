"""Actual Host/UI browser fixture; native model and scheduler are strictly inert."""

import copy
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(tempfile.mkdtemp(prefix="rwb-discovery-browser-"))
os.environ["RESEARCH_DATA_HOME"] = str(DATA_ROOT)
os.environ["LOG_DIR"] = str(PROJECT / "logs")
os.environ["RESEARCH_FRAMEWORK_COLLECTORS_ENABLED"] = "0"
os.environ["RESEARCH_MCP_RUNTIME_ENABLED"] = "0"
os.environ["RESEARCH_AUTOMATIONS_ENABLED"] = "1"
os.environ.pop("RWB_TENANT_MODE", None)
sys.path.insert(0, str(PROJECT / "tests/research_web"))

import keyring
from test_api import NativeFixture

from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store
from core.observability import get_logger

log = get_logger(__name__)
try:
    owner_file = PROJECT / "logs" / f"discovery-browser-owner-{os.getpid()}.json"
    owner_file.parent.mkdir(parents=True, exist_ok=True)
    owner_file.write_text(
        json.dumps(
            {
                "task_id": "intel-discovery-production-20261023",
                "pid": os.getpid(),
                "data_root": str(DATA_ROOT),
                "native": "inert",
                "scheduler": "inert",
            }
        )
    )
except OSError:
    log.error("discovery_browser_ownership_write_failed")
    raise
_credentials = {}
keyring.get_password = lambda service, account: _credentials.get((service, account))
keyring.set_password = lambda service, account, value: _credentials.__setitem__(
    (service, account), value
)
keyring.delete_password = lambda service, account: _credentials.pop((service, account), None)


class InertNative(NativeFixture):
    """Keep native identities for Host recovery; no external runtime or provider."""

    def __init__(self):
        super().__init__()
        self.sessions = {}

    async def rpc(self, method, payload):
        if method == "session.create":
            self.sessions[payload["sessionId"]] = {
                "sessionId": payload["sessionId"],
                "cwd": payload["cwd"],
                "running": False,
            }
        if method == "session.list":
            self.calls.append((method, payload))
            return {"items": list(self.sessions.values())}
        if method == "session.prompt":
            log.info("discovery_browser_inert_prompt", real_model=False)
        return await super().rpc(method, payload)


class InertScheduler:
    """Record scheduling requests but never create a clock, job or execution."""

    def __init__(self):
        self.running = False
        self.jobs = {}

    def start(self):
        self.running = True

    def add_job(self, function, trigger, *, id, **kwargs):
        self.jobs[id] = kwargs

    def remove_job(self, identifier):
        self.jobs.pop(identifier, None)

    def shutdown(self, wait=False):
        self.running = False
        self.jobs.clear()


def fixture_event(identifier, title, group, next_action):
    return {
        "id": identifier,
        "title": title,
        "revision": 2,
        "updated_at": datetime.now(UTC).isoformat(),
        "first_public_at": None,
        "groups": [group],
        "last_change": "离线验收资料：不是市场事实",
        "priority_reason": "离线验证资料与研究交接，不作为投资判断。",
        "extraction": {
            "new_facts": ["离线样例资料尚待核验。"],
            "pending": [next_action],
            "market_chain": ["来源陈述", "经营证据", "反方核验", "结论边界"],
            "counter_evidence": ["缺少原始披露，不应推出方向性结论。"],
        },
        "verification": {
            "status": "待核实",
            "closed_loop": False,
            "blockers": ["离线样例不能获得真实研究验收"],
            "progression": {"next_action": next_action},
        },
    }


EVENTS = [
    fixture_event(
        "browser_ai",
        "AI 扩张的约束，出现在电力还是利润？",
        "technology",
        "核对资本开支、订单与现金流。",
    ),
    fixture_event(
        "browser_rates",
        "利率路径如何传导到美元与长久期资产？",
        "macro",
        "核对同日曲线、政策与预期。",
    ),
    fixture_event("browser_china", "政策预期何时转成企业盈利？", "china", "核对订单、财报和回款。"),
]


async def fixture_reader(path, params=None):
    if path == "/intelligence":
        return {
            "reading": copy.deepcopy(EVENTS),
            "cache_stale": False,
            "as_of": None,
            "logics": [{"id": "technology", "name": "科技"}, {"id": "macro", "name": "宏观"}],
        }
    identifier = path.rsplit("/", 1)[-1]
    event = next((item for item in EVENTS if item["id"] == identifier), None)
    if event is None:
        log.warning("discovery_browser_fixture_event_unknown")
        raise ValueError("fixture_event_unknown")
    return {
        "event": copy.deepcopy(event),
        "revisions": [],
        "articles": [
            {
                "id": "archive-" + identifier,
                "title": "离线验收原件",
                "source": "浏览器隔离夹具",
                "url": "https://example.com/" + identifier,
                "published_at": None,
                "content": "这是离线验收字节，用于证明选材、冻结、质量缺口和手动交接，不是市场事实。",
            },
        ],
    }


service = ResearchService(InertNative(), Store(DATA_ROOT))
service._model_tools_verified = lambda sid: True
service.automations.scheduler = InertScheduler()
if os.environ.get("RWB_DISCOVERY_BROWSER_LIVE") != "1":
    service.discovery.reader = fixture_reader
app = create_app(service)
log.info(
    "discovery_browser_fixture_ready",
    real_native=False,
    real_scheduler=False,
    live_public_reader=os.environ.get("RWB_DISCOVERY_BROWSER_LIVE") == "1",
)
