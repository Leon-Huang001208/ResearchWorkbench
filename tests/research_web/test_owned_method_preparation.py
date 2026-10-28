"""Preparation failures cannot strand unregistered owned-method inputs."""

import pytest
import test_owned_method_execution as fixtures
from test_api import isolated_keyring  # noqa: F401

from app.research_web import scenario_method_sources as methods
from app.research_web.store import StoreError

api = fixtures.api
prepared = fixtures.prepared


def admitted(api, monkeypatch):
    client, service, sid, _context, descriptor, headers, _source = prepared(api, monkeypatch)
    load = client.post(
        "/api/research/internal/data/skill-preflight",
        json={
            "session_id": sid,
            "native_name": descriptor["capability_id"],
            "tool_name": "skill",
            "loaded": True,
        },
        headers=headers,
    )
    assert load.status_code == 200, load.text
    body = {
        "session_id": sid,
        "tool_name": "research_run_script",
        "method_execution": descriptor,
        "call_id": "prepare-first",
        "pack_start": True,
    }
    return client, service, sid, headers, body


def test_resource_preflight_failure_leaves_no_private_files_and_allows_explicit_retry(
    api, monkeypatch
):
    client, service, sid, headers, body = admitted(api, monkeypatch)
    original = methods._file

    def rejected(root, relative, expected):
        if relative.startswith("resources/"):
            raise StoreError("资源预检失败", "method_resource_limit", 409)
        return original(root, relative, expected)

    monkeypatch.setattr(methods, "_file", rejected)
    first = client.post("/api/research/internal/data/skill-preflight", json=body, headers=headers)
    assert first.status_code == 409 and first.json()["error"]["code"] == "method_resource_limit"
    folder = service.store.directory(sid) / "inputs/methods"
    assert not folder.exists() or not any(folder.rglob("*"))
    assert not service._task_capabilities(sid)[0].get("method_executions")
    monkeypatch.setattr(methods, "_file", original)
    retry = client.post(
        "/api/research/internal/data/skill-preflight",
        json={**body, "call_id": "prepare-explicit-retry"},
        headers=headers,
    )
    assert retry.status_code == 200, retry.text


def test_actual_source_and_resource_byte_boundary_precedes_writes(api, monkeypatch):
    client, service, sid, headers, body = admitted(api, monkeypatch)
    context = methods.trusted_context(service, sid)
    selected = methods.bound_capabilities(service, context)[0]
    version, _ = methods._resources(service, selected)
    _, bodies, _ = methods.source_context(service, sid, selected["id"], context)
    root = service.store.directory(sid)
    resources = [
        (selected["resource_path"] + "/SKILL.md", selected["sha256"]),
        *[
            (selected["resource_path"] + "/" + item["path"], item["sha256"])
            for item in version["files"]
        ],
    ]
    exact = sum(methods._file(root, path, digest)["bytes"] for path, digest in resources) + sum(
        map(len, bodies.values())
    )
    monkeypatch.setattr(methods, "MAX_METHOD_BYTES", exact - 1)
    rejected = client.post(
        "/api/research/internal/data/skill-preflight", json=body, headers=headers
    )
    assert (
        rejected.status_code == 409 and rejected.json()["error"]["code"] == "method_resource_limit"
    )
    assert not (root / "inputs/methods").exists()
    monkeypatch.setattr(methods, "MAX_METHOD_BYTES", exact)
    retry = client.post(
        "/api/research/internal/data/skill-preflight",
        json={**body, "call_id": "budget-explicit-retry"},
        headers=headers,
    )
    assert retry.status_code == 200, retry.text


@pytest.mark.parametrize("fault", ["write", "fdopen", "readback", "save"])
def test_prepare_io_failure_rolls_back_only_own_births_and_can_retry(api, monkeypatch, fault):
    client, service, sid, headers, body = admitted(api, monkeypatch)
    root = service.store.directory(sid)
    with monkeypatch.context() as injected:
        if fault == "write":
            original = methods._Preparation.write

            def failed(self, relative, raw):
                original(self, relative, raw)
                raise OSError("injected write failure")

            injected.setattr(methods._Preparation, "write", failed)
        elif fault == "fdopen":
            original = methods.os.fdopen

            def failed(handle, mode, *args, **kwargs):
                if mode == "wb":
                    raise OSError("injected before stream construction")
                return original(handle, mode, *args, **kwargs)

            injected.setattr(methods.os, "fdopen", failed)
        elif fault == "readback":
            original = methods._file

            def failed(root, relative, expected):
                if relative.startswith("inputs/"):
                    raise StoreError("读回失败", "method_resource_changed", 409)
                return original(root, relative, expected)

            injected.setattr(methods, "_file", failed)
        else:
            injected.setattr(
                service.store,
                "save",
                lambda: (_ for _ in ()).throw(OSError("injected before save")),
            )
        failed_request = client.post(
            "/api/research/internal/data/skill-preflight", json=body, headers=headers
        )
        assert failed_request.status_code == 409, failed_request.text
    assert not (root / "inputs/methods").exists()
    assert not (root / "outputs/method-results").exists()
    assert not service._task_capabilities(sid)[0].get("method_executions")
    retry = client.post(
        "/api/research/internal/data/skill-preflight",
        json={**body, "call_id": "io-explicit-retry"},
        headers=headers,
    )
    assert retry.status_code == 200, retry.text


