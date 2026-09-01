#!/usr/bin/env python3
"""Dry-run-first migration of traceable LSH theme CSV files.

This command never imports LSH code. It reads the frozen CSV sources through
the bundled Research Pack manifests and writes accepted facts only when the
operator passes ``--apply`` explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.contracts.theme_research import IngestionCheckpoint
from core.observability import get_logger, setup_logging
from data_layer.repositories.base import Base, db_session
from data_layer.repositories.theme_research_repository import (
    ThemeResearchRepository,
)
from services.theme_pack_registry import ThemePackRegistry
from services.theme_research_service import (
    ThemeIngestionError,
    ThemeResearchService,
)

logger = get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PACK_ROOT = _PROJECT_ROOT / "resources" / "research_packs"

_SOURCE_FOLDERS: dict[str, tuple[str, dict[str, tuple[str, str]]]] = {
    "aerospace-etf-analysis": (
        "aerospace",
        {
            "launch-activity": ("aerospace", "launch_activity"),
            "industry-drivers": ("aerospace", "industry_drivers"),
            "cn5082-valuation-history": ("aerospace", "cn5082_valuation"),
            "market-trend": ("aerospace", "market_trend"),
            "etf-flow-shares": ("aerospace", "etf_flow_shares"),
            "constituent-fundamentals": ("aerospace", "constituent_fundamentals"),
            "market-valuation-sentiment": ("aerospace", "market_valuation_sentiment"),
            "prime-contractor-map": ("aerospace", "prime_contractor_map"),
        },
    ),
    "photovoltaic-etf-analysis": (
        "photovoltaic",
        {
            "weekly-prices-detail": ("photovoltaic", "weekly_prices_detail"),
            "price-consensus": ("photovoltaic", "price_consensus"),
            "demand-installation": ("photovoltaic", "demand_installation"),
            "supply-profitability": ("photovoltaic", "supply_profitability"),
            "weekly-prices": ("photovoltaic", "weekly_prices"),
            "market-trend": ("photovoltaic", "market_trend"),
            "market-valuation-sentiment": (
                "photovoltaic",
                "market_valuation_sentiment",
            ),
            "catalysts": ("photovoltaic", "catalysts"),
        },
    ),
    "chinext50-etf-analysis": (
        "ai_infrastructure",
        {
            "optical-module-customs-official": (
                "ai_infrastructure",
                "optical_module_customs",
            ),
            "ai-token-usage": ("ai_infrastructure", "ai_token_usage"),
            "ai-supply-chain-revenue": (
                "ai_infrastructure",
                "ai_supply_chain_revenue",
            ),
            "ai-model-catalog": ("ai_infrastructure", "ai_model_catalog"),
            "ai-track": ("ai_infrastructure", "ai_track"),
            "macro-snapshot": ("ai_infrastructure", "macro_snapshot"),
            "market-trend": ("ai_infrastructure", "market_trend"),
            "market-valuation-sentiment": (
                "ai_infrastructure",
                "market_valuation_sentiment",
            ),
            "pv-track": ("photovoltaic", "pv_track"),
            "catalysts": ("ai_infrastructure", "catalysts"),
            "driver-summary": ("ai_infrastructure", "driver_summary"),
        },
    ),
}


class MigrationCLIError(RuntimeError):
    """The migration command cannot safely scan or publish its report."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="LSH manual_data/skills root")
    parser.add_argument("--output", type=Path, required=True, help="JSON report destination")
    parser.add_argument(
        "--resume-from",
        type=Path,
        help="prior JSON report whose per-file checkpoints should be resumed",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="write accepted observations")
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="explicitly select the default no-write mode",
    )
    return parser


