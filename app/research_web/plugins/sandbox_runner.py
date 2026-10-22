"""macOS Seatbelt runner for reviewed /bin/sh builtin-only plugin hooks.

No host shell environment, fork, networking, Mach/Keychain, or host data reads.
Only explicitly approved current-session inputs/outputs are additional grants.
Other interpreters and platforms remain unavailable instead of falling back.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import tempfile
from pathlib import Path

from core.observability import get_logger

from .packages import PluginError

log = get_logger(__name__)
OUTPUT_LIMIT = 16384


def available():
    return sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file()


def _canonical(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise PluginError("plugin_hook_scope_invalid")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise PluginError("plugin_hook_scope_invalid")
    if path.resolve(strict=True) != path or not path.is_dir():
        raise PluginError("plugin_hook_scope_invalid")
    return path


def profile(work, script, read_paths=(), write_paths=()):
    quote = lambda value: json.dumps(str(value), ensure_ascii=False)
    reads = " ".join(
        f"(subpath {quote(path)})" for path in ("/System/Library", "/usr/lib", work, *read_paths)
    )
    writes = " ".join(f"(subpath {quote(path)})" for path in (work, *write_paths))
    return (
        "(version 1)(allow default)(deny network*)(deny mach-lookup)(deny mach-register)"
        "(deny process-fork)(deny process-info*)(deny ipc-posix*)(deny signal)"
        '(deny process-exec)(allow process-exec (literal "/bin/sh") (literal "/bin/bash"))'
        f'(deny file-read-data)(allow file-read-data {reads} (literal {quote(script)}) (literal "/") (literal "/bin/sh") (literal "/bin/bash") (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))'
        f'(deny file-write*)(allow file-write* {writes} (literal "/dev/null"))'
    )


async def run_script(source: bytes, *, timeout=2, read_paths=(), write_paths=(), cancel=None):
    """Bounded own process group; cancellation/failure always kills and reaps it."""
    if not available():
        raise PluginError("plugin_hook_os_sandbox_unavailable", 503)
    if not isinstance(source, bytes) or len(source) > 65536 or not 0.1 <= timeout <= 10:
        raise PluginError("plugin_hook_limits_invalid")
    reads = tuple(_canonical(path) for path in read_paths)
    writes = tuple(_canonical(path) for path in write_paths)
    process = None
    tasks = []
    with tempfile.TemporaryDirectory(prefix="rwb-plugin-hook-") as name:
        work = Path(name).resolve()
        home = work / "home"
        home.mkdir(mode=0o700)
        script = work / "hook.sh"
        script.write_bytes(source)
        script.chmod(0o400)

        async def capture(stream):
            output = bytearray()
            while chunk := await stream.read(4096):
                output.extend(chunk)
                if len(output) > OUTPUT_LIMIT:
                    raise PluginError("plugin_hook_output_limit", 409)
            return bytes(output)

        async def completion():
            stdout, stderr = await asyncio.gather(capture(process.stdout), capture(process.stderr))
            await process.wait()
            return stdout, stderr

        try:
            environment = {
                "PATH": "/nonexistent",
                "HOME": str(home),
                "TMPDIR": str(work),
                "LANG": "C",
                "ENV": "/dev/null",
                "BASH_ENV": "/dev/null",
            }
            if reads:
                environment["RWB_PLUGIN_INPUTS"] = str(reads[0])
            if writes:
                environment["RWB_PLUGIN_OUTPUTS"] = str(writes[0])
            process = await asyncio.create_subprocess_exec(
                "/usr/bin/sandbox-exec",
                "-p",
                profile(work, script, reads, writes),
                "/bin/sh",
                str(script),
                cwd=work,
                env=environment,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            operation = asyncio.create_task(completion())
            tasks.append(operation)
            if cancel is not None:
                cancellation = asyncio.create_task(cancel.wait())
                tasks.append(cancellation)
                done, _ = await asyncio.wait(
                    tasks, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
                )
                if cancellation in done:
                    raise PluginError("plugin_hook_cancelled", 409)
                if operation not in done:
                    raise PluginError("plugin_hook_timeout", 409)
                stdout, _stderr = operation.result()
            else:
                try:
                    stdout, _stderr = await asyncio.wait_for(operation, timeout)
                except TimeoutError as exc:
                    raise PluginError("plugin_hook_timeout", 409) from exc
            if process.returncode != 0:
                raise PluginError("plugin_hook_failed", 409)
            try:
                decision = json.loads(stdout)
                if (
                    not isinstance(decision, dict)
                    or set(decision) != {"decision"}
                    or decision["decision"] not in {"allow", "deny", "cancel"}
                ):
                    raise ValueError("invalid decision")
            except (ValueError, UnicodeError) as exc:
                raise PluginError("plugin_hook_decision_invalid", 409) from exc
            log.info("plugin_sandbox_hook_finished", decision=decision["decision"])
            return decision
        except OSError as exc:
            log.warning("plugin_sandbox_hook_start_failed", error_type=type(exc).__name__)
            raise PluginError("plugin_hook_os_sandbox_failed", 503) from exc
        finally:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await process.wait()
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
