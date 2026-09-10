"""Verified MCP package installation into an atomically published directory."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from collections.abc import Callable, Sequence
from pathlib import Path

from core.observability import get_logger

from .credentials import RuntimeCredentialStore
from .models import (
    InstallationManifest,
    InstallationPlan,
    InstallationPlanUnion,
    RemoteInstallationPlan,
)
from .package_planner import MAX_MCPB_EXPANDED_BYTES, PackagePlanner
from .transport import RemoteTarget, build_stdio_target

log = get_logger(__name__)


class PackageInstallError(RuntimeError):
    """A stable local package installation failure."""


Runner = Callable[[Sequence[str], Path, dict[str, str]], None]


class PackageInstaller:
    """Reverify staged bytes, install without shell, then atomically publish."""

    def __init__(
        self,
        staging_root: Path,
        installation_root: Path,
        *,
        runner: Runner | None = None,
        credentials: RuntimeCredentialStore | None = None,
    ) -> None:
        self.staging_root = self._private_root(Path(staging_root), create=False)
        self.installation_root = self._private_root(Path(installation_root), create=True)
        self.runner = runner or self._default_runner
        self.credentials = credentials

    def install(
        self,
        value: InstallationManifest | InstallationPlanUnion,
        environment_values: dict[str, str] | None = None,
    ) -> Path:
        manifest = value if isinstance(value, InstallationManifest) else None
        plan = manifest.plan if manifest is not None else value
        installation_id = manifest.id if manifest is not None else None
        environment_values = dict(environment_values or {})
        if set(environment_values) != set(plan.environment_names):
            raise PackageInstallError("installation_environment_mismatch")
        if isinstance(plan, RemoteInstallationPlan):
            plan.assert_integrity()
            log.info("mcp_remote_installation_recorded", status="installed")
            return self.installation_root
        try:
            plan = InstallationPlan.model_validate_json(plan.model_dump_json())
            plan.assert_integrity()
        except ValueError as exc:
            raise PackageInstallError("installation_plan_invalid") from exc
        staging = self._staging_directory(plan.staging_id)
        self._reverify(staging, plan)
        candidate = staging / ".install"
        if candidate.exists() or candidate.is_symlink():
            raise PackageInstallError("installation_candidate_exists")
        if plan.package_type == "mcpb":
            self._extract_mcpb(staging, candidate, plan.artifacts[0].filename)
        else:
            executable = "npm" if plan.package_type == "npm" else sys.executable
            if plan.package_type == "npm" and shutil.which(executable) is None:
                raise PackageInstallError("package_installer_unavailable")
            environment = self._minimal_environment(staging, executable)
            try:
                if plan.package_type == "npm":
                    for artifact in plan.artifacts:
                        self.runner(
                            [
                                "npm",
                                "cache",
                                "add",
                                artifact.filename,
                                "--ignore-scripts",
                                "--cache",
                                ".npm-cache",
                            ],
                            staging,
                            environment,
                        )
                self.runner(plan.install_argv, staging, environment)
                if plan.package_type == "npm":
                    node_modules = staging / "node_modules"
                    if node_modules.is_symlink() or not node_modules.is_dir():
                        raise PackageInstallError("installation_candidate_missing")
                    node_modules.rename(candidate)
            except PackageInstallError:
                raise
            except Exception as exc:
                log.error(
                    "mcp_package_install_failed", error_type=type(exc).__name__, status="failed"
                )
                raise PackageInstallError("package_install_failed") from exc
        if candidate.is_symlink() or not candidate.is_dir():
            raise PackageInstallError("installation_candidate_missing")
        destination = self.installation_root / (installation_id or plan.staging_id)
        if destination.exists() or destination.is_symlink():
            raise PackageInstallError("installation_destination_exists")
        try:
            os.rename(candidate, destination)
        except OSError as exc:
            raise PackageInstallError("installation_publish_failed") from exc
        if environment_values:
            if installation_id is None or self.credentials is None:
                shutil.rmtree(destination)
                raise PackageInstallError("credential_store_unavailable")
            try:
                self.credentials.write(
                    installation_id, "environment", {"values": environment_values}
                )
            except Exception as exc:
                try:
                    shutil.rmtree(destination)
                except OSError as cleanup_exc:
                    log.error(
                        "mcp_package_install_credential_rollback_failed",
                        error_type=type(cleanup_exc).__name__,
                        status="failed",
                    )
                raise PackageInstallError("credential_store_unavailable") from exc
        log.info("mcp_package_install_published", status="installed")
        return destination

    def target(self, manifest: InstallationManifest):
        """Build a transport target exclusively from an immutable manifest and keyring data."""

        plan = manifest.plan
        plan.assert_integrity()
        if isinstance(plan, RemoteInstallationPlan):
            return RemoteTarget(plan.endpoint, manifest.id, plan.endpoint)  # type: ignore[call-arg]
        destination = self.installation_root / manifest.id
        if destination.is_symlink() or not destination.is_dir():
            raise PackageInstallError("installation_destination_missing")
        explicit: dict[str, str] = {}
        if plan.environment_names:
            if self.credentials is None:
                raise PackageInstallError("credential_store_unavailable")
            payload = self.credentials.read(manifest.id, "environment")
            values = payload.get("values")
            if not isinstance(values, dict) or set(values) != set(plan.environment_names):
                raise PackageInstallError("credential_record_invalid")
            explicit = {str(name): str(value) for name, value in values.items()}
        argv = self._published_argv(destination, plan)
        return build_stdio_target(argv, destination, explicit)

    def update(self, manifest: InstallationManifest):
        """Immutable installations update only by creating a new manifest/version."""

        return self.target(manifest)

    def remove(self, manifest: InstallationManifest) -> None:
        destination = self.installation_root / manifest.id
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or destination.parent.resolve() != self.installation_root:
                raise PackageInstallError("installation_destination_unsafe")
            shutil.rmtree(destination)
        if self.credentials is not None:
            for slot in ("environment", "oauth"):
                self.credentials.delete(manifest.id, slot)
        log.info("mcp_package_installation_removed", status="removed")

    @staticmethod
    def _published_argv(destination: Path, plan: InstallationPlan) -> list[str]:
        if plan.package_type == "pypi" and len(plan.argv) >= 3 and plan.argv[1] == "-m":
            launcher = destination / ".mcp-python-launcher"
            module = plan.argv[2]
            raw = (
                f"#!{sys.executable}\nimport runpy\nrunpy.run_module({module!r}, run_name='__main__')\n"
            ).encode()
            PackageInstaller._write_launcher(launcher, raw)
            return [str(launcher), *plan.argv[3:]]
        if plan.package_type == "mcpb" and len(plan.argv) >= 2:
            runtime = Path(plan.argv[0]).name.lower()
            script = (destination / plan.argv[1]).resolve(strict=True)
            if (
                not script.is_relative_to(destination)
                or script.is_symlink()
                or not script.is_file()
            ):
                raise PackageInstallError("installation_executable_unsafe")
            if runtime in {"node", "node.exe"}:
                node = shutil.which("node")
                if node is None:
                    raise PackageInstallError("package_installer_unavailable")
                launcher = destination / ".mcp-node-launcher"
                raw = f"#!{node}\nrequire({str(script)!r})\n".encode()
                PackageInstaller._write_launcher(launcher, raw)
                return [str(launcher), *plan.argv[2:]]
        if plan.package_type == "npm":
            package = destination.joinpath(*plan.package_identifier.split("/"))
            try:
                metadata = json.loads((package / "package.json").read_text("utf-8"))
                binary = metadata["bin"]
                if isinstance(binary, dict):
                    binary = next(iter(binary.values()))
                executable = (package / str(binary)).resolve(strict=True)
            except (OSError, KeyError, StopIteration, TypeError, ValueError) as exc:
                raise PackageInstallError("installation_executable_missing") from exc
            if not executable.is_relative_to(destination) or executable.is_symlink():
                raise PackageInstallError("installation_executable_unsafe")
            executable.chmod(0o700)
            arguments = list(plan.argv[1:])
            if plan.package_identifier in arguments:
                arguments = arguments[arguments.index(plan.package_identifier) + 1 :]
            return [str(executable), *arguments]
        raise PackageInstallError("installation_executable_unsupported")

    @staticmethod
    def _write_launcher(path: Path, raw: bytes) -> None:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            return
        except OSError as exc:
            raise PackageInstallError("installation_launcher_failed") from exc

    @staticmethod
    def _default_runner(argv: Sequence[str], cwd: Path, environment: dict[str, str]) -> None:
        command = list(argv)
        if not command:
            raise PackageInstallError("package_install_command_invalid")
        if command[0] == "npm":
            executable = shutil.which("npm")
            if executable is None:
                raise PackageInstallError("package_installer_unavailable")
            command[0] = executable
        elif command[:3] == ["python", "-m", "pip"]:
            command[0] = sys.executable
        else:
            raise PackageInstallError("package_install_command_invalid")
        try:
            subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=600,
            )
        except FileNotFoundError as exc:
            raise PackageInstallError("package_installer_unavailable") from exc
        except (subprocess.SubprocessError, OSError) as exc:
            raise PackageInstallError("package_install_failed") from exc

    @staticmethod
    def _private_root(path: Path, *, create: bool) -> Path:
        try:
            if create:
                path.mkdir(mode=0o700, parents=True, exist_ok=True)
            info = path.lstat()
            if (
                path.is_symlink()
                or not stat.S_ISDIR(info.st_mode)
                or info.st_mode & 0o077
                or (hasattr(os, "getuid") and info.st_uid != os.getuid())
            ):
                raise PackageInstallError("package_directory_unsafe")
            return path.resolve(strict=True)
        except PackageInstallError:
            raise
        except OSError as exc:
            raise PackageInstallError("package_directory_unavailable") from exc

    def _staging_directory(self, staging_id: str) -> Path:
        path = self.staging_root / staging_id
        try:
            if path.parent.resolve(strict=True) != self.staging_root:
                raise PackageInstallError("staging_directory_unsafe")
            return self._private_root(path, create=False)
        except OSError as exc:
            raise PackageInstallError("staging_directory_unavailable") from exc

    @staticmethod
    def _reverify(staging: Path, plan: InstallationPlan) -> None:
        for artifact in plan.artifacts:
            path = staging / artifact.filename
            try:
                descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                info = os.fstat(descriptor)
                digest = hashlib.sha256()
                with os.fdopen(descriptor, "rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        digest.update(chunk)
            except OSError as exc:
                raise PackageInstallError("staged_artifact_unavailable") from exc
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_size != artifact.size_bytes
                or not hmac.compare_digest(digest.hexdigest(), artifact.sha256)
            ):
                raise PackageInstallError("staged_artifact_changed")
        auxiliary = (
            ("package-lock.json", plan.package_lock_sha256)
            if plan.package_type == "npm"
            else (
                ("requirements.txt", plan.requirements_sha256)
                if plan.package_type == "pypi"
                else None
            )
        )
        if auxiliary is not None:
            filename, expected = auxiliary
            try:
                raw = (staging / filename).read_bytes()
            except OSError as exc:
                raise PackageInstallError("installation_lock_unavailable") from exc
            if expected is None or not hmac.compare_digest(
                hashlib.sha256(raw).hexdigest(), expected
            ):
                raise PackageInstallError("installation_lock_changed")

    @staticmethod
    def _minimal_environment(staging: Path, executable: str) -> dict[str, str]:
        home = staging / ".home"
        temporary = staging / ".tmp"
        cache = staging / ".npm-cache"
        for path in (home, temporary, cache):
            path.mkdir(mode=0o700, exist_ok=True)
        executable_path = shutil.which(executable) if executable == "npm" else sys.executable
        binary_directory = str(Path(executable_path).parent) if executable_path else ""
        return {
            "HOME": str(home),
            "PATH": binary_directory,
            "TMPDIR": str(temporary),
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "npm_config_cache": str(cache),
            "npm_config_ignore_scripts": "true",
        }

    @staticmethod
    def _extract_mcpb(staging: Path, candidate: Path, filename: str) -> None:
        try:
            candidate.mkdir(mode=0o700)
            total = 0
            with zipfile.ZipFile(staging / filename) as archive:
                for member in archive.infolist():
                    PackagePlanner._validate_mcpb_member(member)
                    relative = Path(*member.filename.rstrip("/").split("/"))
                    destination = candidate / relative
                    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    if member.is_dir():
                        destination.mkdir(mode=0o700, exist_ok=True)
                        continue
                    descriptor = os.open(
                        destination,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                        0o600,
                    )
                    with archive.open(member) as source, os.fdopen(descriptor, "wb") as target:
                        while chunk := source.read(1024 * 1024):
                            total += len(chunk)
                            if total > MAX_MCPB_EXPANDED_BYTES:
                                raise PackageInstallError("mcpb_archive_expanded_size_limit")
                            target.write(chunk)
                        target.flush()
                        os.fsync(target.fileno())
        except PackageInstallError:
            raise
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            raise PackageInstallError("mcpb_extract_failed") from exc
