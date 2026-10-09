"""The model reference cannot fall back to file/environment credential layers."""

import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

BRIDGE = Path(__file__).resolve().parents[2] / "app/research_web/model_credentials.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("model_credentials_tested", BRIDGE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("ambient", [False, True])
def test_private_docker_cli_imports_on_readonly_root(tmp_path, ambient):
    product = BRIDGE.parents[2]
    canary = tmp_path / "untrusted.env"
    canary.write_text("LOG_DIR=/untrusted-import-canary\n")
    script = """
import builtins, errno, os, runpy, sys, sysconfig
from pathlib import Path
sysconfig.get_config_vars()  # Host stdlib configuration precedes the Linux selector simulation.
product = Path(sys.argv[1]).resolve().parents[2]
original_mkdir, original_import = os.mkdir, builtins.__import__
def readonly_mkdir(path, *args, **kwargs):
    if Path(path) != product:
        raise OSError(errno.EROFS, 'readonly-import-canary')
    return original_mkdir(path, *args, **kwargs)
os.mkdir = readonly_mkdir
def guarded_import(name, *args, **kwargs):
    imported = original_import(name, *args, **kwargs)
    if name == 'app.research_web' and 'model_file_store' in (args[2] if len(args) > 2 else ()):
        from core.settings.config import settings, RUNTIME_CONTEXT
        assert RUNTIME_CONTEXT.mode == 'web-prod' and RUNTIME_CONTEXT.env_path is None
        assert all(getattr(settings, key) == product for key in
            ('LOG_DIR', 'OBJECT_STORAGE_PATH', 'PDF_MARKDOWN_DIR', 'PDF_RAW_TEXT_DIR'))
        class Store:
            source = 'docker-private-file'
            def __init__(self, root, installation):
                assert root == '/run/rwb-secrets/private/models/' + installation
                print('private-import-canary')
            def get_password(self, *args):
                return None
        imported.model_file_store.DockerModelStore = Store
    return imported
builtins.__import__ = guarded_import
sys.platform = 'linux'
sys.argv = [sys.argv[1], '--data-home', sys.argv[2], '--backend', 'docker-private-file',
    '--credential-root', '/run/rwb-secrets/private/models/' + sys.argv[3],
    '--installation-id', sys.argv[3]]
runpy.run_path(sys.argv[0], run_name='__main__')
"""
    env = {"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"}
    if ambient:
        env.update(
            RESEARCH_RUN_MODE="web-dev",
            RESEARCH_CONFIG_FILE=str(canary),
            PYTHONPATH=str(tmp_path),
            **{
                key: "/untrusted-import-canary"
                for key in (
                    "LOG_DIR",
                    "OBJECT_STORAGE_PATH",
                    "PDF_MARKDOWN_DIR",
                    "PDF_RAW_TEXT_DIR",
                )
            },
        )
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(BRIDGE), str(tmp_path), INSTALLATION],
        input=json.dumps({"op": "describe", "ref": "RESEARCH_DSH_API_KEY"}),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        env=env,
        cwd="/",
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "ok": True,
        "configured": False,
        "source": "docker-private-file",
        "writable": True,
    }
    assert "private-import-canary" in completed.stderr
    assert list(tmp_path.iterdir()) == [canary]
    assert product.is_dir()


def test_native_model_library_import_preserves_environment(monkeypatch):
    monkeypatch.setenv("RESEARCH_RUN_MODE", "web-dev")
    monkeypatch.setenv("LOG_DIR", "/untrusted-import-canary")
    before = dict(os.environ)
    bridge = load_bridge()
    assert bridge.select_backend("system-keychain") is None
    assert dict(os.environ) == before


def test_explicit_docker_model_backend_factory_exists():
    assert callable(getattr(load_bridge(), "docker_backend", None))


INSTALLATION = "0123456789abcdef0123456789abcdef"


def docker_store(tmp_path, installation=INSTALLATION):
    return load_bridge().docker_backend(tmp_path.resolve() / "models" / installation, installation)


def model_call(home, store, op, **extra):
    return load_bridge().execute(home, {"op": op, "ref": "RESEARCH_DSH_API_KEY", **extra}, store)


