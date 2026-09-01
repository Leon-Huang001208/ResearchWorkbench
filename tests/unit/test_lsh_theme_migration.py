"""Tests for the deterministic LSH theme-data migration CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from data_layer.repositories.theme_research_repository import ThemeResearchRepository
from scripts.migrate_lsh_theme_data import (
    MigrationCLIError,
    build_parser,
    run_migration,
)


def _source_tree(root: Path) -> Path:
    aerospace = root / "aerospace-etf-analysis"
    aerospace.mkdir(parents=True)
    (aerospace / "launch-activity.csv").write_text(
        "observation_date,metric,scope,region,value,unit,status,source,notes,last_checked\n"
        "2026-08-31,launch_count,China,CN,12,count,fresh,CASC,,2026-09-01\n",
        encoding="utf-8",
    )
    photovoltaic = root / "photovoltaic-etf-analysis"
    photovoltaic.mkdir()
    (photovoltaic / "catalysts.csv").write_text(
        "observation_date,catalyst,current_status,score_hint,last_checked\n"
        "2026-08-31,test,active,5,2026-09-01\n",
        encoding="utf-8",
    )
    return root


def test_cli_parser_defaults_to_dry_run(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        ["--source", str(tmp_path), "--output", str(tmp_path / "report.json")]
    )

    assert args.apply is False


def test_script_entrypoint_can_run_from_a_file_path() -> None:
    script = Path(__file__).parents[2] / "scripts" / "migrate_lsh_theme_data.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--source" in completed.stdout


def test_dry_run_writes_aggregate_file_reports_without_database_writes(
    db_session,
    tmp_path: Path,
) -> None:
    source = _source_tree(tmp_path / "skills")
    output = tmp_path / "report.json"

    report = run_migration(source, output, db_session=db_session)

    assert report["mode"] == "dry-run"
    assert report["totals"] == {
        "accepted": 1,
        "quarantined": 0,
        "rejected": 1,
        "duplicate": 0,
        "applied": 0,
    }
    assert len(report["source_hashes"]) == 2
    assert len(report["checkpoints"]) == 2
    assert ThemeResearchRepository(db_session).count_observations("aerospace") == 0
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_explicit_apply_is_idempotent(db_session, tmp_path: Path) -> None:
    source = _source_tree(tmp_path / "skills")

    first = run_migration(source, tmp_path / "first.json", db_session=db_session, apply=True)
    second = run_migration(source, tmp_path / "second.json", db_session=db_session, apply=True)

    assert first["totals"]["applied"] == 1
    assert second["totals"]["duplicate"] == 1
    assert second["totals"]["applied"] == 0
    assert ThemeResearchRepository(db_session).count_observations("aerospace") == 1


def test_missing_source_fails_without_creating_report(db_session, tmp_path: Path) -> None:
    output = tmp_path / "report.json"

    with pytest.raises(MigrationCLIError, match="source directory"):
        run_migration(tmp_path / "missing", output, db_session=db_session)

    assert not output.exists()
