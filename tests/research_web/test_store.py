"""Ownership, idempotency and file path constraints."""

import pytest

from app.research_web.store import Store, StoreError


def test_index_persists_without_storing_transcripts(tmp_path):
    store = Store(tmp_path)
    session = store.create("fingpt", "新研究")
    assert Store(tmp_path).session(session["id"])["title"] == "新研究"
    assert "messages" not in store.session(session["id"])
    with pytest.raises(StoreError):
        store.session("../other")


def test_idempotency_survives_restart_and_rejects_changed_payload(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "研究")["id"]
    assert store.reserve(sid, "key", "hash")
    assert not Store(tmp_path).reserve(sid, "key", "hash")
    with pytest.raises(StoreError):
        store.reserve(sid, "key", "changed")


def test_files_never_follow_symlinks_or_cross_sessions(tmp_path):
    store = Store(tmp_path / "data")
    sid = store.create("fingpt", "研究")["id"]
    outside = tmp_path / "secret.txt"
    outside.write_text("private")
    (store.directory(sid) / "outputs" / "leak.txt").symlink_to(outside)
    assert store.files(sid) == []
    with pytest.raises(StoreError):
        store.file_path(sid, "../../secret.txt")


def test_generated_files_have_opaque_ids_and_are_discovered(tmp_path):
    store = Store(tmp_path)
    sid = store.create("claw", "行业")["id"]
    (store.directory(sid) / "outputs" / "report.md").write_text("# Report")
    files = store.files(sid)
    assert len(files) == 1 and files[0]["name"] == "report.md"
    assert store.file_path(sid, files[0]["id"]).read_text() == "# Report"


def test_download_opens_without_following_replaced_output_symlink(tmp_path):
    store = Store(tmp_path / "store")
    sid = store.create("fingpt", "研究")["id"]
    output = store.directory(sid) / "outputs" / "report.md"
    output.write_text("report")
    fid = store.files(sid)[0]["id"]
    output.unlink()
    secret = tmp_path / "canary.md"
    secret.write_text("canary")
    output.symlink_to(secret)
    with pytest.raises(StoreError):
        store.open_file(sid, fid)
