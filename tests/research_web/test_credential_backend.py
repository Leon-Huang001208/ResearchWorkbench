"""Credential boundary tests use only temporary paths and fake secrets."""

import errno
import os
import stat
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.research_web import credential_backend as module
from app.research_web.credential_backend import (
    CredentialBackendError,
    PrivateFileCredentialBackend,
    SystemKeyringBackend,
    default_credential_backend,
)


@pytest.fixture
def root(tmp_path):
    if os.name != "posix":
        pytest.skip("Docker file credentials execute in the Linux container")
    return tmp_path.resolve() / "credentials"


def record(root):
    return next(root.glob("*.json"))


def test_round_trip_private_hashed_utf8_records(root):
    backend = PrivateFileCredentialBackend(root)
    backend.set_password("service", "account", "fake-secret-中文")
    assert backend.get_password("service", "account") == "fake-secret-中文"
    path = record(root)
    assert len(path.stem) == 64 and all(c in "0123456789abcdef" for c in path.stem)
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert path.stat().st_uid == os.getuid()
    assert path.stat().st_nlink == 1
    assert path.read_bytes() == '{"version":1,"password":"fake-secret-中文"}'.encode()
    backend.delete_password("service", "account")
    assert backend.get_password("service", "account") is None
    backend.delete_password("service", "account")


def test_credentials_persist_across_fresh_backend_instance(root):
    first = PrivateFileCredentialBackend(root)
    first.set_password("provider", "account", "fake-persistent-secret")
    del first
    fresh = PrivateFileCredentialBackend(root)
    assert fresh.get_password("provider", "account") == "fake-persistent-secret"
    fresh.delete_password("provider", "account")
    assert PrivateFileCredentialBackend(root).get_password("provider", "account") is None


def test_factory_native_and_exact_explicit_path(root, monkeypatch):
    monkeypatch.delenv("RESEARCH_CREDENTIAL_HOME", raising=False)
    assert isinstance(default_credential_backend(), SystemKeyringBackend)
    monkeypatch.setenv("RESEARCH_CREDENTIAL_HOME", str(root))
    assert isinstance(default_credential_backend(), PrivateFileCredentialBackend)


@pytest.mark.parametrize(
    "value",
    ["", "relative", "~/secrets", "/tmp/../secrets", "/tmp//secrets", "/tmp/secrets/", " /tmp/secrets"],
)
def test_factory_rejects_nonexact_paths(value, monkeypatch):
    monkeypatch.setenv("RESEARCH_CREDENTIAL_HOME", value)
    with pytest.raises(CredentialBackendError):
        default_credential_backend()


def test_double_slash_root_is_not_exact(root, monkeypatch):
    monkeypatch.setenv("RESEARCH_CREDENTIAL_HOME", "/" + str(root))
    with pytest.raises(CredentialBackendError):
        default_credential_backend()


def test_native_windows_keeps_keyring_and_rejects_file_backend(tmp_path, monkeypatch):
    root = tmp_path.resolve() / "credentials"
    monkeypatch.setattr(module, "_PLATFORM_NAME", "nt")
    monkeypatch.delenv("RESEARCH_CREDENTIAL_HOME", raising=False)
    assert isinstance(default_credential_backend(), SystemKeyringBackend)
    monkeypatch.setenv("RESEARCH_CREDENTIAL_HOME", str(root))
    with pytest.raises(CredentialBackendError, match="credential_platform_unsupported"):
        default_credential_backend()
    assert not root.exists()


@pytest.mark.parametrize("mode", [0o755, 0o770, 0o500])
def test_rejects_nonprivate_root(root, mode):
    root.mkdir(mode=mode)
    with pytest.raises(CredentialBackendError):
        PrivateFileCredentialBackend(root)


