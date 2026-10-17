"""Source permissions and superseded native task results stay fail closed."""

from test_api import api, isolated_keyring

__all__ = ["api", "isolated_keyring"]


def test_quality_source_context_obeys_locked_source_scope(api):
    client, native, service = api
    sid = client.post(
        "/api/research/sessions", json={"mode": "fingpt", "source_scope": ["datahub"]}
    ).json()["id"]
    # Simulate a legacy input already on disk; it remains outside the allowed source scope.
    (service.store.directory(sid) / "inputs/private-legacy.csv").write_text("must-not-enter-prompt")
    source = service.store.files(sid)[0]
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "按冻结范围研究", "expected_formats": []},
        headers={"Idempotency-Key": "scope-context-check"},
    )
    assert response.status_code == 202
    prompt = [payload for name, payload in native.calls if name == "session.prompt"][-1]["content"]
    assert source["id"] not in prompt
    assert source["name"] not in prompt
    assert "must-not-enter-prompt" not in prompt


def test_quality_worker_cannot_publish_after_a_new_task_replaces_its_scope(api, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    import app.research_web.service as service_module

    client, _, service = api
    sid = client.post("/api/research/sessions", json={"mode": "fingpt"}).json()["id"]
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        json={"text": "研究", "expected_formats": []},
        headers={"Idempotency-Key": "quality-old-task"},
    )
    assert response.status_code == 202
    started, release = threading.Event(), threading.Event()
    worker_threads = []

    def quality(_service, _sid, receipt, *_args):
        worker_threads.append(threading.get_ident())
        started.set()
        assert release.wait(10)
        return {
            "status": "passed",
            "issues": [],
            "report": None,
            "contract": receipt["research_contract"],
        }

    monkeypatch.setattr(service_module, "quality_result", quality)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.get, f"/api/research/sessions/{sid}")
        try:
            assert started.wait(10)
            row = service.store.session(sid)
            old_key = row["delivery_key"]
            new_delivery = service.delivery.begin(sid, "quality-new-task", [])
            service.store.reserve(sid, "quality-new-task", "new", new_delivery)
            assert old_key != row["delivery_key"]
        finally:
            release.set()
        result = future.result(timeout=10)
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "research_quality_scope_changed"
    assert "quality_last_result" not in service.store.receipt(sid, "quality-new-task")
    assert worker_threads and worker_threads[0] != threading.get_ident()
