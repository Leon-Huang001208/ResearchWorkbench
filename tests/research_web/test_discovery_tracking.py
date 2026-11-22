"""Discovery tracking uses the existing scheduler with explicit, isolated consent."""

import asyncio
import copy
import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.research_web.automation.service import AutomationService
from app.research_web.discovery.tracking import DiscoveryTracking
from app.research_web.store import Store, StoreError


class Discovery:
    def __init__(self):
        self.feed_id = str(uuid4())
        self.revision = "one"
        self.sent = 0
        self.state = "running"
        self.handoffs = {}

    async def feed(self, horizon, refresh=False):
        return self.cached_preview(self.feed_id, horizon)

    def cached_preview(self, feed_id, horizon):
        if feed_id != self.feed_id:
            raise StoreError("预览已过期", "discovery_feed_expired", 409)
        return {
            "feed_id": self.feed_id,
            "cutoff": "2026-10-23T09:00:00+08:00",
            "themes": [
                {
                    "id": "macro",
                    "title": "宏观观察",
                    "materials": [
                        {
                            "id": self.revision,
                            "content_sha256": self.revision,
                            "revision": self.revision,
                            "event_id": "macro",
                        }
                    ],
                }
            ],
        }

    async def refresh_theme(self, horizon, theme_id, event_ids):
        assert event_ids == [theme_id] == ["macro"]
        feed = await self.feed(horizon, refresh=True)
        feed["themes"][0]["materials"][0]["evidence_sha256"] = hashlib.sha256(
            self.revision.encode()
        ).hexdigest()
        return feed

    async def prepare(self, body):
        hid = str(uuid4())
        session = self.research.store.create("fingpt", "跟踪研究")
        session.update(
            model_provider="deepseek-official",
            model="deepseek-flash",
            model_profile_id="legacy-deepseek-official",
        )
        row = {"handoff_id": hid, "session_id": session["id"], "state": "prepared"}
        self.handoffs[hid] = row
        self.research.store.data.setdefault("discovery_handoffs", {})[hid] = row
        return copy.deepcopy(row)

    async def execute(self, hid, request_id):
        self.sent += 1
        self.handoffs[hid]["state"] = self.state
        row = self.handoffs[hid]
        row["delivery_key"] = "frozen-request"
        self.research.store.data["receipts"][f"{row['session_id']}:frozen-request"] = {
            "status": "accepted",
            "research_contract": {"task_id": "task-current"},
            "quality_checks": {
                "check-one": {"status": "passed", "report_content_sha256": "a" * 64}
            },
            "quality_archives": {
                "version-current": {
                    "check_id": "check-one",
                    "anchor": {
                        "task_id": "task-current",
                        "version_id": "version-current",
                        "files": [{"name": "research-report.json", "sha256": "a" * 64}],
                    },
                }
            },
        }
        return copy.deepcopy(self.handoffs[hid])

    def get_handoff(self, hid):
        return copy.deepcopy(self.handoffs[hid])

    def trusted_context(self, sid):
        return next(
            {"handoff_id": row["handoff_id"]}
            for row in self.handoffs.values()
            if row["session_id"] == sid
        )


def body(discovery):
    return {
        "request_id": str(uuid4()),
        "feed_id": discovery.feed_id,
        "horizon": "short",
        "theme_id": "macro",
        "condition": "核对政策传导与反证",
        "frequency": "daily",
        "time": "09:00",
        "timezone": "Asia/Shanghai",
    }


def setup(tmp_path):
    store = Store(tmp_path)
    discovery = Discovery()
    research = SimpleNamespace(
        store=store,
        default_model={"provider": "deepseek-official", "model": "deepseek-flash"},
        model_profile_identity=lambda provider: "legacy-deepseek-official",
    )
    research.automations = AutomationService(
        store,
        research=research,
        scheduler=False,
        now=lambda: datetime(2026, 10, 23, tzinfo=UTC),
    )
    discovery.research = research

    async def detail(sid):
        return {
            "id": sid,
            "status": "completed",
            "research_quality": {
                "status": "passed",
                "contract": {"task_id": "task-current"},
            },
            "research_report_delivery": {
                "status": "bound",
                "report_content_sha256": "a" * 64,
                "task_id": "task-current",
                "version_id": "version-current",
                "quality_status": "passed",
            },
            "research_report": {"content_sha256": "a" * 64, "task_id": "task-current"},
            "research_report_versions": [
                {
                    "version_id": "version-current",
                    "task_id": "task-current",
                    "is_current": True,
                    "quality_binding": "host_check",
                    "quality": {"status": "passed", "report_content_sha256": "a" * 64},
                    "files": [{"name": "research-report.json", "sha256": "a" * 64}],
                }
            ],
            "files": [],
        }

    research.detail = detail
    tracking = DiscoveryTracking(research, discovery)
    research.automations.executor = tracking.execute
    return tracking, research, discovery


