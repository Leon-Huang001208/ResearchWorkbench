"""Persist commentary generation run logs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from core.contracts.commentary import (
    CommentaryRunRecord,
    CommentaryRunRecordRequest,
    CommentaryRunRecordResponse,
)
from core.observability import get_logger

logger = get_logger(__name__)


class CommentaryRunService:
    """Append and read commentary generation run records from logs."""

    def __init__(self, logs_dir: str | Path = "logs"):
        self.logs_dir = Path(logs_dir)
        self.log_path = self.logs_dir / "commentary_runs.jsonl"

    def record_run(
        self,
        request: CommentaryRunRecordRequest,
    ) -> CommentaryRunRecordResponse:
        """Persist one commentary run as a JSONL record."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        record = CommentaryRunRecord(
            run_id=f"commentary-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
            recipe_id=request.recipe_id,
            recipe_title=request.recipe_title,
            draft_markdown=request.draft_markdown,
            model=request.model,
            provider=request.provider,
            warnings=request.warnings,
            evidence_count=request.evidence_count,
            selected_evidence_count=request.selected_evidence_count,
            quality_status=request.quality_status,
            quality_summary=request.quality_summary,
            created_at=datetime.utcnow(),
        )
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json())
            handle.write("\n")
        logger.info(
            "commentary_run_recorded",
            run_id=record.run_id,
            recipe_id=record.recipe_id,
            quality_status=record.quality_status,
        )
        return CommentaryRunRecordResponse(
            run_id=record.run_id,
            log_path=str(self.log_path),
            record=record,
        )

    def list_runs(self, limit: int = 20) -> list[CommentaryRunRecord]:
        """Return recent commentary run records, newest first."""
        if not self.log_path.exists():
            return []
        records: list[CommentaryRunRecord] = []
        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    records.append(CommentaryRunRecord(**json.loads(raw)))
                except Exception as exc:
                    logger.warning(
                        "commentary_run_record_parse_failed",
                        error=str(exc),
                    )
        return list(reversed(records))[: max(1, min(limit, 100))]
