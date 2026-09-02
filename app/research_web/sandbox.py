"""Fail-closed macOS research runner; intentionally independent of application settings.

The trusted supervisor reads no .env or database configuration. Model code runs in
a separate Seatbelt process with no network, fork, Mach lookup, or host data access.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import selectors
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

LOGGER = logging.getLogger("alphafoundry.research_web.sandbox")
MAX_CODE_BYTES = 65_536
_cancelled = False


class SandboxError(ValueError):
    """A deployment or request failed validation before code execution."""


@dataclass(frozen=True)
class SandboxConfig:
    research_root: Path
    python: Path
    timeout_seconds: float = 15
    max_output_bytes: int = 65_536


@dataclass(frozen=True)
class ScriptResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    error: str | None = None


def child_environment(session: Path) -> dict[str, str]:
    """An explicit environment, never a filtered copy of the host environment."""
    return {
        "PATH": "/usr/bin:/bin",
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
        "TMPDIR": str(session / "tmp"),
        "MPLCONFIGDIR": str(session / "tmp/matplotlib"),
        "XDG_CACHE_HOME": str(session / "tmp/cache"),
        "__CF_USER_TEXT_ENCODING": f"0x{os.getuid():X}:0x0:0x0",
    }


def validate_session(config: SandboxConfig, session: Path) -> Path:
    """Accept only a real UUID directory directly below this deployment's sessions."""
    root = Path(config.research_root).resolve(strict=True)
    candidate = Path(session)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise SandboxError("trusted session directory must be absolute and canonical")
    try:
        canonical = candidate.resolve(strict=True)
        UUID(candidate.name)
    except (OSError, ValueError) as exc:
        raise SandboxError("trusted session directory is unavailable") from exc
    expected_parent = root / "sessions"
    if candidate != canonical or canonical.parent != expected_parent:
        raise SandboxError("trusted session is outside the research session root")
    if expected_parent.is_symlink() or not canonical.is_dir():
        raise SandboxError("symlinked research session directories are forbidden")
    for name in ("inputs", "resources", "outputs", "tmp"):
        child = canonical / name
        if child.is_symlink():
            raise SandboxError("symlinked research capability directories are forbidden")
        child.mkdir(mode=0o700, exist_ok=True)
        if child.resolve(strict=True) != child or not child.is_dir():
            raise SandboxError("research capability directory is not canonical")
    return canonical


