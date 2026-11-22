"""Native offline Python MCP confinement, independent of ordinary stdio targets.

No credentials, host site startup, network, child processes or installation writes.
The Host owns bounded bytes and exact-child shutdown; the official SDK owns MCP
protocol/session behavior. Scratch retires only after that child is reaped.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import anyio

from core.observability import get_logger

log = get_logger(__name__)
POLICY_VERSION = "macos-python-offline-v1"
MAX_STDIO_LINE_BYTES = 1024 * 1024
MAX_STDIO_TOTAL_BYTES = 8 * 1024 * 1024
MAX_CONNECTION_SECONDS = 35
_PYTHON = re.compile(r"python(?:3(?:\.\d+)?)?")
_MODULE = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*")
_BOOTSTRAP = (
    "import sys,runpy; p=sys.argv.pop(1); k=sys.argv.pop(1); "
    "e=sys.argv.pop(1); sys.path.insert(0,p); sys.argv[0]=e; "
    "runpy.run_module(e,run_name='__main__') if k=='module' else "
    "runpy.run_path(e,run_name='__main__')"
)


def available() -> bool:
    return sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file()


def validate_plan(plan) -> None:
    """Validate supported entrypoint shape before installation or secret reads."""
    if not available():
        raise ValueError("mcp_managed_local_process_isolation_required")
    get = (
        plan.get
        if isinstance(plan, dict)
        else lambda key, default=None: getattr(plan, key, default)
    )
    argv = get("argv", [])
    if (
        get("environment_names", [])
        or not isinstance(argv, (list, tuple))
        or not 2 <= len(argv) <= 256
        or any(not isinstance(a, str) or not a or "\0" in a or len(a) > 32768 for a in argv)
        or not _PYTHON.fullmatch(Path(argv[0]).name)
    ):
        raise ValueError("mcp_managed_offline_python_required")
    if get("package_type") == "pypi":
        if len(argv) < 3 or argv[1] != "-m" or not _MODULE.fullmatch(argv[2]):
            raise ValueError("mcp_managed_offline_python_required")
    elif get("package_type") == "mcpb":
        script = Path(argv[1])
        if script.is_absolute() or ".." in script.parts or script.suffix != ".py":
            raise ValueError("mcp_managed_offline_python_required")
    else:
        raise ValueError("mcp_managed_offline_python_required")


def _quote(path) -> str:
    return json.dumps(str(path), ensure_ascii=False)


def profile(package: Path, scratch: Path, runtime) -> str:
    _python, roots, executables, libraries = runtime
    base = Path(roots[0])
    # Never grant the host's global or user site-packages even when installed
    # underneath the configured interpreter. -I -S also disables .pth/startup.
    excludes = [p for p in base.glob("lib/python*/site-packages")]
    runtime_filter = f"(subpath {_quote(base)})"
    if excludes:
        runtime_filter = (
            "(require-all "
            + runtime_filter
            + " "
            + " ".join(f"(require-not (subpath {_quote(p)}))" for p in excludes)
            + ")"
        )
    reads = " ".join(
        f"(subpath {_quote(p)})" for p in ("/System/Library", "/usr/lib", package, scratch)
    )
    files = " ".join(f"(literal {_quote(p)})" for p in libraries)
    execute = " ".join(f"(literal {_quote(p)})" for p in executables)
    return (
        "(version 1)(allow default)(deny file-read-data)"
        f"(allow file-read-data {runtime_filter} {reads} {files}"
        ' (literal "/") (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))'
        "(deny file-write*)"
        f'(allow file-write* (subpath {_quote(scratch)}) (literal "/dev/null"))'
        "(deny network*)(deny process-fork)(deny mach-lookup)(deny mach-register)"
        "(deny ipc-posix*)(deny process-info*)(deny signal)"
        f"(deny process-exec)(allow process-exec {execute})"
    )


def policy_digest() -> str:
    """Changing policy source requires explicit permission review of old packages."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _runtime_identity():
    from ..sandbox import SandboxError, _runtime

    try:
        # Do not inherit the general research runner's host site-package grants.
        runtime = _runtime(str(Path(sys.executable).resolve(strict=True)))
        digest = hashlib.sha256()
        base = Path(runtime[1][0])
        paths = set(runtime[2]) | set(runtime[3])
        for path in base.rglob("*"):
            if "site-packages" in path.parts:
                continue
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(base):
                raise ValueError("mcp_managed_runtime_alias_unsafe")
            if path.is_symlink():
                digest.update(
                    path.relative_to(base).as_posix().encode()
                    + b"\0link\0"
                    + os.readlink(path).encode()
                )
            if path.is_file():
                paths.add(str(resolved))
        total = 0
        for name in sorted(paths):
            path = Path(name)
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("mcp_managed_runtime_file_unsafe")
            total += info.st_size
            if total > 512 * 1024 * 1024:
                raise ValueError("mcp_managed_runtime_limit")
            digest.update(name.encode() + b"\0")
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        return runtime, digest.hexdigest()
    except (OSError, SandboxError) as exc:
        raise ValueError("mcp_managed_runtime_unavailable") from exc


