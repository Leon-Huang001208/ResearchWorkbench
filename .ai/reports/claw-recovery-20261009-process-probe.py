"""macOS process-crash acceptance with a controlled loopback backend, not DSH."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request, urlopen

from app.research_web.automation.models import AutomationCreate
from app.research_web.automation.service import AutomationService
from app.research_web.store import Store
from core.observability import get_logger

log = get_logger(__name__)


class ControlledBackend:
    def __init__(self, root: Path, kind: str):
        self.root, self.kind = root, kind
        self.lock = threading.RLock()
        self.seen = threading.Event()
        self.finish = threading.Event()
        self.validating = threading.Event()
        self.validated = threading.Event()
        self.artifact_ready = threading.Event()
        self.error: str | None = None
        self.reads = 0
        self.counts = {"create": 0, "send": 0, "report_start": 0}
        self.session_id, self.report_id = "owned-claw-session", "owned-report-run"
        self.session_status, self.report_status = "idle", "queued"
        self.artifacts: list[dict] = []

    def execute(self):
        try:
            intermediate = self.root / "controlled-pre-crash.md"
            content = b"controlled artifact created before Web crash\n"
            intermediate.write_bytes(content)
            with self.lock:
                self.artifacts.append(
                    {
                        "id": "owned-intermediate-artifact",
                        "name": intermediate.name,
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                )
            self.artifact_ready.set()
            log.info("controlled_backend_pre_crash_artifact_ready", kind=self.kind)
            if not self.finish.wait(25):
                return
            if self.kind == "report_workflow":
                with self.lock:
                    self.session_status = "completed"
                    self.report_status = "validating"
                self.validating.set()
                if not self.validated.wait(15):
                    return
            path = self.root / "controlled-output.md"
            content = b"controlled execution witness; no financial or model claim\n"
            path.write_bytes(content)
            with self.lock:
                self.artifacts.append(
                    {
                        "id": "owned-artifact",
                        "name": path.name,
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                )
                self.session_status = self.report_status = "completed"
        except OSError as error:
            with self.lock:
                self.error = type(error).__name__
            self.artifact_ready.set()
            log.error("controlled_backend_artifact_io_failed", error_type=type(error).__name__)

    def respond(self, path: str, body: dict):
        with self.lock:
            if path == "/create":
                self.counts["create"] += 1
                return {"id": self.session_id}
            if path == "/send":
                self.counts["send"] += 1
                self.session_status = "running"
                threading.Thread(target=self.execute, daemon=True).start()
                return {"accepted": True}
            if path == "/report-start":
                self.counts["report_start"] += 1
                self.session_status = self.report_status = "running"
                threading.Thread(target=self.execute, daemon=True).start()
                return {"id": self.report_id, "session_id": None}
            if path in {"/detail", "/report"}:
                self.reads += 1
                self.seen.set()
                if path == "/detail":
                    return {
                        "status": self.session_status,
                        "files": copy.deepcopy(self.artifacts),
                        "messages": [{"role": "assistant", "text": "controlled complete"}],
                    }
                return {
                    "id": self.report_id,
                    "workflow_id": "controlled",
                    "version": 2,
                    "trigger": "automation",
                    "status": self.report_status,
                    "session_id": self.session_id,
                    "artifacts": copy.deepcopy(self.artifacts),
                }
            raise ValueError("unexpected controlled backend route")


async def worker(root: Path, port: int, kind: str, recover: bool, baseline: Path | None):
    selected_service = AutomationService
    if baseline is not None:
        name = "app.research_web.automation._process_baseline"
        spec = importlib.util.spec_from_file_location(name, baseline)
        if spec is None or spec.loader is None:
            raise RuntimeError("baseline loader missing")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        selected_service = module.AutomationService

    def request(path: str, body: dict | None = None):
        data = None if body is None else json.dumps(body).encode()
        with urlopen(
            Request(
                f"http://127.0.0.1:{port}{path}",
                data=data,
                headers={"Content-Type": "application/json"},
            ),
            timeout=3,
        ) as response:
            return json.load(response)

    class ReportRuntime:
        catalog = SimpleNamespace(data={"runs": {}})

        async def start_run(self, target_id, *, trigger, version):
            result = await asyncio.to_thread(request, "/report-start", {"version": version})
            self.catalog.data["runs"][result["id"]] = request("/report")
            return result

        def _run(self, report_id):
            return request("/report")

    class Research:
        report_workflows = type("Reports", (), {"runtime": ReportRuntime()})()

        async def create(self, mode, title):
            return await asyncio.to_thread(request, "/create", {"mode": mode})

        async def send(self, session_id, text, key, **kwargs):
            return await asyncio.to_thread(request, "/send", {"key": key})

        async def detail(self, session_id):
            return await asyncio.to_thread(request, "/detail")

    service = selected_service(
        Store(root / "web"),
        research=Research(),
        scheduler=False,
        target_resolver=lambda *_args: {"version": 2, "sha256": "a" * 64},
    )
    if recover:
        await service.start()
    else:
        body = AutomationCreate.model_validate(
            {
                "name": "controlled acceptance",
                "target_kind": kind,
                "target_id": "controlled",
                "target_version": 2,
                "input_template": "controlled acceptance only",
                "workspace_id": "research",
                "output_formats": ["md"],
                "mcp_tools": [],
                "schedule": {"kind": "daily", "timezone": "Asia/Shanghai", "hour": 9, "minute": 0},
                "delivery": {"channel_ids": [], "include_attachments": False},
            }
        )
        automation = service.create(body)
        await service.run(automation["id"])
    await service.wait_for_idle()


def run_case(kind: str, baseline_text: bytes | None, artifact_loss_probe: bool = False):
    with tempfile.TemporaryDirectory(prefix="rwb-claw-crash-") as directory:
        root = Path(directory)
        os.chmod(root, 0o700)
        backend = ControlledBackend(root, kind)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def respond(self):
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size)) if size else {}
                payload = json.dumps(backend.respond(self.path, body)).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(payload)

            do_GET = respond
            do_POST = respond

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        baseline = root / "baseline_service.py"
        if baseline_text is not None:
            baseline.write_bytes(baseline_text)
        args = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            str(root),
            "--port",
            str(server.server_port),
            "--kind",
            kind,
        ]
        if baseline_text is not None:
            args += ["--baseline", str(baseline)]
        processes = []
        try:
            with (root / "worker.log").open("wb") as log:
                original = subprocess.Popen(args, stdout=log, stderr=log)
                processes.append(original)
                assert backend.seen.wait(10), "original did not reach a native monitoring read"
                assert (
                    original.poll() is None
                ), "original process must be alive before controlled kill"
                reference = "report_run_id" if kind == "report_workflow" else "session_id"
                expected = backend.report_id if kind == "report_workflow" else backend.session_id
                deadline = time.monotonic() + 3
                while True:
                    run = next(iter(Store(root / "web").data["automation_runs"].values()))
                    if (
                        run[reference] == expected
                        or original.poll() is not None
                        or time.monotonic() >= deadline
                    ):
                        break
                    time.sleep(0.01)
                assert (
                    run[reference] == expected
                ), "native reference absent before Web process crash"
                assert backend.artifact_ready.wait(3), "pre-crash artifact was not produced"
                assert backend.error is None, "controlled backend failed to produce artifact"
                intermediate = root / "controlled-pre-crash.md"
                before_bytes = intermediate.read_bytes()
                before_sha = hashlib.sha256(before_bytes).hexdigest()
                with backend.lock:
                    pre_crash_artifact = copy.deepcopy(backend.artifacts[0])
                assert pre_crash_artifact["sha256"] == before_sha
                original.kill()
                original.wait(timeout=3)
                assert original.returncode == -9
                if artifact_loss_probe:
                    intermediate.write_bytes(b"controlled artifact corruption witness\n")
                reads_before = backend.reads
                recovery = subprocess.Popen(args + ["--recover"], stdout=log, stderr=log)
                processes.append(recovery)
                deadline = time.monotonic() + 10
                while (
                    backend.reads <= reads_before
                    and recovery.poll() is None
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.02)
                assert (
                    backend.reads > reads_before
                ), "new process did not reconnect to the original run"
                backend.finish.set()
                if kind == "report_workflow":
                    assert backend.validating.wait(3)
                    assert (
                        Store(root / "web").data["automation_runs"][run["id"]]["research_status"]
                        == "running"
                    )
                    backend.validated.set()
                recovery.wait(timeout=10)
                assert recovery.returncode == 0
                restored = Store(root / "web").data["automation_runs"][run["id"]]
                assert restored["research_status"] == "completed"
                assert restored[reference] == expected
                assert restored["artifacts"] == backend.artifacts
                assert pre_crash_artifact in restored["artifacts"]
                after_bytes = intermediate.read_bytes()
                after_sha = hashlib.sha256(after_bytes).hexdigest()
                assert (
                    after_bytes == before_bytes
                ), "pre-crash artifact bytes changed after recovery"
                assert after_sha == before_sha
                output_sha = hashlib.sha256(
                    (root / "controlled-output.md").read_bytes()
                ).hexdigest()
                assert output_sha == backend.artifacts[-1]["sha256"]
                expected_counts = (
                    {"create": 0, "send": 0, "report_start": 1}
                    if kind == "report_workflow"
                    else {"create": 1, "send": 1, "report_start": 0}
                )
                assert backend.counts == expected_counts
                evidence = Path(__file__).with_name("claw-recovery-20261009-evidence")
                (evidence / f"artifact-{kind}-before.md").write_bytes(before_bytes)
                (evidence / f"artifact-{kind}-after.md").write_bytes(after_bytes)
                return {
                    "kind": kind,
                    "status": "PASS",
                    "crashExit": original.returncode,
                    "sameRun": True,
                    "sameNativeReference": True,
                    "nativeCalls": backend.counts,
                    "artifactSHA256": output_sha,
                    "preCrashArtifactSHA256": before_sha,
                    "postRecoveryArtifactSHA256": after_sha,
                    "artifactBytesPreserved": True,
                }
        finally:
            backend.finish.set()
            backend.validated.set()
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=3)
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--kind", choices=["skill", "workflow", "report_workflow"])
    parser.add_argument("--recover", action="store_true")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--baseline-revision")
    parser.add_argument("--artifact-loss-probe", action="store_true")
    options = parser.parse_args()
    if options.worker:
        asyncio.run(
            worker(options.worker, options.port, options.kind, options.recover, options.baseline)
        )
        return
    baseline = (
        subprocess.check_output(
            ["git", "show", f"{options.baseline_revision}:app/research_web/automation/service.py"]
        )
        if options.baseline_revision
        else None
    )
    results = []
    for kind in ["skill", "workflow", "report_workflow"]:
        try:
            results.append(run_case(kind, baseline, options.artifact_loss_probe))
        except (AssertionError, OSError, subprocess.SubprocessError) as error:
            results.append({"kind": kind, "status": "FAIL", "error": str(error)})
    result = {
        "evidence": "real macOS child process SIGKILL and controlled loopback backend",
        "realDSHModel": "NOT_RUN",
        "artifactLossInjected": options.artifact_loss_probe,
        "probeSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "sourceSHA256": hashlib.sha256(
            baseline
            if baseline is not None
            else Path("app/research_web/automation/service.py").read_bytes()
        ).hexdigest(),
        "cases": results,
    }
    suffix = (
        "artifact-loss-red"
        if options.artifact_loss_probe
        else "process-red" if baseline is not None else "process-receipt"
    )
    path = Path(__file__).with_name(f"claw-recovery-20261009-{suffix}.json")
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    if any(row["status"] != "PASS" for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
