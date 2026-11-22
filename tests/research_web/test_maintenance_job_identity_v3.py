"""Exact job targets are read-only contracts, never launchd authority."""

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from research_workbench_entrypoint.resident.evidence import UpdateBlocked
from research_workbench_entrypoint.resident.maintenance_job_identity_v3 import (
    REGISTRATION_FILENAME,
    REHEARSAL_LABEL_PREFIX,
    ExactJobBinding,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX identity contract")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def registered(tmp_path):
    root = tmp_path.resolve() / "rehearsal"
    root.mkdir(mode=0o700)
    (root / "LaunchAgents").mkdir(mode=0o700)
    script = root / "entry.py"
    script.write_text("# Identity fixture only; never executed.\n")
    script.chmod(0o600)
    executable = tmp_path.resolve() / "approved-interpreter"
    executable.write_bytes(b"identity-only executable fixture")
    executable.chmod(0o700)
    kwargs = {
        "root": root,
        "task_id": "identity-contract-test",
        "nonce": str(uuid4()),
        "script": script,
        "executable": executable,
        "script_sha256": digest(script),
        "executable_sha256": digest(executable),
        "port": 54031,
    }
    info = root.stat()
    record = {
        "schema": "rwb-maintenance-job-identity-v3",
        "task_id": kwargs["task_id"],
        "owner_uid": os.getuid(),
        "nonce": kwargs["nonce"],
        "root": str(root),
        "root_identity": [info.st_dev, info.st_ino],
        "script": str(script),
        "script_sha256": kwargs["script_sha256"],
        "executable": str(executable),
        "executable_sha256": kwargs["executable_sha256"],
        "port": kwargs["port"],
    }
    marker = root / REGISTRATION_FILENAME
    marker.write_text(json.dumps(record))
    marker.chmod(0o600)
    return kwargs, record, marker


def test_registered_target_binds_all_fields_without_effects(registered, monkeypatch):
    import socket
    import subprocess

    def forbidden(*args, **kwargs):
        pytest.fail("identity validation attempted an execution or network effect")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket.socket, "bind", forbidden)
    kwargs, _, marker = registered
    before = marker.read_bytes()
    target = ExactJobBinding.rehearsal(**kwargs)
    assert target.home == kwargs["root"]
    assert target.label == REHEARSAL_LABEL_PREFIX + kwargs["nonce"].replace("-", "")
    assert target.domain == f"gui/{os.getuid()}"
    assert target.plist_path == target.home / "LaunchAgents" / f"{target.label}.plist"
    assert target.port == kwargs["port"]
    assert target.script == kwargs["script"]
    assert target.executable == kwargs["executable"]
    target.verify()
    assert marker.read_bytes() == before
    assert not target.plist_path.exists()


def test_registered_json_cannot_override_reviewed_nonce(registered):
    kwargs, record, marker = registered
    record["nonce"] = str(uuid4())
    marker.write_text(json.dumps(record))
    with pytest.raises(UpdateBlocked):
        ExactJobBinding.rehearsal(**kwargs)


def test_revalidation_rejects_target_replacement_and_artifact_drift(registered):
    kwargs, _, _ = registered
    target = ExactJobBinding.rehearsal(**kwargs)
    with pytest.raises(UpdateBlocked):
        replace(target, label="com.research-workbench.multiuser-server").verify()
    kwargs["script"].write_text("# changed after registration\n")
    with pytest.raises(UpdateBlocked):
        target.verify()


@pytest.mark.parametrize(
    "case",
    [
        "uid",
        "task",
        "nonce",
        "port",
        "root_identity",
        "root",
        "script",
        "executable",
        "hash",
        "extra",
        "duplicate",
        "mode",
        "hardlink",
        "fifo",
        "root_mode",
        "script_mode",
        "script_symlink",
        "script_parent_symlink",
    ],
)
def test_rejects_untrusted_registration_and_files(registered, case):
    kwargs, record, marker = registered
    if case in {
        "uid",
        "task",
        "nonce",
        "port",
        "root_identity",
        "root",
        "script",
        "executable",
        "hash",
        "extra",
    }:
        key, value = {
            "uid": ("owner_uid", os.getuid() + 1),
            "task": ("task_id", "another-task"),
            "nonce": ("nonce", str(uuid4())),
            "port": ("port", 8089),
            "root_identity": ("root_identity", [0, 0]),
            "root": ("root", str(kwargs["root"].parent)),
            "script": ("script", "/unreviewed-script.py"),
            "executable": ("executable", "/unreviewed-executable"),
            "hash": ("script_sha256", "0" * 64),
            "extra": ("label", "com.research-workbench.multiuser-server"),
        }[case]
        record[key] = value
        marker.write_text(json.dumps(record))
    elif case == "duplicate":
        marker.write_text(json.dumps(record)[:-1] + ', "port":54031}')
    elif case == "mode":
        marker.chmod(0o644)
    elif case == "hardlink":
        os.link(marker, kwargs["root"] / "second-owner-record")
    elif case == "fifo":
        marker.unlink()
        os.mkfifo(marker, 0o600)
    elif case == "root_mode":
        kwargs["root"].chmod(0o755)
    elif case == "script_mode":
        kwargs["script"].chmod(0o644)
    elif case == "script_symlink":
        target = kwargs["root"] / "original-script"
        kwargs["script"].rename(target)
        kwargs["script"].symlink_to(target)
    else:
        directory = kwargs["root"] / "real"
        directory.mkdir(mode=0o700)
        kwargs["script"].rename(directory / "entry.py")
        alias = kwargs["root"] / "alias"
        alias.symlink_to(directory, target_is_directory=True)
        kwargs["script"] = alias / "entry.py"
        record["script"] = str(kwargs["script"])
        marker.write_text(json.dumps(record))
    with pytest.raises(UpdateBlocked):
        ExactJobBinding.rehearsal(**kwargs)


