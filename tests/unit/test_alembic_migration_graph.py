"""Alembic migration graph integrity tests."""


def test_alembic_migrations_have_unique_revisions_and_single_head():
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    migrations_dir = Path(__file__).resolve().parents[2] / "storage" / "migrations"
    config = Config(str(migrations_dir / "alembic.ini"))
    config.set_main_option("script_location", str(migrations_dir))

    script = ScriptDirectory.from_config(config)

    revision_ids = [revision.revision for revision in script.walk_revisions()]
    assert len(revision_ids) == len(set(revision_ids))
    assert script.get_heads() == ["012"]