def test_replaced_inode_is_not_removed_and_unknown_residual_still_blocks(api, monkeypatch):
    client, service, sid, headers, body = admitted(api, monkeypatch)
    original = methods._Preparation.write
    replaced = []

    def changed(self, relative, raw):
        original(self, relative, raw)
        path = self.root / relative
        other = path.with_name(path.name + ".replacement")
        other.write_bytes(b"unknown replacement")
        other.replace(path)
        replaced.append(path)
        raise OSError("injected replacement")

    with monkeypatch.context() as injected:
        injected.setattr(methods._Preparation, "write", changed)
        result = client.post(
            "/api/research/internal/data/skill-preflight", json=body, headers=headers
        )
    assert (
        result.status_code == 409
        and result.json()["error"]["code"] == "method_preparation_rollback_unverified"
    )
    assert replaced[0].read_bytes() == b"unknown replacement"
    assert not service._task_capabilities(sid)[0].get("method_executions")
    retry = client.post(
        "/api/research/internal/data/skill-preflight",
        json={**body, "call_id": "unknown-not-retryable"},
        headers=headers,
    )
    assert retry.status_code == 409 and retry.json()["error"]["code"] == "method_input_unbound"


def test_committed_save_error_retains_real_unknown_without_retry(api, monkeypatch):
    client, service, sid, headers, body = admitted(api, monkeypatch)
    original = service.store.save

    def committed():
        original()
        raise OSError("injected after atomic publication")

    with monkeypatch.context() as injected:
        injected.setattr(service.store, "save", committed)
        result = client.post(
            "/api/research/internal/data/skill-preflight", json=body, headers=headers
        )
    assert (
        result.status_code == 409
        and result.json()["error"]["code"] == "method_preparation_outcome_unknown"
    )
    record = service._task_capabilities(sid)[0]["method_executions"][0]
    assert record["state"] == "started" and "native_result" not in record
    retry = client.post(
        "/api/research/internal/data/skill-preflight",
        json={**body, "call_id": "unknown-cannot-repeat"},
        headers=headers,
    )
    assert (
        retry.status_code == 409
        and retry.json()["error"]["code"] == "method_execution_unknown_do_not_retry"
    )


def test_reused_file_is_not_owned_by_failed_preparation(tmp_path):
    root = tmp_path.resolve()
    parent = root / "inputs/methods/previous"
    parent.mkdir(parents=True)
    original = parent / "source.source"
    original.write_bytes(b"existing")
    identity = original.stat().st_ino
    transaction = methods._Preparation(root)
    transaction.write("inputs/methods/previous/source.source", b"existing")
    transaction.write("inputs/methods/previous/new.source", b"new")
    assert transaction.rollback()
    assert original.read_bytes() == b"existing" and original.stat().st_ino == identity
    assert not (parent / "new.source").exists()


def test_failure_after_exclusive_open_still_has_rollback_identity(tmp_path, monkeypatch):
    transaction = methods._Preparation(tmp_path.resolve())
    with monkeypatch.context() as injected:
        injected.setattr(
            methods.os,
            "fdopen",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("fdopen failed")),
        )
        with pytest.raises(StoreError) as rejected:
            transaction.write("inputs/methods/new/source.source", b"not yet written")
        assert isinstance(rejected.value.__cause__, OSError)
        assert str(rejected.value.__cause__) == "fdopen failed"
    assert transaction.rollback()
    assert not (tmp_path / "inputs").exists()


def test_replaced_parent_directory_is_not_followed_during_rollback(tmp_path):
    transaction = methods._Preparation(tmp_path.resolve())
    transaction.write("inputs/methods/new/source.source", b"owned original")
    parent = tmp_path / "inputs/methods/new"
    moved = tmp_path / "inputs/methods/moved"
    parent.rename(moved)
    parent.mkdir()
    (parent / "source.source").write_bytes(b"unknown replacement")
    assert not transaction.rollback()
    assert (parent / "source.source").read_bytes() == b"unknown replacement"
    assert (moved / "source.source").read_bytes() == b"owned original"