def test_docker_installation_lifecycle_and_namespace_isolation(tmp_path, monkeypatch):
    first = docker_store(tmp_path)
    second = docker_store(tmp_path, "a" * 32)
    monkeypatch.setenv("RESEARCH_DSH_API_KEY", "synthetic-ambient")
    (tmp_path / ".credentials.yaml").write_text("RESEARCH_DSH_API_KEY: synthetic-legacy")
    assert model_call(tmp_path, first, "resolve") == {"value": None}
    model_call(tmp_path, first, "set", value="synthetic-中文")
    assert model_call(tmp_path, docker_store(tmp_path), "resolve")["value"] == "synthetic-中文"
    assert model_call(tmp_path, second, "resolve") == {"value": None}
    assert first.namespace == "org.research-workbench.model.docker." + INSTALLATION
    assert model_call(tmp_path, first, "describe") == {
        "configured": True,
        "source": "docker-private-file",
        "writable": True,
    }
    model_call(tmp_path, first, "unset")
    model_call(tmp_path, first, "unset")
    assert model_call(tmp_path, docker_store(tmp_path), "resolve") == {"value": None}


@pytest.mark.parametrize("installation", ["", "A" * 32, "0" * 31, "g" * 32, "../x", None])
def test_docker_invalid_installation_rejected_before_creation(tmp_path, installation):
    with pytest.raises(RuntimeError, match="model_credential_binding_invalid"):
        load_bridge().docker_backend(tmp_path.resolve() / "uncreated", installation)
    assert not (tmp_path / "uncreated").exists()


def test_docker_store_denies_other_namespaces_and_request_extras(tmp_path):
    store = docker_store(tmp_path)
    for service, ref in [("ResearchWorkbench.DataHub", "OTHER"), (store.namespace, "OTHER")]:
        with pytest.raises(RuntimeError, match="model_credential_reference_invalid"):
            store.get_password(service, ref)
    for extra in [{"namespace": store.namespace}, {"backend": "system-keychain"}, {"value": "x"}]:
        with pytest.raises(ValueError, match="model_credential_request_invalid"):
            model_call(tmp_path, store, "resolve", **extra)
    assert not list(store.root.glob("*.json"))


@pytest.mark.parametrize("kind", ["mode", "symlink", "hardlink", "oversize", "invalid", "owner"])
@pytest.mark.parametrize("operation", ["resolve", "set", "unset"])
def test_docker_rejects_unsafe_records(tmp_path, monkeypatch, kind, operation):
    store = docker_store(tmp_path)
    model_call(tmp_path, store, "set", value="synthetic-old")
    path = next(store.root.glob("*.json"))
    if kind == "mode":
        path.chmod(0o644)
    elif kind in {"symlink", "hardlink"}:
        outside = tmp_path / "outside"
        path.rename(outside)
        path.symlink_to(outside) if kind == "symlink" else os.link(outside, path)
    elif kind == "oversize":
        path.write_bytes(b"x" * 9000)
    elif kind == "invalid":
        path.write_bytes(b'{"version":1,"password":"x"}')
    else:
        # An unprivileged test cannot chown to a foreign UID.
        from app.research_web import credential_backend

        monkeypatch.setattr(credential_backend.os, "getuid", lambda: path.stat().st_uid + 1)
    with pytest.raises(RuntimeError, match="model_credential_"):
        model_call(
            tmp_path, store, operation, **({"value": "synthetic-new"} if operation == "set" else {})
        )


@pytest.mark.parametrize(
    "kind", ["root-mode", "root-replaced", "lock-mode", "lock-symlink", "lock-hardlink"]
)
def test_docker_root_and_lock_guards(tmp_path, kind):
    store = docker_store(tmp_path)
    model_call(tmp_path, store, "set", value="synthetic-old")
    lock = store.root / ".credentials.lock"
    if kind == "root-mode":
        store.root.chmod(0o755)
    elif kind == "root-replaced":
        store.root.rename(store.root.with_name("old"))
        store.root.mkdir(mode=0o700)
    elif kind == "lock-mode":
        lock.chmod(0o644)
    else:
        outside = tmp_path / "outside-lock"
        lock.rename(outside)
        lock.symlink_to(outside) if kind == "lock-symlink" else os.link(outside, lock)
    with pytest.raises(RuntimeError, match="model_credential_"):
        model_call(tmp_path, store, "resolve")


