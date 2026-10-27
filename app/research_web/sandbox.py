"""Fail-closed macOS research runner; intentionally independent of application settings.

The trusted supervisor reads no .env or database configuration. Model code runs in
a separate Seatbelt process with no network, fork, Mach lookup, or host data access.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

LOGGER = logging.getLogger("research_web.sandbox")
MAX_CODE_BYTES = 65_536
WEEKLY_INPUT_POLICY = "weekly-frozen-inputs-v1"
SCENARIO_INPUT_POLICY = "scenario-frozen-inputs-v1"
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
        "OMP_NUM_THREADS": "4",
        "OPENBLAS_NUM_THREADS": "4",
        "VECLIB_MAXIMUM_THREADS": "4",
        "NUMEXPR_NUM_THREADS": "4",
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
    permitted_paths: tuple[str, ...] = (),
    input_policy: str | None = None,
    output_root: str | None = None,
) -> str:
    """Build a read-data allowlist and narrow mutation grants (metadata stays visible)."""
    read_paths = ["/System/Library", "/usr/lib", "/usr/bin", "/usr/share", "/bin", *read_roots]
    read_paths.extend(
        [
            str(session / "tmp"),
            str(session / output_root) if output_root else str(session / "outputs"),
        ]
    )
    read_paths.extend(permitted_paths)
    literals = [str(session / "inputs"), str(session / "resources")]
    for directory_name, excluded in [
        ("inputs", {"datasets", "scenarios"}),
        ("resources", {"capabilities", "skills"}),
    ]:
        if input_policy == SCENARIO_INPUT_POLICY:
            continue
        if directory_name == "inputs" and input_policy == WEEKLY_INPUT_POLICY:
            continue
        for entry in (session / directory_name).iterdir():
            if entry.name in excluded or entry.is_symlink():
                continue
            if entry.is_dir():
                read_paths.append(str(entry))
            elif entry.is_file():
                literals.append(str(entry))
    # SBPL strings do not decode JSON's ASCII \u escapes; retain UTF-8 paths
    # while preserving JSON's quote/backslash escaping and the same exact grants.
    file_filters = " ".join(
        f"(literal {json.dumps(path, ensure_ascii=False)})" for path in [*read_files, *literals]
    )
    read_filters = " ".join(
        f"(subpath {json.dumps(path, ensure_ascii=False)})" for path in read_paths
    )
    writes = " ".join(
        f"(subpath {json.dumps(str(session / name), ensure_ascii=False)})"
        for name in ((output_root, "tmp") if output_root else ("outputs", "tmp"))
    )
    protected_outputs = (
        ""
        if output_root
        else f'(deny file-write* (subpath {json.dumps(str(session / "outputs/scenario-results"))}))'
    )
    exec_filters = " ".join(
        f"(literal {json.dumps(path, ensure_ascii=False)})" for path in executables
    )
    return (
        "(version 1)(allow default)"
        "(deny file-read-data)"
        f'(allow file-read-data {read_filters} {file_filters} (literal "/") (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))'
        "(deny file-write*)"
        f'(allow file-write* {writes} (literal "/dev/null"))'
        + protected_outputs
        + "(deny network*)(deny process-fork)(deny mach-lookup)(deny mach-register)"
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


def _report_sdk_scope() -> tuple[str, tuple[str, ...]]:
    """Read only the packaged SDK's fixed files; never overwrite legacy session copies."""
    try:
        root = Path(__file__).resolve(strict=True).parent / "resources"
        if root.is_symlink() or not root.is_dir() or root.resolve(strict=True) != root:
            raise SandboxError("bundled report SDK directory is unsafe")
        fonts = root / "fonts"
        if fonts.is_symlink() or not fonts.is_dir():
            raise SandboxError("bundled report SDK fonts are unsafe")
        files = [str(root), str(fonts)]
        for name in (
            "research_helpers.py",
            "research_report.py",
            "research_report_plan.py",
            "research_report_calculations.py",
            "fonts/NotoSansSC-Regular.ttf",
        ):
            target = root / name
            info = target.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or target.resolve(strict=True) != target
            ):
                raise SandboxError("bundled report SDK file is unsafe")
            files.append(str(target))
        LOGGER.info("research_report_sdk_scope_verified files=5")
        return str(root), tuple(files)
    except SandboxError:
        LOGGER.warning("research_report_sdk_scope_rejected")
        raise
    except OSError as exc:
        LOGGER.warning("research_report_sdk_scope_unavailable")
        raise SandboxError("bundled report SDK is unavailable") from exc