def run_migration(
    source: Path,
    output: Path,
    *,
    db_session: Session,
    apply: bool = False,
    resume_from: Path | None = None,
) -> dict[str, Any]:
    """Scan all known top-level LSH Pack CSVs and atomically publish a report."""

    source_root = Path(source).resolve()
    if not source_root.is_dir():
        raise MigrationCLIError("source directory does not exist or is not readable")
    output_path = Path(output).resolve()
    checkpoints = _load_resume_checkpoints(resume_from, source_root, apply=apply)
    service = ThemeResearchService(
        ThemeResearchRepository(db_session),
        ThemePackRegistry(_PACK_ROOT),
    )
    totals = {
        "accepted": 0,
        "quarantined": 0,
        "rejected": 0,
        "duplicate": 0,
        "applied": 0,
    }
    files: list[dict[str, Any]] = []

    for source_file, pack_key, dataset_key in _iter_sources(source_root):
        relative_path = source_file.relative_to(source_root).as_posix()
        checkpoint = checkpoints.get(relative_path)
        try:
            result = service.ingest_file(
                pack_key,
                dataset_key,
                source_file,
                apply=apply,
                checkpoint=checkpoint,
            )
            file_report = result.model_dump(mode="json")
        except ThemeIngestionError as exc:
            try:
                source_hash = f"sha256:{hashlib.sha256(source_file.read_bytes()).hexdigest()}"
            except OSError as read_exc:
                raise MigrationCLIError("source file became unreadable during scan") from read_exc
            logger.warning(
                "LSH theme file rejected",
                pack_key=pack_key,
                dataset_key=dataset_key,
                source_hash=source_hash,
                error_type=type(exc).__name__,
            )
            file_report = {
                "pack_key": pack_key,
                "dataset_key": dataset_key,
                "source_hash": source_hash,
                "dry_run": not apply,
                "accepted": 0,
                "quarantined": 0,
                "rejected": 1,
                "duplicate": 0,
                "applied": 0,
                "rows": [],
                "checkpoint": {
                    "source_hash": source_hash,
                    "last_row_number": 1,
                    "mode": "apply" if apply else "dry-run",
                },
                "file_error_code": "invalid_source_file",
            }
        file_report["source_file"] = relative_path
        files.append(file_report)
        for key in totals:
            totals[key] += int(file_report[key])

    report = {
        "mode": "apply" if apply else "dry-run",
        "source_root": str(source_root),
        "generated_at": datetime.now(UTC).isoformat(),
        "target_revision": "018",
        "resumed_from": str(Path(resume_from).resolve()) if resume_from else None,
        "files_scanned": len(files),
        "totals": totals,
        "source_hashes": {item["source_file"]: item["source_hash"] for item in files},
        "checkpoints": {item["source_file"]: item["checkpoint"] for item in files},
        "files": files,
    }
    if apply:
        try:
            db_session.commit()
        except SQLAlchemyError as exc:
            db_session.rollback()
            logger.error(
                "LSH theme migration commit failed",
                files_scanned=len(files),
                error_type=type(exc).__name__,
            )
            raise MigrationCLIError("database commit failed; apply report was not written") from exc
    _write_report_atomic(output_path, report)
    logger.info(
        "LSH theme migration completed",
        mode=report["mode"],
        files_scanned=report["files_scanned"],
        accepted=totals["accepted"],
        quarantined=totals["quarantined"],
        rejected=totals["rejected"],
        duplicate=totals["duplicate"],
        applied=totals["applied"],
    )
    return report


def _load_resume_checkpoints(
    resume_from: Path | None,
    source_root: Path,
    *,
    apply: bool,
) -> dict[str, IngestionCheckpoint]:
    if resume_from is None:
        return {}
    resume_path = Path(resume_from).resolve()
    try:
        raw = json.loads(resume_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MigrationCLIError("resume report cannot be read safely") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("checkpoints"), dict):
        raise MigrationCLIError("resume report does not contain checkpoints")
    if Path(str(raw.get("source_root", ""))).resolve() != source_root:
        raise MigrationCLIError("resume report source root does not match --source")
    expected_mode = "apply" if apply else "dry-run"
    if raw.get("mode") != expected_mode:
        raise MigrationCLIError("resume report mode is incompatible with this migration")
    try:
        return {
            str(relative_path): IngestionCheckpoint.model_validate(checkpoint)
            for relative_path, checkpoint in raw["checkpoints"].items()
        }
    except (TypeError, ValueError) as exc:
        raise MigrationCLIError("resume report contains invalid checkpoints") from exc


def _iter_sources(source_root: Path) -> list[tuple[Path, str, str]]:
    sources: list[tuple[Path, str, str]] = []
    for folder_name, (default_pack, mappings) in sorted(_SOURCE_FOLDERS.items()):
        folder = source_root / folder_name
        if not folder.is_dir():
            continue
        for source_file in sorted(folder.glob("*.csv")):
            pack_key, dataset_key = mappings.get(
                source_file.stem,
                (default_pack, f"unmapped_{source_file.stem.replace('-', '_')}"),
            )
            sources.append((source_file.resolve(), pack_key, dataset_key))
    return sources


def _write_report_atomic(output: Path, report: dict[str, Any]) -> None:
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            temporary_path = Path(handle.name)
        os.replace(temporary_path, output)
    except OSError as exc:
        logger.error(
            "LSH migration report write failed",
            output=str(output),
            error_type=type(exc).__name__,
        )
        raise MigrationCLIError("migration report cannot be written") from exc


def main(argv: Sequence[str] | None = None) -> int:
    setup_logging()
    args = build_parser().parse_args(argv)
    try:
        if args.apply:
            with db_session() as session:
                run_migration(
                    args.source,
                    args.output,
                    db_session=session,
                    apply=True,
                    resume_from=args.resume_from,
                )
        else:
            import data_layer.repositories.models  # noqa: F401

            engine = create_engine("sqlite:///:memory:")
            Base.metadata.create_all(engine)
            with Session(engine) as session:
                run_migration(
                    args.source,
                    args.output,
                    db_session=session,
                    apply=False,
                    resume_from=args.resume_from,
                )
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns a stable nonzero status
        logger.error("LSH theme migration failed", error_type=type(exc).__name__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