@pytest.mark.asyncio
async def test_save_disabled_idempotent_and_separate_enable_version(tmp_path):
    tracking, research, discovery = setup(tmp_path)
    request = body(discovery)
    saved = await tracking.save(request)
    assert saved["request_id"] == request["request_id"]
    assert saved["enabled"] is False
    assert saved["definition_version"] == 1
    assert discovery.sent == 0
    assert (await tracking.save(request))["id"] == saved["id"]
    restored = DiscoveryTracking(research, discovery).list()["items"]
    assert (
        next(row for row in restored if row["request_id"] == request["request_id"])["id"]
        == saved["id"]
    )
    changed = {**request, "condition": "不同任务"}
    with pytest.raises(StoreError, match="同一请求"):
        await tracking.save(changed)
    with pytest.raises(StoreError) as conflict:
        tracking.enable(saved["id"], 2)
    assert conflict.value.code == "automation_version_conflict"
    assert tracking.enable(saved["id"], 1)["enabled"] is True
    assert tracking.disable(saved["id"], 1)["enabled"] is False
    assert research.automations.list_runs()["items"] == []


@pytest.mark.asyncio
async def test_enable_failure_preserves_same_disabled_saved_definition(tmp_path, monkeypatch):
    tracking, research, discovery = setup(tmp_path)
    saved = await tracking.save(body(discovery))

    def fail(*args, **kwargs):
        raise StoreError("暂不可用", "scheduler_unavailable", 503)

    monkeypatch.setattr(research.automations, "enable", fail)
    with pytest.raises(StoreError):
        tracking.enable(saved["id"], 1)
    item = tracking.list()["items"][0]
    assert item["id"] == saved["id"] and item["enabled"] is False
    assert item["enable_error"] == "scheduler_unavailable"


@pytest.mark.asyncio
async def test_foreign_automation_never_exposed_or_mutated(tmp_path):
    tracking, research, discovery = setup(tmp_path)
    saved = await tracking.save(body(discovery))
    owned = research.automations._row(saved["id"])
    foreign = copy.deepcopy(owned)
    foreign["id"] = "automation-foreign"
    research.store.data["automations"][foreign["id"]] = foreign
    assert [row["id"] for row in tracking.list()["items"]] == [saved["id"]]
    assert tracking.eligible(foreign) is False
    with pytest.raises(StoreError) as failure:
        tracking.enable(foreign["id"], 1)
    assert failure.value.status == 404


@pytest.mark.asyncio
async def test_unchanged_skips_model_and_changed_runs_once(tmp_path):
    tracking, research, discovery = setup(tmp_path)
    saved = await tracking.save(body(discovery))
    # Saving locks the current evidence as baseline. No novelty means no paid work.
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert discovery.sent == 0
    assert tracking.list()["items"][0]["runs"][0]["execution_status"] == "skipped_unchanged"
    discovery.revision = "two"
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert discovery.sent == 1
    item = tracking.list()["items"][0]
    assert item["runs"][0]["quality_status"] == "passed"
    assert item["runs"][0]["accepted"] is True
    session = research.store.session(item["runs"][0]["session_id"])
    assert session["source_scope"] == ["datahub", "uploads"]
    assert session["automation_research_scope"]["approved_tools"] == [
        "research_run_script",
        "research_document_operation",
    ]
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert discovery.sent == 1


@pytest.mark.asyncio
async def test_unknown_fingerprint_is_never_automatically_resent(tmp_path):
    tracking, research, discovery = setup(tmp_path)
    saved = await tracking.save(body(discovery))
    discovery.revision, discovery.state = "two", "execution_outcome_unknown"
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert discovery.sent == 1
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert discovery.sent == 1
    runs = tracking.list()["items"][0]["runs"]
    assert any(row["execution_status"] == "interrupted" for row in runs)
    assert not any(row["accepted"] for row in runs)


@pytest.mark.asyncio
async def test_completed_execution_with_failed_quality_is_not_accepted(tmp_path):
    tracking, research, discovery = setup(tmp_path)
    saved = await tracking.save(body(discovery))

    async def detail(sid):
        return {
            "status": "completed",
            "research_quality": {"status": "incomplete"},
            "research_report_delivery": {"status": "unbound"},
        }

    research.detail = detail
    discovery.revision = "two"
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    run = tracking.list()["items"][0]["runs"][0]
    assert run["execution_status"] == "completed"
    assert run["quality_status"] == "incomplete" and run["accepted"] is False


