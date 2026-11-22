"""Source publication and the watchlist persistence primitive share one Store fence.

These thread-level tests do not claim HTTP scheduling or import authorization coverage.
"""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from source_capture_fixture import fixed_response, offline_http

from app.research_web import research_web_sources as sources
from app.research_web.resources.research_report import source_id
from app.research_web.store import Store, StoreError
from app.research_web.watchlist_import import NAMESPACE, WatchlistImports


@pytest.mark.parametrize(
    "capture_fails,import_fails", [(True, False), (False, True), (False, False)]
)
def test_source_and_watchlist_persistence_keep_committed_state(
    tmp_path, monkeypatch, capture_fails, import_fails
):
    store = Store(tmp_path / "store")
    sid = store.create("claw", "synthetic")["id"]
    store.data["watchlists"]["fixture"] = {"items": []}
    store.save()
    imports = WatchlistImports(SimpleNamespace(store=store))
    selected = {
        "id": source_id("https://capture.invalid/article"),
        "url": "https://capture.invalid/article",
        "title": "fixture",
    }
    offline_http(monkeypatch, fixed_response(b"synthetic source body"))
    document = sources.fetch_document(selected["url"])
    staged, importer_observed_lock = threading.Event(), threading.Event()
    identities = {}
    real_save, real_replace = store.save, os.replace

    def save():
        if threading.get_ident() == identities.get("capture"):
            staged.set()
            assert importer_observed_lock.wait(10), "importer never reached the Store fence"
        return real_save()

    def replace(source, destination, *args, **kwargs):
        if destination == store.index:
            current = threading.get_ident()
            if (capture_fails and current == identities.get("capture")) or (
                import_fails and current == identities.get("importer")
            ):
                raise OSError("injected pre-replace persistence failure")
        return real_replace(source, destination, *args, **kwargs)

    monkeypatch.setattr(store, "save", save)
    monkeypatch.setattr(os, "replace", replace)

    def capture():
        identities["capture"] = threading.get_ident()
        try:
            sources._publish_source(SimpleNamespace(store=store), sid, selected, document)
        except StoreError:
            assert capture_fails
            return "failed"
        assert not capture_fails
        return "saved"

    def import_watchlist():
        identities["importer"] = threading.get_ident()
        assert staged.wait(10), "capture did not stage"
        # In the old implementation this succeeds and persists the uncommitted
        # capture first. Under the publication fence it must wait for rollback.
        acquired = store.write_lock.acquire(blocking=False)
        try:
            if not acquired:
                importer_observed_lock.set()
                store.write_lock.acquire()
                acquired = True
            try:
                imports._save(
                    {"schema_version": 1, "previews": {}, "keys": {}},
                    "fixture",
                    {"items": [{"asset": "600519.SH"}]},
                )
            except StoreError:
                assert import_fails
                return "failed"
            assert not import_fails
            return "saved"
        finally:
            if acquired:
                store.write_lock.release()
            importer_observed_lock.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        publication = pool.submit(capture)
        importing = pool.submit(import_watchlist)
        assert publication.result(timeout=15) == ("failed" if capture_fails else "saved")
        assert importing.result(timeout=15) == ("failed" if import_fails else "saved")

    disk = json.loads(store.index.read_text())
    memory = store.session(sid)
    assert disk["watchlists"] == store.data["watchlists"]
    assert disk.get(NAMESPACE) == store.data.get(NAMESPACE)
    assert disk["sessions"][sid].get("files", {}) == memory["files"]
    assert disk["sessions"][sid].get("web_evidence", {}) == memory.get("web_evidence", {})
    relative = "inputs/web-" + selected["id"][4:] + ".txt"
    assert (store.directory(sid) / relative).exists() is not capture_fails
    assert bool(disk["watchlists"]["fixture"]["items"]) is not import_fails
    if not capture_fails:
        source = disk["sessions"][sid]["web_evidence"][selected["id"]]
        assert source["capture_schema"] == "research_web_capture_v1"
        assert sources.capture_proof(store.root, sid, source, b"synthetic source body")
