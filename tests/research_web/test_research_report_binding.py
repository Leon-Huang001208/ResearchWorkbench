"""A same-turn repaired canonical report has its own Host-anchored quality receipt."""

import asyncio
import hashlib
import json
from types import SimpleNamespace

from app.research_web.research_evidence import evidence_index
from app.research_web.research_quality import make_contract
from app.research_web.research_quality_service import (
    check_quality,
    quality_result,
    quality_versions,
)
from app.research_web.resources.research_report import write_research_report
from app.research_web.store import Store


def test_repaired_version_binds_new_bytes_and_retains_previous_host_quality(tmp_path):
    async def run():
        store = Store(tmp_path / "data")
        sid = store.create("fingpt", "版本绑定")["id"]
        store.session(sid)["delivery_key"] = "one-turn"
        receipt = {
            "research_contract": make_contract("a" * 24, "风险", ["风险"], "2026-10-16", "deep")
        }
        store.data["receipts"][sid + ":one-turn"] = receipt
        root = store.directory(sid)
        (root / "inputs/risk.txt").write_text("存在经营不确定性。", encoding="utf-8")
        source = evidence_index(store.files(sid), [], [])[0]
        payload = {
            "task_id": "a" * 24,
            "title": "风险",
            "as_of": "2026-10-16",
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
                {"requirement_id": "r1", "section_ids": ["risk"], "excerpt": "存在经营不确定性。"}
            ],
            "sources": [{"id": source["id"], "title": source["title"]}],
            "missing": ["待补查"],
        }
        service = SimpleNamespace(store=store, lock=asyncio.Lock())

        async def detail(_sid):
            current = json.loads((root / "outputs/research-report.json").read_text())
            delivery = {"files": [{**a, "valid": True} for a in current["artifacts"]]}
            files = store.files(sid)
            sources = evidence_index(files, [], [])
            result = quality_result(service, sid, receipt, files, sources, delivery)
            return {"research_quality": result, "research_report": result["report"]}

        service.detail = detail
        write_research_report(root / "outputs", payload)
        first = await check_quality(service, sid)
        first_bytes = (root / "outputs/research-report.json").read_bytes()
        assert first["report_content_sha256"] == hashlib.sha256(first_bytes).hexdigest()
        assert first["status"] == "incomplete" and first["may_repair"]
        payload["missing"] = []
        write_research_report(root / "outputs", payload)
        second = await check_quality(service, sid)
        assert second["report_content_sha256"] != first["report_content_sha256"]
        assert second["status"] == "passed" and not second["may_repair"]
        assert second["repair_count"] == 1
        assert await check_quality(service, sid) == second
        versions = quality_versions(service, sid)
        assert len(versions) == 1
        assert versions[0]["quality"]["status"] == "incomplete"
        assert (
            next(f for f in versions[0]["files"] if f["name"] == "research-report.json")["sha256"]
            == first["report_content_sha256"]
        )
        # A model-written sidecar cannot replace the canonical report or receipt.
        (root / "outputs/research-report-v3.json").write_text('{"quality":"passed"}')
        assert await check_quality(service, sid) == second

    asyncio.run(run())


def test_exact_version_quality_wins_over_unrelated_latest_result():
    from app.research_web.research_quality_service import receipt_archives

    anchor = {"version_id": "A", "files": [{"name": "research-report.json", "sha256": "a" * 64}]}
    old = {"status": "incomplete", "report_content_sha256": "a" * 64}
    other = {"status": "passed", "report_content_sha256": "b" * 64}
    receipt = {
        "quality_archive": anchor,
        "quality_last_result": other,
        "quality_archives": {"A": {"anchor": anchor, "check_id": "check-A"}},
        "quality_checks": {"check-A": old},
    }
    assert receipt_archives(receipt) == [(anchor, old)]
    receipt["quality_archives"] = {}
    assert receipt_archives(receipt)[0][1]["status"] == "incomplete"
    receipt["quality_last_result"] = {"status": "passed", "report_content_sha256": "a" * 64}
    assert receipt_archives(receipt)[0][1]["status"] == "passed"
