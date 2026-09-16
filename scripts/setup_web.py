#!/usr/bin/env python3
"""Create and diagnose the project-owned Research Workbench Web environment."""

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
from urllib.parse import urlsplit
from uuid import uuid4

ENVIRONMENT_MARKER = ".rwb-web-environment.json"
CJPY_VERSION = "0.5.2"
CJPY_WHEEL = "cjpy-0.5.2-py3-none-any.whl"
CJPY_SHA256 = "d8c6820a718ae5f79061b54815473dd3ecd3be73cd808634fbac5bc1c385bd94"
DSH_REMOTE = "https://github.com/Leon-Huang001208/deepseek-harness.git"
DSH_COMMIT = "c919b2a460753859665db3f60143d525fb9140cf"
DSH_PNPM = "11.7.0"
DSH_CLOSURE_FILES = 11084
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
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.data_home = Path(data_home or Path.home() / ".research-workbench").resolve()
        self.venv = self.project_root / ".venv"
        self.python_executable = Path(python_executable or sys.executable).resolve()
        self.node_executable = Path(node_executable or shutil.which("node") or "node").resolve()
        self.git_executable = Path(git_executable or shutil.which("git") or "git").resolve()
        discovered_corepack = corepack_executable or shutil.which("corepack")
        self.corepack_executable = (
            Path(discovered_corepack).resolve() if discovered_corepack else None
        )
        discovered_npm = npm_executable or shutil.which("npm")
        self.npm_executable = Path(discovered_npm).resolve() if discovered_npm else None
        self.version_reader = version_reader or _command_version
        self.node_version_reader = node_version_reader or _command_version
        self.log = logging.getLogger("research_workbench.setup_web")
        self.dsh_root = self.data_home / "runtime" / "dsh"
        self.dsh_source = self.dsh_root / DSH_COMMIT
        self.install_root = self.data_home / "install"
        self.install_manifest = self.install_root / "manifest.json"

    @staticmethod
    def _python_supported(value: str) -> bool:
        match = re.search(r"(?<!\d)(\d+)\.(\d+)", value)
        return bool(match and (int(match.group(1)), int(match.group(2))) == (3, 12))

    @staticmethod
    def _node_supported(value: str) -> bool:
        match = re.search(r"(?<!\d)(\d+)\.(\d+)", value)
        if not match:
            return False
        major, minor = int(match.group(1)), int(match.group(2))
        return (major == 22 and minor >= 19) or major == 24

    def check(self) -> dict[str, object]:
        """Inspect prerequisites and ownership without mutating the checkout."""
        issues: list[str] = []
        if self.venv.exists() and not (self.venv / ENVIRONMENT_MARKER).is_file():
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
            except (OSError, RuntimeError, subprocess.SubprocessError):
                issues.append("python_version_unreadable")
        if "node_missing" not in issues:
            try:
                if not self._node_supported(self.node_version_reader(self.node_executable)):
                    issues.append("node_version_unsupported")
            except (OSError, RuntimeError, subprocess.SubprocessError):
                issues.append("node_version_unreadable")
        if issues:
            self.log.warning("setup_web_check_failed", extra={"issue_count": len(issues)})
        return {
            "schema_version": 1,
            "ok": not issues,
            "issues": issues,
            "environment_owned": (self.venv / ENVIRONMENT_MARKER).is_file(),
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
                or "\nVersion: 0.5.2\n" not in f"\n{metadata}"
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
        environment = self._subprocess_environment()
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
            "assert m.version('cjpy') == '0.5.2'; "
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

    def _owned_environment(self, environment: Path) -> bool:
        marker = environment / ENVIRONMENT_MARKER
        try:
            if environment.is_symlink() or marker.is_symlink():
                return False
            value = json.loads(marker.read_text(encoding="utf-8"))
            return (
                value.get("schema_version") == 1
                and value.get("owner") == "research-workbench-web-installer"
                and value.get("project_root_sha256")
                == hashlib.sha256(str(self.project_root).encode()).hexdigest()
            )
        except (OSError, AttributeError, TypeError, json.JSONDecodeError):
            return False

    def prepare_environment(self, *, repair: bool = False) -> Path:
        """Create or reuse the marked project-local Python 3.12 environment."""
        if self.venv.exists():
            if not self._owned_environment(self.venv):
                raise RuntimeError("unowned_virtual_environment")
            environment_python = self._environment_python(self.venv)
            if environment_python.is_file():
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
                [str(self.git_executable), "status", "--porcelain", "--untracked-files=no"],
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
                "-c",
                "core.longpaths=true",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.eol=lf",
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
                "-c",
                "core.longpaths=true",
                "-c",
                "core.autocrlf=false",
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
        environment_python = self.prepare_environment(repair=repair)
        python_state = self.install_python_dependencies(environment_python)
        dsh_state = self.provision_dsh(repair=repair)
        manifest = self.write_install_manifest(
            python_state=python_state,
            dsh_state=dsh_state,
            status="installed",
        )
        if start:
            os.environ["RESEARCH_DSH_SOURCE"] = str(self.dsh_source)
            from app.research_web.service_manager import WebServiceManager

            manager = WebServiceManager(
                project_root=self.project_root,
                data_root=self.data_home / "research-web",
                runtime_source=self.dsh_source,
                python=str(environment_python),
                node=str(self.node_executable),
            )
            manager.start(open_browser=True)
        return manifest


def _configure_logging(project_root: Path) -> None:
    log_root = project_root / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_root / "setup-web.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="只检查，不写入环境")
    parser.add_argument("--repair", action="store_true", help="修复安装器拥有的环境")
    parser.add_argument("--no-start", action="store_true", help="安装完成后不启动服务")
    arguments = parser.parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    _configure_logging(project_root)
    installer = SetupWebInstaller(project_root=project_root)
    try:
        if arguments.check_only:
            report = installer.check()
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["ok"] else 1
        manifest = installer.install(repair=arguments.repair, start=not arguments.no_start)
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
        logging.getLogger("research_workbench.setup_web").error(
            "setup_web_failed", extra={"failure_code": str(exc)}
        )
        print(f"安装失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
