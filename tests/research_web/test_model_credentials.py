"""The model reference cannot fall back to file/environment credential layers."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BRIDGE = Path(__file__).resolve().parents[2] / "app/research_web/model_credentials.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("model_credentials_tested", BRIDGE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
