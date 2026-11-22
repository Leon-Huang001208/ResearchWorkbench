"""Opt-in Host/HTTP indices acceptance using the existing owned socket-only PG helper."""

import os

import pytest
import test_market_reader as reader_tests
import test_market_store_live_postgres as postgres_tests

pytestmark = pytest.mark.skipif(
    os.environ.get("RWB_MARKET_STORE_LIVE_PG") != "1", reason="owned PostgreSQL gate not enabled"
)


@pytest.mark.asyncio
async def test_default_host_http_indices_owned_postgres(tmp_path, monkeypatch):
    # Reuse exactly the established bounded cluster/start/stop/remove contract.
    cluster = postgres_tests.LivePostgresTests
    reader_tests.forbid_credentials.__wrapped__(monkeypatch)
    cluster.setUpClass()
    instance = cluster()
    initialized = False
    try:
        instance.setUp()
        initialized = True
        await reader_tests.exercise_default_host(tmp_path, monkeypatch, instance.store)
        with instance.connect() as connection:
            assert connection.execute("SELECT count(*) FROM rwb_market_facts").fetchone()[0] == 1
    finally:
        try:
            if initialized:
                instance.tearDown()
        finally:
            cluster.tearDownClass()