def test_docker_independent_writers_use_same_persistent_lock(tmp_path):
    stores = [docker_store(tmp_path) for _ in range(4)]
    model_call(tmp_path, stores[0], "set", value="synthetic-initial")
    identity = (stores[0].root / ".credentials.lock").stat().st_ino

    def write(index):
        for step in range(8):
            model_call(tmp_path, stores[index], "set", value=f"synthetic-{index}-{step}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(write, range(4)))
    assert model_call(tmp_path, docker_store(tmp_path), "resolve")["value"].startswith("synthetic-")
    assert (stores[0].root / ".credentials.lock").stat().st_ino == identity
    assert len(list(stores[0].root.glob("*.json"))) == 1


@pytest.mark.parametrize(
    "fault",
    ["temp-fsync", "replace-before", "replace-after", "directory-fsync", "readback", "lock-exit"],
)
def test_docker_transaction_faults_preserve_destination_and_uncertainty(
    tmp_path, monkeypatch, fault
):
    from app.research_web import credential_backend

    store = docker_store(tmp_path)
    model_call(tmp_path, store, "set", value="synthetic-old")
    replace, fsync = os.replace, os.fsync
    read, verify = store._read, store._verify_root
    state = {"published": False}

    def replacement(src, dst, **kwargs):
        if fault == "replace-before":
            raise OSError("synthetic-sensitive-detail")
        replace(src, dst, **kwargs)
        state["published"] = True
        if fault == "replace-after":
            raise OSError("synthetic-sensitive-detail")

    def sync(fd):
        if fault == "temp-fsync" and not state["published"]:
            raise OSError("synthetic-sensitive-detail")
        if fault == "directory-fsync" and state["published"]:
            raise OSError("synthetic-sensitive-detail")
        fsync(fd)

    def reader(directory, name):
        if fault == "readback" and state["published"]:
            raise OSError("synthetic-sensitive-detail")
        return read(directory, name)

    def verifier(directory):
        if fault == "lock-exit" and state["published"]:
            raise credential_backend.CredentialBackendError("credential_home_changed")
        verify(directory)

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", replacement)
        patch.setattr(os, "fsync", sync)
        patch.setattr(store, "_read", reader)
        patch.setattr(store, "_verify_root", verifier)
        expected = (
            "model_credential_store_unavailable"
            if fault == "temp-fsync"
            else "model_credential_commit_uncertain"
        )
        with pytest.raises(RuntimeError, match=expected):
            model_call(tmp_path, store, "set", value="synthetic-new")
    current = model_call(tmp_path, docker_store(tmp_path), "resolve")["value"]
    assert current == ("synthetic-new" if state["published"] else "synthetic-old")
    assert not list(store.root.glob("*.tmp"))


def test_docker_unset_post_unlink_failure_is_uncertain(tmp_path, monkeypatch):
    store = docker_store(tmp_path)
    model_call(tmp_path, store, "set", value="synthetic-old")
    with monkeypatch.context() as patch:
        patch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("sensitive")))
        with pytest.raises(RuntimeError, match="model_credential_commit_uncertain"):
            model_call(tmp_path, store, "unset")
    assert model_call(tmp_path, docker_store(tmp_path), "resolve") == {"value": None}


