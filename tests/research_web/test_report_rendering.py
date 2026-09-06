"""Reviewed report projection regressions."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

from app.research_web.report_rendering import render_report_payload
from app.research_web.store import Store


@pytest.mark.skipif(sys.platform != "darwin", reason="renderer requires native macOS sandbox")
def test_report_payload_projects_to_real_office_and_html_files(tmp_path: Path):
    store = Store(tmp_path)
    session = store.create("claw", "report projection")
    root = store.directory(session["id"])
    (root / "outputs" / "report_payload.json").write_text(
        json.dumps(
            {
                "title": "真实周报",
                "as_of": "2026-09-04",
                "summary": "基于锁定资料形成。",
                "sections": [
                    {"id": "market", "title": "市场回顾", "content": "市场数据存在部分缺失。"},
                    {"id": "risk", "title": "风险提示", "content": "历史数据不代表未来。"},
                ],
                "sources": [{"title": "DataHub 快照", "as_of": "2026-09-04"}],
                "missing": ["行业数据尚未更新"],
            },
            ensure_ascii=False,
        )
    )

    result = asyncio.run(
        render_report_payload(store, session["id"], ["docx", "html", "xlsx"])
    )

    assert result["status"] == "completed"
    for name in ("report.docx", "report.html", "report.xlsx"):
        assert (root / "outputs" / name).stat().st_size > 0


@pytest.mark.skipif(sys.platform != "darwin", reason="renderer requires native macOS sandbox")
def test_report_projection_requires_structured_payload(tmp_path: Path):
    store = Store(tmp_path)
    session = store.create("claw", "missing payload")
    result = asyncio.run(render_report_payload(store, session["id"], ["html"]))
    assert result["status"] == "missing_payload"
