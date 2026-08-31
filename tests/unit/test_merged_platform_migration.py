"""Schema and Alembic tests for the merged platform's 20 additive tables."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Column, MetaData, Table, Text, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from data_layer.repositories.base import Base

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "storage" / "migrations" / "versions"
EXPECTED_BY_REVISION = {
    "015": {
        "asset_registry",
        "asset_identifier",
        "theme_observation",
        "scheduled_job",
        "domain_event",
    },
    "016": {"theme_pack", "market_home_snapshot"},
    "017": {
        "research_workspace",
        "research_session",
        "research_message",
        "runtime_provider",
        "skill_definition",
        "agent_team",
        "agent_schedule",
        "research_note",
    },
    "018": {
        "watchlist",
        "watchlist_item",
        "alert_rule",
        "alert_event",
        "notification",
    },
}
MIGRATION_FILES = {
    "015": MIGRATIONS / "015_add_platform_fact_core.py",
    "016": MIGRATIONS / "016_add_theme_and_market_home.py",
    "017": MIGRATIONS / "017_add_research_workspace_runtime.py",
    "018": MIGRATIONS / "018_add_asset_observation.py",
}


def _load_migration(revision: str):
    path = MIGRATION_FILES[revision]
    spec = importlib.util.spec_from_file_location(f"migration_{revision}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_four_migrations_create_exactly_the_approved_twenty_tables():
    found: set[str] = set()
    for revision, expected in EXPECTED_BY_REVISION.items():
        source = MIGRATION_FILES[revision].read_text(encoding="utf-8")
        created = set(re.findall(r'op\.create_table\(\s*"([^"]+)"', source))
        assert created == expected
        found.update(expected)

    assert len(found) == 20
    assert not {
        "source_ref",
        "research_run_v2",
        "stock_fact",
        "index_fact",
        "etf_fact",
        "fund_fact",
        "theme_kpi_series",
        "theme_value_chain",
    }.intersection(found)


def test_merged_migrations_form_a_single_015_to_018_chain():
    expected_down = {"015": "014", "016": "015", "017": "016", "018": "017"}
    for revision, down_revision in expected_down.items():
        module = _load_migration(revision)
        assert module.revision == revision
        assert module.down_revision == down_revision


def test_orm_metadata_contains_exact_merged_table_set_and_builds_on_sqlite():
    expected = set().union(*EXPECTED_BY_REVISION.values())
    assert expected.issubset(Base.metadata.tables)

    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    try:
        assert expected.issubset(set(inspect(engine).get_table_names()))
    finally:
        Base.metadata.drop_all(bind=engine)


def test_identity_note_and_watchlist_foreign_keys_are_explicit():
    identifiers = Base.metadata.tables["asset_identifier"]
    watchlist_items = Base.metadata.tables["watchlist_item"]
    notes = Base.metadata.tables["research_note"]

    assert {fk.target_fullname for fk in identifiers.foreign_keys} == {"asset_registry.asset_id"}
    assert {fk.target_fullname for fk in watchlist_items.foreign_keys} == {
        "asset_registry.asset_id",
        "watchlist.watchlist_id",
    }
    assert {fk.target_fullname for fk in notes.foreign_keys} == {
        "research_claim.claim_id",
        "research_run.run_id",
        "research_workspace.workspace_id",
    }
    assert "workspace_id" not in Base.metadata.tables["research_message"].c
    assert any(
        constraint.name == "ck_research_note_source_shape" for constraint in notes.constraints
    )
    assert any(
        constraint.name == "ck_asset_identifier_valid_window"
        for constraint in identifiers.constraints
    )
    assert any(
        constraint.name == "ex_asset_identifier_no_overlap"
        for constraint in identifiers.constraints
    )


def test_new_tables_define_identity_constraints_and_time_indexes():
    asset_identifier = Base.metadata.tables["asset_identifier"]
    observation = Base.metadata.tables["theme_observation"]
    domain_event = Base.metadata.tables["domain_event"]
    notification = Base.metadata.tables["notification"]

    identifier_unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in asset_identifier.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("scheme", "value", "market", "valid_from") in identifier_unique_columns
    assert observation.c.observed_at.index is True
    assert domain_event.c.occurred_at.index is True
    assert notification.c.created_at.index is True


def test_015_to_018_upgrade_and_downgrade_on_sqlite(tmp_path: Path):
    database_path = tmp_path / "merged.sqlite"
    database_url = f"sqlite:///{database_path}"
    engine = create_engine(database_url)
    prerequisite_metadata = MetaData()
    Table("research_run", prerequisite_metadata, Column("run_id", Text, primary_key=True))
    Table(
        "research_claim",
        prerequisite_metadata,
        Column("claim_id", Text, primary_key=True),
        Column("run_id", Text, nullable=False),
    )
    prerequisite_metadata.create_all(engine)

    config = Config(str(ROOT / "storage" / "migrations" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "storage" / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.stamp(config, "014")
    command.upgrade(config, "018")

    expected = set().union(*EXPECTED_BY_REVISION.values())
    assert expected.issubset(set(inspect(engine).get_table_names()))

    with engine.begin() as connection:
        connection.execute(text("""
                INSERT INTO asset_registry (asset_id, asset_type, canonical_name)
                VALUES ('asset-1', 'stock', 'Asset 1')
                """))
        connection.execute(text("""
                INSERT INTO asset_identifier (
                    identifier_id, asset_id, scheme, value, market, valid_from, valid_to
                ) VALUES (
                    'identifier-1', 'asset-1', 'wind', '600000.SH', 'CN',
                    '2026-01-01T00:00:00+00:00', '2026-02-01T00:00:00+00:00'
                )
                """))
        connection.execute(text("""
                INSERT INTO asset_identifier (
                    identifier_id, asset_id, scheme, value, market, valid_from, valid_to
                ) VALUES (
                    'identifier-adjacent', 'asset-1', 'wind', '600000.SH', 'CN',
                    '2026-02-01T00:00:00+00:00', '2026-03-01T00:00:00+00:00'
                )
                """))

    with (
        pytest.raises(IntegrityError, match="asset_identifier validity overlap"),
        engine.begin() as connection,
    ):
        connection.execute(text("""
                INSERT INTO asset_identifier (
                    identifier_id, asset_id, scheme, value, market, valid_from, valid_to
                ) VALUES (
                    'identifier-overlap', 'asset-1', 'wind', '600000.SH', 'CN',
                    '2026-01-15T00:00:00+00:00', '2026-01-20T00:00:00+00:00'
                )
                """))

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("""
                INSERT INTO asset_identifier (
                    identifier_id, asset_id, scheme, value, market, valid_from, valid_to
                ) VALUES (
                    'identifier-reversed', 'asset-1', 'wind', '600001.SH', 'CN',
                    '2026-02-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'
                )
                """))

    with engine.begin() as connection:
        connection.execute(text("""
                INSERT INTO research_workspace (
                    workspace_id, project_id, title, status
                ) VALUES ('workspace-1', 'project-1', 'Workspace', 'active')
                """))

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("""
                INSERT INTO research_note (
                    note_id, note_key, workspace_id, run_id, claim_id, revision,
                    source_kind, summary
                ) VALUES (
                    'note-invalid', 'note-key', 'workspace-1', 'run-1', 'claim-1', 1,
                    'claim', 'invalid dual source'
                )
                """))

    command.downgrade(config, "014")
    assert expected.isdisjoint(set(inspect(engine).get_table_names()))
