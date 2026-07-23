"""ETLRunRepository 单元测试"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_layer.repositories.base import Base
from data_layer.repositories.etl_run_repository import ETLRunRepository


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture
def repo(db_session):
    return ETLRunRepository(db_session)


class TestETLRunRepository:
    def test_start_creates_run(self, repo):
        repo.start("run-001", "ingest_stock_master", "akshare")

        run = repo.get_run("run-001")
        assert run is not None
        assert run.job_name == "ingest_stock_master"
        assert run.source == "akshare"
        assert run.status == "running"

    def test_finish_updates_run(self, repo):
        repo.start("run-002", "ingest_daily_bars", "akshare")
        repo.finish("run-002", status="success", items_fetched=100, items_saved=100)

        run = repo.get_run("run-002")
        assert run.status == "success"
        assert run.items_fetched == 100
        assert run.items_saved == 100
        assert run.finished_at is not None

    def test_fail_updates_run(self, repo):
        repo.start("run-003", "ingest_daily_bars", "akshare")
        repo.fail("run-003", "Network timeout")

        run = repo.get_run("run-003")
        assert run.status == "failed"
        assert run.error_message == "Network timeout"
        assert run.finished_at is not None

    def test_get_recent_runs(self, repo):
        repo.start("run-a", "job_a", "akshare")
        repo.start("run-b", "job_b", "akshare")
        repo.start("run-c", "job_c", "akshare")

        runs = repo.get_recent_runs(limit=2)
        assert len(runs) == 2

    def test_get_nonexistent_run(self, repo):
        assert repo.get_run("nonexistent") is None