@dataclass(frozen=True)
class TrustedManagedStdioTarget:
    package: Path
    argv: tuple[str, ...]
    package_type: str
    policy_sha256: str
    runtime_sha256: str
    package_sha256: str


def build_managed_target(package: Path, argv, package_type: str) -> TrustedManagedStdioTarget:
    from ..plugins.mcp_policy import artifact_digest
    from ..plugins.packages import PluginError

    validate_plan({"argv": argv, "package_type": package_type})
    try:
        package = Path(package)
        if package.is_symlink() or package.resolve(strict=True) != package:
            raise ValueError("mcp_managed_package_unsafe")
        if package_type == "mcpb":
            script = package / argv[1]
            if not script.resolve(strict=True).is_relative_to(package) or not script.is_file():
                raise ValueError("mcp_managed_package_unsafe")
        package_hash = artifact_digest(package)
        _, runtime_hash = _runtime_identity()
        # Match transport.py: the bounded follow-imports=skip lane does not
        # expand dataclass-generated constructors; runtime shape is checked above.
        return TrustedManagedStdioTarget(  # type: ignore[call-arg]
            package, tuple(argv), package_type, policy_digest(), runtime_hash, package_hash
        )
    except (OSError, PluginError) as exc:
        raise ValueError("mcp_managed_package_unsafe") from exc


def validate_managed_target(target: TrustedManagedStdioTarget):
    if not isinstance(target, TrustedManagedStdioTarget):
        raise TypeError("mcp_managed_target_invalid")
    rebuilt = build_managed_target(target.package, target.argv, target.package_type)
    if target != rebuilt:
        raise ValueError("mcp_managed_target_changed")
    return rebuilt


async def _stop_owned_process(process, lifecycle) -> None:
    """Reap our exact child before scratch or admission capacity can retire."""
    with anyio.CancelScope(shield=True):
        if process.stdin is not None:
            with anyio.move_on_after(0.25):
                try:
                    await process.stdin.aclose()
                except (OSError, anyio.BrokenResourceError, anyio.ClosedResourceError):
                    pass
        with anyio.move_on_after(0.25):
            await process.wait()
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            with anyio.move_on_after(1.0):
                await process.wait()
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        with anyio.move_on_after(2.0) as reap:
            await process.wait()
        if reap.cancelled_caught or process.returncode is None:
            log.error("mcp_managed_process_reap_failed")
            raise ValueError("mcp_managed_process_reap_failed")
        lifecycle["reaped"] = True
        with anyio.move_on_after(0.5) as close:
            await process.aclose()
        if close.cancelled_caught:
            raise ValueError("mcp_managed_process_close_failed")
        lifecycle["closed"] = True


async def _await_owned_task(task):
    """Defer repeated native Task.cancel until owned birth/cleanup finishes."""
    cancelled = False
    with anyio.CancelScope(shield=True):
        while True:
            try:
                return await asyncio.shield(task), cancelled
            except asyncio.CancelledError:
                if task.done():
                    # An independently cancelled owned task is unknown, not a
                    # completed birth/reap. Its caller retains the fence.
                    return task.result(), True
                cancelled = True


async def _reap_owned_process(process, lifecycle):
    cleanup = asyncio.create_task(_stop_owned_process(process, lifecycle))
    _, cancelled = await _await_owned_task(cleanup)
    return cancelled


