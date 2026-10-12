"""Docker model secrets use authenticated encryption and stable instance identity."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.research_web.credential_backend import (
    CredentialBackendError,
    EncryptedModelCredentialBackend,
)
from app.research_web.model_credentials import execute, initialize_docker_store


def store(home: Path, identity: str):
    records, keys = home / "models", home / "master"
    keys.mkdir(parents=True, mode=0o700)
    initialize_docker_store(records, keys, identity)
    return EncryptedModelCredentialBackend(records, keys, identity)


def call(home, backend, op, value=None):
    request = {"op": op, "ref": "RESEARCH_DSH_API_KEY"}
    if value is not None:
        request["value"] = value
    return execute(home, request, backend)


def test_independent_instances_and_reopen(tmp_path):
    a, b = store(tmp_path / "a", "a" * 32), store(tmp_path / "b", "b" * 32)
    call(tmp_path, a, "set", "synthetic-a")
    assert call(tmp_path, b, "resolve")["value"] is None
    call(tmp_path, b, "set", "synthetic-b")
    assert call(tmp_path, a, "resolve")["value"] == "synthetic-a"
    call(tmp_path, b, "unset")
    assert call(tmp_path, a, "resolve")["value"] == "synthetic-a"
    reopened = EncryptedModelCredentialBackend(a.root, a.key_root, "a" * 32)
    assert call(tmp_path, reopened, "resolve")["value"] == "synthetic-a"
    assert call(tmp_path, a, "describe")["source"] == "docker-encrypted"
    assert "synthetic-a" not in next(a.root.glob("*.json")).read_text()


def test_missing_key_and_identity_never_reinitialize(tmp_path):
    a = store(tmp_path / "a", "a" * 32)
    call(tmp_path, a, "set", "synthetic-a")
    (a.key_root / "master.key").unlink()
    with pytest.raises(CredentialBackendError):
        EncryptedModelCredentialBackend(a.root, a.key_root, "a" * 32)
    with pytest.raises(CredentialBackendError):
        initialize_docker_store(a.root, a.key_root, "a" * 32)
    assert not (a.key_root / "master.key").exists()


@pytest.mark.parametrize(
    "failure",
    ["wrong_key", "identity", "tamper", "permissions", "symlink", "key_permissions", "key_symlink"],
)
def test_fail_closed(tmp_path, failure):
    a = store(tmp_path / "a", "a" * 32)
    call(tmp_path, a, "set", "synthetic-a")
    record = next(a.root.glob("*.json"))
    if failure == "wrong_key":
        (a.key_root / "master.key").write_bytes(os.urandom(32))
    elif failure == "identity":
        (a.key_root / "identity.json").write_text(json.dumps({"version": 1, "instance": "b" * 32}))
    elif failure == "tamper":
        payload = json.loads(record.read_text())
        encrypted = json.loads(payload["password"])
        encrypted["ciphertext"] = "AAAA"
        payload["password"] = json.dumps(encrypted)
        record.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    elif failure == "permissions":
        record.chmod(0o644)
    elif failure == "key_permissions":
        (a.key_root / "master.key").chmod(0o644)
    elif failure == "key_symlink":
        (a.key_root / "master.key").unlink()
        (a.key_root / "master.key").symlink_to(record)
    else:
        record.unlink()
        record.symlink_to(a.key_root / "master.key")
    with pytest.raises(CredentialBackendError):
        other = EncryptedModelCredentialBackend(a.root, a.key_root, "a" * 32)
        call(tmp_path, other, "resolve")


def test_failed_replace_and_clear_keep_old_value(tmp_path, monkeypatch):
    a = store(tmp_path / "a", "a" * 32)
    call(tmp_path, a, "set", "synthetic-a")
    with monkeypatch.context() as patch:
        patch.setattr(
            os, "replace", lambda *args, **kw: (_ for _ in ()).throw(OSError("interrupted"))
        )
        with pytest.raises(CredentialBackendError):
            call(tmp_path, a, "set", "synthetic-new")
    assert call(tmp_path, a, "resolve")["value"] == "synthetic-a"


def test_failed_clear_keeps_old_value(tmp_path, monkeypatch):
    a = store(tmp_path / "a", "a" * 32)
    call(tmp_path, a, "set", "synthetic-a")
    with monkeypatch.context() as patch:
        patch.setattr(os, "unlink", lambda *args, **kw: (_ for _ in ()).throw(OSError("denied")))
        with pytest.raises(CredentialBackendError):
            call(tmp_path, a, "unset")
    assert call(tmp_path, a, "resolve")["value"] == "synthetic-a"


def test_isolated_product_bridge_ignores_ambient_secret(tmp_path):
    a = store(tmp_path / "a", "a" * 32)
    bridge = Path(__file__).resolve().parents[2] / "app/research_web/model_credentials.py"
    args = [
        sys.executable,
        "-I",
        "-B",
        str(bridge),
        "--data-home",
        str(tmp_path),
        "--backend",
        "docker-encrypted",
        "--credential-root",
        str(a.root),
        "--key-root",
        str(a.key_root),
        "--instance",
        a.instance,
    ]
    for operation in ("describe", "set", "resolve", "unset", "resolve"):
        request = {"op": operation, "ref": "RESEARCH_DSH_API_KEY"}
        if operation == "set":
            request["value"] = "synthetic-pipe"
        result = subprocess.run(
            args,
            input=json.dumps(request),
            text=True,
            capture_output=True,
            cwd="/",
            env={
                "PATH": "/usr/bin:/bin",
                "LANG": "C.UTF-8",
                "PYTHONPATH": "/not-trusted",
                "RESEARCH_DSH_API_KEY": "ambient",
            },
            timeout=20,
            check=False,
        )
        assert result.returncode == 0
        reply = json.loads(result.stdout)
        assert reply["ok"] is True
        if operation == "describe":
            assert reply["configured"] is False and reply["source"] == "docker-encrypted"
        if operation == "resolve":
            assert reply["value"] in ("synthetic-pipe", None)


def test_isolated_backend_import_never_initializes_global_settings():
    product = str(Path(__file__).resolve().parents[2])
    script = (
        "import sys; "
        f"sys.path.insert(0,{product!r});\n"
        "class DenySettings:\n"
        " def find_spec(self, fullname, path=None, target=None):\n"
        "  if fullname.startswith('core.settings'): raise RuntimeError('settings_import_denied')\n"
        "sys.meta_path.insert(0,DenySettings())\n"
        "from app.research_web.credential_backend import EncryptedModelCredentialBackend\n"
        "print('isolated_import_pass')\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        cwd="/",
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "isolated_import_pass"
