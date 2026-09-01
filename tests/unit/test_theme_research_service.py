"""Behavior tests for theme observations, projections, and safe ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from core.contracts.platform_shared import FreshnessStatus
from core.contracts.theme_research import IngestionCheckpoint, PackLifecycle
from data_layer.repositories.theme_research_repository import ThemeResearchRepository
from services.theme_pack_registry import ThemePackRegistry
from services.theme_research_service import ThemeIngestionError, ThemeResearchService

PACK_ROOT = Path(__file__).parents[2] / "resources" / "research_packs"
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _service(db_session) -> ThemeResearchService:
    repository = ThemeResearchRepository(db_session)
    registry = ThemePackRegistry(PACK_ROOT)
    return ThemeResearchService(repository, registry, now=lambda: NOW)


def _write_gold_csv(path: Path) -> Path:
    path.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-31,XAUUSD,close,3500.5,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n",
        encoding="utf-8",
    )
    return path


def test_ingestion_defaults_to_dry_run_and_preserves_source_hash(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = _write_gold_csv(tmp_path / "gold-price.csv")

    report = service.ingest_file("gold", "gold_price", source)

    assert report.dry_run is True
    assert report.accepted == 1
    assert report.applied == 0
    assert report.source_hash.startswith("sha256:")
    assert service.repository.count_observations("gold") == 0


def test_apply_is_idempotent_by_source_hash_and_row_identity(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = _write_gold_csv(tmp_path / "gold-price.csv")

    first = service.ingest_file("gold", "gold_price", source, apply=True)
    second = service.ingest_file("gold", "gold_price", source, apply=True)

    assert (first.accepted, first.applied, first.duplicate) == (1, 1, 0)
    assert (second.accepted, second.applied, second.duplicate) == (0, 0, 1)
    assert first.source_hash == second.source_hash
    assert service.repository.count_observations("gold") == 1


def test_duplicate_rows_inside_one_source_are_not_inserted_twice(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = _write_gold_csv(tmp_path / "gold-price.csv")
    content = source.read_text(encoding="utf-8")
    source.write_text(content + content.splitlines()[1] + "\n", encoding="utf-8")

    report = service.ingest_file("gold", "gold_price", source, apply=True)

    assert (report.accepted, report.duplicate, report.applied) == (1, 1, 1)
    assert service.repository.count_observations("gold") == 1


def test_optional_manifest_columns_may_be_absent_from_csv_header(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,status,last_checked\n"
        "2026-08-31,XAUUSD,close,3500.5,USD/oz,LBMA,fresh,2026-09-01T01:00:00+00:00\n",
        encoding="utf-8",
    )

    report = service.ingest_file("gold", "gold_price", source)

    assert report.accepted == 1


def test_normalizer_accepts_grouped_numbers_and_datetime_in_date_column(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,status,last_checked\n"
        '2026-08-31 00:00:00,XAUUSD,close,"3,500.5",USD/oz,LBMA,available,2026-09-01\n',
        encoding="utf-8",
    )

    report = service.ingest_file("gold", "gold_price", source)

    assert report.accepted == 1


def test_resume_checkpoint_must_match_the_immutable_source_hash(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = _write_gold_csv(tmp_path / "gold-price.csv")

    try:
        service.ingest_file(
            "gold",
            "gold_price",
            source,
            checkpoint=IngestionCheckpoint(
                source_hash="sha256:different",
                last_row_number=2,
            ),
        )
    except ThemeIngestionError as exc:
        assert "checkpoint source hash" in str(exc)
    else:
        raise AssertionError("mismatched checkpoint must be rejected")


def test_ingestion_reports_quarantined_and_rejected_rows(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "bad-date,XAUUSD,close,3500,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n"
        "2026-08-31,XAUUSD,close,3500,,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n",
        encoding="utf-8",
    )

    report = service.ingest_file("gold", "gold_price", source)

    assert report.accepted == 0
    assert report.quarantined == 1
    assert report.rejected == 1
    assert {row.outcome for row in report.rows} == {"quarantined", "rejected"}
    assert report.checkpoint.last_row_number == 3


def test_ingestion_rejects_prohibited_lsh_files_and_fields(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "catalysts.csv"
    source.write_text(
        "observation_date,catalyst,current_status,score_hint,last_checked\n"
        "2026-08-31,test,active,5,2026-09-01\n",
        encoding="utf-8",
    )

    report = service.ingest_file("photovoltaic", "catalysts", source)

    assert report.rejected == 1
    assert report.rows[0].error_code == "forbidden_lsh_content"
    assert service.repository.count_observations("photovoltaic") == 0


def test_apply_persists_only_rejection_totals_not_forbidden_source_rows(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "driver-summary.csv"
    source.write_text(
        "observation_date,driver_summary\n2026-08-31,do-not-migrate\n",
        encoding="utf-8",
    )

    report = service.ingest_file("ai_infrastructure", "driver_summary", source, apply=True)
    health = service.get_health("ai_infrastructure")

    assert report.rejected == 1
    assert health.rejected == 1
    assert service.repository.count_observations("ai_infrastructure") == 0


def test_gold_vertical_returns_typed_six_projection_surface(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    service.sync_manifests()
    service.ingest_file(
        "gold",
        "gold_price",
        _write_gold_csv(tmp_path / "gold-price.csv"),
        apply=True,
    )

    snapshot = service.get_snapshot("gold")
    kpis = service.get_kpis("gold")
    value_chain = service.get_value_chain("gold")
    events = service.get_events("gold")
    assets = service.get_assets("gold")
    health = service.get_health("gold")

    assert snapshot.pack_key == "gold"
    assert snapshot.coverage > 0
    assert snapshot.freshness_status is FreshnessStatus.FRESH
    assert kpis.pack_key == "gold" and kpis.series
    assert value_chain.pack_key == "gold" and value_chain.nodes
    assert events.pack_key == "gold"
    assert assets.pack_key == "gold" and assets.assets
    assert health.pack_key == "gold" and health.accepted == 1


def test_manifest_sync_is_idempotent(db_session) -> None:
    service = _service(db_session)

    first = service.sync_manifests()
    second = service.sync_manifests()

    assert [manifest.status for manifest in first] == [PackLifecycle.ENABLED] * 4
    assert [manifest.status for manifest in second] == [PackLifecycle.ENABLED] * 4


def test_manifest_resync_preserves_ingestion_health_history(db_session, tmp_path: Path) -> None:
    service = _service(db_session)
    service.sync_manifests()
    service.ingest_file(
        "gold",
        "gold_price",
        _write_gold_csv(tmp_path / "gold-price.csv"),
        apply=True,
    )

    service.sync_manifests()

    assert service.get_health("gold").accepted == 1


def test_workspace_entry_builds_prefilled_request_without_writing_facts(db_session) -> None:
    service = _service(db_session)

    request = service.create_research_workspace_request("gold", "央行购金与金价")

    assert request.pack_key == "gold"
    assert request.title == "央行购金与金价"
    assert request.template_key in service.registry.get("gold").research_template_keys
    assert service.repository.count_observations("gold") == 0