def test_rejects_unsafe_ancestor_and_alias(root):
    root.parent.chmod(0o777)
    try:
        with pytest.raises(CredentialBackendError):
            PrivateFileCredentialBackend(root)
    finally:
        root.parent.chmod(0o700)
    real = root.parent / "real"
    real.mkdir(mode=0o700)
    root.symlink_to(real, target_is_directory=True)
    with pytest.raises(CredentialBackendError):
        PrivateFileCredentialBackend(root)


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "public", "directory", "fifo"])
@pytest.mark.parametrize("operation", ["get_password", "set_password", "delete_password"])
def test_rejects_unsafe_record(root, kind, operation):
    backend = PrivateFileCredentialBackend(root)
    backend.set_password("s", "a", "fake-original")
    path = record(root)
    outside = root.parent / "outside"
    if kind in {"symlink", "hardlink"}:
        path.rename(outside)
        if kind == "symlink":
            path.symlink_to(outside)
        else:
            os.link(outside, path)
    elif kind == "public":
        path.chmod(0o644)
    else:
        path.unlink()
        if kind == "directory":
            path.mkdir()
        else:
            os.mkfifo(path, 0o600)
    with pytest.raises(CredentialBackendError):
        arguments = ["fake-new"] if operation == "set_password" else []
        getattr(backend, operation)("s", "a", *arguments)
    if outside.exists():
        assert "fake-original" in outside.read_text()


def test_rejects_root_replacement(root):
    backend = PrivateFileCredentialBackend(root)
    root.rename(root.with_name("old"))
    root.mkdir(mode=0o700)
    with pytest.raises(CredentialBackendError):
        backend.set_password("s", "a", "fake-secret")
    assert not list(root.iterdir())


@pytest.mark.parametrize(
    "value", [123, "x" * (64 * 1024 + 1), "中" * (64 * 1024 // 3 + 1), "\ud800"]
)
def test_rejects_unbounded_or_invalid_value(root, value):
    backend = PrivateFileCredentialBackend(root)
    with pytest.raises(CredentialBackendError):
        backend.set_password("s", "a", value)
    assert not list(root.glob("*.json"))


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b'{"version":1,"password":123}',
        b'{"version":1,"password":"x","password":"y"}',
        b"\xff",
        b"x" * (400 * 1024),
    ],
)
def test_rejects_corrupt_records(root, raw):
    backend = PrivateFileCredentialBackend(root)
    backend.set_password("s", "a", "fake-secret")
    record(root).write_bytes(raw)
    with pytest.raises(CredentialBackendError):
        backend.get_password("s", "a")


def test_atomic_failure_preserves_old_and_cleans_temporary(root, monkeypatch):
    backend = PrivateFileCredentialBackend(root)
    backend.set_password("s", "a", "fake-old")

    def fail(*args, **kwargs):
        raise OSError("fake-secret-must-not-leak")

    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(CredentialBackendError) as caught:
        backend.set_password("s", "a", "fake-new")
    assert "fake-secret-must-not-leak" not in "".join(traceback.format_exception(caught.value))
    assert backend.get_password("s", "a") == "fake-old"
    assert sorted(p.suffix for p in root.iterdir()) == [".json", ".lock"]


def test_readback_detects_corruption_and_cleans_new_record(root, monkeypatch):
    backend = PrivateFileCredentialBackend(root)
    original = module.os.replace

    def corrupt(src, dst, **kwargs):
        original(src, dst, **kwargs)
        (root / dst).write_text('{"version":1,"password":"wrong"}')

    monkeypatch.setattr(module.os, "replace", corrupt)
    with pytest.raises(CredentialBackendError):
        backend.set_password("s", "a", "fake-secret")
    assert not list(root.glob("*.json"))
    assert not list(root.glob("*.tmp"))


def test_concurrent_instances_and_processes(root):
    PrivateFileCredentialBackend(root)

    def write(index):
        backend = PrivateFileCredentialBackend(root)
        backend.set_password("s", str(index), f"fake-{index}")
        assert backend.get_password("s", str(index)) == f"fake-{index}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(20)))
    script = (
        "from pathlib import Path; "
        "from app.research_web.credential_backend import PrivateFileCredentialBackend; "
        "import sys; b=PrivateFileCredentialBackend(Path(sys.argv[1])); "
        "[b.set_password('process', str(i), 'fake-process') for i in range(10)]"
    )
    children = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(root)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(3)
    ]
    for child in children:
        stdout, stderr = child.communicate(timeout=30)
        assert child.returncode == 0, (stdout, stderr)
    assert len(list(root.glob("*.json"))) == 30


