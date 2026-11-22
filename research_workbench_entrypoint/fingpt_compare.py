"""Finite, loopback-only FinGPT experiment control plane; no production mutations."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import stat
import subprocess
import sys
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import time

log = logging.getLogger(__name__)
CURRENT = "0c3391cc27784d4b820a910124c121bf9faf4fbd"
ORIGINAL = "267a8b0b1e327a407595b35709055841edb53d75"
GROUPS = {"A": CURRENT, "B": ORIGINAL, "C": ORIGINAL}
FLASH = {"provider": "deepseek-official", "model": "deepseek-flash"}


class ComparisonError(RuntimeError):
    """Stable diagnostic, never a provider response or credential value."""


def private(path: Path) -> Path:
    path = path.absolute()
    if path.is_symlink() or path.resolve() != path:
        raise ComparisonError("comparison_root_unsafe")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ComparisonError("comparison_root_unsafe")
    return path


def atomic(path: Path, value) -> None:
    private(path.parent)
    tmp = path.parent / (".write-" + secrets.token_hex(12))
    descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        sync_directory(path.parent)
    finally:
        tmp.unlink(missing_ok=True)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read(path: Path) -> dict:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > 32_000_000:
        raise ComparisonError("comparison_record_unsafe")
    return json.loads(path.read_text())


def credential(home, request):
    from app.research_web.model_credentials import execute

    return execute(home, request)


class Experiment:
    def __init__(self, root, *, credential=credential):
        self.root = private(Path(root))
        self.credential = credential
        self.lock = threading.RLock()

    @classmethod
    def initialize(cls, root, *, credential=credential):
        candidate = Path(root).absolute()
        home = Path.home() / ".research-workbench"
        if candidate.is_relative_to(home) and not candidate.is_relative_to(home / "acceptance"):
            raise ComparisonError("comparison_production_root_denied")
        exp = cls(root, credential=credential)
        if not (exp.root / "experiment.json").exists() and any(exp.root.iterdir()):
            raise ComparisonError("comparison_unknown_root_contents")
        private(exp.root / "credentials/lite")
        private(exp.root / "logs")
        private(exp.root / "results")
        if not (exp.root / "experiment.json").exists():
            atomic(
                exp.root / "experiment.json",
                {
                    "version": 1,
                    "groups": GROUPS,
                    "as_of": "2026-10-16",
                    "limits": {"seconds": 900, "tools": 48, "searches": 6, "repairs": 1},
                    "lite": {"model": "", "base_url": "https://api.xiaomimimo.com/v1"},
                },
            )
        return exp

    def configure_lite(self, model, key):
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,120}", model):
            raise ComparisonError("comparison_model_invalid")
        if not isinstance(key, str) or not key or len(key) > 1024 or any(c in key for c in "\r\n"):
            raise ComparisonError("comparison_credential_invalid")
        with self.lock:
            if (self.root / "sequence.json").exists():
                raise ComparisonError("comparison_already_reserved")
            self.credential(
                self.root / "credentials/lite",
                {
                    "op": "set",
                    "ref": "RESEARCH_DSH_API_KEY",
                    "value": key,
                },
            )
            config = read(self.root / "experiment.json")
            config["lite"]["model"] = model
            atomic(self.root / "experiment.json", config)
            log.info("comparison_lite_configuration_saved")

    def status(self):
        config = read(self.root / "experiment.json")
        if (
            config.get("version") != 1
            or config.get("groups") != GROUPS
            or config.get("as_of") != "2026-10-16"
        ):
            raise ComparisonError("comparison_manifest_changed")
        ready = self.credential(
            self.root / "credentials/lite",
            {
                "op": "describe",
                "ref": "RESEARCH_DSH_API_KEY",
            },
        )
        return {
            "groups": GROUPS,
            "as_of": config["as_of"],
            "limits": config["limits"],
            "lite": {
                "model": config["lite"]["model"],
                "configured": bool(ready.get("configured") and config["lite"]["model"]),
            },
            "prepared": (self.root / "prepared.json").exists(),
            "reviewed": review_valid(self.root),
            "sequence": (
                read(self.root / "sequence.json")
                if (self.root / "sequence.json").exists()
                else None
            ),
        }

    def admit_sequence(self):
        with self.lock:
            status = self.status()
            if not status["prepared"] or not status["reviewed"] or not status["lite"]["configured"]:
                raise ComparisonError("comparison_not_ready")
            if (self.root / "sequence.json").exists():
                raise ComparisonError("comparison_already_reserved")
            value = {"status": "reserved", "created_at": time(), "groups": list(GROUPS)}
            try:
                fd = os.open(
                    self.root / "sequence.json",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                )
            except FileExistsError:
                raise ComparisonError("comparison_already_reserved") from None
            with os.fdopen(fd, "w") as stream:
                json.dump(value, stream)
                stream.flush()
                os.fsync(stream.fileno())
            sync_directory(self.root)
            return value

    def reserve(self, group):
        if group not in GROUPS:
            raise ComparisonError("comparison_group_invalid")
        path = self.root / "results" / (group + "-attempt.json")
        with self.lock:
            value = {
                "status": "submission_intent",
                "group": group,
                "idempotency_key": "compare-" + secrets.token_hex(24),
                "created_at": time(),
            }
            # Exclusive create survives process restart and competing HTTP requests.
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            except FileExistsError:
                raise ComparisonError("comparison_already_reserved") from None
            with os.fdopen(fd, "w") as stream:
                json.dump(value, stream)
                stream.flush()
                os.fsync(stream.fileno())
            sync_directory(path.parent)
            return value


def code_binding():
    base = Path(__file__).parent
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (
            base / "fingpt_compare.py",
            base / "fingpt_compare_worker.py",
            base / "fingpt_compare_node.mjs",
            base / "fingpt_compare.html",
        )
        if p.exists()
    }


def review_valid(root, scope="execution"):
    try:
        value = read(root / "review.json")
        return (
            value.get("status") == "APPROVE"
            and scope in value.get("scopes", [])
            and value.get("code_binding") == code_binding()
            and len(code_binding()) == 4
        )
    except (OSError, ValueError, ComparisonError):
        return False


def build_server(exp, port):
    if not 1024 <= port <= 65535:
        raise ComparisonError("comparison_port_invalid")
    origin = f"http://127.0.0.1:{port}"
    bootstrap = secrets.token_urlsafe(32)
    cookie = secrets.token_urlsafe(32)
    expires = time() + 8 * 3600
    loaded_binding = code_binding()
    atomic(exp.root / "browser-grant.json", {"origin": origin, "bootstrap": bootstrap})
    granted = False

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # No request path, submitted secret or arbitrary diagnostics in access logs.

        def output(self, status, body, content_type="application/json", *, set_cookie=False):
            raw = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; form-action 'self'",
            )
            if set_cookie:
                self.send_header(
                    "Set-Cookie",
                    f"comparison={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800",
                )
            self.end_headers()
            self.wfile.write(raw)

        def boundary(self):
            if (
                self.headers.get("Host") != f"127.0.0.1:{port}"
                or self.client_address[0] != "127.0.0.1"
            ):
                raise ComparisonError("comparison_host_denied")
            if self.headers.get("Origin") not in (None, origin):
                raise ComparisonError("comparison_origin_denied")
            if self.command == "POST" and self.headers.get("Origin") != origin:
                raise ComparisonError("comparison_origin_denied")
            if self.headers.get("Sec-Fetch-Site") == "cross-site" or time() > expires:
                raise ComparisonError("comparison_access_denied")

        def authenticated(self):
            cookies = SimpleCookie()
            cookies.load(self.headers.get("Cookie", ""))
            value = cookies.get("comparison")
            return bool(value and hmac.compare_digest(value.value, cookie))

        def do_GET(self):
            try:
                self.boundary()
                if self.path == "/":
                    return self.output(
                        200,
                        Path(__file__).with_suffix(".html").read_bytes(),
                        "text/html; charset=utf-8",
                    )
                if not self.authenticated():
                    return self.output(403, {"error": "comparison_access_denied"})
                if self.path == "/api/status":
                    return self.output(200, exp.status())
                self.output(404, {"error": "comparison_route_not_found"})
            except Exception as exc:  # noqa: BLE001
                log.warning("comparison_http_failed type=%s", type(exc).__name__)
                self.output(403, {"error": "comparison_access_denied"})

        def do_POST(self):
            nonlocal granted
            try:
                self.boundary()
                if self.path == "/bootstrap":
                    with exp.lock:
                        token = self.headers.get("X-Comparison-Bootstrap", "")
                        if granted or not hmac.compare_digest(token, bootstrap):
                            raise ComparisonError("comparison_access_denied")
                        granted = True
                    return self.output(200, {"authenticated": True}, set_cookie=True)
                if not self.authenticated():
                    raise ComparisonError("comparison_access_denied")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192 or self.headers.get("Content-Type") != "application/json":
                    raise ComparisonError("comparison_request_invalid")
                body = json.loads(self.rfile.read(length))
                if (
                    self.path == "/api/lite"
                    and isinstance(body, dict)
                    and set(body) == {"model", "api_key"}
                ):
                    exp.configure_lite(body["model"], body["api_key"])
                    return self.output(200, {"saved": True})
                if self.path == "/api/run" and body == {}:
                    if code_binding() != loaded_binding or not review_valid(exp.root):
                        raise ComparisonError("comparison_execution_review_required")
                    exp.admit_sequence()
                    with open(exp.root / "logs/sequence.log", "ab") as log_file:
                        subprocess.Popen(
                            [
                                sys.executable,
                                "-m",
                                "research_workbench_entrypoint.fingpt_compare_worker",
                                "sequence",
                                "--root",
                                str(exp.root),
                            ],
                            stdin=subprocess.DEVNULL,
                            stdout=log_file,
                            stderr=log_file,
                            start_new_session=True,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                        )
                    return self.output(202, {"status": "reserved"})
                raise ComparisonError("comparison_request_invalid")
            except ComparisonError as exc:
                self.output(409, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                log.warning("comparison_http_failed type=%s", type(exc).__name__)
                self.output(400, {"error": "comparison_request_invalid"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    atomic(exp.root / "server.json", {"pid": os.getpid(), "origin": origin})
    log.info("comparison_settings_started port=%s", port)
    return server


def serve(exp, port):
    import fcntl

    if not review_valid(exp.root, "settings"):
        raise ComparisonError("comparison_review_required")
    fd = os.open(exp.root / "server.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        server = build_server(exp, port)
        try:
            server.serve_forever()
        finally:
            server.server_close()
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "serve", "status"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--port", type=int, default=8097)
    args = parser.parse_args()
    if sys.platform != "darwin":
        print(json.dumps({"status": "BLOCKED", "error": "comparison_macos_required"}))
        raise SystemExit(1)
    os.umask(0o077)
    exp = Experiment.initialize(args.root)
    logging.basicConfig(filename=exp.root / "logs/control.log", level=logging.INFO)
    try:
        if args.operation == "prepare":
            from .fingpt_compare_worker import prepare

            if args.project is None:
                raise ComparisonError("comparison_project_required")
            result = prepare(exp, args.project)
        elif args.operation == "serve":
            serve(exp, args.port)
            return
        else:
            result = exp.status()
        print(json.dumps(result))
    except Exception as exc:  # noqa: BLE001
        log.error("comparison_failed type=%s", type(exc).__name__)
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "error": str(exc) if isinstance(exc, ComparisonError) else "comparison_failed",
                }
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    from research_workbench_entrypoint.fingpt_compare import main as dispatch

    dispatch()
