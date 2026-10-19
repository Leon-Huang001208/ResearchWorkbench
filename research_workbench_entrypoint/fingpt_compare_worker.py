"""Owned experiment workers. Credential responses are private subprocess pipes only."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
from contextlib import ExitStack
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE.parent))
from research_workbench_entrypoint.fingpt_compare import (
    CURRENT,
    FLASH,
    GROUPS,
    ORIGINAL,
    ComparisonError,
    Experiment,
    atomic,
    credential,
    private,
    read,
    review_valid,
)

log = logging.getLogger(__name__)
PRODUCTION_DATA = Path.home() / ".research-workbench/research-web"
RETIRE_LOCK = threading.RLock()


def flash_credential(home, request, backend=credential):
    if (
        not isinstance(request, dict)
        or set(request) != {"op", "ref"}
        or request.get("ref") != "RESEARCH_DSH_API_KEY"
        or request.get("op") not in {"resolve", "describe"}
    ):
        raise ComparisonError("comparison_credential_write_denied")
    return backend(Path(home), request)


def export_source(project, commit, target):
    if target.exists():
        raise ComparisonError("comparison_source_exists")
    names = subprocess.check_output(
        ["/usr/bin/git", "-C", str(project), "ls-tree", "--name-only", commit], text=True
    ).splitlines()
    excluded = {"outputs", "docs", "tests", "data", "logs", "backups", "graphify-out"}
    names = [name for name in names if name not in excluded]
    raw = subprocess.check_output(
        ["/usr/bin/git", "-C", str(project), "archive", "--format=tar", commit, "--", *names],
        timeout=90,
    )
    if len(raw) > 200_000_000:
        raise ComparisonError("comparison_source_too_large")
    private(target)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        members = archive.getmembers()
        for member in members:
            if (
                not (member.isfile() or member.isdir())
                or Path(member.name).is_absolute()
                or ".." in Path(member.name).parts
            ):
                raise ComparisonError("comparison_source_unsafe")
        archive.extractall(target, members=members, filter="data")
    return hashlib.sha256(raw).hexdigest()


def prepare(exp, project):
    if (exp.root / "prepared.json").exists():
        return {"status": "prepared", **read(exp.root / "prepared.json")}
    resident = read(Path.home() / ".research-workbench/resident/config.json")
    python = str(Path(resident["project"]) / ".venv/bin/python")
    node = resident["node"]
    for executable in (python, node):
        if not Path(executable).is_file():
            raise ComparisonError("comparison_toolchain_unavailable")
    sources = private(exp.root / "sources")
    proofs = {}
    for label, commit in (("current", CURRENT), ("original", ORIGINAL)):
        proofs[label] = {
            "commit": commit,
            "archive_sha256": export_source(project, commit, sources / label),
        }
    for relative in ("requirements/web.lock", "requirements/web.in"):
        if (sources / "current" / relative).read_bytes() != (
            sources / "original" / relative
        ).read_bytes():
            raise ComparisonError("comparison_dependency_mismatch")
    original = read(
        Path.home() / ".research-workbench/acceptance/fingpt-deep-live-20261016/initial.json"
    )
    question = original["prompt"]
    atomic(
        exp.root / "question.json",
        {
            "text": question,
            "as_of": "2026-10-16",
            "sha256": hashlib.sha256(question.encode()).hexdigest(),
        },
    )
    import secrets

    atomic(exp.root / "runner-auth.json", {"token": secrets.token_urlsafe(32)})
    for group in GROUPS:
        private(exp.root / "groups" / group / "data")
        private(exp.root / "groups" / group / "logs")
    value = {
        "python": python,
        "node": node,
        "sources": proofs,
        "production_namespace": str(PRODUCTION_DATA),
        "source_deltas": "model seam and external limits only",
    }
    atomic(exp.root / "prepared.json", value)
    return {
        "status": "prepared",
        "groups": list(GROUPS),
        "question_sha256": hashlib.sha256(question.encode()).hexdigest(),
    }


def group_data(root, group, *, preflight=False):
    return root / "groups" / group / ("preflight-data" if preflight else "research-data")


def environment(root, group, *, preflight=False):
    config = read(root / "prepared.json")
    data = private(group_data(root, group, preflight=preflight))
    source = root / "sources" / ("current" if group == "A" else "original")
    return {
        "PATH": os.pathsep.join(
            (str(Path(config["node"]).parent), "/usr/bin", "/bin", "/usr/sbin", "/sbin")
        ),
        "LANG": "en_US.UTF-8",
        "HOME": str(Path.home()),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(PACKAGE.parent),
        "RESEARCH_DATA_HOME": str(data),
        "RESEARCH_RUN_MODE": "web-prod",
        "RESEARCH_PROJECT_ROOT": str(source),
        "LOG_DIR": str(root / "groups" / group / "logs"),
        "OBJECT_STORAGE_PATH": str(data / "objects"),
        "PDF_MARKDOWN_DIR": str(data / "markdown"),
        "PDF_RAW_TEXT_DIR": str(data / "raw_text"),
        "RESEARCH_NODE_BINARY": config["node"],
        "RESEARCH_RUNTIME_URL": "http://127.0.0.1:13081",
        "RESEARCH_RUNTIME_AUTH": str(data / "runtime/auth.json"),
        "RESEARCH_WEB_INTERNAL_URL": "http://127.0.0.1:18088",
        "RESEARCH_AUTOMATIONS_ENABLED": "0",
        "RESEARCH_FRAMEWORK_COLLECTORS_ENABLED": "0",
        "RESEARCH_MCP_RUNTIME_ENABLED": "0",
        "RWB_COMPARE_ROOT": str(root),
        "RWB_COMPARE_GROUP": group,
        "RWB_FINGPT_ENV_FILE": str(root / "no-plaintext-env"),
    }


def runtime(root, group):
    config = read(root / "prepared.json")
    source = root / "sources/current"
    sys.path.insert(0, str(source))
    from app.research_web import PINNED_DSH_COMMIT
    from app.research_web import launch_runtime as launch

    data = Path(os.environ["RESEARCH_DATA_HOME"])
    if data not in (group_data(root, group), group_data(root, group, preflight=True)):
        raise ComparisonError("comparison_data_binding_invalid")
    dsh = Path.home() / ".research-workbench/runtime/dsh" / PINNED_DSH_COMMIT
    command, env, work = launch.prepare(
        dsh,
        data,
        config["node"],
        13081,
        research_tools=True,
        datahub_url="http://127.0.0.1:18088",
        state_root=data / "runtime",
    )
    launch.prepare_runtime_module_fallback(dsh, data / "runtime/home", config["node"])
    launch.stage_tabbit_package(launch.TABBIT_VENDOR, data / "runtime/home")
    launch.stage_tabbit_adapter(
        source / "app/research_web/runtime/tabbit-adapter.mjs", data / "runtime/home"
    )
    # The original provider consumes exactly the existing credential adapter contract.
    # This shim permits describe/resolve only, including for Host's credential readiness check.
    shim = root / "groups" / group / "credential-readonly.py"
    shim.write_text(
        "import sys,json\nfrom pathlib import Path\n"
        + f"sys.path.insert(0,{str(PACKAGE.parent)!r})\n"
        + "from research_workbench_entrypoint.fingpt_compare_worker import flash_credential\n"
        + f"result=flash_credential(Path({str(PRODUCTION_DATA)!r}),json.loads(sys.stdin.read(8193)))\n"
        + "print(json.dumps({'ok':True,**result}))\n"
    )
    shim.chmod(0o600)
    overlay = data / "runtime/overlay.yml"
    old_bridge = str(source / "app/research_web/model_credentials.py")
    text = overlay.read_text()
    if text.count(f"bridge: {json.dumps(old_bridge)}") != 1:
        raise ComparisonError("comparison_credential_binding_unknown")
    text = text.replace(f"bridge: {json.dumps(old_bridge)}", f"bridge: {json.dumps(str(shim))}", 1)
    text += (
        "\n- insert:\n    - id: comparison-limits\n"
        f"      name: {json.dumps(str(PACKAGE / 'fingpt_compare_node.mjs'))}\n"
        f"      config:\n        metrics: {json.dumps(str(root / 'groups' / group / 'logs/metrics.jsonl'))}\n"
    )
    overlay.write_text(text)
    os.chdir(work)
    os.execve(config["node"], command, env)


def host(root, group):
    source = root / "sources" / ("current" if group == "A" else "original")
    sys.path.insert(0, str(source))
    from app.research_web import main

    if group != "A":
        base = main.FinGPTQA

        class Adapter(base):
            def __init__(self, research):
                super().__init__(research)
                self.entry = PACKAGE / "fingpt_compare_node.mjs"

        main.FinGPTQA = Adapter
        app = main.create_app()
    else:
        app = main.app
    import hmac

    from fastapi.responses import JSONResponse

    token = read(root / "runner-auth.json")["token"]

    @app.middleware("http")
    async def comparison_read_only(request, next_handler):
        # Native callbacks retain the original Host's private Data key check.
        callback = request.url.path.startswith("/api/research/internal/data/")
        if request.method not in {"GET", "HEAD"} and not callback:
            supplied = request.headers.get("X-Comparison-Runner", "")
            if not hmac.compare_digest(supplied, token):
                return JSONResponse({"error": {"code": "comparison_read_only"}}, status_code=403)
        return await next_handler(request)

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=18088, access_log=False)


def request(path, body=None, key=None, timeout=30, method=None, root=None):
    base = "http://127.0.0.1:18088"
    headers = {"Origin": base}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if key:
        headers["Idempotency-Key"] = key
    if root is not None:
        headers["X-Comparison-Runner"] = read(root / "runner-auth.json")["token"]
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as response:
        raw = response.read(32_000_001)
        if len(raw) > 32_000_000:
            raise ComparisonError("comparison_response_too_large")
        return json.loads(raw)


def wait_for(callback, seconds=90):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        try:
            return callback()
        except (OSError, ValueError):
            time.sleep(1)
    raise ComparisonError("comparison_startup_timeout")


def assert_flash_ready(value):
    if (
        any(
            value.get(key) is not True
            for key in (
                "connected",
                "owned_runtime",
                "health_check_passed",
                "credential_configured",
            )
        )
        or value.get("credential_code") not in (None, "")
        or any(value.get(key) != expected for key, expected in FLASH.items())
    ):
        raise ComparisonError("comparison_flash_not_ready")


def assert_owned_listener(port, child):
    if child.poll() is not None:
        raise ComparisonError("comparison_process_exited")
    result = subprocess.run(
        ["/usr/sbin/lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 1 and not result.stdout:
        raise OSError("comparison_process_starting")
    if result.returncode != 0 or {int(p) for p in result.stdout.split()} != {child.pid}:
        raise ComparisonError("comparison_listener_not_owned")


def complete_auth(root, group, child, exchange=None, data_root=None):
    from app.research_web.multiuser.runtime import _exchange_auth
    from app.research_web.runtime_auth import read_runtime_auth_record

    assert_owned_listener(13081, child)
    data = data_root or group_data(root, group)
    path = data / "runtime/auth.json"
    record = read_runtime_auth_record(path)
    pin = read(root / "sources/current/runtimes/research_web.json")["dsh"]["commit"]
    expected = {
        "authority": "127.0.0.1:13081",
        "cwd": str(data / "runtime/work"),
        "source_commit": pin,
        "pid": child.pid,
    }
    if any(record.get(k) != v for k, v in expected.items()):
        raise OSError("comparison_auth_starting")
    if isinstance(record.get("cookie"), str) and record["cookie"].startswith("dsh-auth-"):
        return
    token = record.get("bootstrap_token")
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ComparisonError("comparison_auth_invalid")
    cookie = (exchange or _exchange_auth)(13081, token)
    if cookie is None:
        raise OSError("comparison_auth_starting")
    if (
        not isinstance(cookie, str)
        or not cookie.startswith("dsh-auth-")
        or len(cookie) > 4096
        or any(c in cookie for c in "\r\n")
    ):
        raise ComparisonError("comparison_auth_invalid")
    if read_runtime_auth_record(path) != record or child.poll() is not None:
        raise ComparisonError("comparison_auth_identity_changed")
    assert_owned_listener(13081, child)
    final = {k: v for k, v in record.items() if k != "bootstrap_token"}
    final["cookie"] = cookie
    atomic(path, final)


def owned_members(child):
    child.poll()  # Reap our own leader; leader exit is not evidence its group ended.
    rows = subprocess.check_output(
        ["/bin/ps", "-axo", "pid=,pgid=,uid=,lstart="],
        text=True,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        timeout=5,
    ).splitlines()
    members = []
    for row in rows:
        parts = row.split(None, 3)
        if len(parts) != 4 or int(parts[1]) != child.pid:
            continue
        pid, _, uid = map(int, parts[:3])
        born = time.mktime(time.strptime(parts[3].strip(), "%a %b %d %H:%M:%S %Y"))
        try:
            session = os.getsid(pid)
        except ProcessLookupError:
            continue
        if uid != os.getuid() or session != child.pid or born < int(child.comparison_started) - 1:
            raise ComparisonError("comparison_process_group_identity_unknown")
        if pid == child.pid:
            if child.poll() is not None:
                # A new live leader with a re-used pid must never be signalled.
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    continue
                raise ComparisonError("comparison_process_group_leader_reused")
            if getattr(child, "comparison_birth", born) != born:
                raise ComparisonError("comparison_process_group_leader_reused")
        members.append({"pid": pid, "born": born})
    return members


def start_owned(command, **options):
    started = time.time()
    child = subprocess.Popen(command, start_new_session=True, **options)
    child.comparison_started = started
    for item in owned_members(child):
        if item["pid"] == child.pid:
            child.comparison_birth = item["born"]
    return child


def stop_owned(children):
    errors = []
    with RETIRE_LOCK:
        for child in reversed(children):
            try:
                members = owned_members(child)
                if not members:
                    continue
                os.killpg(child.pid, signal.SIGTERM)
                until = time.monotonic() + 1
                while time.monotonic() < until and owned_members(child):
                    time.sleep(0.05)
                if owned_members(child):
                    os.killpg(child.pid, signal.SIGKILL)
                until = time.monotonic() + 3
                while time.monotonic() < until and owned_members(child):
                    time.sleep(0.05)
                if owned_members(child):
                    raise ComparisonError("comparison_process_group_not_retired")
                child.poll()
            except (OSError, ValueError, subprocess.SubprocessError, ComparisonError) as exc:
                log.error("comparison_process_retirement_failed type=%s", type(exc).__name__)
                errors.append(type(exc).__name__)
    if errors:
        raise ComparisonError("comparison_process_retirement_unverified")


def arm_deadline(children, cancel, reached, seconds=890):
    """Reserve ten seconds for bounded retirement inside the 900s ceiling."""

    def expire():
        reached.set()

        def notify_cancel():
            try:
                cancel()
            except Exception as exc:  # noqa: BLE001
                log.warning("comparison_deadline_cancel type=%s", type(exc).__name__)

        threading.Thread(target=notify_cancel, daemon=True).start()
        try:
            stop_owned(children)
        except ComparisonError:
            log.error("comparison_deadline_retirement_unverified")

    timer = threading.Timer(seconds, expire)
    timer.daemon = True
    timer.start()
    return timer


def audit_group(exp, group, detail):
    """Read actual bytes only; never normalize evidence back into a model report."""
    root = exp.root
    folder = private(root / "results" / group)
    files = []
    sid = detail["id"]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for item in detail.get("files", []):
        if item.get("kind") != "outputs":
            continue
        name = item.get("name", "")
        if not name or Path(name).name != name:
            raise ComparisonError("comparison_artifact_identity_invalid")
        if not name.lower().endswith((".html", ".docx", ".pdf", ".md", ".json")):
            continue
        proofs = {}
        for action in ("download", "preview"):
            url = f"http://127.0.0.1:18088/api/research/sessions/{sid}/files/{item['id']}/{action}"
            try:
                with opener.open(url, timeout=15) as response:
                    raw = response.read(16_000_001)
                    if len(raw) > 16_000_000:
                        raise ComparisonError("comparison_artifact_too_large")
                    proofs[action] = {
                        "status": response.status,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "bytes": len(raw),
                    }
                    if action == "download":
                        destination = folder / name
                        fd = os.open(
                            destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                        )
                        with os.fdopen(fd, "wb") as output:
                            output.write(raw)
            except OSError:
                proofs[action] = {"status": "unavailable"}
        files.append({"name": name, **proofs})
    events = []
    metrics = root / "groups" / group / "logs/metrics.jsonl"
    if metrics.exists():
        events = [json.loads(line) for line in metrics.read_text().splitlines() if line]
    source_records = []
    native_binding = False
    quality_check_count = 0
    checked_archives = []
    if group == "A":
        data = group_data(root, group)
        index = read(data / "index.json")
        for identity, value in index["sessions"][sid].get("web_evidence", {}).items():
            path = data / "sessions" / sid / value["path"]
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != value["sha256"]:
                raise ComparisonError("comparison_source_integrity_failed")
            source_records.append(
                {
                    "id": identity,
                    "url": value["url"],
                    "sha256": actual,
                    "as_of": value.get("as_of", "unknown"),
                    "file": str(path.relative_to(root)),
                }
            )
        receipt = index.get("receipts", {}).get(
            f"{sid}:{index['sessions'][sid].get('delivery_key','')}", {}
        )
        checks = receipt.get("quality_checks", {})
        quality_check_count = len(checks)
        report_path = data / "sessions" / sid / "outputs/research-report.json"
        current_digest = (
            hashlib.sha256(report_path.read_bytes()).hexdigest() if report_path.is_file() else None
        )
        for version, item in receipt.get("quality_archives", {}).items():
            anchor = item["anchor"]
            check = checks[item["check_id"]]
            for artifact in anchor["files"]:
                path = (
                    data
                    / "sessions"
                    / sid
                    / "outputs"
                    / anchor["directory"]
                    / artifact["stored_name"]
                )
                if (
                    path.is_symlink()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]
                ):
                    raise ComparisonError("comparison_report_integrity_failed")
            matches = current_digest is not None and current_digest == check.get(
                "report_content_sha256"
            )
            native_binding = native_binding or matches
            checked_archives.append(
                {
                    "version_id": version,
                    "check_id": item["check_id"],
                    "report_content_sha256": check.get("report_content_sha256"),
                    "matches_current": matches,
                }
            )
    else:
        for event in events:
            if event.get("event") == "source_observed":
                path = root / event["file"]
                if (
                    path.is_symlink()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != event["sha256"]
                ):
                    raise ComparisonError("comparison_source_integrity_failed")
                source_records.append(event)
    from collections import Counter

    totals = Counter(e.get("event") for e in events)
    names = [item["name"] for item in files if item.get("download", {}).get("status") == 200]
    same_bytes = bool(files) and all(
        item.get("download", {}).get("sha256") == item.get("preview", {}).get("sha256")
        and item.get("download", {}).get("status") == 200
        for item in files
    )
    native_quality = detail.get("research_quality") or {}
    # Missing original quality/version contracts remain missing. A separate
    # audit manifest cannot manufacture native acceptance for B or C.
    result = {
        "group": group,
        "source_commit": GROUPS[group],
        "session_id": sid,
        "execution_status": detail.get("execution_status", detail.get("status")),
        "native_quality_status": native_quality.get("status", "NOT_RUN"),
        "native_research_accepted": detail.get("research_accepted", False),
        "common_quality_status": "incomplete",
        "independent_claim_review": "NOT_RUN",
        "sources_observed": source_records,
        "files": files,
        "preview_download_match": same_bytes,
        "html_available": any(name.endswith(".html") for name in names),
        "docx_available": any(name.endswith(".docx") for name in names),
        "native_version_binding": native_binding,
        "native_checked_archives": checked_archives,
        "native_quality_check_count": quality_check_count,
        "counters": dict(totals),
        "tool_target_20_met": totals["tool_admitted"] <= 20,
        "usage": [event["usage"] for event in events if event.get("event") == "usage"],
        "usage_available": any(event.get("event") == "usage" for event in events),
        "remaining": (
            native_quality.get("issues", [])
            if group == "A"
            else [
                "native_quality_receipt_not_implemented",
                "native_version_binding_not_implemented",
                "independent_claim_review_not_run",
            ]
        ),
    }
    atomic(root / "results" / (group + "-audit.json"), result)
    return result


def run_group(exp, group, *, preflight=False):
    root = exp.root
    config = read(root / "prepared.json")
    env = environment(root, group, preflight=preflight)
    children = []
    handles = ExitStack()
    attempt = None
    timer = None
    reservations = []
    try:
        for port in (13081, 18088):
            probe = socket.socket()
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                probe.close()
                raise ComparisonError("comparison_port_in_use") from None
            reservations.append(probe)
        for operation in ("runtime", "host"):
            if operation == "host":
                wait_for(
                    lambda: complete_auth(
                        root, group, children[0], data_root=Path(env["RESEARCH_DATA_HOME"])
                    )
                )
            reservations[0 if operation == "runtime" else 1].close()
            log_path = root / "groups" / group / "logs" / (operation + ".log")
            output = handles.enter_context(open(log_path, "ab"))  # noqa: SIM115
            child = start_owned(
                [
                    config["python"],
                    str(Path(__file__)),
                    operation,
                    "--root",
                    str(root),
                    "--group",
                    group,
                ],
                env=env,
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=output,
            )
            children.append(child)

        def ready():
            assert_owned_listener(13081, children[0])
            assert_owned_listener(18088, children[1])
            value = request("/api/research/runtime")
            if not value.get("connected") or not value.get("owned_runtime"):
                raise OSError("comparison_runtime_starting")
            return value

        wait_for(ready)
        if group == "A":
            request("/api/research/runtime/model", FLASH, method="PUT", root=root)
            assert_flash_ready(request("/api/research/runtime"))
        else:
            tiers = request("/api/research/fingpt/tiers")
            tier = "frontier" if group == "B" else "lite"
            if not tiers["tiers"][tier]["configured"]:
                raise ComparisonError("comparison_model_not_ready")
        if preflight:
            atomic(
                root / "results" / (group + "-preflight.json"),
                {"ready": True, "generation_verified": False},
            )
            return
        session = request(
            "/api/research/sessions",
            {
                "mode": "fingpt",
                "research_depth": "deep",
                "title": f"三组对照 {group} GDP 2024/2025",
                **({"research_mode": "deep"} if group == "A" else {}),
            },
            root=root,
        )
        sid = session["id"]
        question = read(root / "question.json")
        if (
            question.get("as_of") != "2026-10-16"
            or hashlib.sha256(question["text"].encode()).hexdigest() != question["sha256"]
        ):
            raise ComparisonError("comparison_question_changed")
        attempt = exp.reserve(group)
        attempt.update(
            session_id=sid,
            model=FLASH if group != "C" else read(root / "experiment.json")["lite"],
            prompt_sha256=question["sha256"],
        )
        atomic(root / "results" / (group + "-attempt.json"), attempt)
        start = time.monotonic()
        # Independent hard deadline still applies while HTTP polling is blocked.
        deadline_reached = threading.Event()
        timer = arm_deadline(
            children,
            lambda: request(f"/api/research/sessions/{sid}/cancel", {}, timeout=5, root=root),
            deadline_reached,
        )
        if group == "A":
            path = f"/api/research/sessions/{sid}/messages"
            payload = {
                "text": question["text"],
                "research_mode": "deep",
                "research_as_of": "2026-10-16",
            }
        else:
            path = f"/api/research/fingpt/sessions/{sid}/ask"
            payload = {
                "msg": question["text"],
                "mode": "deep",
                "tier": "frontier" if group == "B" else "lite",
            }
        result = request(path, payload, attempt["idempotency_key"], timeout=90, root=root)
        atomic(root / "results" / (group + "-send.json"), result)
        first_content = None
        while time.monotonic() - start < 900:
            detail = request(f"/api/research/sessions/{sid}")
            atomic(root / "results" / (group + "-detail.json"), detail)
            if first_content is None and any(
                m.get("role") == "assistant" and m.get("text") for m in detail.get("messages", [])
            ):
                first_content = time.monotonic() - start
            if detail.get("status") not in {"running", "starting", "queued"} and not detail.get(
                "can_cancel", False
            ):
                attempt.update(
                    status="deadline_reached" if deadline_reached.is_set() else "completed",
                    seconds=time.monotonic() - start,
                    first_content_seconds=first_content,
                )
                atomic(root / "results" / (group + "-attempt.json"), attempt)
                audit_group(exp, group, detail)
                return
            time.sleep(5)
        request(f"/api/research/sessions/{sid}/cancel", {}, root=root)
        attempt.update(status="deadline_reached", seconds=time.monotonic() - start)
        atomic(root / "results" / (group + "-attempt.json"), attempt)
    finally:
        for probe in reservations:
            probe.close()
        if timer is not None:
            timer.cancel()
        stop_owned(children)
        handles.close()


def sequence(exp):
    import fcntl

    fd = os.open(exp.root / "sequence.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _sequence(exp)
    finally:
        os.close(fd)


def _sequence(exp):
    if not review_valid(exp.root) or read(exp.root / "sequence.json")["status"] != "reserved":
        raise ComparisonError("comparison_sequence_not_admitted")
    for group in GROUPS:
        atomic(exp.root / "sequence.json", {"status": "preflight", "active_group": group})
        run_group(exp, group, preflight=True)
    for group in GROUPS:
        atomic(exp.root / "sequence.json", {"status": "running", "active_group": group})
        run_group(exp, group)
    atomic(exp.root / "sequence.json", {"status": "completed", "groups": list(GROUPS)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("sequence", "runtime", "host", "node-credential"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--group", choices=tuple(GROUPS))
    args = parser.parse_args()
    if sys.platform != "darwin" or (args.operation != "sequence" and args.group is None):
        raise SystemExit("comparison_worker_scope_invalid")
    os.umask(0o077)
    exp = Experiment(args.root)
    logging.basicConfig(filename=exp.root / "logs/worker.log", level=logging.INFO)
    try:
        if args.operation == "node-credential":
            if sys.stdout.isatty() or args.group not in {"B", "C"} or not review_valid(exp.root):
                raise ComparisonError("comparison_private_pipe_required")
            home = PRODUCTION_DATA if args.group == "B" else exp.root / "credentials/lite"
            result = flash_credential(home, {"op": "resolve", "ref": "RESEARCH_DSH_API_KEY"})
            print(json.dumps(result))
        elif args.operation == "sequence":
            sequence(exp)
        elif args.operation == "runtime":
            runtime(exp.root, args.group)
        else:
            host(exp.root, args.group)
    except Exception as exc:  # noqa: BLE001
        log.error("comparison_worker_failed type=%s", type(exc).__name__)
        if args.operation == "sequence":
            atomic(
                exp.root / "sequence.json",
                {
                    "status": "BLOCKED",
                    "error": (
                        str(exc) if isinstance(exc, ComparisonError) else "comparison_worker_failed"
                    ),
                },
            )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