@asynccontextmanager
async def _bounded_stdio(argv, scratch, environment, lifecycle):
    """Own bytes/process only; official SDK still owns all MCP protocol/session work."""
    import mcp_types
    from mcp.shared.message import SessionMessage

    lifecycle["spawned"] = True
    launch = asyncio.create_task(
        anyio.open_process(
            argv,
            cwd=str(scratch),
            env=environment,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    )
    process, cancelled = await _await_owned_task(launch)
    if cancelled:
        # A cancellation during birth must still retrieve and reap this exact
        # child; an interrupted/unknown birth retains the admission fence.
        await _reap_owned_process(process, lifecycle)
        raise asyncio.CancelledError
    read_sender, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_receiver = anyio.create_memory_object_stream(0)

    async def reader():
        buffered = bytearray()
        consumed = 0
        try:
            async with read_sender:
                while True:
                    chunk = await process.stdout.receive(65536)
                    consumed += len(chunk)
                    if consumed > MAX_STDIO_TOTAL_BYTES:
                        raise ValueError("mcp_managed_output_limit")
                    buffered.extend(chunk)
                    while (newline := buffered.find(b"\n")) >= 0:
                        if newline > MAX_STDIO_LINE_BYTES:
                            raise ValueError("mcp_managed_output_limit")
                        line = bytes(buffered[:newline])
                        del buffered[: newline + 1]
                        try:
                            message = mcp_types.jsonrpc_message_adapter.validate_json(
                                line, by_name=False
                            )
                        except ValueError:
                            raise ValueError("mcp_managed_output_invalid") from None
                        await read_sender.send(SessionMessage(message))
                    if len(buffered) > MAX_STDIO_LINE_BYTES:
                        raise ValueError("mcp_managed_output_limit")
        except anyio.EndOfStream:
            return
        except (OSError, anyio.BrokenResourceError, anyio.ClosedResourceError):
            return
        except ValueError as exc:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            # Re-open no channels: the stable error is propagated via the task
            # group, while finally below completes exact-child teardown.
            raise ValueError(str(exc)) from None

    async def writer():
        try:
            async with write_receiver:
                async for message in write_receiver:
                    raw = message.message.model_dump_json(
                        by_alias=True, exclude_unset=True
                    ).encode()
                    if len(raw) > MAX_STDIO_LINE_BYTES:
                        raise ValueError("mcp_managed_request_limit")
                    await process.stdin.send(raw + b"\n")
        except (OSError, anyio.BrokenResourceError, anyio.ClosedResourceError):
            await read_sender.aclose()

    try:
        async with anyio.create_task_group() as group:
            group.start_soon(reader)
            group.start_soon(writer)
            try:
                yield read_stream, write_stream
            finally:
                cancelled = await _reap_owned_process(process, lifecycle)
                group.cancel_scope.cancel()
                if cancelled:
                    raise asyncio.CancelledError
    finally:
        # Errors before/during task-group entry and repeated cleanup are safe.
        if not lifecycle.get("closed"):
            await _reap_owned_process(process, lifecycle)
        with anyio.CancelScope(shield=True):
            await read_stream.aclose()
            await write_stream.aclose()
            await read_sender.aclose()
            await write_receiver.aclose()


@asynccontextmanager
async def official_transport(target: TrustedManagedStdioTarget, on_cleanup_blocked=None):
    target = validate_managed_target(target)
    runtime, runtime_hash = _runtime_identity()
    if runtime_hash != target.runtime_sha256:
        raise ValueError("mcp_managed_target_changed")
    scratch = Path(tempfile.mkdtemp(prefix="rwb-mcp-offline-", dir="/private/tmp"))
    identity = scratch.stat()
    lifecycle = {"spawned": False, "reaped": False, "closed": False}
    try:
        environment = {
            "HOME": str(scratch),
            "TMPDIR": str(scratch),
            "TMP": str(scratch),
            "TEMP": str(scratch),
            "XDG_CACHE_HOME": str(scratch),
            "XDG_CONFIG_HOME": str(scratch),
            "XDG_DATA_HOME": str(scratch),
            "PATH": "/usr/bin:/bin",
            "LOGNAME": "mcp",
            "USER": "mcp",
            "SHELL": "/usr/bin/false",
            "TERM": "dumb",
            "LANG": "en_US.UTF-8",
        }
        if target.package_type == "pypi":
            kind, entry, arguments = "module", target.argv[2], target.argv[3:]
        else:
            kind, entry, arguments = "script", str(target.package / target.argv[1]), target.argv[2:]
        argv = [
            "/usr/bin/sandbox-exec",
            "-p",
            profile(target.package, scratch, runtime),
            runtime[0],
            "-I",
            "-S",
            "-B",
            "-c",
            _BOOTSTRAP,
            str(target.package),
            kind,
            entry,
            *arguments,
        ]
        log.info("mcp_managed_sandbox_started", policy=POLICY_VERSION)
        with anyio.fail_after(MAX_CONNECTION_SECONDS):
            async with _bounded_stdio(argv, scratch, environment, lifecycle) as streams:
                yield streams
    finally:
        try:
            if lifecycle["spawned"] and (not lifecycle["reaped"] or not lifecycle["closed"]):
                log.error("mcp_managed_scratch_retained_unreaped_process")
                raise ValueError("mcp_managed_scratch_retained_unreaped_process")
            current = scratch.lstat()
            if scratch.is_symlink() or (identity.st_dev, identity.st_ino) != (
                current.st_dev,
                current.st_ino,
            ):
                log.error("mcp_managed_scratch_identity_changed")
                raise ValueError("mcp_managed_scratch_identity_changed")
            shutil.rmtree(scratch)
        except BaseException:
            if on_cleanup_blocked is not None:
                on_cleanup_blocked()
            log.error("mcp_managed_scratch_retirement_failed")
            raise
        log.info("mcp_managed_sandbox_retired", policy=POLICY_VERSION)
