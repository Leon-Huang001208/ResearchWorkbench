"""Market data scheduler index structure job tests."""


def test_market_data_scheduler_runs_configured_index_structure_batch():
    from services.market_data_scheduler import MarketDataScheduler

    calls = []

    class FakeSessionFactory:
        def __enter__(self):
            return "db-session"

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

    def fake_repo_factory(db):
        assert db == "db-session"
        return "repo"

    def fake_ingestor(repo, *, provider, index_codes):
        assert repo == "repo"
        calls.append((provider, tuple(index_codes)))
        return {
            "index_master": len(index_codes),
            "index_component_snapshot": len(index_codes) * 100,
            "errors": 0,
        }

    scheduler = MarketDataScheduler(
        index_structure_codes={"CSI": ["000300"], "CNI": ["399001", "399006"]},
        index_structure_ingestor=fake_ingestor,
        index_structure_session_factory=FakeSessionFactory,
        index_structure_repo_factory=fake_repo_factory,
    )

    result = scheduler._index_structure_ingest()

    assert calls == [("CSI", ("000300",)), ("CNI", ("399001", "399006"))]
    assert result == {
        "status": "completed",
        "providers": 2,
        "index_master": 3,
        "index_component_snapshot": 300,
        "errors": 0,
    }
    stats = scheduler.get_status()["stats"]
    assert stats["last_index_structure_run"] is not None
    assert stats["last_index_structure_errors"] == 0


def test_market_data_scheduler_can_start_without_gap_check(monkeypatch):
    import services.market_data_scheduler as scheduler_module
    from services.market_data_scheduler import MarketDataScheduler

    jobs = []

    class FakeScheduler:
        def __init__(self, timezone):
            self.timezone = timezone

        def add_job(self, func, trigger, **kwargs):
            jobs.append(kwargs["id"])

        def start(self):
            return None

        def shutdown(self, wait=False):
            return None

    monkeypatch.setattr(scheduler_module, "APSCHEDULER_AVAILABLE", True)
    monkeypatch.setattr(scheduler_module, "AsyncIOScheduler", FakeScheduler)

    scheduler = MarketDataScheduler(enable_gap_check=False)
    scheduler.start()

    assert "market_data_daily_ingest" in jobs
    assert "market_data_index_structure_ingest" in jobs
    assert "market_data_gap_check" not in jobs
    scheduler.stop()