@pytest.mark.parametrize("nonce", [None, True, 1, {}, "invalid"])
def test_invalid_nonce_has_stable_failure(registered, nonce):
    kwargs, _, _ = registered
    kwargs["nonce"] = nonce
    with pytest.raises(UpdateBlocked):
        ExactJobBinding.rehearsal(**kwargs)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "directory"])
def test_planned_plist_cannot_be_redirected(registered, kind):
    kwargs, _, _ = registered
    target = ExactJobBinding.rehearsal(**kwargs)
    if kind == "symlink":
        target.plist_path.symlink_to(kwargs["script"])
    elif kind == "hardlink":
        os.link(kwargs["script"], target.plist_path)
    elif kind == "fifo":
        os.mkfifo(target.plist_path, 0o600)
    else:
        target.plist_path.mkdir(mode=0o700)
    with pytest.raises(UpdateBlocked):
        target.verify()


def test_interpreter_alias_is_preserved_and_retargeting_rejected(registered):
    kwargs, record, marker = registered
    alias = kwargs["root"] / "venv-python"
    alias.symlink_to(kwargs["executable"])
    kwargs["executable"] = alias
    record["executable"] = str(alias)
    marker.write_text(json.dumps(record))
    target = ExactJobBinding.rehearsal(**kwargs)
    assert target.executable == alias
    target.verify()
    alias.unlink()
    alias.symlink_to(kwargs["script"])
    with pytest.raises(UpdateBlocked):
        target.verify()


def test_replacing_registration_with_equal_bytes_is_not_same_identity(registered):
    kwargs, _, marker = registered
    target = ExactJobBinding.rehearsal(**kwargs)
    replacement = marker.with_suffix(".replacement")
    replacement.write_bytes(marker.read_bytes())
    replacement.chmod(0o600)
    replacement.replace(marker)
    with pytest.raises(UpdateBlocked):
        target.verify()


@pytest.fixture
def production_home(tmp_path, monkeypatch):
    user = tmp_path.resolve() / "user"
    user.mkdir(mode=0o700)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: user))
    home = user / ".research-workbench"
    home.mkdir(mode=0o700)
    (home / "server").mkdir(mode=0o700)
    (user / "Library/LaunchAgents").mkdir(mode=0o700, parents=True)
    config = home / "server/resident.json"
    config.write_text(json.dumps({"port": 8089}))
    config.chmod(0o600)
    return home, config


def test_production_is_fixed_and_does_not_attest_loaded_policy(production_home):
    home, config = production_home
    original = config.read_bytes()
    target = ExactJobBinding.production(home=home)
    assert target.label == "com.research-workbench.multiuser-server"
    assert target.port == 8089
    assert target.nonce is None
    assert target.script is None
    target.verify()
    assert not target.plist_path.exists()
    assert config.read_bytes() == original
    config.write_text(json.dumps({"port": 54031}))
    with pytest.raises(UpdateBlocked):
        target.verify()


def test_production_rejects_alternate_root_and_configured_port(production_home):
    home, config = production_home
    with pytest.raises(UpdateBlocked):
        ExactJobBinding.production(home=home.parent)
    config.write_text(json.dumps({"port": 54031}))
    with pytest.raises(UpdateBlocked):
        ExactJobBinding.production(home=home)


def test_plist_redirect_during_artifact_read_is_rejected(registered, monkeypatch):
    from research_workbench_entrypoint.resident import maintenance_job_identity_v3 as module

    kwargs, _, _ = registered
    target = ExactJobBinding.rehearsal(**kwargs)
    original = module._pin_file

    def concurrent_change(path, **options):
        result = original(path, **options)
        if path == kwargs["script"]:
            target.plist_path.symlink_to(kwargs["script"])
        return result

    monkeypatch.setattr(module, "_pin_file", concurrent_change)
    with pytest.raises(UpdateBlocked):
        target.verify()


@pytest.mark.parametrize("name", ["script_sha256", "executable_sha256"])
@pytest.mark.parametrize("value", [None, "", "g" * 64])
def test_requires_independent_reviewed_artifact_hashes(registered, name, value):
    kwargs, record, marker = registered
    kwargs[name] = value
    record[name] = value
    marker.write_text(json.dumps(record))
    with pytest.raises(UpdateBlocked):
        ExactJobBinding.rehearsal(**kwargs)


@pytest.mark.parametrize("changed", ["script", "registration"])
def test_later_binary_read_cannot_hide_earlier_file_change(registered, monkeypatch, changed):
    from research_workbench_entrypoint.resident import maintenance_job_identity_v3 as module

    kwargs, _, marker = registered
    target = ExactJobBinding.rehearsal(**kwargs)
    original = module._pin_file

    def concurrent_change(path, **options):
        result = original(path, **options)
        if path == kwargs["executable"].resolve():
            selected = marker if changed == "registration" else kwargs["script"]
            with selected.open("ab") as stream:
                stream.write(b"\n# changed during later binary read\n")
        return result

    monkeypatch.setattr(module, "_pin_file", concurrent_change)
    with pytest.raises(UpdateBlocked):
        target.verify()