@pytest.mark.parametrize("contender", ["private", "symlink", "hardlink", "public", "removed"])
def test_lock_creation_loser_opens_validated_existing_inode(root, monkeypatch, contender):
    """Deterministically model the observed Darwin concurrent-create outcome."""
    backend = PrivateFileCredentialBackend(root)
    real_open = module.os.open
    raced = False
    contender_identity = None
    lock_path = root / ".credentials.lock"

    def race(name, flags, *args, **kwargs):
        nonlocal raced, contender_identity
        if name == ".credentials.lock" and flags & os.O_CREAT and not raced:
            raced = True
            # A competing initializer publishes the lock before our open resolves.
            descriptor = real_open(name, flags | os.O_EXCL, *args, **kwargs)
            contender_identity = module._identity(os.fstat(descriptor))
            os.close(descriptor)
            if contender in {"symlink", "hardlink"}:
                outside = root.parent / "fake-contender-lock"
                lock_path.rename(outside)
                if contender == "symlink":
                    lock_path.symlink_to(outside)
                else:
                    os.link(outside, lock_path)
            elif contender == "public":
                lock_path.chmod(0o644)
            elif contender == "removed":
                lock_path.unlink()
                raise FileExistsError(errno.EEXIST, "simulated concurrent winner")
            if not flags & os.O_EXCL:
                # Observed nonexclusive O_CREAT|O_NOFOLLOW result on macOS.
                raise FileNotFoundError(errno.ENOENT, "simulated concurrent create")
        return real_open(name, flags, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", race)
    if contender == "private":
        backend.set_password("s", "a", "fake-value")
        assert backend.get_password("s", "a") == "fake-value"
        assert module._identity(lock_path.stat()) == contender_identity
    else:
        with pytest.raises(CredentialBackendError):
            backend.set_password("s", "a", "fake-value")
        assert not list(root.glob("*.json"))
    assert raced


def test_default_injection_and_explicit_falsey_backend(root, monkeypatch, tmp_path):
    from app.research_web.automation.channels import DeliveryChannelStore
    from app.research_web.datahub.connections import MySQLConnectionStore
    from app.research_web.mcp_registry.credentials import RegistryCredentialStore
    from app.research_web.mcp_runtime.credentials import RuntimeCredentialStore
    from app.research_web.mcp_runtime.installation_store import InstallationStore
    from app.research_web.service import _persistent_mcp_key

    monkeypatch.setenv("RESEARCH_CREDENTIAL_HOME", str(root))
    stores = [
        MySQLConnectionStore(tmp_path),
        RegistryCredentialStore(),
        RuntimeCredentialStore(),
        DeliveryChannelStore(SimpleNamespace(data={})),
    ]
    assert all(isinstance(store.keyring, PrivateFileCredentialBackend) for store in stores)
    assert _persistent_mcp_key("fake-account") == _persistent_mcp_key("fake-account")
    integrity_key = InstallationStore._persistent_integrity_key(None)
    assert integrity_key == InstallationStore._persistent_integrity_key(None)
    fake = {}
    monkeypatch.setenv("RESEARCH_CREDENTIAL_HOME", "invalid")
    stores = [
        MySQLConnectionStore(tmp_path, keyring_backend=fake),
        RegistryCredentialStore(fake),
        RuntimeCredentialStore(fake),
        DeliveryChannelStore(SimpleNamespace(data={}), keyring_backend=fake),
    ]
    assert all(store.keyring is fake for store in stores)


def test_system_adapter_sanitizes_arbitrary_backend_errors(monkeypatch):
    class VendorFailure(Exception):
        pass

    def fail(*args):
        raise VendorFailure("fake-secret-must-not-leak")

    monkeypatch.setitem(sys.modules, "keyring", SimpleNamespace(get_password=fail))
    with pytest.raises(CredentialBackendError) as caught:
        SystemKeyringBackend().get_password("s", "a")
    assert "fake-secret-must-not-leak" not in "".join(traceback.format_exception(caught.value))


def test_owner_and_reparse_record_checks(root, monkeypatch):
    backend = PrivateFileCredentialBackend(root)
    backend.set_password("s", "a", "fake-value")
    info = record(root).stat()
    for changes in ({"st_uid": info.st_uid + 1}, {"st_file_attributes": 0x400}):
        fields = {key: getattr(info, key) for key in ("st_mode", "st_nlink", "st_uid", "st_size")}
        fields.update(changes)
        with pytest.raises(CredentialBackendError):
            module._validate_file(SimpleNamespace(**fields))
    monkeypatch.setattr(module.os, "getuid", lambda: info.st_uid + 1)
    with pytest.raises(CredentialBackendError):
        backend.get_password("s", "a")


def test_record_replacement_between_stat_and_open_is_rejected(root, monkeypatch):
    backend = PrivateFileCredentialBackend(root)
    backend.set_password("s", "a", "fake-value")
    path = record(root)
    original = module.os.open

    def swap(name, *args, **kwargs):
        if name == path.name:
            path.rename(root / "retained")
            path.write_text('{"version":1,"password":"fake-attacker"}')
            path.chmod(0o600)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", swap)
    with pytest.raises(CredentialBackendError, match="credential_record_changed"):
        backend.get_password("s", "a")


def test_process_lock_timeout_and_recovery(root, monkeypatch):
    backend = PrivateFileCredentialBackend(root)
    backend.set_password("s", "a", "fake-value")
    script = (
        "import fcntl, sys; f=open(sys.argv[1], 'r+'); fcntl.flock(f, fcntl.LOCK_EX); "
        "print('locked', flush=True); sys.stdin.read(1)"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(root / ".credentials.lock")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert child.stdout.readline() == b"locked\n"
        monkeypatch.setattr(module, "_LOCK_TIMEOUT_SECONDS", 0.05)
        with pytest.raises(CredentialBackendError, match="credential_store_busy"):
            backend.get_password("s", "a")
    finally:
        child.communicate(b"x", timeout=10)
    assert child.returncode == 0
    assert backend.get_password("s", "a") == "fake-value"


def test_fsync_failure_cleans_stage_and_preserves_old(root, monkeypatch):
    backend = PrivateFileCredentialBackend(root)
    backend.set_password("s", "a", "fake-old")

    def fail(*args):
        raise OSError("fake-fsync-failure")

    monkeypatch.setattr(module.os, "fsync", fail)
    with pytest.raises(CredentialBackendError):
        backend.set_password("s", "a", "fake-new")
    assert backend.get_password("s", "a") == "fake-old"
    assert not list(root.glob("*.tmp"))


def test_boundary_values_and_unambiguous_references(root):
    backend = PrivateFileCredentialBackend(root)
    backend.set_password("a:b", "c", "x" * module.MAX_VALUE_BYTES)
    backend.set_password("a", "b:c", "")
    assert backend.get_password("a:b", "c") == "x" * module.MAX_VALUE_BYTES
    assert backend.get_password("a", "b:c") == ""
    backend.set_password("a", "b:c", "\x00" * module.MAX_VALUE_BYTES)
    assert backend.get_password("a", "b:c") == "\x00" * module.MAX_VALUE_BYTES


def test_logs_and_names_never_contain_secret(root, monkeypatch):
    backend = PrivateFileCredentialBackend(root)
    secret = "fake-value-do-not-log"
    events = []
    monkeypatch.setattr(
        module,
        "log",
        SimpleNamespace(warning=lambda *args, **kwargs: events.append((args, kwargs))),
    )
    backend.set_password("s", "a", secret)

    def fail(*args, **kwargs):
        raise OSError(secret)

    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(CredentialBackendError):
        backend.set_password("s", "a", secret)
    assert events
    assert secret not in repr(events)
    assert all(secret not in path.name for path in root.iterdir())