def run_script(
    config: SandboxConfig,
    session: Path,
    code: str,
    *,
    read_paths=(),
    input_policy=None,
    file_bindings=None,
    output_root=None,
) -> ScriptResult:
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
        sdk_root, sdk_files = _report_sdk_scope()
        read_files = (*read_files, *sdk_files)
    except OSError as exc:
        raise SandboxError("research sandbox directories are unavailable") from exc
    if not isinstance(read_paths, (list, tuple)) or len(read_paths) > 320:
        raise SandboxError("invalid script resource scope")
    if input_policy not in (None, WEEKLY_INPUT_POLICY, SCENARIO_INPUT_POLICY):
        raise SandboxError("invalid script input policy")
    scenario = input_policy == SCENARIO_INPUT_POLICY
    if scenario:
        if (
            not isinstance(file_bindings, list)
            or len(file_bindings) != len(read_paths)
            or not read_paths
            or len(set(read_paths)) != len(read_paths)
            or not isinstance(output_root, str)
            or not re.fullmatch(r"outputs/scenario-results/[a-f0-9]{32}", output_root)
        ):
            raise SandboxError("invalid scenario resource scope")
        output = session / output_root
        if (
            output.resolve(strict=True) != output
            or not output.is_dir()
            or any(p.is_symlink() for p in (output, *output.parents))
        ):
            raise SandboxError("unsafe scenario output scope")
    elif file_bindings is not None or output_root is not None:
        raise SandboxError("unexpected scenario resource scope")
    weekly = input_policy == WEEKLY_INPUT_POLICY
    if weekly and (
        not read_paths
        or any(not isinstance(path, str) for path in read_paths)
        or len(set(read_paths)) != len(read_paths)
    ):
        raise SandboxError("invalid weekly input scope")
    permitted = []
    for file_index, relative in enumerate(read_paths):
        if scenario:
            if (
                not isinstance(relative, str)
                or not re.fullmatch(
                    r"(?:inputs/scenarios/(?:[a-f0-9]{32}|[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12})/(?:input|manifest)\.json|resources/capabilities/[a-z0-9_-]+/[1-9][0-9]*/[A-Za-z0-9_./-]+)",
                    relative,
                )
                or any(not part or part.startswith(".") for part in relative.split("/"))
            ):
                raise SandboxError("invalid scenario resource path")
            binding = file_bindings[file_index]
            if (
                not isinstance(binding, dict)
                or set(binding) != {"path", "sha256", "bytes", "device", "inode"}
                or binding["path"] != relative
            ):
                raise SandboxError("invalid scenario resource binding")
            target = session / relative
            try:
                for parent in (target, *target.parents):
                    if parent.is_symlink():
                        raise SandboxError("unsafe scenario resource scope")
                if target.resolve(strict=True) != target:
                    raise SandboxError("unsafe scenario resource scope")
                before = target.lstat()
                if (
                    not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                    or before.st_size > 64 * 1024 * 1024
                ):
                    raise SandboxError("unsafe scenario resource scope")
                with os.fdopen(os.open(target, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
                    opened = os.fstat(stream.fileno())
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                    after = os.fstat(stream.fileno())
                identities = lambda s: (
                    s.st_dev,
                    s.st_ino,
                    s.st_size,
                    s.st_mtime_ns,
                    s.st_ctime_ns,
                    s.st_nlink,
                )
                if (
                    identities(before) != identities(opened)
                    or identities(opened) != identities(after)
                    or identities(after) != identities(target.lstat())
                    or (before.st_dev, before.st_ino, before.st_size, digest)
                    != (binding["device"], binding["inode"], binding["bytes"], binding["sha256"])
                ):
                    raise SandboxError("scenario resource changed")
            except OSError as exc:
                raise SandboxError("unsafe scenario resource scope") from exc
            read_files = (*read_files, str(target))
            if relative.startswith("resources/capabilities/") and "/scripts/" in relative:
                # Importlib needs directory names, never a subtree read grant.
                # Only exact reviewed files above receive read-data authority.
                script_base = session / relative.split("/scripts/", 1)[0] / "scripts"
                parent = target.parent
                while parent.is_relative_to(script_base):
                    read_files = (*read_files, str(parent))
                    if parent == script_base:
                        break
                    parent = parent.parent
            continue
        if weekly:
            if (
                not isinstance(relative, str)
                or len(relative) > 512
                or not relative.startswith("inputs/report-workflow/")
                or re.search(r"[\\:\x00-\x1f\x7f]", relative)
                or any(not part or part.startswith(".") for part in relative.split("/"))
            ):
                raise SandboxError("invalid weekly input scope")
            target = session
            parts = relative.split("/")
            for index, part in enumerate(parts):
                target = target / part
                try:
                    info = target.lstat()
                except OSError as exc:
                    raise SandboxError("unsafe weekly input scope") from exc
                if stat.S_ISLNK(info.st_mode) or (
                    index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode)
                ):
                    raise SandboxError("unsafe weekly input scope")
                if index == len(parts) - 1 and (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or info.st_size > 32 * 1024 * 1024
                ):
                    raise SandboxError("unsafe weekly input scope")
            if target.resolve(strict=True) != target:
                raise SandboxError("unsafe weekly input scope")
            read_files = (*read_files, str(target))
            continue
        if not isinstance(relative, str) or not re.fullmatch(
            r"(?:resources/capabilities/[a-z0-9_-]+/[1-9][0-9]*|inputs/datasets/[0-9a-f-]{36})",
            relative,
        ):
            raise SandboxError("invalid script resource scope")
        target = session
        for part in Path(relative).parts:
            target = target / part
            if target.is_symlink() or not target.is_dir():
                raise SandboxError("unsafe script resource scope")
        if target.resolve(strict=True) != target:
            raise SandboxError("unsafe script resource scope")
        permitted.append(str(target))
    # -I -S prevents user startup/.pth execution. Only the configured venv's
    # site-packages, fixed packaged SDK literals and session resources use absolute
    # paths. The current SDK precedes legacy copies; no session file is replaced.
    # Only the four curated SDK files gain read-data, never their parent subtree.
    site_paths = [sdk_root, *[path for path in reads if path.endswith("/site-packages")]]
    site_paths.append(str(session / "resources"))
    bootstrap = (
        "import sys,resource,mimetypes;"
        f"resource.setrlimit(resource.RLIMIT_CPU,({math.ceil(config.timeout_seconds) + 1},)*2);"
        "resource.setrlimit(resource.RLIMIT_FSIZE,(16777216,)*2);"
        "resource.setrlimit(resource.RLIMIT_NOFILE,(64,)*2);"
        "mimetypes.knownfiles=[];mimetypes.init();"
        f"sys.path.extend({site_paths!r});"
        "import research_report;"
        f"research_report._SESSION_ROOT={str(session)!r};"
        "exec(compile(sys.stdin.buffer.read(),'<research-script>','exec'),{'__name__':'__main__'})"
    )
    command = [
        "/usr/bin/sandbox-exec",
        "-p",
        seatbelt_profile(
            session, reads, exec_paths, read_files, tuple(permitted), input_policy, output_root
        ),
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
        if not isinstance(request, dict) or set(request) not in (
            {"code"},
            {"code", "read_paths"},
            {"code", "read_paths", "input_policy"},
            {"code", "read_paths", "input_policy", "file_bindings", "output_root"},
        ):
            raise SandboxError("runner request accepts only code")
        result = run_script(
            config,
            Path(args.session),
            request["code"],
            read_paths=request.get("read_paths", ()),
            input_policy=request.get("input_policy"),
            file_bindings=request.get("file_bindings"),
            output_root=request.get("output_root"),
        )
    except (SandboxError, OSError, ValueError) as exc:
        LOGGER.warning("research_sandbox_request_rejected: %s", type(exc).__name__)
        result = ScriptResult("failed", error=str(exc))
    print(json.dumps(asdict(result), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
