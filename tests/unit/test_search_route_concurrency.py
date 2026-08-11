"""Concurrency contract for search routes used by the desktop workbench."""

import inspect

from app.api.routes.search import global_search


def test_global_search_runs_blocking_sources_in_fastapi_threadpool():
    assert not inspect.iscoroutinefunction(global_search)
