#!/usr/bin/env python3
"""Create, verify, and diagnose an isolated cross-platform Research Workbench Web environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict, cast
from urllib.parse import urlsplit
from uuid import uuid4

# The public script must import checkout facts before dependencies are installed.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).absolute().parents[1]))

from app.research_web import RUNTIME_CONTRACT

# port_busy remains an explicit re-export for existing adapters and test doubles.
from research_workbench_entrypoint.docker_runtime import (
    ControlError,
)
from research_workbench_entrypoint.docker_runtime import DockerRuntime as _DockerRuntimeController
from research_workbench_entrypoint.docker_runtime import port_busy as port_busy  # noqa: PLC0414
from research_workbench_entrypoint.runtime_mode import (
    RuntimeModeStore,
    _atomic_write_posix,
    _leaf_identity_at,
    _private_posix_parent,
    _read_bytes,
    _same_identity,
)
from research_workbench_entrypoint.web_contract import (
    environment_marker_valid,
    node_version_issue,
)

ENVIRONMENT_MARKER = ".rwb-web-environment.json"
CJPY_VERSION = RUNTIME_CONTRACT.cjpy_version
CJPY_WHEEL = f"cjpy-{CJPY_VERSION}-py3-none-any.whl"
CJPY_SHA256 = RUNTIME_CONTRACT.cjpy_sha256
DSH_REMOTE = RUNTIME_CONTRACT.dsh_remote
DSH_COMMIT = RUNTIME_CONTRACT.dsh_commit
DSH_PNPM = RUNTIME_CONTRACT.dsh_pnpm
DSH_CLOSURE_FILES = RUNTIME_CONTRACT.dsh_closure_files
DSH_MARKER = ".rwb-dsh-source.json"
COREPACK_VERSION = "0.34.0"
PYPI_INDEX = "https://pypi.org/simple"
NPM_REGISTRY = "https://registry.npmjs.org"


def _command_version(path: Path) -> str:
    completed = subprocess.run(
        [str(path), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        raise RuntimeError("version_command_failed")
    return (completed.stdout or completed.stderr).strip()


class SetupWebInstaller:
    """Public bootstrap API used by the shell wrappers and contract tests."""

    def __init__(
        self,
        *,
        project_root: Path,
        data_home: Path | None = None,
        python_executable: Path | None = None,
        node_executable: Path | None = None,
        git_executable: Path | None = None,
        version_reader: Callable[[Path], str] | None = None,
        node_version_reader: Callable[[Path], str] | None = None,
        corepack_executable: Path | None = None,
        npm_executable: Path | None = None,
        platform_name: str | None = None,
        web_port: int | None = None,
        runtime_port: int | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.web_port = web_port
        self.runtime_port = runtime_port
        configured_data_home = Path(data_home or Path.home() / ".research-workbench").expanduser()
        self.data_home = Path(os.path.abspath(configured_data_home))
        self.venv = self.project_root / ".venv"
        self.python_executable = Path(python_executable or sys.executable).resolve()
        configured_node = os.environ.get("RESEARCH_NODE_BINARY")
        codex_bundled_node = (
            Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
        )
        discovered_node = (
            node_executable
            or configured_node
            or (
                codex_bundled_node
                if codex_bundled_node.is_file() and os.access(codex_bundled_node, os.X_OK)
                else None
            )
            or shutil.which("node")
            or "node"
        )
        self.node_executable = Path(discovered_node).expanduser().resolve()
        self.git_executable = Path(git_executable or shutil.which("git") or "git").resolve()
        discovered_corepack = corepack_executable or shutil.which("corepack")
        self.corepack_executable = (
            Path(discovered_corepack).resolve() if discovered_corepack else None
        )
        discovered_npm = npm_executable or shutil.which("npm")
        self.npm_executable = Path(discovered_npm).resolve() if discovered_npm else None
        self.version_reader = version_reader or _command_version
        self.node_version_reader = node_version_reader or _command_version
        self.platform_name = platform_name or os.name
        self.log = logging.getLogger("research_workbench.setup_web")
        self.dsh_root = self.data_home / "runtime" / "dsh"
        self.dsh_source = self.dsh_root / DSH_COMMIT
        self.install_root = self.data_home / "install"
        self.install_manifest = self.install_root / "manifest.json"

    def _git_worktree_options(self) -> list[str]:
        """Keep clone, checkout, and status semantics aligned across hosts."""
        options = ["-c", "core.longpaths=true"]
        if self.platform_name == "nt":
            options.extend(["-c", "core.symlinks=false"])
        options.extend(["-c", "core.autocrlf=false", "-c", "core.eol=lf"])
        return options

    @staticmethod
    def _python_supported(value: str) -> bool:
        match = re.search(r"(?<!\d)(\d+)\.(\d+)", value)
        return bool(
            match
            and (int(match.group(1)), int(match.group(2)))
            == (RUNTIME_CONTRACT.python_major, RUNTIME_CONTRACT.python_minor)
        )

    @staticmethod
    def _node_supported(value: str) -> bool:
        return node_version_issue(value) is None

    def check(self) -> dict[str, object]:
        """Inspect prerequisites and ownership without mutating the checkout."""
        issues: list[str] = []
        environment_exists = self.venv.exists()
        environment_owned = self._owned_environment(self.venv) if environment_exists else False
        if self.data_home.exists() and (
            self.data_home.is_symlink()
            or self._is_reparse_point(self.data_home)
            or not self.data_home.is_dir()
        ):
            issues.append("data_home_unsafe")
        if environment_exists and not environment_owned:
            issues.append("unowned_virtual_environment")
        for code, path in (
            ("python_missing", self.python_executable),
            ("node_missing", self.node_executable),
            ("git_missing", self.git_executable),
        ):
            if not path.is_file():
                issues.append(code)
        if "python_missing" not in issues:
            try:
                if not self._python_supported(self.version_reader(self.python_executable)):
                    issues.append("python_version_unsupported")
            except (OSError, RuntimeError, subprocess.SubprocessError, UnicodeError):
                issues.append("python_version_unreadable")
        if "node_missing" not in issues:
            try:
                if not self._node_supported(self.node_version_reader(self.node_executable)):
                    issues.append("node_version_unsupported")
            except (OSError, RuntimeError, subprocess.SubprocessError, UnicodeError):
                issues.append("node_version_unreadable")
        if issues:
            self.log.warning("setup_web_check_failed", extra={"issue_count": len(issues)})
        return {
            "schema_version": 1,
            "ok": not issues,
            "issues": issues,
            "environment_owned": environment_owned,
        }

    @staticmethod
    def _is_reparse_point(path: Path) -> bool:
        try:
            identity = path.lstat()
        except OSError:
            return False
        flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return bool(getattr(identity, "st_file_attributes", 0) & flag)

    @classmethod
    def _reject_alias(cls, path: Path, code: str) -> None:
        if path.is_symlink() or cls._is_reparse_point(path):
            raise RuntimeError(code)

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
        try:
            temporary.write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.chmod(temporary, 0o600)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def _prepare_data_home(self) -> None:
        """Reuse the existing outer-home boundary before acquiring a lease."""
        self.data_home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._reject_alias(self.data_home, "runtime_build_lock_unsafe")
        data_home_identity = self.data_home.lstat()
        if not stat.S_ISDIR(data_home_identity.st_mode):
            raise RuntimeError("runtime_build_lock_unsafe")
        if self.platform_name != "nt":
            if data_home_identity.st_uid != os.getuid():
                raise RuntimeError("runtime_build_lock_unsafe")
            os.chmod(self.data_home, 0o700)

    def _runtime_lock_directory(self) -> int | Path:
        """Open the product runtime directory without following aliases."""
        self._prepare_data_home()
        if self.platform_name == "nt":
            trusted_root = self.data_home.resolve(strict=True)
            directory = self.data_home
            for component in ("research-web", "runtime"):
                directory = directory / component
                directory.mkdir(mode=0o700, exist_ok=True)
                identity = directory.lstat()
                if (
                    self._is_reparse_point(directory)
                    or directory.is_symlink()
                    or not stat.S_ISDIR(identity.st_mode)
                    or not directory.resolve(strict=True).is_relative_to(trusted_root)
                ):
                    raise RuntimeError("runtime_build_lock_unsafe")
            return directory

        descriptor = None
        try:
            descriptor = os.open(self.data_home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            for component in ("research-web", "runtime"):
                try:
                    os.mkdir(component, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                child = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                identity = os.fstat(child)
                if not stat.S_ISDIR(identity.st_mode):
                    os.close(child)
                    raise RuntimeError("runtime_build_lock_unsafe")
                os.close(descriptor)
                descriptor = child
            return descriptor
        except (OSError, RuntimeError) as exc:
            if descriptor is not None:
                os.close(descriptor)
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError("runtime_build_lock_unsafe") from exc

    def _write_runtime_lock_json(self, value: dict[str, object]) -> None:
        directory = self._runtime_lock_directory()
        name = "build-lock.json"
        if isinstance(directory, Path):
            destination = directory / name
            try:
                if destination.exists() or destination.is_symlink():
                    identity = destination.lstat()
                    if (
                        self._is_reparse_point(destination)
                        or destination.is_symlink()
                        or not stat.S_ISREG(identity.st_mode)
                        or identity.st_nlink != 1
                    ):
                        raise RuntimeError("runtime_build_lock_unsafe")
                self._atomic_json(destination, value)
                return
            except OSError as exc:
                raise RuntimeError("runtime_build_lock_unsafe") from exc

        temporary = f".build-lock.{uuid4().hex}.tmp"
        handle = None
        try:
            try:
                existing = os.stat(name, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                existing = None
            if existing is not None and (
                not stat.S_ISREG(existing.st_mode)
                or existing.st_nlink != 1
                or bool(existing.st_mode & 0o077)
            ):
                raise RuntimeError("runtime_build_lock_unsafe")
            handle = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                handle = None
                identity = os.fstat(stream.fileno())
                if not stat.S_ISREG(identity.st_mode) or identity.st_nlink != 1:
                    raise RuntimeError("runtime_build_lock_unsafe")
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        except OSError as exc:
            raise RuntimeError("runtime_build_lock_unsafe") from exc
        finally:
            if handle is not None:
                os.close(handle)
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
            os.close(directory)

    def _subprocess_environment(self) -> dict[str, str]:
        """Return a minimal build environment without application credentials."""
        allowed = {
            "PATH",
            "HOME",
            "USERPROFILE",
            "LOCALAPPDATA",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "TMPDIR",
            "TMP",
            "TEMP",
            "LANG",
            "LC_ALL",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "no_proxy",
        }
        environment = {key: value for key, value in os.environ.items() if key in allowed}
        environment.update(
            {
                "GIT_TERMINAL_PROMPT": "0",
                "COREPACK_HOME": str(self.data_home / "runtime" / "corepack"),
                "npm_config_cache": str(self.data_home / "runtime" / "npm-cache"),
                "npm_config_registry": NPM_REGISTRY,
                "npm_config_userconfig": str(self.data_home / "runtime" / "npm-empty-user-config"),
                "NPM_CONFIG_AUDIT": "false",
                "NPM_CONFIG_FUND": "false",
                "NO_UPDATE_NOTIFIER": "1",
            }
        )
        return environment

    def _node_subprocess_environment(self) -> dict[str, str]:
        """Return a credential-free environment with only Node-compatible proxies."""
        environment = self._subprocess_environment()
        node_directory = str(self.node_executable.parent)
        existing_path = environment.get("PATH", "")
        environment["PATH"] = (
            f"{node_directory}{os.pathsep}{existing_path}" if existing_path else node_directory
        )
        if self.platform_name == "nt":
            for key in (
                "PSMODULEPATH",
                "PROGRAMFILES",
                "PROGRAMFILES(X86)",
                "PROGRAMDATA",
                "SYSTEMDRIVE",
                "COMMONPROGRAMFILES",
                "COMMONPROGRAMFILES(X86)",
            ):
                value = os.environ.get(key)
                if value:
                    environment[key] = value
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            value = environment.get(key)
            if value and urlsplit(value).scheme.lower() not in {"http", "https"}:
                environment.pop(key, None)
        cpp_include = self._macos_cpp_include()
        if cpp_include is not None:
            environment["CPLUS_INCLUDE_PATH"] = str(cpp_include)
        return environment

    def _python_subprocess_environment(self) -> dict[str, str]:
        """Return a credential-free environment with only pip-compatible proxies."""
        environment = self._subprocess_environment()
        filtered = 0
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            value = environment.get(key)
            if value and urlsplit(value).scheme.lower() not in {"http", "https"}:
                environment.pop(key, None)
                filtered += 1
        if filtered:
            self.log.warning(
                "setup_web_python_proxy_protocol_filtered",
                extra={"proxy_count": filtered},
            )
        return environment

    @staticmethod
    def _macos_cpp_include() -> Path | None:
        """Find the active macOS SDK libc++ headers for native Node modules."""
        if sys.platform != "darwin":
            return None
        xcrun = shutil.which("xcrun")
        if not xcrun:
            return None
        try:
            completed = subprocess.run(
                [xcrun, "--show-sdk-path"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if completed.returncode != 0:
                return None
            include = Path(completed.stdout.strip()).resolve() / "usr/include/c++/v1"
            return include if (include / "memory").is_file() else None
        except (OSError, RuntimeError, subprocess.SubprocessError):
            return None

    def _run_checked(
        self,
        command: list[str],
        *,
        cwd: Path,
        failure_code: str,
        timeout: int,
        environment: dict[str, str] | None = None,
    ) -> None:
        self.log.info(
            "setup_web_command_started",
            extra={"operation": failure_code, "argument_count": len(command)},
        )
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                check=False,
                timeout=timeout,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.log.error(
                "setup_web_command_failed",
                extra={"operation": failure_code, "error_type": type(exc).__name__},
            )
            raise RuntimeError(failure_code) from exc
        if completed.returncode != 0:
            self.log.error(
                "setup_web_command_failed",
                extra={"operation": failure_code, "return_code": completed.returncode},
            )
            raise RuntimeError(failure_code)
        self.log.info("setup_web_command_completed", extra={"operation": failure_code})

    def verify_cjpy_bundle(self) -> dict[str, str]:
        """Verify the closed CJPY file set, digests, and wheel metadata."""
        directory = self.project_root / "vendor" / "cjpy" / CJPY_VERSION
        manifest_path = directory / "manifest.json"
        try:
            if directory.is_symlink() or manifest_path.is_symlink():
                raise ValueError("unsafe bundle path")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = manifest["files"]
            if (
                manifest.get("schema_version") != 1
                or manifest.get("package") != "cjpy"
                or manifest.get("version") != CJPY_VERSION
                or manifest.get("wheel") != CJPY_WHEEL
                or not isinstance(files, dict)
            ):
                raise ValueError("invalid bundle manifest")
            if {path.name for path in directory.iterdir()} != {"manifest.json", *files}:
                raise ValueError("unexpected bundle file")
            for name, expected in files.items():
                path = directory / name
                if (
                    Path(name).name != name
                    or path.is_symlink()
                    or not path.is_file()
                    or not re.fullmatch(r"[a-f0-9]{64}", str(expected))
                    or hashlib.sha256(path.read_bytes()).hexdigest() != expected
                ):
                    raise ValueError("bundle digest mismatch")
            if files.get(CJPY_WHEEL) != CJPY_SHA256:
                raise ValueError("unapproved wheel digest")
            with zipfile.ZipFile(directory / CJPY_WHEEL) as archive:
                metadata_names = [
                    name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
                ]
                if len(metadata_names) != 1:
                    raise ValueError("wheel metadata missing")
                metadata = archive.read(metadata_names[0]).decode("utf-8")
            if (
                "\nName: cjpy\n" not in f"\n{metadata}"
                or f"\nVersion: {CJPY_VERSION}\n" not in f"\n{metadata}"
            ):
                raise ValueError("wheel identity mismatch")
            if "\nLicense-Expression: Apache-2.0\n" not in f"\n{metadata}":
                raise ValueError("wheel license mismatch")
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            zipfile.BadZipFile,
            json.JSONDecodeError,
        ) as exc:
            self.log.error(
                "setup_web_cjpy_bundle_invalid", extra={"error_type": type(exc).__name__}
            )
            raise RuntimeError("cjpy_bundle_invalid") from exc
        return {"version": CJPY_VERSION, "wheel": CJPY_WHEEL, "sha256": CJPY_SHA256}

    def dependency_install_commands(self, environment_python: Path) -> list[list[str]]:
        """Return the fixed, auditable Python installation sequence."""
        python = str(environment_python)
        return [
            [python, "-m", "pip", "uninstall", "--yes", "research-workbench"],
            [
                python,
                "-m",
                "pip",
                "install",
                "--index-url",
                PYPI_INDEX,
                "--require-hashes",
                "-r",
                str(self.project_root / "requirements" / "web.lock"),
            ],
            [
                python,
                "-m",
                "pip",
                "install",
                "--no-build-isolation",
                "--no-deps",
                str(self.project_root),
            ],
            [
                python,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                str(self.project_root / "vendor" / "cjpy" / CJPY_VERSION / CJPY_WHEEL),
                "--force-reinstall",
            ],
        ]

    def install_python_dependencies(self, environment_python: Path) -> dict[str, str]:
        """Install and verify the complete Web dependency closure."""
        bundle = self.verify_cjpy_bundle()
        lock = self.project_root / "requirements" / "web.lock"
        try:
            lock_text = lock.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError("web_lock_missing") from exc
        if "--hash=sha256:" not in lock_text or "cjpy==" in lock_text.lower():
            raise RuntimeError("web_lock_invalid")
        environment = self._python_subprocess_environment()
        commands = self.dependency_install_commands(environment_python)
        # A previous interrupted or repeated run can leave the root distribution metadata in
        # place. Remove only this project's distribution before checking the Web-only closure;
        # otherwise pip check reports the root project's intentionally excluded legacy extras.
        self._run_checked(
            commands[0],
            cwd=self.project_root,
            environment=environment,
            failure_code="python_root_uninstall_failed",
            timeout=120,
        )
        self._run_checked(
            commands[1],
            cwd=self.project_root,
            environment=environment,
            failure_code="python_install_step_1_failed",
            timeout=1800,
        )
        # Check the Web closure before installing the root distribution with --no-deps. The root
        # project intentionally retains legacy non-Web metadata for older commands; those optional
        # stacks are outside this Web-only environment and must not be pulled in accidentally.
        self._run_checked(
            [str(environment_python), "-m", "pip", "check"],
            cwd=self.project_root,
            environment=environment,
            failure_code="python_dependency_check_failed",
            timeout=120,
        )
        for index, command in enumerate(commands[2:], 2):
            self._run_checked(
                command,
                cwd=self.project_root,
                environment=environment,
                failure_code=f"python_install_step_{index}_failed",
                timeout=1800,
            )
        validation = (
            "import importlib.metadata as m; "
            "import cjpy, requests, urllib3; "
            f"assert m.version('cjpy') == {CJPY_VERSION!r}; "
            "assert m.version('requests'); assert m.version('urllib3')"
        )
        self._run_checked(
            [str(environment_python), "-c", validation],
            cwd=self.project_root,
            environment=environment,
            failure_code="python_import_check_failed",
            timeout=60,
        )
        return {
            "lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
            "cjpy_version": bundle["version"],
            "cjpy_sha256": bundle["sha256"],
        }

    def verify_web_import(self, environment_python: Path) -> None:
        """Prove the installed interpreter can load the checkout's Web entrypoint."""
        self._run_checked(
            [
                str(environment_python),
                "-B",
                "-c",
                "from app.research_web.main import app; assert app is not None",
            ],
            cwd=self.project_root,
            environment=self._python_subprocess_environment(),
            failure_code="python_web_import_failed",
            timeout=300,
        )

    def _corepack_prefix(self) -> list[str]:
        if self.corepack_executable is not None and self.corepack_executable.is_file():
            return [str(self.corepack_executable)]
        if self.npm_executable is None or not self.npm_executable.is_file():
            raise RuntimeError("corepack_unavailable")
        return [
            str(self.npm_executable),
            "exec",
            "--yes",
            f"--package=corepack@{COREPACK_VERSION}",
            "--",
            "corepack",
        ]

    def dsh_build_commands(self, source: Path) -> list[list[str]]:
        """Return the pinned Corepack/pnpm installation and build commands."""
        del source
        prefix = self._corepack_prefix()
        return [
            [*prefix, f"pnpm@{DSH_PNPM}", "install", "--frozen-lockfile"],
            [*prefix, f"pnpm@{DSH_PNPM}", "run", "build"],
        ]

    def prepare_pnpm_shims(self, environment: dict[str, str]) -> dict[str, str]:
        """Expose a project-private pnpm shim to DSH child build scripts."""
        directory = self.data_home / "runtime" / "corepack-shims" / DSH_PNPM
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._reject_alias(directory, "corepack_shim_directory_unsafe")
        self._run_checked(
            [
                *self._corepack_prefix(),
                "enable",
                "pnpm",
                "--install-directory",
                str(directory),
            ],
            cwd=self.project_root,
            environment=environment,
            failure_code="corepack_shim_install_failed",
            timeout=120,
        )
        candidates = (directory / "pnpm", directory / "pnpm.cmd")
        if not any(candidate.is_file() for candidate in candidates):
            raise RuntimeError("corepack_shim_missing")
        updated = dict(environment)
        existing_path = updated.get("PATH", "")
        updated["PATH"] = (
            f"{directory}{os.pathsep}{existing_path}" if existing_path else str(directory)
        )
        return updated

    @staticmethod
    def _environment_python(environment: Path) -> Path:
        if os.name == "nt":
            return environment / "Scripts" / "python.exe"
        return environment / "bin" / "python"

    def _environment_pip_ready(self, environment_python: Path) -> bool:
        """Bound repair-mode reuse by the package manager needed for installation."""
        try:
            completed = subprocess.run(
                [str(environment_python), "-m", "pip", "--version"],
                cwd=self.project_root,
                env=self._python_subprocess_environment(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.log.warning(
                "setup_web_owned_environment_probe_failed",
                extra={"error_type": type(exc).__name__},
            )
            return False
        if completed.returncode != 0:
            self.log.warning(
                "setup_web_owned_environment_probe_failed",
                extra={"return_code": completed.returncode},
            )
            return False
        return True

    def _owned_environment(self, environment: Path) -> bool:
        return environment_marker_valid(
            environment,
            self.project_root,
            platform_name=self.platform_name,
        )

    def prepare_environment(self, *, repair: bool = False) -> Path:
        """Create or reuse the marked project-local Python 3.12 environment."""
        if self.venv.exists():
            if not self._owned_environment(self.venv):
                raise RuntimeError("unowned_virtual_environment")
            environment_python = self._environment_python(self.venv)
            if environment_python.is_file() and (
                not repair or self._environment_pip_ready(environment_python)
            ):
                return environment_python
            if not repair:
                raise RuntimeError("owned_virtual_environment_broken")
            failed = self.project_root / f".venv.failed-{uuid4().hex}"
            try:
                self.venv.replace(failed)
            except OSError as exc:
                raise RuntimeError("virtual_environment_repair_failed") from exc

        staging = self.project_root / f".venv.rwb-staging-{uuid4().hex}"
        try:
            completed = subprocess.run(
                [str(self.python_executable), "-m", "venv", str(staging)],
                cwd=self.project_root,
                check=False,
                timeout=180,
            )
            if completed.returncode != 0:
                raise RuntimeError("virtual_environment_creation_failed")
            environment_python = self._environment_python(staging)
            if not environment_python.is_file():
                raise RuntimeError("virtual_environment_python_missing")
            marker = {
                "schema_version": 1,
                "owner": "research-workbench-web-installer",
                "project_root_sha256": hashlib.sha256(str(self.project_root).encode()).hexdigest(),
                "python": self.version_reader(self.python_executable),
                "created_at": datetime.now(UTC).isoformat(),
            }
            (staging / ENVIRONMENT_MARKER).write_text(
                json.dumps(marker, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            staging.replace(self.venv)
            return self._environment_python(self.venv)
        except RuntimeError:
            raise
        except (OSError, subprocess.SubprocessError) as exc:
            self.log.error(
                "setup_web_environment_creation_failed",
                extra={"error_type": type(exc).__name__},
            )
            raise RuntimeError("virtual_environment_creation_failed") from exc

    @staticmethod
    def calculate_dsh_closure(source: Path) -> tuple[str, int]:
        """Calculate the same runtime closure enforced by the DSH launcher."""
        digest = hashlib.sha256()
        count = 0
        for root in (source / "packages", source / "apps" / "cli", source / "vendor"):
            for path in sorted(root.rglob("*")):
                if (
                    path.is_file()
                    and "node_modules" not in path.parts
                    and ("lib" in path.parts or path.suffix in {".yml", ".json", ".ts"})
                ):
                    digest.update(path.relative_to(source).as_posix().encode())
                    digest.update(path.read_bytes())
                    count += 1
        return digest.hexdigest(), count

    def verify_dsh_source(self, source: Path, *, require_build: bool = True) -> dict[str, object]:
        """Verify the immutable DSH source identity and its built runtime closure."""
        source = Path(source)
        try:
            self._reject_alias(source, "dsh_source_unsafe")
            if not source.is_dir():
                raise RuntimeError("dsh_source_unsafe")
            source = source.resolve()
            remote = subprocess.check_output(
                [str(self.git_executable), "remote", "get-url", "origin"],
                cwd=source,
                text=True,
                timeout=10,
            ).strip()
            if remote.rstrip("/") != DSH_REMOTE.rstrip("/"):
                raise RuntimeError("dsh_remote_mismatch")
            commit = subprocess.check_output(
                [str(self.git_executable), "rev-parse", "HEAD"],
                cwd=source,
                text=True,
                timeout=10,
            ).strip()
            if commit != DSH_COMMIT:
                raise RuntimeError("dsh_commit_mismatch")
            status = subprocess.check_output(
                [
                    str(self.git_executable),
                    *self._git_worktree_options(),
                    "status",
                    "--porcelain",
                    "--untracked-files=no",
                ],
                cwd=source,
                text=True,
                timeout=15,
            ).strip()
            if status:
                raise RuntimeError("dsh_worktree_modified")
            package = json.loads((source / "package.json").read_text(encoding="utf-8"))
            if package.get("packageManager") != f"pnpm@{DSH_PNPM}":
                raise RuntimeError("dsh_pnpm_mismatch")
            closure_hash = None
            closure_files = None
            if require_build:
                if not (source / "apps" / "cli" / "lib" / "bin.js").is_file():
                    raise RuntimeError("dsh_build_missing")
                closure_hash, closure_files = self.calculate_dsh_closure(source)
                if closure_files != DSH_CLOSURE_FILES:
                    raise RuntimeError("dsh_closure_mismatch")
                marker = source / DSH_MARKER
                if marker.is_file():
                    attestation = json.loads(marker.read_text(encoding="utf-8"))
                    if (
                        attestation.get("closure_sha256") != closure_hash
                        or attestation.get("closure_files") != closure_files
                    ):
                        raise RuntimeError("dsh_closure_mismatch")
            return {
                "commit": commit,
                "remote": remote,
                "pnpm": DSH_PNPM,
                "closure_sha256": closure_hash,
                "closure_files": closure_files,
            }
        except RuntimeError:
            raise
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            subprocess.SubprocessError,
        ) as exc:
            self.log.error(
                "setup_web_dsh_verification_failed",
                extra={"error_type": type(exc).__name__},
            )
            raise RuntimeError("dsh_verification_failed") from exc

    def _owned_dsh_source(self, source: Path) -> bool:
        marker = source / DSH_MARKER
        try:
            self._reject_alias(source, "dsh_source_unsafe")
            self._reject_alias(marker, "dsh_source_unsafe")
            value = json.loads(marker.read_text(encoding="utf-8"))
            return (
                value.get("schema_version") == 1
                and value.get("owner") == "research-workbench-web-installer"
                and value.get("commit") == DSH_COMMIT
                and value.get("remote") == DSH_REMOTE
                and isinstance(value.get("closure_sha256"), str)
                and re.fullmatch(r"[a-f0-9]{64}", value["closure_sha256"]) is not None
                and value.get("closure_files") == DSH_CLOSURE_FILES
            )
        except (OSError, RuntimeError, TypeError, json.JSONDecodeError):
            return False

    def _publish_dsh_build(self, staging: Path, verified: dict[str, object]) -> dict[str, object]:
        """Attest and atomically publish one fully verified DSH build."""
        self._atomic_json(
            staging / DSH_MARKER,
            {
                "schema_version": 1,
                "owner": "research-workbench-web-installer",
                "remote": DSH_REMOTE,
                "commit": DSH_COMMIT,
                "closure_sha256": verified["closure_sha256"],
                "closure_files": verified["closure_files"],
                "installed_at": datetime.now(UTC).isoformat(),
            },
        )
        try:
            staging.replace(self.dsh_source)
        except OSError as exc:
            raise RuntimeError("dsh_publish_failed") from exc
        return verified

    def _recover_completed_dsh_staging(self) -> dict[str, object] | None:
        """Publish a prior completed installer staging after full verification."""
        pattern = re.compile(rf"^\.{DSH_COMMIT}\.staging-[a-f0-9]{{32}}$")
        try:
            candidates = sorted(
                (
                    path
                    for path in self.dsh_root.iterdir()
                    if pattern.fullmatch(path.name) is not None
                ),
                key=lambda path: path.stat().st_mtime_ns,
                reverse=True,
            )
        except OSError:
            return None
        for candidate in candidates:
            try:
                self._reject_alias(candidate, "dsh_source_unsafe")
                verified = self.verify_dsh_source(candidate)
                return self._publish_dsh_build(candidate, verified)
            except RuntimeError:
                continue
        return None

    def provision_dsh(self, *, repair: bool = False) -> dict[str, object]:
        """Clone and build the exact DSH runtime into a versioned private directory."""
        self.dsh_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._reject_alias(self.dsh_root, "dsh_root_unsafe")
        if self.dsh_source.exists():
            if not self._owned_dsh_source(self.dsh_source):
                raise RuntimeError("unowned_dsh_source")
            try:
                return self.verify_dsh_source(self.dsh_source)
            except RuntimeError:
                if not repair:
                    raise
                failed = self.dsh_root / f"{DSH_COMMIT}.failed-{uuid4().hex}"
                try:
                    self.dsh_source.replace(failed)
                except OSError as exc:
                    raise RuntimeError("dsh_repair_failed") from exc

        recovered = self._recover_completed_dsh_staging()
        if recovered is not None:
            return recovered

        staging = self.dsh_root / f".{DSH_COMMIT}.staging-{uuid4().hex}"
        git_environment = self._subprocess_environment()
        node_environment = self._node_subprocess_environment()
        self._run_checked(
            [
                str(self.git_executable),
                *self._git_worktree_options(),
                "clone",
                "--filter=blob:none",
                "--no-checkout",
                DSH_REMOTE,
                str(staging),
            ],
            cwd=self.dsh_root,
            environment=git_environment,
            failure_code="dsh_clone_failed",
            timeout=600,
        )
        self._run_checked(
            [
                str(self.git_executable),
                *self._git_worktree_options(),
                "-C",
                str(staging),
                "checkout",
                "--detach",
                DSH_COMMIT,
            ],
            cwd=self.dsh_root,
            environment=git_environment,
            failure_code="dsh_checkout_failed",
            timeout=300,
        )
        self.verify_dsh_source(staging, require_build=False)
        node_environment = self.prepare_pnpm_shims(node_environment)
        for index, command in enumerate(self.dsh_build_commands(staging), 1):
            self._run_checked(
                command,
                cwd=staging,
                environment=node_environment,
                failure_code=f"dsh_build_step_{index}_failed",
                timeout=3600,
            )
        verified = self.verify_dsh_source(staging)
        return self._publish_dsh_build(staging, verified)

    def _code_commit(self) -> str | None:
        try:
            value = subprocess.check_output(
                [str(self.git_executable), "rev-parse", "HEAD"],
                cwd=self.project_root,
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=10,
            ).strip()
            return value if re.fullmatch(r"[a-f0-9]{40}", value) else None
        except (OSError, subprocess.SubprocessError):
            return None

    def write_install_manifest(
        self,
        *,
        python_state: dict[str, str],
        dsh_state: dict[str, object],
        status: str,
    ) -> dict[str, object]:
        """Persist only version and digest evidence in the private data directory."""
        manifest: dict[str, object] = {
            "schema_version": 1,
            "status": status,
            "code_commit": self._code_commit(),
            "python_version": self.version_reader(self.python_executable),
            "node_version": self.node_version_reader(self.node_executable),
            "web_lock_sha256": python_state["lock_sha256"],
            "cjpy_version": python_state["cjpy_version"],
            "cjpy_sha256": python_state["cjpy_sha256"],
            "dsh_commit": dsh_state["commit"],
            "dsh_closure_sha256": dsh_state["closure_sha256"],
            "dsh_closure_files": dsh_state["closure_files"],
            "installed_at": datetime.now(UTC).isoformat(),
            "last_diagnosis": "installed",
        }
        self._atomic_json(self.install_manifest, manifest)
        return manifest

    def write_install_transaction_state(self) -> dict[str, object]:
        """Invalidate any previous success before the installation mutates owned state."""
        manifest: dict[str, object] = {
            "schema_version": 1,
            "status": "installing",
            "code_commit": self._code_commit(),
            "started_at": datetime.now(UTC).isoformat(),
            "last_diagnosis": "installing",
        }
        self._atomic_json(self.install_manifest, manifest)
        return manifest

    def write_runtime_build_lock(self, *, dsh_state: dict[str, object]) -> dict[str, object]:
        """Publish the verified DSH closure consumed by the runtime launcher."""
        commit = dsh_state.get("commit")
        closure_sha256 = dsh_state.get("closure_sha256")
        closure_files = dsh_state.get("closure_files")
        if (
            commit != DSH_COMMIT
            or not isinstance(closure_sha256, str)
            or re.fullmatch(r"[a-f0-9]{64}", closure_sha256) is None
            or type(closure_files) is not int
            or closure_files != DSH_CLOSURE_FILES
        ):
            raise RuntimeError("dsh_runtime_lock_invalid")
        runtime_lock: dict[str, object] = {
            "source_commit": commit,
            "closure_sha256": closure_sha256,
            "closure_files": closure_files,
            "mode": "build",
        }
        self._write_runtime_lock_json(runtime_lock)
        return runtime_lock

    def install(self, *, repair: bool = False, start: bool = True) -> dict[str, object]:
        """Install the Web stack and optionally start both loopback services."""
        report = self.check()
        report_issues = report.get("issues")
        if not isinstance(report_issues, list) or not all(
            isinstance(issue, str) for issue in report_issues
        ):
            raise RuntimeError("prerequisite_check_invalid")
        issues = [str(issue) for issue in report_issues]
        blocking = [issue for issue in issues if issue != "unowned_virtual_environment"]
        if "unowned_virtual_environment" in issues:
            raise RuntimeError("unowned_virtual_environment")
        if blocking:
            raise RuntimeError(str(blocking[0]))
        self._prepare_data_home()
        self.write_install_transaction_state()
        environment_python = self.prepare_environment(repair=repair)
        python_state = self.install_python_dependencies(environment_python)
        self.verify_web_import(environment_python)

        def complete_runtime(manager=None, lease=None):
            def check_scope():
                if manager is not None:
                    manager._assert_installation_scope(lease)

            check_scope()
            dsh_state = self.provision_dsh(repair=repair)
            check_scope()
            self.write_runtime_build_lock(dsh_state=dsh_state)
            check_scope()
            manifest = self.write_install_manifest(
                python_state=python_state,
                dsh_state=dsh_state,
                status="installed",
            )
            check_scope()
            return manifest

        if not start:
            return complete_runtime()
        from app.research_web.service_manager import WebServiceManager

        manager = WebServiceManager(
            project_root=self.project_root,
            data_root=self.data_home / "research-web",
            runtime_source=self.dsh_source,
            python=str(environment_python),
            node=str(self.node_executable),
            web_port=self.web_port,
            runtime_port=self.runtime_port,
        )
        with manager._installation_start_scope() as lease:
            manifest = complete_runtime(manager, lease)
            manager._start_installed(lease, open_browser=True)
        return manifest


def _configure_logging(project_root: Path) -> None:
    log_root = project_root / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_root / "setup-web.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def build_parser() -> argparse.ArgumentParser:
    """Keep the public bootstrap flags testable without invoking installation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", choices=("native", "docker"), default="native")
    parser.add_argument("--check-only", action="store_true", help="只检查，不写入环境")
    parser.add_argument("--repair", action="store_true", help="修复安装器拥有的环境")
    parser.add_argument("--no-start", action="store_true", help="安装完成后不启动服务")
    parser.add_argument("--web-port", type=int, default=None, help="显式 Web 回环端口")
    parser.add_argument("--runtime-port", type=int, default=None, help="仅 Native 的 DSH 回环端口")
    return parser


def _docker_issue(report: dict[str, object], fallback: str) -> str:
    issues = report.get("issues")
    if isinstance(issues, list) and issues and isinstance(issues[0], str):
        code = issues[0]
        if re.fullmatch(r"[a-z][a-z0-9_]{1,79}", code):
            return code
    return fallback


def _docker_manifest(project_root: Path, image_id: str) -> dict[str, object]:
    """Record public build facts, never command output or host file paths."""
    if re.fullmatch(r"sha256:[a-f0-9]{64}", image_id) is None:
        raise RuntimeError("docker_build_not_ready")
    try:
        lock_sha256 = hashlib.sha256(
            (project_root / "requirements/web.lock").read_bytes()
        ).hexdigest()
        compose_sha256 = hashlib.sha256((project_root / "compose.yaml").read_bytes()).hexdigest()
    except OSError as exc:
        raise RuntimeError("docker_install_summary_failed") from exc
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        commit = ""
    return {
        "schema_version": 1,
        "status": "installed",
        "runtime": "docker",
        "code_commit": commit if re.fullmatch(r"[a-f0-9]{40}", commit) else None,
        "image_id": image_id,
        "python_version": f"{RUNTIME_CONTRACT.python_major}.{RUNTIME_CONTRACT.python_minor}",
        "node_major": RUNTIME_CONTRACT.node_major,
        "web_lock_sha256": lock_sha256,
        "cjpy_version": CJPY_VERSION,
        "cjpy_sha256": CJPY_SHA256,
        "dsh_commit": DSH_COMMIT,
        "compose_sha256": compose_sha256,
        "installed_at": datetime.now(UTC).isoformat(),
    }


def _write_docker_manifest(path: Path, manifest: dict[str, object]) -> os.stat_result | None:
    """Publish only into the private install directory owned by mode store."""
    try:
        parent = path.parent.lstat()
        if (
            not stat.S_ISDIR(parent.st_mode)
            or path.parent.is_symlink()
            or SetupWebInstaller._is_reparse_point(path.parent)
            or (
                os.name == "posix"
                and (parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) != 0o700)
            )
        ):
            raise RuntimeError("docker_install_summary_unsafe")
        try:
            existing = path.lstat()
        except FileNotFoundError:
            existing = None
        if existing is not None and (
            not stat.S_ISREG(existing.st_mode)
            or existing.st_nlink != 1
            or SetupWebInstaller._is_reparse_point(path)
            or (
                os.name == "posix"
                and (existing.st_uid != os.getuid() or stat.S_IMODE(existing.st_mode) != 0o600)
            )
        ):
            raise RuntimeError("docker_install_summary_unsafe")
        if os.name == "posix":
            raw = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            return _atomic_write_posix(path, raw, existing)
        SetupWebInstaller._atomic_json(path, manifest)
        return None
    except OSError as exc:
        raise RuntimeError("docker_install_summary_failed") from exc


class DockerRuntime(_DockerRuntimeController):
    """Public installer adapter around the stdlib Docker lifecycle controller."""

    def _verify_selection_safe(self, current: object, image_id: str, *, repair=False) -> None:
        """Apply the bootstrap's no-stop switch checks before publishing setup state."""
        from research_workbench_entrypoint.bootstrap import NativeRuntime, _running

        checked = self.preflight(require_image=False)
        if not checked.get("ok"):
            raise RuntimeError(_docker_issue(checked, "docker_preflight_failed"))
        native_runtime = NativeRuntime(self.project_root, self.home)
        native = native_runtime.status()
        docker = self.status()
        if not self._native_selection_safe(native_runtime, native) or not docker.get("ok"):
            raise RuntimeError("runtime_stop_current_required")
        try:
            native_running = _running(native) if native.get("ok") else False
            docker_running = _running(docker)
            if native_running or docker_running:
                raise RuntimeError("runtime_stop_current_required")
        except ControlError as exc:
            raise RuntimeError("runtime_ownership_unknown") from exc
        if checked.get("container_image_id") not in (None, image_id):
            if not repair:
                raise RuntimeError("docker_upgrade_requires_container_disposition")
            self._dispose_stopped_for_repair(current)
        if RuntimeModeStore(self.home).read() != current:
            raise RuntimeError("runtime_mode_changed")

    def install(self, *, repair: bool = False, start: bool = True) -> dict[str, object]:
        # The controller always performs a bounded build and verifies its image
        # identity. Repair repeats that same safe build without deleting state.
        logging.getLogger("research_workbench.setup_web").info(
            "docker_setup_build", extra={"repair": repair}
        )
        report = super().install()
        if not report.get("ok"):
            raise RuntimeError(_docker_issue(report, "docker_build_failed"))
        image_id = report.get("image_id")
        if not isinstance(image_id, str):
            # Keep the coded installer RuntimeError contract.
            raise RuntimeError("docker_build_not_ready")  # noqa: TRY004
        manifest = _docker_manifest(self.project_root, image_id)
        store = RuntimeModeStore(self.home)
        current = store.read()
        if not current.installation_id:
            current = store.write(current.mode)

        def accept_candidate():
            self._verify_selection_safe(current, image_id, repair=repair)
            try:
                if start:
                    started = self._start_candidate(manifest)
                    if not started.get("ok"):
                        raise RuntimeError(_docker_issue(started, "docker_start_failed"))
                    if not all(
                        started.get("services", {}).get(role, {}).get("healthy") is True
                        for role in ("web", "runtime")
                    ):
                        raise RuntimeError("docker_services_unhealthy")
                self._publish_selection(store, current, manifest)
            except (OSError, RuntimeError) as error:
                self._recover_fresh_failure(error, self._abort_candidate)
                raise
            return manifest

        accepted = self._locked_guard("install_selection", accept_candidate)
        if accepted.get("ok") is False:
            raise RuntimeError(_docker_issue(accepted, "docker_install_failed"))
        return accepted

    def _publish_selection(self, store, current, manifest):
        """Serialize mode publication and restore the receipt on a failed commit."""
        path = self.home / "install/docker-manifest.json"
        self._revalidate_missing_selection()
        with store._write_lock():
            if store.read() != current:
                raise RuntimeError("runtime_mode_changed")
            self._manifest(allow_missing=True, check_contract=False)
            try:
                previous, previous_identity = _read_bytes(path)
            except FileNotFoundError:
                previous, previous_identity = None, None
            published_mode = None
            publication_identity = None
            publication_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(
                "utf-8"
            )
            try:
                publication_identity = _write_docker_manifest(path, manifest)
                # Keep the origin transaction pending until receipt and mode agree.
                if current.mode != "docker":
                    published_mode = store._write_locked("docker", expected=current)
                    if self._fresh_root is not None:
                        self._fresh_root["mode"] = published_mode
                self._revalidate_missing_selection()
                self._commit_candidate()
            except (OSError, RuntimeError) as error:

                def restore_publication():
                    if published_mode is not None:
                        restored_mode = store._write_locked(current.mode, expected=published_mode)
                        if self._fresh_root is not None:
                            self._fresh_root["mode"] = restored_mode
                    try:
                        published, identity = _read_bytes(path)
                    except FileNotFoundError:
                        published, identity = None, None
                    if publication_identity is None:
                        # A failed writer cannot establish ownership by later readback.
                        if published != previous or not _same_identity(identity, previous_identity):
                            raise RuntimeError(
                                "docker_install_summary_recovery_unverified"
                            ) from None
                        return
                    matches = published == publication_bytes and _same_identity(
                        identity, publication_identity
                    )
                    if not matches:
                        raise RuntimeError("docker_install_summary_recovery_unverified") from None
                    if matches:
                        if previous is not None:
                            _atomic_write_posix(path, previous, identity)
                        else:
                            with _private_posix_parent(path) as parent:
                                if not _same_identity(
                                    _leaf_identity_at(parent, path.name), identity
                                ):
                                    raise RuntimeError("docker_install_summary_changed") from None
                                os.unlink(path.name, dir_fd=parent)
                                os.fsync(parent)

                self._recover_fresh_failure(error, restore_publication)
                logging.getLogger("research_workbench.setup_web").warning(
                    "docker_setup_publish_failed"
                )
                raise


class _NativePortOptions(TypedDict, total=False):
    """Only explicitly supplied ports are forwarded to the Native installer."""

    web_port: int
    runtime_port: int


def _validated_setup_ports(arguments: argparse.Namespace) -> tuple[int | None, int | None]:
    web_port = getattr(arguments, "web_port", None)
    runtime_port = getattr(arguments, "runtime_port", None)
    for port in (web_port, runtime_port):
        if port is not None and (type(port) is not int or not 1 <= port <= 65535):
            raise RuntimeError("endpoint_invalid_port")
    if arguments.runtime == "docker" and runtime_port is not None:
        raise RuntimeError("docker_runtime_port_unsupported")
    if web_port is not None and web_port == runtime_port:
        raise RuntimeError("endpoint_invalid_pair")
    return web_port, runtime_port


def install_selected_runtime(
    arguments: argparse.Namespace, *, project_root: Path
) -> dict[str, object]:
    data_home = Path.home() / ".research-workbench"
    web_port, runtime_port = _validated_setup_ports(arguments)
    if arguments.runtime == "docker":
        controller = DockerRuntime(project_root, data_home)
        if web_port is not None:
            controller.requested_web_port = web_port
        return controller.install(
            repair=arguments.repair,
            start=not arguments.no_start,
        )
    options = cast(
        _NativePortOptions,
        {
            key: value
            for key, value in (("web_port", web_port), ("runtime_port", runtime_port))
            if value is not None
        },
    )
    return SetupWebInstaller(project_root=project_root, **options).install(
        repair=arguments.repair,
        start=not arguments.no_start,
    )


_DOCKER_REMEDIATION = {
    "docker_cli_missing": "请安装并启动 {platform} 的 Docker Desktop。",
    "docker_daemon_unavailable": "请启动 {platform} 的 Docker Desktop，并等待 Engine 就绪。",
    "docker_compose_missing": "请检查 {platform} 的 Docker Desktop Compose 插件。",
    "docker_architecture_unsupported": "当前 CPU 架构不受支持，请使用 arm64 或 x86_64 主机。",
    "docker_data_home_unsafe": "请检查本机 Research Workbench 数据目录的所有权与权限。",
    "docker_port_8088_occupied": "所选宿主 Web 端口发生绑定竞争；请重试或显式选择空闲 --web-port。",
    "docker_port_3081_conflict": "Docker DSH 使用容器内部 3081；请检查旧版本端口配置，不要停止无关宿主服务。",
    "endpoint_port_in_use": "显式端口被占用；请选择空闲端口，或省略端口参数使用自动候选。",
    "docker_stopped_port_conflict": "停止的受管容器保留原端口绑定；当前不会隐式重建容器。",
    "docker_ownership_mismatch": "检测到容器归属冲突，请检查已有容器。",
    "docker_build_not_ready": "请重新运行 Docker 模式安装以构建受管镜像。",
    "docker_build_failed": "Docker 镜像构建失败，请检查 Docker Desktop 与构建日志后重试。",
    "docker_start_failed": "Docker 服务启动失败，请检查容器状态与健康检查后重试。",
    "docker_io": "Docker 命令或本机文件访问失败，请检查 Docker Desktop 后重试。",
    "runtime_stop_current_required": "当前运行时或端口仍在使用；请先通过 rwb runtime 安全停止或切换。",
}


def _maybe_reexec_native(arguments, project_root: Path, argv: list[str]) -> int | None:
    """Enter the exact owned venv before any product-root creation/witness."""
    if arguments.runtime != "native" or arguments.check_only or arguments.no_start:
        return None
    installer = SetupWebInstaller(project_root=project_root)
    if Path(sys.prefix).resolve() == installer.venv.resolve() and installer._owned_environment(
        installer.venv
    ):
        return None
    report = installer.check()
    issues = report.get("issues")
    if not isinstance(issues, list) or not all(isinstance(issue, str) for issue in issues):
        raise RuntimeError("prerequisite_check_invalid")
    if issues:
        raise RuntimeError(issues[0])
    python = installer.prepare_environment(repair=arguments.repair)
    if python != installer._environment_python(installer.venv) or not installer._owned_environment(
        installer.venv
    ):
        raise RuntimeError("unowned_virtual_environment")
    installer.log.info("setup_web_owned_environment_reexec")
    completed = subprocess.run(
        [str(python), "-I", str(Path(__file__).resolve()), *argv],
        cwd=Path.cwd(),
        env=dict(os.environ),
        check=False,
    )
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    original_arguments = list(sys.argv[1:] if argv is None else argv)
    arguments = build_parser().parse_args(original_arguments)
    project_root = Path(__file__).resolve().parents[1]
    if not arguments.check_only:
        _configure_logging(project_root)
    try:
        _validated_setup_ports(arguments)
        reexecuted = _maybe_reexec_native(arguments, project_root, original_arguments)
        if reexecuted is not None:
            return reexecuted
        if arguments.check_only:
            if arguments.runtime == "docker":
                report = DockerRuntime(project_root, Path.home() / ".research-workbench").preflight(
                    require_image=False
                )
                report = {
                    "schema_version": 1,
                    "ok": bool(report.get("ok")),
                    "issues": (
                        [_docker_issue(report, "docker_preflight_failed")]
                        if not report.get("ok")
                        else []
                    ),
                    "mode": "docker",
                }
            else:
                report = SetupWebInstaller(project_root=project_root).check()
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["ok"] else 1
        manifest = install_selected_runtime(arguments, project_root=project_root)
        if arguments.runtime == "docker":
            print(
                json.dumps(
                    {
                        "status": manifest["status"],
                        "runtime": "docker",
                        "code_commit": manifest["code_commit"],
                        "image_id": manifest["image_id"],
                        "started": not arguments.no_start,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        print(
            json.dumps(
                {
                    "status": manifest["status"],
                    "code_commit": manifest["code_commit"],
                    "cjpy_version": manifest["cjpy_version"],
                    "dsh_commit": manifest["dsh_commit"],
                    "started": not arguments.no_start,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except RuntimeError as exc:
        code = str(exc)
        if arguments.runtime == "docker":
            code = code if re.fullmatch(r"[a-z][a-z0-9_]{1,79}", code) else "docker_install_failed"
            advice = _DOCKER_REMEDIATION.get(code, "请检查 Docker Desktop 状态和安装日志后重试。")
            platform = "Windows" if os.name == "nt" else "macOS"
            print(f"安装失败：{code}。{advice.format(platform=platform)}", file=sys.stderr)
        else:
            print(f"安装失败：{exc}", file=sys.stderr)
        logging.getLogger("research_workbench.setup_web").error(
            "setup_web_failed", extra={"failure_code": code}
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