@pytest.mark.asyncio
async def test_restricted_scheduler_never_wakes_unrelated_tasks(tmp_path):
    tracking, research, discovery = setup(tmp_path)
    saved = await tracking.save(body(discovery))
    own = research.automations._row(saved["id"])
    foreign = copy.deepcopy(own)
    foreign.update(id="foreign", enabled=True, next_run_at="2026-10-22T00:00:00+00:00")
    research.store.data["automations"]["foreign"] = foreign
    research.automations.eligibility = tracking.eligible
    await research.automations.start()
    assert foreign["next_run_at"] == "2026-10-22T00:00:00+00:00"
    assert research.automations.list_runs()["items"] == []
    with pytest.raises(StoreError) as denied:
        research.automations.enable("foreign")
    assert denied.value.code == "automation_scope_denied"
    with pytest.raises(StoreError):
        await research.automations.run("foreign")


@pytest.mark.asyncio
async def test_changed_model_never_silently_switches_locked_tracking(tmp_path):
    tracking, research, discovery = setup(tmp_path)
    saved = await tracking.save(body(discovery))
    discovery.revision = "two"
    research.default_model = {"provider": "deepseek-official", "model": "different"}
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert discovery.sent == 0
    assert tracking.list()["items"][0]["runs"][0]["failure_code"] == "discovery_model_changed"


@pytest.mark.asyncio
@pytest.mark.parametrize("existing", [False, True])
async def test_save_failure_rolls_back_companion_and_preserves_other_tasks(
    tmp_path, monkeypatch, existing
):
    tracking, research, discovery = setup(tmp_path)
    if existing:
        await tracking.save(body(discovery))
    before = copy.deepcopy(research.store.data)

    def fail():
        raise StoreError("保存失败", "index_failed", 503)

    monkeypatch.setattr(research.store, "save", fail)
    with pytest.raises(StoreError):
        await tracking.save(body(discovery))
    assert research.store.data == before
    assert len(tracking.list()["items"]) == int(existing)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation", ["different_task", "old_version", "unbound", "different_hash", "another_turn"]
)
async def test_passed_label_without_current_version_binding_never_accepted(tmp_path, mutation):
    tracking, research, discovery = setup(tmp_path)
    saved = await tracking.save(body(discovery))
    original = research.detail

    async def detail(sid):
        result = await original(sid)
        if mutation == "different_task":
            result["research_report_delivery"]["task_id"] = "another-task"
        elif mutation == "old_version":
            result["research_report_versions"][0]["is_current"] = False
        elif mutation == "unbound":
            result["research_report_versions"][0]["quality_binding"] = "unbound"
        elif mutation == "different_hash":
            result["research_report_versions"][0]["files"][0]["sha256"] = "b" * 64
        else:
            research.store.data["receipts"][f"{sid}:frozen-request"]["research_contract"][
                "task_id"
            ] = "a-newer-turn"
        return result

    research.detail = detail
    discovery.revision = "two"
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert tracking.list()["items"][0]["runs"][0]["accepted"] is False


@pytest.mark.asyncio
async def test_unbound_stale_feed_and_recovery_never_start_another_research(tmp_path):
    tracking, research, discovery = setup(tmp_path)
    saved = await tracking.save(body(discovery))
    discovery.revision = "two"
    run = await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert discovery.sent == 1
    actual = research.automations._run_row(run["id"])
    actual["research_status"] = "running"
    research.automations.resume_executor = tracking.resume
    await research.automations._resume(run["id"])
    assert discovery.sent == 1 and actual["research_status"] == "completed"
    before = discovery.feed

    async def stale(horizon, refresh=False):
        feed = await before(horizon, refresh=refresh)
        feed["stale"] = True
        return feed

    discovery.feed = stale
    await research.automations.run(saved["id"])
    await research.automations.wait_for_idle()
    assert discovery.sent == 1
    assert (
        tracking.list()["items"][0]["runs"][0]["failure_code"]
        == "discovery_track_source_unavailable"
    )


def test_read_probes_never_persist_new_empty_extension(tmp_path):
    tracking, research, _ = setup(tmp_path)
    before = copy.deepcopy(research.store.data)
    assert tracking.list() == {"items": []}
    assert tracking.has_enabled() is False
    assert research.store.data == before
    assert "discovery_tracks" not in research.store.data