@pytest.mark.parametrize(
    "arguments",
    [
        ["--backend", "unknown"],
        ["--credential-root", "/tmp/synthetic"],
        ["--installation-id", INSTALLATION],
        ["--backend", "docker-private-file"],
        [
            "--backend",
            "docker-private-file",
            "--credential-root",
            "/tmp/synthetic",
            "--installation-id",
            INSTALLATION,
        ],
        ["--unknown", "synthetic-detail"],
    ],
)
def test_private_cli_binding_errors_are_stable(tmp_path, arguments):
    completed = subprocess.run(
        [sys.executable, "-I", "-B", str(BRIDGE), "--data-home", str(tmp_path), *arguments],
        input=json.dumps({"op": "describe", "ref": "RESEARCH_DSH_API_KEY"}),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 1
    assert json.loads(completed.stdout) == {
        "ok": False,
        "error": "model_credential_binding_invalid",
    }
    assert "synthetic" not in completed.stderr and str(tmp_path) not in completed.stderr


def isolated_store_process(tmp_path, request, *, repeat=1):
    script = (
        "import json, runpy, sys; from pathlib import Path; "
        "b=runpy.run_path(sys.argv[1]); request=json.loads(sys.stdin.read()); "
        "store=b['docker_backend'](Path(sys.argv[2]), sys.argv[3]); "
        "[b['execute'](Path(sys.argv[4]), request, store) for _ in range(int(sys.argv[5]))]; "
        "print(json.dumps(b['execute'](Path(sys.argv[4]), {'op':'describe','ref':'RESEARCH_DSH_API_KEY'}, store)))"
    )
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            script,
            str(BRIDGE),
            str(tmp_path.resolve() / "models" / INSTALLATION),
            INSTALLATION,
            str(tmp_path),
            str(repeat),
        ],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env={
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": str(tmp_path / "untrusted"),
            "RESEARCH_DSH_API_KEY": "synthetic-ambient",
        },
        cwd=tmp_path,
    )


def test_docker_cold_process_and_concurrent_processes(tmp_path):
    (tmp_path / "app.py").write_text("raise RuntimeError('synthetic-untrusted-cwd')")
    ambient = tmp_path / "untrusted"
    ambient.mkdir()
    (ambient / "app.py").write_text("raise RuntimeError('synthetic-untrusted-pythonpath')")
    store = docker_store(tmp_path)
    model_call(tmp_path, store, "set", value="synthetic-initial")
    lock_inode = (store.root / ".credentials.lock").stat().st_ino

    def write(index):
        completed = isolated_store_process(
            tmp_path,
            {"op": "set", "ref": "RESEARCH_DSH_API_KEY", "value": f"synthetic-process-{index}"},
            repeat=10,
        )
        assert completed.returncode == 0
        assert json.loads(completed.stdout)["configured"] is True

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(write, range(4)))
    assert model_call(tmp_path, docker_store(tmp_path), "resolve")["value"].startswith(
        "synthetic-process-"
    )
    assert (store.root / ".credentials.lock").stat().st_ino == lock_inode
    assert len(list(store.root.glob("*.json"))) == 1
    completed = isolated_store_process(tmp_path, {"op": "unset", "ref": "RESEARCH_DSH_API_KEY"})
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["configured"] is False
    completed = isolated_store_process(tmp_path, {"op": "describe", "ref": "RESEARCH_DSH_API_KEY"})
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["configured"] is False


@pytest.mark.parametrize("target", ["record", "lock"])
def test_docker_inode_replaced_while_reading_rejected(tmp_path, monkeypatch, target):
    store = docker_store(tmp_path)
    model_call(tmp_path, store, "set", value="synthetic-old")
    path = (
        next(store.root.glob("*.json")) if target == "record" else store.root / ".credentials.lock"
    )
    original = os.open
    replaced = False

    def swap(name, flags, *args, **kwargs):
        nonlocal replaced
        if name == path.name and not flags & os.O_CREAT and not replaced:
            replaced = True
            raw = path.read_bytes()
            path.rename(tmp_path / "retained")
            path.write_bytes(raw)
            path.chmod(0o600)
        return original(name, flags, *args, **kwargs)

    if target == "lock":
        # Replace after the FD is opened: the persistent lock pin must detect it.
        import fcntl

        flock = fcntl.flock

        def lock_swap(fd, operation):
            nonlocal replaced
            flock(fd, operation)
            if not replaced:
                replaced = True
                path.rename(tmp_path / "retained")
                path.write_bytes(b"")
                path.chmod(0o600)

        monkeypatch.setattr(fcntl, "flock", lock_swap)
    else:
        monkeypatch.setattr(os, "open", swap)
    with pytest.raises(RuntimeError, match="model_credential_"):
        model_call(tmp_path, store, "resolve")
    assert replaced