@lru_cache(maxsize=4)
def _runtime(python_path: str) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Inspect only the explicitly configured interpreter, with site startup disabled."""
    python = Path(python_path)
    if not python.is_absolute() or not python.is_file():
        raise SandboxError("an existing absolute Python executable is required")
    probe = "import json,sys; print(json.dumps([sys.base_prefix," "list(sys.version_info[:2])]))"
    try:
        result = subprocess.run(
            [str(python), "-I", "-S", "-B", "-c", probe],
            env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"},
            cwd="/",
            capture_output=True,
            timeout=5,
            check=True,
        )
        prefix, version = json.loads(result.stdout)
        base = Path(prefix).resolve(strict=True)
        executable = python.resolve(strict=True)
        if not executable.is_relative_to(base):
            raise SandboxError("Python executable is outside its declared runtime")
        sites = python.parent.parent / "lib" / f"python{version[0]}.{version[1]}" / "site-packages"
        site_roots = (str(sites.resolve(strict=True)),) if sites.is_dir() else ()
        # The Homebrew framework launcher execs this second exact executable.
        framework_app = base / "Resources/Python.app/Contents/MacOS/Python"
        executables = [str(executable)]
        if framework_app.is_file():
            executables.append(str(framework_app.resolve(strict=True)))
        # Homebrew's stdlib extensions can link sibling Cellar dylibs, e.g.
        # pyexpat -> expat. Grant only real linked files, never their parent
        # Cellar / opt / etc trees. The inputs are trusted runtime binaries.
        extensions = list(base.glob("lib/python*/lib-dynload/*.so"))
        linked_files: set[str] = set()
        if extensions:
            linkage = subprocess.run(
                ["/usr/bin/otool", "-L", *map(str, extensions)],
                env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"},
                capture_output=True,
                timeout=5,
                check=True,
                text=True,
            )
            for line in linkage.stdout.splitlines():
                dependency = line.strip().split(" (", 1)[0]
                if line.startswith("\t") and dependency.startswith("/opt/homebrew/"):
                    target = Path(dependency).resolve(strict=True)
                    if not target.is_file():
                        raise SandboxError("runtime library dependency is not a regular file")
                    linked_files.add(str(target))
        return (
            str(executable),
            (str(base), *site_roots),
            tuple(executables),
            tuple(sorted(linked_files)),
        )
    except (OSError, subprocess.SubprocessError, ValueError, TypeError) as exc:
        raise SandboxError("configured Python runtime could not be verified") from exc


def seatbelt_profile(
    session: Path,
    read_roots: tuple[str, ...],
    executables: tuple[str, ...],
    read_files: tuple[str, ...] = (),
) -> str:
    """Build a read-data allowlist and narrow mutation grants (metadata stays visible)."""
    read_paths = ["/System/Library", "/usr/lib", "/usr/bin", "/usr/share", "/bin", *read_roots]
    read_paths.extend(str(session / name) for name in ("inputs", "resources", "outputs", "tmp"))
    read_filters = " ".join(f"(subpath {json.dumps(path)})" for path in read_paths)
    writes = " ".join(f"(subpath {json.dumps(str(session / name))})" for name in ("outputs", "tmp"))
    exec_filters = " ".join(f"(literal {json.dumps(path)})" for path in executables)
    file_filters = " ".join(f"(literal {json.dumps(path)})" for path in read_files)
    return (
        "(version 1)(allow default)"
        "(deny file-read-data)"
        f'(allow file-read-data {read_filters} {file_filters} (literal "/") (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))'
        "(deny file-write*)"
        f'(allow file-write* {writes} (literal "/dev/null"))'
        "(deny network*)(deny process-fork)(deny mach-lookup)(deny mach-register)"
        "(deny ipc-posix*)(deny process-info*)(deny signal)"
        f"(deny process-exec)(allow process-exec {exec_filters})"
    )


def _kill_group(process: subprocess.Popen[bytes]) -> bool:
    """Stop every child; report incomplete kernel teardown rather than hanging forever."""
    if process.poll() is not None:
        return True
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=1)
        return True
    except subprocess.TimeoutExpired:
        LOGGER.error("research_sandbox_kernel_teardown_incomplete")
        return False


def run_script(config: SandboxConfig, session: Path, code: str) -> ScriptResult:
    """Execute bounded Python source under kernel-enforced research capabilities."""
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise SandboxError("research scripts require the verified native macOS sandbox")
    if not isinstance(code, str) or not code.strip() or len(code.encode()) > MAX_CODE_BYTES:
        raise SandboxError("code must be nonempty UTF-8 text of at most 65536 bytes")
    if not math.isfinite(config.timeout_seconds) or not 0 < config.timeout_seconds <= 60:
        raise SandboxError("timeout must be within (0, 60] seconds")
    if (
        not isinstance(config.max_output_bytes, int)
        or not 1 <= config.max_output_bytes <= 1_048_576
    ):
        raise SandboxError("output limit must be within [1, 1048576] bytes")
    try:
        session = validate_session(config, session)
        executable, reads, exec_paths, read_files = _runtime(str(config.python))
    except OSError as exc:
        raise SandboxError("research sandbox directories are unavailable") from exc
    # -I -S prevents user startup/.pth execution. Only the configured venv's
    # site-packages and this session's reviewed resources use absolute paths.
    # Relative imports require getcwd(), denied at the session root. Adding the
    # already-readable resource directory needs no new filesystem permission.
    site_paths = [path for path in reads if path.endswith("/site-packages")]
    site_paths.append(str(session / "resources"))
    bootstrap = (
        "import sys,resource,mimetypes;"
        f"resource.setrlimit(resource.RLIMIT_CPU,({math.ceil(config.timeout_seconds) + 1},)*2);"
        "resource.setrlimit(resource.RLIMIT_FSIZE,(16777216,)*2);"
        "resource.setrlimit(resource.RLIMIT_NOFILE,(64,)*2);"
        "mimetypes.knownfiles=[];mimetypes.init();"
        f"sys.path.extend({site_paths!r});"
        "exec(compile(sys.stdin.buffer.read(),'<research-script>','exec'),{'__name__':'__main__'})"
    )
    command = [
        "/usr/bin/sandbox-exec",
        "-p",
        seatbelt_profile(session, reads, exec_paths, read_files),
        executable,
        "-I",
        "-S",
        "-B",
        "-c",
        bootstrap,
    ]
    deadline = time.monotonic() + config.timeout_seconds
    captured: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    status = "completed"
    process: subprocess.Popen[bytes] | None = None
    teardown_complete = True
    LOGGER.info("research_sandbox_started")
    try:
        process = subprocess.Popen(
            command,
            cwd=session,
            env=child_environment(session),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        assert (
            process.stdin is not None and process.stdout is not None and process.stderr is not None
        )
        # Nonblocking source transfer is part of the same deadline; a kernel
        # startup failure must not trap the supervisor in a pipe write.
        source = memoryview(code.encode())
        os.set_blocking(process.stdin.fileno(), False)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                if _cancelled:
                    status = "cancelled"
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    status = "timed_out"
                    break
                for key, _ in selector.select(min(remaining, 0.05)):
                    if key.data == "stdin":
                        try:
                            source = source[os.write(key.fd, source[:8192]) :]
                        except BlockingIOError:
                            continue
                        if not source:
                            selector.unregister(process.stdin)
                            process.stdin.close()
                        continue
                    chunk = os.read(key.fd, 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    space = config.max_output_bytes - sum(map(len, captured.values()))
                    captured[key.data].extend(chunk[:space])
                    if len(chunk) > space:
                        status = "output_limit"
                        break
                if status != "completed":
                    break
            if status == "completed":
                # A script may close stdout/stderr while still executing. Do
                # not block for the full budget after the selector drains:
                # SIGTERM must still trigger child-group teardown promptly.
                while process.poll() is None:
                    if _cancelled:
                        status = "cancelled"
                        break
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        status = "timed_out"
                        break
                    try:
                        process.wait(timeout=min(0.05, remaining))
                    except subprocess.TimeoutExpired:
                        continue
                if _cancelled:
                    status = "cancelled"
    except (OSError, subprocess.SubprocessError) as exc:
        LOGGER.warning("research_sandbox_execution_failed: %s", type(exc).__name__)
        status = "failed"
    finally:
        if process is not None:
            teardown_complete = _kill_group(process)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
    exit_code = None if process is None else process.returncode
    if status == "completed" and exit_code != 0:
        status = "failed"
    error = None if status == "completed" else f"research script {status}"
    if not teardown_complete:
        status, error = "failed", "sandbox process teardown could not be confirmed"
    LOGGER.info("research_sandbox_finished status=%s exit_code=%s", status, exit_code)
    # Ignore incomplete UTF-8 suffixes so decoded output cannot expand beyond
    # the combined byte cap because replacement characters are multibyte.
    return ScriptResult(
        status,
        captured["stdout"].decode("utf-8", "ignore"),
        captured["stderr"].decode("utf-8", "ignore"),
        exit_code,
        error,
    )


def _request_cancel(_signum: int, _frame: Any) -> None:
    global _cancelled
    _cancelled = True


def main() -> int:
    """Single-request JSON supervisor used by the native DSH tool, not a server."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-root", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--max-output", type=int, default=65_536)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, _request_cancel)
    signal.signal(signal.SIGINT, _request_cancel)
    try:
        config = SandboxConfig(
            Path(args.research_root), Path(args.python), args.timeout, args.max_output
        )
        validate_session(config, Path(args.session))
        logs = config.research_root.resolve() / "logs"
        logs.mkdir(mode=0o700, exist_ok=True)
        if logs.is_symlink():
            raise SandboxError("sandbox log directory must not be a symlink")
        logging.basicConfig(
            filename=logs / "sandbox.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
        raw = sys.stdin.buffer.read(MAX_CODE_BYTES * 6 + 1025)
        if len(raw) > MAX_CODE_BYTES * 6 + 1024:
            raise SandboxError("runner request is too large")
        request = json.loads(raw)
        if not isinstance(request, dict) or set(request) != {"code"}:
            raise SandboxError("runner request accepts only code")
        result = run_script(config, Path(args.session), request["code"])
    except (SandboxError, OSError, ValueError) as exc:
        LOGGER.warning("research_sandbox_request_rejected: %s", type(exc).__name__)
        result = ScriptResult("failed", error=str(exc))
    print(json.dumps(asdict(result), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