@pytest.mark.asyncio
async def test_weekly_schedule_is_the_approved_friday_even_when_saved_on_monday(tmp_path):
    tracking, research, discovery = setup(tmp_path)
    research.automations.now = lambda: datetime(2026, 10, 19, tzinfo=UTC)
    saved = await tracking.save({**body(discovery), "frequency": "weekly"})
    assert saved["schedule"]["weekday"] == 4
    assert saved["schedule"]["timezone"] == "Asia/Shanghai"


@pytest.mark.asyncio
@pytest.mark.parametrize("check_proof", ["bound", "missing_check", "mismatched_check"])
async def test_real_host_quality_projection_accepts_exact_bound_report_without_public_check_digest(
    tmp_path,
    check_proof,
):
    from app.research_web.research_evidence import evidence_index
    from app.research_web.research_quality import make_contract
    from app.research_web.research_quality_service import (
        check_quality,
        quality_result,
        quality_versions,
        report_delivery,
    )
    from app.research_web.resources.research_report import write_research_report

    tracking, research, discovery = setup(tmp_path)
    research.lock = asyncio.Lock()
    saved = await tracking.save(body(discovery))
    original_execute = discovery.execute

    async def detail(sid):
        receipt = research.store.data["receipts"][f"{sid}:frozen-request"]
        root = research.store.directory(sid)
        manifest = json.loads((root / "outputs/research-report.json").read_text())
        delivery = {
            "task_id": receipt["research_contract"]["task_id"],
            "required_formats": ["html"],
            "files": [{**item, "valid": True} for item in manifest["artifacts"]],
        }
        files = research.store.files(sid)
        sources = evidence_index(files, [], [])
        quality = quality_result(research, sid, receipt, files, sources, delivery)
        report = quality.pop("report")
        assert quality["status"] == "passed", quality["issues"]
        assert "report_content_sha256" not in quality
        return {
            "status": "completed",
            "research_quality": quality,
            "research_report": report,
            "research_report_versions": quality_versions(research, sid),
            "research_report_delivery": report_delivery(
                research, sid, receipt, report["content_sha256"]
            ),
        }

    async def execute(hid, request_id):
        result = await original_execute(hid, request_id)
        sid = result["session_id"]
        root = research.store.directory(sid)
        research.store.session(sid)["delivery_key"] = "frozen-request"
        receipt = research.store.data["receipts"][f"{sid}:frozen-request"]
        receipt["research_contract"] = make_contract(
            "a" * 24, "风险", ["风险"], "2026-10-23", "deep"
        )
        receipt["delivery"] = {"task_id": "a" * 24, "required_formats": ["html"]}
        receipt["quality_checks"], receipt["quality_archives"] = {}, {}
        (root / "inputs/risk.txt").write_text("存在经营不确定性。", encoding="utf-8")
        source = evidence_index(research.store.files(sid), [], [])[0]
        write_research_report(
            root / "outputs",
            {
                "task_id": "a" * 24,
                "title": "风险",
                "as_of": "2026-10-23",
                "required_sections": ["风险"],
                "sections": [
                    {
                        "id": "risk",
                        "heading": "风险",
                        "text": "存在经营不确定性。",
                        "citations": [source["id"]],
                    }
                ],
                "notes": [
                    {"stage_id": "risk", "text": "存在经营不确定性。", "citations": [source["id"]]}
                ],
                "coverage": [
                    {
                        "requirement_id": "r1",
                        "section_ids": ["risk"],
                        "excerpt": "存在经营不确定性。",
                    }
                ],
                "sources": [{"id": source["id"], "title": source["title"]}],
                "missing": [],
            },
            formats=["html"],
        )
        checked = await check_quality(research, sid)
        assert checked["status"] == "passed" and checked["report_delivery"]["status"] == "bound"
        assert checked["report_content_sha256"]
        if check_proof == "missing_check":
            receipt["quality_checks"].clear()
        elif check_proof == "mismatched_check":
            checked["report_content_sha256"] = "b" * 64
        return result

    research.detail, discovery.execute = detail, execute
    discovery.revision = "two"
    actual = research.automations._new_run(
        saved["id"], trigger="manual", scheduled_for=None, retry_of=None, status="running"
    )
    await tracking.execute(research.automations.get(saved["id"]), actual)
    run = tracking.list()["items"][0]["runs"][0]
    assert run["quality_status"] == "passed"
    assert run["accepted"] is (check_proof == "bound")