def test_docker_before_publication_readback_failure_keeps_old(tmp_path, monkeypatch):
    store = docker_store(tmp_path)
    model_call(tmp_path, store, "set", value="synthetic-old")
    read = store._read
    with monkeypatch.context() as patch:

        def reader(directory, name):
            if name.endswith(".tmp"):
                raise OSError("synthetic-private-detail")
            return read(directory, name)

        patch.setattr(store, "_read", reader)
        with pytest.raises(RuntimeError, match="model_credential_store_unavailable"):
            model_call(tmp_path, store, "set", value="synthetic-new")
    assert model_call(tmp_path, docker_store(tmp_path), "resolve")["value"] == "synthetic-old"
    assert not list(store.root.glob("*.tmp"))


def test_private_cli_docker_failure_cannot_write_logs_into_stdout(tmp_path):
    unsafe = tmp_path.resolve() / "unsafe"
    unsafe.mkdir(mode=0o755)
    unsafe.chmod(0o755)
    script = (
        "import runpy, sys; b=runpy.run_path(sys.argv[1]); "
        "root, identifier, home=sys.argv[2:5]; "
        "factory=lambda *args: b['docker_backend'](root, identifier); "
        "b['main'].__globals__['select_backend']=factory; "
        "sys.argv=['model-bridge','--data-home',home]; sys.exit(b['main']())"
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            script,
            str(BRIDGE),
            str(unsafe),
            INSTALLATION,
            str(tmp_path),
        ],
        input=json.dumps({"op": "describe", "ref": "RESEARCH_DSH_API_KEY"}),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 1
    assert json.loads(completed.stdout) == {"ok": False, "error": "model_credential_bridge_failed"}
    assert "synthetic" not in completed.stderr and str(tmp_path) not in completed.stderr


def test_private_selector_demands_linux_exact_leaf(tmp_path, monkeypatch):
    bridge = load_bridge()
    seen = []
    monkeypatch.setattr(
        bridge,
        "docker_backend",
        lambda root, identifier: seen.append((root, identifier)) or "selected",
    )
    root = "/run/rwb-secrets/private/models/" + INSTALLATION
    monkeypatch.setattr(bridge.sys, "platform", "linux")
    assert bridge.select_backend("docker-private-file", root, INSTALLATION) == "selected"
    for wrong in [root + "/", root.replace("/models/", "/private/"), root + "/..", str(tmp_path)]:
        with pytest.raises(ValueError, match="model_credential_binding_invalid"):
            bridge.select_backend("docker-private-file", wrong, INSTALLATION)
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    with pytest.raises(ValueError, match="model_credential_binding_invalid"):
        bridge.select_backend("docker-private-file", root, INSTALLATION)
    assert seen == [(root, INSTALLATION)]


@pytest.mark.parametrize("value", ["", 123, "x" * 1025, "\ud800"])
def test_docker_value_bounds_preserve_previous(tmp_path, value):
    store = docker_store(tmp_path)
    model_call(tmp_path, store, "set", value="synthetic-old")
    with pytest.raises((RuntimeError, ValueError)):
        model_call(tmp_path, store, "set", value=value)
    assert model_call(tmp_path, docker_store(tmp_path), "resolve")["value"] == "synthetic-old"


def test_docker_dedicated_models_parent_remains_private(tmp_path):
    store = docker_store(tmp_path)
    model_call(tmp_path, store, "set", value="synthetic-old")
    store.root.parent.chmod(0o755)
    with pytest.raises(RuntimeError, match="model_credential_store_unavailable"):
        model_call(tmp_path, store, "resolve")
    with pytest.raises(RuntimeError, match="model_credential_store_unavailable"):
        docker_store(tmp_path)
    assert store.root.parent.stat().st_mode & 0o777 == 0o755


def test_docker_unsafe_model_parent_rejected_before_installation_leaf_creation(tmp_path):
    parent = tmp_path.resolve() / "models"
    parent.mkdir(mode=0o700)
    parent.chmod(0o755)
    with pytest.raises(RuntimeError, match="model_credential_store_unavailable"):
        docker_store(tmp_path)
    assert not (parent / INSTALLATION).exists()
    assert parent.stat().st_mode & 0o777 == 0o755


@pytest.mark.parametrize("op", [[], {}, 5, None])
def test_invalid_nonstring_operation_rejected_stably(tmp_path, op):
    with pytest.raises(ValueError, match="model_credential_request_invalid"):
        load_bridge().execute(tmp_path, {"op": op, "ref": "RESEARCH_DSH_API_KEY"}, MemoryBackend())


