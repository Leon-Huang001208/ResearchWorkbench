"""Fail-closed MCP transport configuration without ambient process state."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_BLOCKED_ENV = {
    "BASH_ENV",
    "ENV",
    "HOME",
    "LANG",
    "LC_ALL",
    "LD_PRELOAD",
    "NODE_OPTIONS",
    "PATH",
    "PYTHONHOME",
    "PYTHONPATH",
    "SHELLOPTS",
    "TEMP",
    "TMP",
    "TMPDIR",
}
_MAX_ARGV = 256
_MAX_ARGUMENT_BYTES = 32 * 1024
_SHELL_EXECUTABLES = {
    "bash",
    "cmd",
    "cmd.exe",
    "env",
    "fish",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
    "sh",
    "zsh",
}


@dataclass(frozen=True)
class RemoteTarget:
    endpoint: str
    installation_id: str
    audience: str
    credential_slot: str = "oauth"


@dataclass(frozen=True)
class StdioTarget:
    argv: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str]
    environment_names: tuple[str, ...] = ()


def _canonical_endpoint(value: str) -> tuple[str, object]:
    if not isinstance(value, str) or len(value) > 2048 or any(ord(char) < 32 for char in value):
        raise ValueError("remote endpoint is invalid")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("remote endpoint is invalid")
    hostname = parsed.hostname.lower()
    is_explicit_loopback = hostname in {"127.0.0.1", "::1"}
    if parsed.scheme != "https" and not is_explicit_loopback:
        raise ValueError("remote endpoint requires HTTPS or explicit loopback")
    netloc = f"[{hostname}]" if ":" in hostname else hostname
    if parsed.port is not None:
        netloc += f":{parsed.port}"
    normalized = urlunsplit((parsed.scheme, netloc, parsed.path or "", "", ""))
    return normalized, parsed


def validate_remote_endpoint(value: str) -> str:
    """Allow HTTPS everywhere and HTTP only on literal loopback IPs."""

    return _canonical_endpoint(value)[0]


def validate_redirect(source: str, location: str) -> str:
    """Accept only same-origin redirects or same-host HTTP-to-HTTPS upgrades."""

    source_url = validate_remote_endpoint(source)
    destination_url = validate_remote_endpoint(urljoin(source_url, location))
    before = urlsplit(source_url)
    after = urlsplit(destination_url)
    same_origin = (before.scheme, before.hostname, before.port) == (
        after.scheme,
        after.hostname,
        after.port,
    )
    safe_upgrade = (
        before.scheme == "http" and after.scheme == "https" and before.hostname == after.hostname
    )
    if not (same_origin or safe_upgrade):
        raise ValueError("cross-origin redirect is not allowed")
    return destination_url


def minimal_stdio_environment(
    installation_root: Path,
    explicit: Mapping[str, str] | None = None,
    *,
    platform_name: str | None = None,
) -> dict[str, str]:
    """Build an environment from constants and explicit server values only."""

    root = Path(installation_root)
    if not root.is_absolute():
        root = root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("installation cwd is unsafe")
    explicit_values: dict[str, str] = {}
    for name, value in (explicit or {}).items():
        if (
            not isinstance(name, str)
            or not _ENV_NAME.fullmatch(name)
            or name in _BLOCKED_ENV
            or name.startswith("DYLD_")
            or not isinstance(value, str)
            or len(value.encode("utf-8")) > 16 * 1024
            or "\x00" in value
        ):
            raise ValueError("explicit stdio environment is invalid")
        explicit_values[name] = value
    resolved_root = root.resolve(strict=True)
    temporary = resolved_root / "tmp"
    if temporary.is_symlink():
        raise ValueError("stdio temporary directory is unsafe")
    temporary.mkdir(mode=0o700, exist_ok=True)
    if not temporary.is_dir() or temporary.is_symlink():
        raise ValueError("stdio temporary directory is unsafe")
    resolved_temporary = temporary.resolve(strict=True)
    try:
        resolved_temporary.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("stdio temporary directory escapes installation") from exc
    platform = platform_name or os.name
    environment = {
        "PATH": (
            r"C:\Windows\System32;C:\Windows"
            if platform == "nt"
            else "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        ),
        "LANG": "en_US.UTF-8",
        "HOME": str(resolved_root),
        "TMPDIR": str(resolved_temporary),
    }
    environment.update(explicit_values)
    return environment


def build_stdio_target(
    argv: Sequence[str],
    cwd: Path,
    explicit_environment: Mapping[str, str],
    *,
    platform_name: str | None = None,
) -> StdioTarget:
    """Validate a direct argv target; shell command strings are never accepted."""

    if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence):
        raise TypeError("stdio argv must be a sequence")
    arguments = tuple(argv)
    if not arguments or len(arguments) > _MAX_ARGV:
        raise ValueError("stdio argv is invalid")
    if any(
        not isinstance(item, str)
        or not item
        or "\x00" in item
        or len(item.encode("utf-8")) > _MAX_ARGUMENT_BYTES
        for item in arguments
    ):
        raise ValueError("stdio argv is invalid")
    working = Path(cwd)
    if not working.is_absolute():
        working = working.resolve()
    if not working.is_dir() or working.is_symlink():
        raise ValueError("stdio cwd is unsafe")
    command = Path(arguments[0])
    if command.name.lower() in _SHELL_EXECUTABLES:
        raise ValueError("stdio shell executable is forbidden")
    if (
        not command.is_absolute()
        or not command.is_file()
        or command.is_symlink()
        or not os.access(command, os.X_OK)
    ):
        raise ValueError("stdio argv executable is unsafe")
    resolved_working = working.resolve(strict=True)
    resolved_command = command.resolve(strict=True)
    try:
        resolved_command.relative_to(resolved_working)
    except ValueError as exc:
        raise ValueError("stdio argv executable escapes installation") from exc
    runtime_name = resolved_command.name.lower()
    inline_flags = {"-c"} if runtime_name.startswith("python") else set()
    if runtime_name in {"node", "node.exe"}:
        inline_flags.update({"-e", "--eval", "-p", "--print"})
    if any(argument in inline_flags for argument in arguments[1:]):
        raise ValueError("stdio inline execution is forbidden")
    if not isinstance(explicit_environment, Mapping):
        raise TypeError("explicit stdio environment is invalid")
    environment_names = tuple(sorted(explicit_environment))
    environment = minimal_stdio_environment(
        working,
        explicit_environment,
        platform_name=platform_name,
    )
    # The repository's bounded ``--follow-imports=skip`` mypy lane does not expand
    # dataclass-generated constructors, while runtime validation above owns the shape.
    return StdioTarget(  # type: ignore[call-arg]
        arguments, resolved_working, environment, environment_names
    )


def validate_stdio_target(
    target: StdioTarget,
    *,
    platform_name: str | None = None,
) -> StdioTarget:
    """Rebuild a stdio target from its explicit names and reject forged ambient state."""

    if not isinstance(target, StdioTarget) or not isinstance(target.env, Mapping):
        raise TypeError("stdio target is invalid")
    names = target.environment_names
    if (
        not isinstance(names, tuple)
        or len(set(names)) != len(names)
        or any(name not in target.env for name in names)
    ):
        raise ValueError("explicit stdio environment is invalid")
    explicit = {name: target.env[name] for name in names}
    rebuilt = build_stdio_target(
        target.argv,
        target.cwd,
        explicit,
        platform_name=platform_name,
    )
    if dict(rebuilt.env) != dict(target.env):
        raise ValueError("stdio environment contains implicit values")
    return rebuilt
