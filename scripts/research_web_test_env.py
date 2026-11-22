"""Prepare a project-shared test environment without touching resident environments."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = Path.home() / ".research-workbench" / "test-envs"
HEALTH_CODE = "import pytest, pytest_asyncio, pytest_cov, ruff, black, isort, mypy, yaml, pydantic, sqlalchemy"


class EnvError(Exception):
    """A safe, stable error code; child output remains in private logs."""


def fingerprint(project: Path) -> str:
    digest = hashlib.sha256()
    identity = [
        sys.implementation.name,
        platform.python_version(),
        sys.platform,
        platform.machine(),
    ]
    digest.update(json.dumps(identity).encode())
    for name in ("requirements/web.lock", "requirements/research-test.in"):
        digest.update(name.encode())
        digest.update((project / name).read_bytes())
    return digest.hexdigest()


def interpreter(env: Path) -> Path:
    return env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def health(env: Path, key: str) -> bool:
    try:
        metadata = json.loads((env / "owner.json").read_text())
        if metadata != {
            "project": "research-workbench",
            "lifecycle": "project-shared",
            "digest": key,
        }:
            return False
        if (env / "prepared").read_text() != key:
            return False
        result = subprocess.run(
            [str(interpreter(env)), "-I", "-c", HEALTH_CODE],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
        return result.returncode == 0
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def private_write(path: Path, content: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(content)


def run_logged(command: list[str], log: Path) -> None:
    child_env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("PYTHON", "PIP_"))
        and key.upper() not in {"VIRTUAL_ENV", "__PYVENV_LAUNCHER__"}
    }
    # pip's null config disables every config file, including global/site files;
    # --isolated alone only ignores user config and pip environment options.
    child_env["PIP_CONFIG_FILE"] = os.devnull
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=1800,
                check=False,
                env=child_env,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise EnvError("SUBPROCESS_FAILED") from exc
        if result.returncode:
            raise EnvError("INSTALL_FAILED")


def record(log: Path, event: str, code: str = "") -> None:
    descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "a") as stream:
        stream.write(json.dumps({"event": event, "code": code, "time": time.time()}) + "\n")


def inspect(project: Path, root: Path) -> dict:
    key = fingerprint(project)
    env = root / key
    return {
        "digest": key,
        "environment": str(env),
        "python": str(interpreter(env)),
        "healthy": health(env, key),
    }


def prepare(project: Path, root: Path) -> dict:
    status = inspect(project, root)
    if status["healthy"]:
        return {**status, "reused": True}
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = root / (status["digest"] + ".lock")
    token = uuid.uuid4().hex
    try:
        private_write(lock, json.dumps({"token": token, "pid": os.getpid()}))
    except FileExistsError as exc:
        raise EnvError("PREPARE_LOCKED") from exc
    try:
        # A concurrent prepare may have completed between inspect and lock acquisition.
        status = inspect(project, root)
        if status["healthy"]:
            return {**status, "reused": True}
        env = Path(status["environment"])
        if env.exists():
            raise EnvError("EXISTING_ENV_UNHEALTHY")
        logs = root / "logs"
        logs.mkdir(exist_ok=True, mode=0o700)
        prefix = logs / (time.strftime("%Y%m%dT%H%M%S") + "-" + token)
        event_log = Path(str(prefix) + "-events.jsonl")
        record(event_log, "prepare_started")
        # mkdir is exclusive: existing or broken environments are never replaced.
        env.mkdir(mode=0o700)
        private_write(
            env / "owner.json",
            json.dumps(
                {
                    "project": "research-workbench",
                    "lifecycle": "project-shared",
                    "digest": status["digest"],
                }
            ),
        )
        run_logged([sys.executable, "-I", "-m", "venv", str(env)], Path(str(prefix) + "-venv.log"))
        python = str(interpreter(env))
        run_logged(
            [
                python,
                "-I",
                "-m",
                "pip",
                "--isolated",
                "--disable-pip-version-check",
                "--no-input",
                "install",
                "--require-hashes",
                "--no-deps",
                "-r",
                str(project / "requirements/web.lock"),
            ],
            Path(str(prefix) + "-web.log"),
        )
        # Keep runtime pins while resolving test-tool dependencies. Hashes apply to
        # the locked runtime install above, not to the separately declared tools.
        constraints = env / "runtime-constraints.txt"
        lock_text = (project / "requirements/web.lock").read_text()
        pins = re.sub(r"--hash=sha256:[a-f0-9]+", "", lock_text).replace("\\\n", "")
        private_write(constraints, pins)
        run_logged(
            [
                python,
                "-I",
                "-m",
                "pip",
                "--isolated",
                "--disable-pip-version-check",
                "--no-input",
                "install",
                "-c",
                str(constraints),
                "-r",
                str(project / "requirements/research-test.in"),
            ],
            Path(str(prefix) + "-tools.log"),
        )
        private_write(env / "prepared", status["digest"])
        if not health(env, status["digest"]):
            raise EnvError("HEALTH_FAILED")
        record(event_log, "prepare_ready")
        return {**status, "healthy": True, "reused": False, "logs": str(prefix)}
    except (EnvError, OSError, ValueError) as exc:
        if "event_log" in locals():
            record(
                event_log,
                "prepare_failed",
                str(exc) if isinstance(exc, EnvError) else "ENV_IO_FAILED",
            )
        raise
    finally:
        # Only the lock created by this invocation is eligible for removal.
        if json.loads(lock.read_text()).get("token") == token:
            lock.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--check", action="store_true", help="Read-only environment health")
    actions.add_argument(
        "--prepare", action="store_true", help="Create/install only with prior approval"
    )
    parser.add_argument("--json", action="store_true", help="Emit structured status")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    try:
        result = prepare(PROJECT, args.root) if args.prepare else inspect(PROJECT, args.root)
        result["status"] = "ready" if result["healthy"] else "missing_or_unhealthy"
        code = 0 if result["healthy"] else 1
    except (EnvError, OSError, ValueError) as exc:
        result = {
            "status": "error",
            "error": str(exc) if isinstance(exc, EnvError) else "ENV_IO_FAILED",
        }
        code = 2
    print(
        json.dumps(result)
        if args.json
        else f"{result['status']}: {result.get('python', result.get('error'))}"
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