@pytest.mark.parametrize("operation", ["get_password", "set_password", "delete_password"])
def test_docker_all_store_operations_reject_arbitrary_reference(tmp_path, operation):
    store = docker_store(tmp_path)
    arguments = ["synthetic-new"] if operation == "set_password" else []
    with pytest.raises(RuntimeError, match="model_credential_reference_invalid"):
        getattr(store, operation)("ResearchWorkbench.DataHub", "arbitrary", *arguments)
    assert not list(store.root.glob("*.json"))


@pytest.mark.parametrize("stage", ["before", "after"])
def test_docker_ambiguous_unlink_is_uncertain_and_never_restored(tmp_path, monkeypatch, stage):
    store = docker_store(tmp_path)
    model_call(tmp_path, store, "set", value="synthetic-old")
    unlink = os.unlink
    with monkeypatch.context() as patch:

        def fail(name, **kwargs):
            if stage == "after":
                unlink(name, **kwargs)
            raise OSError("synthetic-sensitive-error")

        patch.setattr(os, "unlink", fail)
        with pytest.raises(RuntimeError, match="model_credential_commit_uncertain"):
            model_call(tmp_path, store, "unset")
    assert model_call(tmp_path, docker_store(tmp_path), "resolve")["value"] == (
        None if stage == "after" else "synthetic-old"
    )


def test_docker_broken_diagnostics_cannot_hide_uncertain_commit(tmp_path, monkeypatch):
    from app.research_web import model_file_store

    store = docker_store(tmp_path)
    model_call(tmp_path, store, "set", value="synthetic-old")
    replace = os.replace

    def replace_then_fail(*args, **kwargs):
        replace(*args, **kwargs)
        raise OSError("synthetic-sensitive-os-error")

    def log_failure(*args, **kwargs):
        raise RuntimeError("synthetic-sensitive-logger-error")

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", replace_then_fail)
        patch.setattr(model_file_store.log, "warning", log_failure)
        with pytest.raises(RuntimeError, match="^model_credential_commit_uncertain$"):
            model_call(tmp_path, store, "set", value="synthetic-new")
    assert model_call(tmp_path, docker_store(tmp_path), "resolve")["value"] == "synthetic-new"


@pytest.mark.parametrize("kind", ["public", "symlink"])
def test_docker_initial_root_never_repairs_unsafe_existing_nodes(tmp_path, kind):
    root = tmp_path.resolve() / "models" / INSTALLATION
    root.parent.mkdir(mode=0o700)
    if kind == "public":
        root.mkdir(mode=0o700)
        root.chmod(0o755)
    else:
        target = tmp_path / "other"
        target.mkdir(mode=0o700)
        root.symlink_to(target, target_is_directory=True)
    with pytest.raises(RuntimeError, match="model_credential_store_unavailable"):
        load_bridge().docker_backend(root, INSTALLATION)
    assert root.is_symlink() if kind == "symlink" else root.stat().st_mode & 0o777 == 0o755


