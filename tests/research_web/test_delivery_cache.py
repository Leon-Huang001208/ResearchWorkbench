"""Pure delivery proof/cache tests; native parser acceptance remains in test_delivery."""

import asyncio

import pytest

from app.research_web.store import Store


@pytest.mark.asyncio
async def test_final_delivery_is_revalidated_after_publication_changes(tmp_path, monkeypatch):
    import ast
    import hashlib
    import json

    from app.research_web import sandbox
    from app.research_web.delivery import Delivery

    store = Store(tmp_path)
    sid = store.create("fingpt", "report")["id"]
    delivery = Delivery(store)
    metadata = delivery.begin(sid, "key", ["md"])
    store.reserve(sid, "key", "digest", metadata)
    store.receipt(sid, "key", "accepted")
    folder = store.directory(sid) / "outputs"
    (folder / "result.md").write_text("first")
    calls = []

    def validate(_config, _cwd, code):
        candidates = json.loads(ast.literal_eval(code.splitlines()[0].split(" = ", 1)[1]))
        calls.append(candidates)
        return sandbox.ScriptResult(
            "completed",
            stdout=json.dumps([{**row, "valid": True, "reason": ""} for row in candidates]),
        )

    monkeypatch.setattr(sandbox, "run_script", validate)
    entries = [
        {"event": {"seq": 1, "type": "user/message", "data": {"content": metadata["marker"]}}},
        {"event": {"seq": 2, "type": "turn/end", "data": {"reason": {"kind": "completed"}}}},
    ]
    assert (await delivery.refresh(sid, entries, busy=False, connected=True))[
        "status"
    ] == "completed"
    await delivery.refresh(sid, entries, busy=False, connected=True)
    assert len(calls) == 1
    (folder / "result.md").write_text("corrected report")
    (folder / "verified.html").write_text("<p>corrected report</p>")
    result = await delivery.refresh(sid, entries, busy=False, connected=True)
    assert len(calls) == 2
    assert {f["name"] for f in result["files"]} == {"result.md", "verified.html"}
    assert (
        next(f["sha256"] for f in result["files"] if f["name"] == "result.md")
        == hashlib.sha256(b"corrected report").hexdigest()
    )


def test_archived_previous_report_cannot_satisfy_current_delivery(tmp_path):
    from app.research_web.delivery import Delivery

    store = Store(tmp_path)
    sid = store.create("fingpt", "report")["id"]
    archive = store.directory(sid) / "outputs/report-versions/previous"
    archive.mkdir(parents=True)
    (archive / "previous.pdf").write_bytes(b"old report")
    assert Delivery(store).snapshot(sid) == {}


@pytest.mark.asyncio
async def test_old_completed_key_is_not_returned_as_verified_current_delivery(tmp_path):
    from app.research_web.delivery import Delivery

    store = Store(tmp_path)
    sid = store.create("fingpt", "report")["id"]
    delivery = Delivery(store)
    old = delivery.begin(sid, "old", ["md"])
    store.reserve(sid, "old", "digest", old)
    old["status"] = "completed"
    current = delivery.begin(sid, "new", ["md"])
    store.reserve(sid, "new", "different", current)
    stale = await delivery.refresh(sid, [], busy=False, connected=True, key="old")
    assert stale["status"] == "verification_failed"
    assert stale["failure_code"] == "delivery_scope_unconfirmed"
    assert stale["files"] == []
    assert store.receipt(sid, "old")["delivery"]["status"] == "completed"
    assert store.session(sid)["delivery_key"] == "new"


@pytest.mark.asyncio
async def test_changed_bytes_revalidate_file_failure_without_retrying_unchanged_bytes(
    tmp_path, monkeypatch
):
    import ast
    import json

    from app.research_web import sandbox
    from app.research_web.delivery import Delivery

    store = Store(tmp_path)
    sid = store.create("fingpt", "report")["id"]
    delivery = Delivery(store)
    record = delivery.begin(sid, "key", ["md"])
    store.reserve(sid, "key", "digest", record)
    store.receipt(sid, "key", "accepted")
    output = store.directory(sid) / "outputs/result.md"
    output.write_text("first bytes")
    calls = []

    def check(_config, _cwd, code):
        calls.append(code)
        if len(calls) == 1:
            return sandbox.ScriptResult("failed")
        candidates = json.loads(ast.literal_eval(code.splitlines()[0].split(" = ", 1)[1]))
        return sandbox.ScriptResult(
            "completed",
            stdout=json.dumps([{**row, "valid": True, "reason": ""} for row in candidates]),
        )

    monkeypatch.setattr(sandbox, "run_script", check)
    entries = [
        {"event": {"seq": 1, "type": "user/message", "data": {"content": record["marker"]}}},
        {"event": {"seq": 2, "type": "turn/end", "data": {"reason": {"kind": "completed"}}}},
    ]
    assert (await delivery.refresh(sid, entries, busy=False, connected=True))[
        "status"
    ] == "verification_failed"
    assert (await delivery.refresh(sid, entries, busy=False, connected=True))[
        "status"
    ] == "verification_failed"
    assert len(calls) == 1
    output.write_text("corrected bytes")
    assert (await delivery.refresh(sid, entries, busy=False, connected=True))[
        "status"
    ] == "completed"
    assert len(calls) == 2
    record.update(status="verification_failed", failure_code="cancel_terminal_event_missing")
    output.write_text("another version cannot prove native cancellation")
    assert (await delivery.refresh(sid, entries, busy=False, connected=True))[
        "status"
    ] == "verification_failed"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_delivery_worker_scope_change_returns_unverified_without_publishing_old_pass(
    tmp_path, monkeypatch
):
    import ast
    import json
    import threading

    from app.research_web import sandbox
    from app.research_web.delivery import Delivery

    store = Store(tmp_path)
    sid = store.create("fingpt", "report")["id"]
    delivery = Delivery(store)
    record = delivery.begin(sid, "old-key", ["md"])
    store.reserve(sid, "old-key", "digest", record)
    store.receipt(sid, "old-key", "accepted")
    (store.directory(sid) / "outputs/report.md").write_text("valid bytes")
    started, release = threading.Event(), threading.Event()

    def parser(_config, _cwd, code):
        started.set()
        assert release.wait(10)
        candidates = json.loads(ast.literal_eval(code.splitlines()[0].split(" = ", 1)[1]))
        return sandbox.ScriptResult(
            "completed", stdout=json.dumps([{**r, "valid": True, "reason": ""} for r in candidates])
        )

    monkeypatch.setattr(sandbox, "run_script", parser)
    entries = [
        {"event": {"seq": 1, "type": "user/message", "data": {"content": record["marker"]}}},
        {"event": {"seq": 2, "type": "turn/end", "data": {"reason": {"kind": "completed"}}}},
    ]
    future = asyncio.create_task(delivery.refresh(sid, entries, busy=False, connected=True))
    try:
        assert await asyncio.to_thread(started.wait, 10)
        store.reserve(sid, "new-key", "new-digest", delivery.begin(sid, "new-key", []))
    finally:
        release.set()
    result = await future
    assert result["status"] == "verification_failed" and result["files"] == []
    assert result["failure_code"] == "delivery_scope_unconfirmed"
    assert store.receipt(sid, "old-key")["delivery"]["status"] != "completed"
    assert not any(f.get("valid") for f in store.receipt(sid, "old-key")["delivery"]["files"])
    assert store.session(sid)["delivery_key"] == "new-key"
