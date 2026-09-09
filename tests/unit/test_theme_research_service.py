"""Behavior tests for theme observations, projections, and safe ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier, Lock, Thread

import pytest
import yaml
from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.dml import Update

from core.contracts.market_home import MarketHomeSectionKey
from core.contracts.platform_shared import FreshnessStatus, SourceRef, SourceTier
from core.contracts.theme_research import (
    IngestionCheckpoint,
    PackLifecycle,
    ThemeObservation,
)
from data_layer.repositories.base import Base
from data_layer.repositories.models import DomainEventDB, ThemePackDB
from data_layer.repositories.theme_research_repository import ThemeResearchRepository
from services.theme_pack_registry import ThemePackRegistry
from services.theme_research_service import (
    ThemeIngestionError,
    ThemePackNotFoundError,
    ThemeResearchService,
)

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


def test_duplicate_requires_equal_fully_normalized_payload(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        '2026-08-31,XAUUSD,close,"3,500.5",USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n'
        "2026-08-31,XAUUSD,close,3500.5,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n",
        encoding="utf-8",
    )

    report = service.ingest_file("gold", "gold_price", source, apply=True)

    assert (report.accepted, report.duplicate, report.quarantined, report.applied) == (
        1,
        1,
        0,
        1,
    )


def test_semantically_equal_identity_dates_are_deduplicated_after_normalization(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = _write_gold_csv(tmp_path / "gold-price.csv")
    service.ingest_file("gold", "gold_price", source, apply=True)
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-31T15:30:00+08:00,XAUUSD,close,3500.5,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n",
        encoding="utf-8",
    )

    report = service.ingest_file("gold", "gold_price", source, apply=True)

    assert (report.accepted, report.duplicate, report.quarantined) == (0, 1, 0)
    assert service.repository.count_observations("gold") == 1


def test_same_source_payload_remains_duplicate_when_computed_freshness_ages(
    db_session,
    tmp_path: Path,
) -> None:
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-31,XAUUSD,close,3500.5,USD/oz,LBMA,https://www.lbma.org.uk,available,2026-09-01T01:00:00+00:00\n",
        encoding="utf-8",
    )
    repository = ThemeResearchRepository(db_session)
    ThemeResearchService(
        repository,
        ThemePackRegistry(PACK_ROOT),
        now=lambda: datetime(2026, 9, 1, 12, tzinfo=UTC),
    ).ingest_file("gold", "gold_price", source, apply=True)

    report = ThemeResearchService(
        repository,
        ThemePackRegistry(PACK_ROOT),
        now=lambda: datetime(2026, 9, 3, 12, tzinfo=UTC),
    ).ingest_file("gold", "gold_price", source, apply=True)

    assert (report.accepted, report.duplicate, report.quarantined) == (0, 1, 0)
    assert repository.count_observations("gold") == 1


def test_identity_with_different_normalized_value_is_quarantined_without_overwrite(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-31,XAUUSD,close,3500.5,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n"
        "2026-08-31,XAUUSD,close,3600.5,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n",
        encoding="utf-8",
    )

    report = service.ingest_file("gold", "gold_price", source, apply=True)
    stored = service.repository.list_observations("gold", dataset_key="gold_price")

    assert (report.accepted, report.duplicate, report.quarantined, report.applied) == (
        1,
        0,
        1,
        1,
    )
    assert next(row.error_code for row in report.rows if row.outcome == "quarantined") == (
        "identity_payload_conflict"
    )
    assert [observation.value for observation in stored] == [3500.5]


def test_wide_row_expands_each_declared_value_into_an_observation(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "weekly-prices-detail.csv"
    source.write_text(
        "observation_date,metric,spec,price_low,price_mid,price_high,unit,source_name,source_url,source_date,confidence,notes\n"
        "2026-08-20,polysilicon,N-type,30,31.5,41,CNY/kg,InfoLink,https://www.infolink-group.com/spot-price/cn/,2026-08-20,high,test\n",
        encoding="utf-8",
    )

    report = service.ingest_file("photovoltaic", "weekly_prices_detail", source, apply=True)
    observations = service.repository.list_observations(
        "photovoltaic", dataset_key="weekly_prices_detail"
    )

    assert (report.accepted, report.applied) == (3, 3)
    assert {item.metric_key for item in observations} == {
        "polysilicon.price_low",
        "polysilicon.price_mid",
        "polysilicon.price_high",
    }
    assert {item.value for item in observations} == {30.0, 31.5, 41.0}


def test_customs_source_row_discriminator_preserves_distinct_same_dimension_rows(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "optical-module-customs-official.csv"
    source.write_text(
        "observation_date,flow,region,partner,hs_code,metric,value,unit,quantity,quantity_unit,source_name,source_url,source_file,status,notes,imported_at\n"
        "2026-06-01,export,福建省,马来西亚,85177950,optical_module_trade_value,3045005,元人民币,269,千克,海关统计数据查询,http://stats.customs.gov.cn/,数据导出.csv,official_manual_import,first,2026-07-27\n"
        "2026-06-01,export,福建省,马来西亚,85177950,optical_module_trade_value,6579,元人民币,1,千克,海关统计数据查询,http://stats.customs.gov.cn/,数据导出.csv,official_manual_import,second,2026-07-27\n",
        encoding="utf-8",
    )

    report = service.ingest_file(
        "ai_infrastructure",
        "optical_module_customs",
        source,
        apply=True,
    )
    observations = service.repository.list_observations(
        "ai_infrastructure",
        dataset_key="optical_module_customs",
    )

    assert (report.accepted, report.quarantined, report.applied) == (4, 0, 4)
    assert len({item.row_identity for item in observations}) == 4
    assert {item.value for item in observations} == {3045005.0, 269.0, 6579.0, 1.0}
    snapshot = service.get_snapshot("ai_infrastructure")
    assert len(snapshot.facts) == len(observations) == 4


def test_customs_value_revision_conflicts_instead_of_creating_a_new_identity(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    header = (
        "observation_date,flow,region,partner,hs_code,metric,value,unit,quantity,"
        "quantity_unit,source_name,source_url,source_file,status,notes,imported_at\n"
    )
    first = tmp_path / "customs-first.csv"
    first.write_text(
        header
        + "2026-06-01,export,福建省,马来西亚,85177950,optical_module_trade_value,3045005,元人民币,269,千克,海关统计数据查询,http://stats.customs.gov.cn/,数据导出.csv,official_manual_import,first,2026-07-27\n",
        encoding="utf-8",
    )
    revised = tmp_path / "customs-revised.csv"
    revised.write_text(
        header
        + "2026-06-01,export,福建省,马来西亚,85177950,optical_module_trade_value,4045005,元人民币,269,千克,海关统计数据查询,http://stats.customs.gov.cn/,数据导出.csv,official_manual_import,first,2026-07-27\n",
        encoding="utf-8",
    )

    first_report = service.ingest_file(
        "ai_infrastructure", "optical_module_customs", first, apply=True
    )
    revised_report = service.ingest_file(
        "ai_infrastructure", "optical_module_customs", revised, apply=True
    )

    assert first_report.accepted == 2
    assert (revised_report.accepted, revised_report.quarantined, revised_report.duplicate) == (
        0,
        2,
        0,
    )
    assert service.repository.count_observations("ai_infrastructure") == 2


def test_token_usage_other_rank_preserves_both_wide_row_facts(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "ai-token-usage.csv"
    source.write_text(
        "observation_date,window,model_permaslug,total_tokens,rank_position,source_name,source_url,source_date,confidence,notes\n"
        "2026-07-21,daily,other,571651059916,other,OpenRouter rankings daily,https://openrouter.ai/docs/api/api-reference/datasets/get-rankings-daily,2026-08-20,high,aggregate remainder\n",
        encoding="utf-8",
    )

    report = service.ingest_file("ai_infrastructure", "ai_token_usage", source, apply=True)

    assert (report.accepted, report.quarantined, report.rejected) == (2, 0, 0)
    observations = service.repository.list_observations(
        "ai_infrastructure", dataset_key="ai_token_usage"
    )
    assert {item.metric_key for item in observations} == {
        "total_tokens",
        "rank_position",
    }


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
                mode="dry-run",
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


def test_row_source_tier_is_not_inherited_from_dataset_priority(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-31,XAUUSD,close,3500.5,USD/oz,Unknown Blog,https://example.com/gold,fresh,2026-09-01T01:00:00+00:00\n",
        encoding="utf-8",
    )

    service.ingest_file("gold", "gold_price", source, apply=True)
    observation = service.repository.list_observations("gold")[0]

    assert observation.source_refs[0].tier is SourceTier.PUBLIC


def test_source_name_tokens_cannot_self_promote_to_official(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-31,XAUUSD,close,3500.5,USD/oz,official_attacker,https://example.com/gold,fresh,2026-09-01T01:00:00+00:00\n",
        encoding="utf-8",
    )

    service.ingest_file("gold", "gold_price", source, apply=True)

    observation = service.repository.list_observations("gold")[0]
    assert observation.source_refs[0].tier is SourceTier.PUBLIC


def test_unavailable_row_does_not_count_toward_snapshot_coverage(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-31,XAUUSD,close,3500.5,USD/oz,LBMA,https://www.lbma.org.uk,unavailable,2026-09-01T01:00:00+00:00\n",
        encoding="utf-8",
    )

    service.ingest_file("gold", "gold_price", source, apply=True)

    assert service.get_snapshot("gold").coverage == 0.0


def test_snapshot_applies_dataset_sla_even_when_row_reports_fresh(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-20,XAUUSD,close,3500.5,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-08-21T01:00:00+00:00\n",
        encoding="utf-8",
    )
    service.ingest_file("gold", "gold_price", source, apply=True)

    snapshot = service.get_snapshot("gold")

    assert snapshot.coverage == 0.0
    assert snapshot.freshness_status is FreshnessStatus.STALE


def test_official_event_requires_explicit_row_verification(
    db_session,
) -> None:
    service = _service(db_session)
    source = SourceRef(
        source_id="official",
        name="Official",
        tier=SourceTier.OFFICIAL,
        content_hash="sha256:event",
    )
    base = {
        "pack_key": "gold",
        "dataset_key": "gold_events",
        "subject_ref": "theme:gold:event",
        "metric_key": "central_bank_purchase",
        "value": "reported",
        "unit": None,
        "as_of": NOW,
        "observed_at": NOW,
        "available_at": NOW,
        "source_refs": [source],
        "freshness_status": FreshnessStatus.FRESH,
        "quality_flags": [],
        "source_hash": "sha256:event",
    }
    service.repository.insert_observation(
        ThemeObservation(
            observation_id="event-lead",
            row_identity="lead",
            payload={"record_type": "event"},
            **base,
        )
    )
    service.repository.insert_observation(
        ThemeObservation(
            observation_id="event-verified",
            row_identity="verified",
            payload={"record_type": "event", "verification_status": "verified"},
            **base,
        )
    )

    events = service.get_events("gold")

    assert [event.observation_id for event in events.verified] == ["event-verified"]
    assert [event.observation_id for event in events.leads] == ["event-lead"]


def test_snapshot_keeps_subjects_separate_and_uses_fact_as_of(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-30,XAUUSD,close,3500.5,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n"
        "2026-08-31,XAUCNY,close,25000,CNY/oz,SGE,https://www.sge.com.cn,fresh,2026-09-01T02:00:00+00:00\n",
        encoding="utf-8",
    )
    service.ingest_file("gold", "gold_price", source, apply=True)

    snapshot = service.get_snapshot("gold")

    assert set(snapshot.facts) == {
        "gold_price:theme:gold:XAUUSD:close",
        "gold_price:theme:gold:XAUCNY:close",
    }
    assert snapshot.as_of == datetime(2026, 8, 31, tzinfo=UTC)
    assert snapshot.available_at == datetime(2026, 9, 1, 2, tzinfo=UTC)


def test_snapshot_selects_max_fact_as_of_not_latest_publication_of_old_fact(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-31,XAUUSD,close,3500,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n"
        "2026-08-30,XAUUSD,close,3400,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T02:00:00+00:00\n"
        "2026-09-01,XAUUSD,close,3600,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-02T01:00:00+00:00\n",
        encoding="utf-8",
    )
    service.ingest_file("gold", "gold_price", source, apply=True)

    snapshot = service.get_snapshot("gold", datetime(2026, 9, 1, 3, tzinfo=UTC))
    fact = snapshot.facts["gold_price:theme:gold:XAUUSD:close"]

    assert fact["value"] == 3500
    assert snapshot.as_of == datetime(2026, 8, 31, tzinfo=UTC)


def test_snapshot_and_health_share_selected_fact_coverage_semantics(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-31,XAUUSD,close,3500,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n"
        "2026-08-31,XAUCNY,close,25000,CNY/oz,SGE,https://www.sge.com.cn,unavailable,2026-09-01T02:00:00+00:00\n",
        encoding="utf-8",
    )
    service.ingest_file("gold", "gold_price", source, apply=True)

    snapshot = service.get_snapshot("gold")
    health = service.get_health("gold")

    assert snapshot.freshness_status is FreshnessStatus.UNAVAILABLE
    assert snapshot.coverage == 0.0
    assert health.dataset_coverage["gold_price"] == 0.0


def test_snapshot_kpi_and_events_expose_effective_sla_freshness(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-20,XAUUSD,close,3500,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-08-20T01:00:00+00:00\n"
        "2026-08-20,central-bank,central_bank_purchase,1,event,LBMA,https://www.lbma.org.uk,fresh,2026-08-20T01:00:00+00:00\n",
        encoding="utf-8",
    )
    service.ingest_file("gold", "gold_price", source, apply=True)

    snapshot = service.get_snapshot("gold")
    kpis = service.get_kpis("gold")
    events = service.get_events("gold")

    assert snapshot.freshness_status is FreshnessStatus.STALE
    assert {fact["freshness_status"] for fact in snapshot.facts.values()} == {"stale"}
    assert kpis.series[0].observation.freshness_status is FreshnessStatus.STALE
    assert events.leads[0].freshness_status is FreshnessStatus.STALE
    assert service.repository.list_observations("gold")[0].freshness_status is FreshnessStatus.FRESH


def test_kpi_projection_filters_the_manifest_metric_exactly(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
        "2026-08-31,XAUUSD,close,3500.5,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n"
        "2026-08-31,XAUUSD,open,3400.5,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n",
        encoding="utf-8",
    )
    service.ingest_file("gold", "gold_price", source, apply=True)

    kpis = service.get_kpis("gold")

    gold_close = [item for item in kpis.series if item.kpi_key == "gold_close"]
    assert [item.observation.metric_key for item in gold_close] == ["close"]


def test_observation_as_of_is_observed_time_not_publication_time(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)
    service.ingest_file(
        "gold",
        "gold_price",
        _write_gold_csv(tmp_path / "gold-price.csv"),
        apply=True,
    )

    observation = service.repository.list_observations("gold")[0]

    assert observation.as_of == datetime(2026, 8, 31, tzinfo=UTC)
    assert observation.available_at == datetime(2026, 9, 1, 1, tzinfo=UTC)


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


def test_database_lifecycle_remains_authoritative_across_manifest_resync(db_session) -> None:
    first_service = _service(db_session)
    first_service.sync_manifests()
    first_service.repository.update_pack_status("gold", "1.0.0", PackLifecycle.DEGRADED)

    second_service = _service(db_session)
    synced = second_service.sync_manifests()

    gold = next(manifest for manifest in synced if manifest.pack_key == "gold")
    assert gold.status is PackLifecycle.DEGRADED


def test_manifest_version_is_immutable_but_new_version_can_be_inserted(db_session) -> None:
    service = _service(db_session)
    service.sync_manifests()
    original = service.repository.get_manifest("gold", "1.0.0")
    assert original is not None
    changed = original.model_copy(update={"boundary": "changed without version bump"})

    with pytest.raises(ValueError, match="immutable"):
        service.repository.save_manifest(changed)

    assert service.repository.get_manifest("gold", "1.0.0") == original
    upgraded = changed.model_copy(update={"version": "1.1.0"})
    service.repository.save_manifest(upgraded)
    assert service.repository.get_manifest("gold", "1.1.0") == upgraded


def test_manifest_caller_cannot_bypass_immutability_with_persisted_hash(db_session) -> None:
    service = _service(db_session)
    service.sync_manifests()
    original = service.repository.get_manifest("gold", "1.0.0")
    assert original is not None
    changed = original.model_copy(update={"boundary": "caller-controlled overwrite"})

    with pytest.raises(TypeError):
        service.repository.save_manifest(  # type: ignore[call-arg]
            changed,
            content_hash=service.registry.content_hash(original),
        )

    assert service.repository.get_manifest("gold", "1.0.0") == original


def test_repository_rejects_invalid_or_illegal_lifecycle_writes(db_session) -> None:
    service = _service(db_session)
    service.sync_manifests()

    with pytest.raises(ValueError, match="PackLifecycle"):
        service.repository.update_pack_status(
            "gold", "1.0.0", "evil_status"  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="transition"):
        service.repository.update_pack_status("gold", "1.0.0", PackLifecycle.VALIDATED)

    persisted = service.repository.get_manifest("gold", "1.0.0")
    assert persisted is not None
    assert persisted.status is PackLifecycle.ENABLED


def test_lifecycle_update_uses_expected_status_compare_and_swap(db_session) -> None:
    service = _service(db_session)
    service.sync_manifests()
    statements: list[str] = []

    def capture_update(conn, cursor, statement, parameters, context, executemany) -> None:
        del conn, cursor, parameters, context, executemany
        if statement.lstrip().upper().startswith("UPDATE THEME_PACK"):
            statements.append(statement)

    event.listen(db_session.get_bind(), "before_cursor_execute", capture_update)
    try:
        service.repository.update_pack_status("gold", "1.0.0", PackLifecycle.DEGRADED)
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", capture_update)

    assert len(statements) == 1
    where_clause = statements[0].split("WHERE", maxsplit=1)[1]
    assert "pack_key" in where_clause
    assert "version" in where_clause
    assert "status" in where_clause


def test_lifecycle_compare_and_swap_rejects_intervening_terminal_state(
    db_session,
    monkeypatch,
) -> None:
    service = _service(db_session)
    service.sync_manifests()
    original_execute = db_session.execute
    injected = False

    def inject_terminal_transition(statement, *args, **kwargs):
        nonlocal injected
        if isinstance(statement, Update) and not injected:
            injected = True
            original_execute(
                update(ThemePackDB)
                .where(
                    ThemePackDB.pack_key == "gold",
                    ThemePackDB.version == "1.0.0",
                )
                .values(status=PackLifecycle.DISABLED.value)
            )
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", inject_terminal_transition)

    with pytest.raises(ValueError, match="concurrent lifecycle transition"):
        service.repository.update_pack_status("gold", "1.0.0", PackLifecycle.DEGRADED)

    db_session.expire_all()
    persisted = service.repository.get_manifest("gold", "1.0.0")
    assert persisted is not None
    assert persisted.status is PackLifecycle.DISABLED


def test_workspace_entry_builds_prefilled_request_without_writing_facts(db_session) -> None:
    service = _service(db_session)

    request = service.create_research_workspace_request("gold", "央行购金与金价")

    assert request.pack_key == "gold"
    assert request.title == "央行购金与金价"
    assert request.template_key in service.registry.get("gold").research_template_keys
    assert service.repository.count_observations("gold") == 0


def test_declared_market_home_fact_flushes_invalidation_in_same_transaction(
    db_session,
    tmp_path: Path,
) -> None:
    raw = yaml.safe_load((PACK_ROOT / "gold" / "manifest.yaml").read_text("utf-8"))
    raw["datasets"][0]["market_home_section"] = "market_mainlines"
    pack_dir = tmp_path / "packs" / "gold"
    pack_dir.mkdir(parents=True)
    (pack_dir / "manifest.yaml").write_text(
        yaml.safe_dump(raw, allow_unicode=True),
        encoding="utf-8",
    )
    repository = ThemeResearchRepository(db_session)
    service = ThemeResearchService(
        repository,
        ThemePackRegistry(tmp_path / "packs"),
        now=lambda: NOW,
    )

    service.ingest_file(
        "gold",
        "gold_price",
        _write_gold_csv(tmp_path / "gold-price.csv"),
        apply=True,
    )

    event = db_session.query(DomainEventDB).one()
    assert event.payload["section_key"] == MarketHomeSectionKey.MARKET_MAINLINES.value
    assert repository.count_observations("gold") == 1
    repeated = service.ingest_file(
        "gold",
        "gold_price",
        _write_gold_csv(tmp_path / "gold-price.csv"),
        apply=True,
    )
    assert repeated.duplicate == 1
    assert db_session.query(DomainEventDB).count() == 1
    db_session.rollback()
    assert db_session.query(DomainEventDB).count() == 0
    assert repository.count_observations("gold") == 0


def test_source_payload_cannot_self_authorize_market_home_invalidation(
    db_session,
    tmp_path: Path,
) -> None:
    raw = yaml.safe_load((PACK_ROOT / "gold" / "manifest.yaml").read_text("utf-8"))
    raw["datasets"][0]["fields"].append(
        {"name": "market_home_section", "data_type": "string", "required": False}
    )
    pack_dir = tmp_path / "packs" / "gold"
    pack_dir.mkdir(parents=True)
    (pack_dir / "manifest.yaml").write_text(
        yaml.safe_dump(raw, allow_unicode=True),
        encoding="utf-8",
    )
    service = ThemeResearchService(
        ThemeResearchRepository(db_session),
        ThemePackRegistry(tmp_path / "packs"),
        now=lambda: NOW,
    )
    source = tmp_path / "gold-price.csv"
    source.write_text(
        "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked,market_home_section\n"
        "2026-08-31,XAUUSD,close,3500.5,USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00,market_mainlines\n",
        encoding="utf-8",
    )

    service.ingest_file("gold", "gold_price", source, apply=True)

    assert db_session.query(DomainEventDB).count() == 0


def test_concurrent_source_hash_conflict_serializes_semantic_identity(tmp_path: Path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'theme-concurrency.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as setup_session:
        _service(setup_session).sync_manifests()
        setup_session.commit()
    files = []
    for index, value in enumerate((3500.0, 3600.0), start=1):
        source = tmp_path / f"gold-{index}.csv"
        source.write_text(
            "observation_date,subject,metric,value,unit,source_name,source_url,status,last_checked\n"
            f"2026-08-31,XAUUSD,close,{value},USD/oz,LBMA,https://www.lbma.org.uk,fresh,2026-09-01T01:00:00+00:00\n",
            encoding="utf-8",
        )
        files.append(source)
    barrier = Barrier(2)
    result_lock = Lock()
    outcomes: list[tuple[int, int]] = []
    errors: list[Exception] = []

    def ingest(source: Path) -> None:
        with SessionLocal() as session:
            try:
                barrier.wait()
                report = _service(session).ingest_file("gold", "gold_price", source, apply=True)
                session.commit()
                with result_lock:
                    outcomes.append((report.accepted, report.quarantined))
            except Exception as exc:  # noqa: BLE001 - preserve thread failure for assertion
                session.rollback()
                with result_lock:
                    errors.append(exc)

    threads = [Thread(target=ingest, args=(source,)) for source in files]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert sorted(outcomes) == [(0, 1), (1, 0)]
    with SessionLocal() as verify_session:
        assert ThemeResearchRepository(verify_session).count_observations("gold") == 1


def test_sqlite_ingestion_lock_starts_transaction_and_releases_on_rollback(
    db_session,
) -> None:
    repository = ThemeResearchRepository(db_session)

    repository.lock_ingestion_namespace("gold", "gold_price")
    assert db_session.in_transaction()
    db_session.rollback()
    assert "theme_research_sqlite_locks" not in db_session.info

    repository.lock_ingestion_namespace("gold", "gold_price")
    db_session.rollback()
    assert "theme_research_sqlite_locks" not in db_session.info


def test_unknown_pack_apply_does_not_acquire_sqlite_ingestion_lock(
    db_session,
    tmp_path: Path,
) -> None:
    service = _service(db_session)

    with pytest.raises(ThemePackNotFoundError):
        service.ingest_file(
            "unknown",
            "unknown",
            tmp_path / "not-read.csv",
            apply=True,
        )

    assert "theme_research_sqlite_locks" not in db_session.info