def test_docker_canonical_record_binds_installation_and_fixed_ref(tmp_path):
    store = docker_store(tmp_path)
    value = "中" * 1024
    model_call(tmp_path, store, "set", value=value)
    path = next(store.root.glob("*.json"))
    payload = {
        "version": 1,
        "installation_id": INSTALLATION,
        "ref": "RESEARCH_DSH_API_KEY",
        "password": value,
    }
    assert (
        path.read_bytes() == json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    )
    assert path.stat().st_size < 8192 and path.stat().st_mode & 0o777 == 0o600
    payload["installation_id"] = "a" * 32
    path.write_bytes(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
    with pytest.raises(RuntimeError, match="model_credential_record_invalid"):
        model_call(tmp_path, store, "resolve")


class MemoryBackend:
    def __init__(self):
        self.values = {}

    def get_password(self, service, account):
        return self.values.get((service, account))

    def set_password(self, service, account, value):
        self.values[service, account] = value

    def delete_password(self, service, account):
        del self.values[service, account]


def test_only_fixed_reference_and_valid_operations(tmp_path):
    bridge = load_bridge()
    backend = MemoryBackend()
    for request in [{"op": "readRecord"}, {"op": "resolve", "ref": "OTHER"}]:
        with pytest.raises(ValueError, match="model_credential_request_invalid"):
            bridge.execute(tmp_path, request, backend)
    assert backend.values == {}


def test_namespace_lifecycle_ignores_legacy_values(tmp_path, monkeypatch):
    bridge = load_bridge()
    backend = MemoryBackend()
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv(bridge.MODEL_REF, "synthetic-ambient")
    (tmp_path / ".credentials.yaml").write_text("RESEARCH_DSH_API_KEY: synthetic-file")
    call = lambda op, **kw: bridge.execute(
        tmp_path, {"op": op, "ref": bridge.MODEL_REF, **kw}, backend
    )
    assert call("resolve") == {"value": None}
    assert call("describe") == {"configured": False, "source": "system-keychain", "writable": True}
    call("set", value="synthetic-first")
    assert call("resolve")["value"] == "synthetic-first"
    with pytest.raises(ValueError):
        call("set", value="")
    assert call("resolve")["value"] == "synthetic-first"
    call("set", value="synthetic-second")
    assert call("resolve")["value"] == "synthetic-second"
    assert bridge.execute(other, {"op": "resolve", "ref": bridge.MODEL_REF}, backend) == {
        "value": None
    }
    call("unset")
    call("unset")
    assert call("resolve") == {"value": None}


def test_other_platform_fails_without_importing_macos_backend(monkeypatch):
    bridge = load_bridge()
    monkeypatch.setattr(bridge.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="model_credential_backend_unavailable"):
        bridge.system_backend()


def test_atomic_replacement_failure_never_deletes_old_value():
    bridge = load_bridge()

    class API:
        class error:
            item_not_found = -25300

        class Error:
            @staticmethod
            def raise_for_status(status):
                if status:
                    raise RuntimeError("synthetic-denied")

        @staticmethod
        def k_(value):
            return value

        @staticmethod
        def create_query(**value):
            return value

        @staticmethod
        def SecItemAdd(*args):
            raise AssertionError("replacement must not add or delete")

    def denied_update(query, attributes):
        assert query["kSecAttrService"] == "isolated-test-service"
        return -128

    with pytest.raises(RuntimeError, match="synthetic-denied"):
        bridge.update_or_add(
            API, denied_update, "isolated-test-service", bridge.MODEL_REF, "synthetic-new"
        )


@pytest.mark.skipif(
    sys.platform != "darwin" or os.environ.get("RWB_C1_KEYCHAIN_TEST") != "1",
    reason="explicitly authorized native Keychain evidence only",
)
def test_real_keychain_cross_process_lifecycle(tmp_path):
    """Only fresh pytest homes; synthetic values stay in private process pipes."""
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()

    def call(home, op, value=None):
        request = {"op": op, "ref": "RESEARCH_DSH_API_KEY"}
        if value is not None:
            request["value"] = value
        completed = subprocess.run(
            [sys.executable, "-I", "-B", str(BRIDGE), "--data-home", str(home)],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env={
                "PATH": "/usr/bin:/bin",
                "LANG": "en_US.UTF-8",
                "RESEARCH_DSH_API_KEY": "synthetic-ambient",
            },
        )
        if completed.returncode:
            pytest.fail("Keychain bridge unavailable; no secret diagnostics captured")
        return json.loads(completed.stdout)

    (first / ".credentials.yaml").write_text("RESEARCH_DSH_API_KEY: synthetic-old")
    (first / ".env").write_text("RESEARCH_DSH_API_KEY=synthetic-old")
    try:
        assert call(first, "resolve")["value"] is None
        assert call(second, "resolve")["value"] is None
        call(first, "set", "synthetic-first")
        assert bool(call(first, "resolve")["value"] == "synthetic-first")
        assert call(first, "describe")["configured"] is True
        # A describe/resolve never overwrites: product blank retention skips set.
        assert bool(call(first, "resolve")["value"] == "synthetic-first")
        call(first, "set", "synthetic-second")
        assert bool(call(first, "resolve")["value"] == "synthetic-second")
        assert call(second, "resolve")["value"] is None
        call(second, "set", "synthetic-isolated")
        call(first, "unset")
        # Each call is a new process: cold read after deletion cannot revive old values.
        assert call(first, "resolve")["value"] is None
        assert bool(call(second, "resolve")["value"] == "synthetic-isolated")
    finally:
        call(first, "unset")
        call(second, "unset")


@pytest.mark.skipif(
    sys.platform != "darwin" or os.environ.get("RWB_C1_RUNTIME_TEST") != "1",
    reason="explicitly authorized owned fixed DSH native evidence only",
)
def test_owned_overlay_fixed_dsh_consumer_and_cold_recovery(tmp_path):
    from app.research_web import launch_runtime

    source = Path(os.environ["RWB_C1_DSH_SOURCE"])
    node = os.environ["RWB_C1_NODE"]
    data = tmp_path / "isolated-runtime"
    data.mkdir()
    _command, env, work = launch_runtime.prepare(source, data, node, 13081, research_tools=True)
    home = data / "runtime/home"
    launch_runtime.prepare_runtime_module_fallback(source, home, node)
    launch_runtime.stage_tabbit_package(launch_runtime.TABBIT_VENDOR, home)
    launch_runtime.stage_tabbit_adapter(BRIDGE.parent / "runtime/tabbit-adapter.mjs", home)
    # Deliberately place legacy values AFTER prepare; the model provider must
    # independently reject every fallback, not rely on environment cleaning.
    (home / ".credentials.yaml").write_text("RESEARCH_DSH_API_KEY: synthetic-old")
    (work / ".env").write_text("RESEARCH_DSH_API_KEY=synthetic-old")
    (home / ".env").write_text("RESEARCH_DSH_API_KEY=synthetic-old")
    env["RESEARCH_DSH_API_KEY"] = "synthetic-ambient"
    helper = Path(__file__).with_name("model_credentials_native.mjs")
    try:
        for phase in ("empty", "restart-with-key", "restart-cleared", "backend-unavailable"):
            if phase == "backend-unavailable":
                overlay = data / "runtime/overlay.yml"
                original = overlay.read_text()
                overlay.write_text(
                    original.replace(json.dumps(sys.executable), json.dumps("/usr/bin/false"))
                )
            completed = subprocess.run(
                [node, str(helper), str(source), str(data), phase, "13081"],
                cwd=work,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            # Raw boot output can contain a launch token. Never persist/echo it.
            if completed.returncode:
                diagnostics = [
                    line for line in completed.stdout.splitlines() if line.startswith("C1_DIAG:")
                ]
                pytest.fail(
                    "owned Runtime acceptance failed; raw auth output withheld; "
                    + " ".join(diagnostics)
                )
            results = [
                line.removeprefix("C1_RESULT:")
                for line in completed.stdout.splitlines()
                if line.startswith("C1_RESULT:")
            ]
            assert len(results) == 1
            assert json.loads(results[0]) == {
                "phase": phase,
                "preset": True,
                "consumer": True,
                "hostRecords": True,
                "noModelFile": True,
            }
    finally:
        subprocess.run(
            [sys.executable, "-I", "-B", str(BRIDGE), "--data-home", str(data)],
            input=json.dumps({"op": "unset", "ref": "RESEARCH_DSH_API_KEY"}),
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )


def test_compatible_reference_is_independent_and_has_no_legacy_fallback(tmp_path, monkeypatch):
    bridge = load_bridge()
    backend = MemoryBackend()
    compatible_ref = "RESEARCH_COMPAT_API_KEY"
    monkeypatch.setenv(compatible_ref, "synthetic-ambient")
    (tmp_path / ".credentials.yaml").write_text("RESEARCH_COMPAT_API_KEY: synthetic-file")
    call = lambda ref, op, **kw: bridge.execute(tmp_path, {"op": op, "ref": ref, **kw}, backend)
    call(bridge.MODEL_REF, "set", value="synthetic-original")
    assert call(compatible_ref, "resolve") == {"value": None}
    call(compatible_ref, "set", value="synthetic-compatible")
    assert call(bridge.MODEL_REF, "resolve")["value"] == "synthetic-original"
    assert call(compatible_ref, "resolve")["value"] == "synthetic-compatible"
    call(compatible_ref, "unset")
    assert call(compatible_ref, "resolve") == {"value": None}
    assert call(bridge.MODEL_REF, "resolve")["value"] == "synthetic-original"
