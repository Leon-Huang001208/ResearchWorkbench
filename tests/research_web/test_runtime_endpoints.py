"""Private endpoint snapshots and loopback candidates are fail closed."""

import json
import os
import socket

import pytest

from research_workbench_entrypoint.runtime_endpoints import (
    EndpointError,
    EndpointStore,
    select_port,
)


@pytest.fixture
def store(tmp_path):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    return EndpointStore(home)


def test_endpoint_store_round_trip(tmp_path):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    store = EndpointStore(home)
    assert store.read("native") is None
    native = store.publish("native", web_port=18088, runtime_port=13081, expected=None)
    assert native.web_port == 18088
    assert native.runtime_port == 13081
    docker = store.publish("docker", web_port=18089, expected=None)
    assert docker.web_port == 18089
    assert docker.runtime_port is None
    assert store.read("native") == native
    assert store.read("docker") == docker
    assert store.path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("value", [True, False, 0, -1, 65536, "8088", 8088.0])
def test_endpoint_store_rejects_invalid_port(tmp_path, value):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    store = EndpointStore(home)
    with pytest.raises(EndpointError):
        store.publish("docker", web_port=value, expected=None)
    assert store.read("docker") is None


@pytest.mark.parametrize("mode,runtime", [("native", None), ("native", 18088),
                                           ("docker", 13081), ("other", None)])
def test_invalid_mode_pair(store, mode, runtime):
    with pytest.raises(EndpointError):
        store.publish(mode, web_port=18088, runtime_port=runtime, expected=None)


def test_compare_and_swap_rejects_stale_and_preserves_other_mode(store):
    first = store.publish("native", web_port=18088, runtime_port=13081, expected=None)
    other = EndpointStore(store.home)
    docker = other.publish("docker", web_port=18089, expected=None)
    second = store.publish("native", web_port=18090, runtime_port=13081, expected=first)
    with pytest.raises(EndpointError, match="endpoint_conflict"):
        other.publish("native", web_port=18091, runtime_port=13081, expected=first)
    assert store.read("native") == second
    assert store.read("docker") == docker


@pytest.mark.parametrize("mutation", ["version", "extra", "unknown_mode", "duplicate", "bool"])
def test_corrupt_record_never_defaults(store, mutation):
    store.publish("docker", web_port=18089, expected=None)
    value = json.loads(store.path.read_bytes())
    if mutation == "version":
        value["schema_version"] = 2
    elif mutation == "extra":
        value["extra"] = None
    elif mutation == "unknown_mode":
        value["records"]["other"] = value["records"]["docker"]
    elif mutation == "bool":
        value["records"]["docker"]["web_port"] = True
    raw = json.dumps(value)
    if mutation == "duplicate":
        raw = raw.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1')
    store.path.write_text(raw)
    with pytest.raises(EndpointError):
        store.read("native")


@pytest.mark.parametrize("kind", ["file_mode", "parent_mode", "symlink", "hardlink", "ancestor"])
def test_unsafe_paths_rejected(store, kind):
    previous = store.publish("docker", web_port=18089, expected=None)
    if kind == "file_mode":
        store.path.chmod(0o644)
    elif kind == "parent_mode":
        store.path.parent.chmod(0o755)
    elif kind == "hardlink":
        os.link(store.path, store.home / "alias")
    elif kind == "symlink":
        saved = store.home / "saved"
        store.path.rename(saved)
        store.path.symlink_to(saved)
    else:
        saved = store.home / "saved"
        store.path.parent.rename(saved)
        store.path.parent.symlink_to(saved, target_is_directory=True)
    with pytest.raises(EndpointError):
        store.read("docker")
    with pytest.raises(EndpointError):
        store.publish("docker", web_port=18090, expected=previous)


def test_recorded_process_facts_must_match(store):
    store.publish("native", web_port=18088, runtime_port=13081, expected=None)
    store.verify_facts("native", web_port=18088, runtime_port=13081)
    with pytest.raises(EndpointError, match="endpoint_facts_mismatch"):
        store.verify_facts("native", web_port=8088, runtime_port=13081)
    with pytest.raises(EndpointError, match="endpoint_facts_mismatch"):
        store.verify_facts("docker", web_port=18088)


def test_port_candidates_prefer_free_and_reject_explicit_conflict():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        occupied = listener.getsockname()[1]
        listener.listen()
        with pytest.raises(EndpointError, match="endpoint_port_in_use"):
            select_port(occupied, explicit=True)
        selected = select_port(occupied, excluded=(occupied,))
        assert selected != occupied
    assert select_port(selected) == selected


def test_missing_read_has_no_side_effect(tmp_path):
    home = tmp_path / "absent"
    assert EndpointStore(home).read("native") is None
    assert not home.exists()


def test_strict_writer_does_not_repair_permissions(tmp_path):
    from research_workbench_entrypoint import runtime_mode

    folder = tmp_path / "private"
    folder.mkdir(mode=0o755)
    with pytest.raises(runtime_mode.RuntimeModeError):
        runtime_mode._atomic_write_posix(folder / "file", b"{}", None, strict_parent=True)
    assert folder.stat().st_mode & 0o777 == 0o755
    assert not (folder / "file").exists()


def test_atomic_writer_rejects_post_publication_identical_replacement(tmp_path, monkeypatch):
    from research_workbench_entrypoint import runtime_mode

    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    real_replace = os.replace

    def replace_then_substitute(source, target, **kwargs):
        real_replace(source, target, **kwargs)
        replacement = folder / "foreign"
        replacement.write_bytes(b"{}")
        replacement.chmod(0o600)
        real_replace(replacement, folder / "file")

    monkeypatch.setattr(os, "replace", replace_then_substitute)
    with pytest.raises(runtime_mode.RuntimeModeError, match="runtime_mode_changed"):
        runtime_mode._atomic_write_posix(folder / "file", b"{}", None, strict_parent=True)
