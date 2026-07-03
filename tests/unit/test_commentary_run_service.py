from core.contracts.commentary import CommentaryRunRecordRequest
from services.commentary_run_service import CommentaryRunService


def test_commentary_run_service_records_and_lists_runs(tmp_path):
    service = CommentaryRunService(logs_dir=tmp_path / "logs")

    response = service.record_run(
        CommentaryRunRecordRequest(
            recipe_id="market-drawdown",
            recipe_title="市场大跌归因",
            draft_markdown="# 市场大跌归因\n\n## 核心判断\n风险偏好回落。",
            model="deepseek-test",
            provider="fake-provider",
            warnings=["llm_returned_empty"],
            evidence_count=8,
            selected_evidence_count=5,
            quality_status="blocked",
            quality_summary={"blocked": 1, "warning": 2, "info": 0},
        )
    )

    assert response.run_id.startswith("commentary-")
    assert response.log_path.endswith("commentary_runs.jsonl")
    assert response.record.recipe_id == "market-drawdown"
    assert response.record.quality_status == "blocked"
    assert (tmp_path / "logs" / "commentary_runs.jsonl").exists()

    records = service.list_runs(limit=5)

    assert len(records) == 1
    assert records[0].run_id == response.run_id
    assert records[0].recipe_title == "市场大跌归因"
    assert records[0].selected_evidence_count == 5
