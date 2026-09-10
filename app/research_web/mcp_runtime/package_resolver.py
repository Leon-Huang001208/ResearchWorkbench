"""Trusted, staged package resolution for MCP installations.

The browser supplies only :class:`InstallationSelection`. Registry lookup and
package resolution are injected Host services; without both services this
boundary fails closed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import uuid4

from core.observability import get_logger

from .models import InstallationRequest, InstallationSelection, PackageArtifact

log = get_logger(__name__)

MAX_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024
MAX_ARCHIVE_MEMBERS = 4096
STAGING_ID = re.compile(r"^mcp-stage-[a-f0-9]{32}$")
LIFECYCLE_SCRIPTS = frozenset(
    {"preinstall", "install", "postinstall", "prepublish", "prepare", "postprepare"}
)
_TRUST_PROOF = object()


class PackageResolutionError(RuntimeError):
    """A stable trusted-resolution failure."""


class ResolutionBackend(Protocol):
    """Host-owned adapter that downloads one Registry package closure."""

    def resolve(
        self,
        selection: InstallationSelection,
        registry_detail: Mapping[str, Any],
        staging_directory: Path,
    ) -> InstallationRequest: ...


@dataclass(frozen=True, slots=True)
class ResolvedInstallation:
    """Opaque output accepted by PackagePlanner; it is not JSON deserializable."""

    request: InstallationRequest
    staging_id: str
    staging_root: Path
    _proof: object

    def trusted(self) -> bool:
        return self._proof is _TRUST_PROOF


@dataclass(frozen=True, slots=True)
class ResolvedRemoteInstallation:
    """Opaque Registry-selected remote endpoint without credentials."""

    selection: InstallationSelection
    endpoint: str
    transport: str
    _proof: object

    def trusted(self) -> bool:
        return self._proof is _TRUST_PROOF


def _argument_values(package: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for item in [*package.get("runtime_arguments", []), *package.get("package_arguments", [])]:
        if not isinstance(item, Mapping) or item.get("value_hint") is not None:
            raise PackageResolutionError("registry_argument_requires_runtime_input")
        value = item.get("value")
        if item.get("type") == "named":
            name = item.get("name")
            if not isinstance(name, str):
                raise PackageResolutionError("registry_argument_invalid")
            result.append(name)
            if value is not None and value not in {"true", ""}:
                result.append(str(value))
        elif item.get("type") == "positional" and isinstance(value, str):
            result.append(value)
        else:
            raise PackageResolutionError("registry_argument_invalid")
    return result


def _registry_argv(package: Mapping[str, Any]) -> list[str]:
    executable = package.get("runtime_hint")
    if not isinstance(executable, str) or not executable:
        executable = "npx" if package.get("registry_type") == "npm" else sys.executable
    return [executable, *_argument_values(package)]


class DefaultPackageBackend:
    """Resolve fixed Registry packages with local npm/pip and bounded HTTPS downloads."""

    def __init__(self, *, timeout_seconds: float = 120.0) -> None:
        self.timeout_seconds = timeout_seconds

    def resolve(
        self,
        selection: InstallationSelection,
        registry_detail: Mapping[str, Any],
        staging_directory: Path,
    ) -> InstallationRequest:
        assert selection.package_index is not None
        package = registry_detail["packages"][selection.package_index]
        package_type = package.get("registry_type")
        if package_type == "npm":
            return self._resolve_npm(selection, package, staging_directory)
        if package_type == "pypi":
            return self._resolve_pypi(selection, package, staging_directory)
        if package_type == "mcpb":
            return self._resolve_mcpb(selection, package, staging_directory)
        raise PackageResolutionError("registry_package_type_unsupported")

    @staticmethod
    def _run(argv: list[str], cwd: Path, environment: dict[str, str]) -> bytes:
        try:
            result = subprocess.run(
                argv,
                cwd=cwd,
                env=environment,
                shell=False,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PackageResolutionError("package_resolution_command_failed") from exc
        return result.stdout

    @staticmethod
    def _environment(staging: Path, executable: str) -> dict[str, str]:
        home = staging / ".home"
        cache = staging / ".npm-cache"
        temporary = staging / ".tmp"
        for path in (home, cache, temporary):
            path.mkdir(mode=0o700, exist_ok=True)
        resolved = shutil.which(executable)
        if resolved is None:
            raise PackageResolutionError("package_resolver_unavailable")
        return {
            "HOME": str(home),
            "PATH": str(Path(resolved).parent),
            "TMPDIR": str(temporary),
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "npm_config_cache": str(cache),
            "npm_config_ignore_scripts": "true",
        }

    def _resolve_npm(
        self, selection: InstallationSelection, package: Mapping[str, Any], staging: Path
    ) -> InstallationRequest:
        npm = shutil.which("npm")
        if npm is None:
            raise PackageResolutionError("package_resolver_unavailable")
        identifier, version = self._fixed_identity(package)
        source = str(package.get("registry_base_url") or "https://registry.npmjs.org")
        environment = self._environment(staging, "npm")
        project = {
            "name": "research-workbench-mcp-resolution",
            "private": True,
            "version": "0.0.0",
            "dependencies": {identifier: version},
        }
        self._exclusive_json(staging / "package.json", project)
        self._run(
            [
                npm,
                "install",
                "--package-lock-only",
                "--ignore-scripts",
                "--registry",
                source,
                "--cache",
                str(staging / ".npm-cache"),
            ],
            staging,
            environment,
        )
        lock_raw = self._bounded_read(staging / "package-lock.json", 8 * 1024 * 1024)
        try:
            lock = json.loads(lock_raw)
            rows = lock["packages"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise PackageResolutionError("npm_lock_invalid") from exc
        artifacts: list[PackageArtifact] = []
        resolved_identities: dict[tuple[str, str], tuple[str, str]] = {}
        if not isinstance(rows, dict):
            raise PackageResolutionError("npm_lock_invalid")
        for key, row in rows.items():
            if key == "" or not isinstance(row, dict):
                continue
            name = row.get("name") or str(key).rsplit("node_modules/", 1)[-1]
            resolved = row.get("resolved")
            integrity = row.get("integrity")
            dependency_version = row.get("version")
            if not all(
                isinstance(value, str) and value
                for value in (name, resolved, integrity, dependency_version)
            ):
                raise PackageResolutionError("npm_lock_resolution_incomplete")
            assert isinstance(name, str)
            assert isinstance(resolved, str)
            assert isinstance(integrity, str)
            assert isinstance(dependency_version, str)
            identity = (name, dependency_version)
            location = (resolved, integrity)
            if identity in resolved_identities:
                if resolved_identities[identity] != location:
                    raise PackageResolutionError("npm_lock_identity_conflict")
                continue
            resolved_identities[identity] = location
            payload = self._download_https(resolved)
            filename = f"npm-{len(artifacts):04d}-{hashlib.sha256(payload).hexdigest()[:16]}.tgz"
            self._exclusive_bytes(staging / filename, payload)
            artifacts.append(
                PackageArtifact(
                    name=name,
                    version=dependency_version,
                    filename=filename,
                    sha256=hashlib.sha256(payload).hexdigest(),
                    integrity=integrity,
                )
            )
        return self._request(
            selection,
            package,
            source,
            artifacts,
            package_lock_sha256=hashlib.sha256(lock_raw).hexdigest(),
        )

    def _resolve_pypi(
        self, selection: InstallationSelection, package: Mapping[str, Any], staging: Path
    ) -> InstallationRequest:
        identifier, version = self._fixed_identity(package)
        source = str(package.get("registry_base_url") or "https://pypi.org/simple")
        environment = self._environment(staging, sys.executable)
        self._run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--only-binary=:all:",
                "--dest",
                str(staging),
                "--index-url",
                source,
                f"{identifier}=={version}",
            ],
            staging,
            environment,
        )
        artifacts: list[PackageArtifact] = []
        for path in sorted(staging.glob("*.whl")):
            raw = self._bounded_read(path, MAX_ARTIFACT_BYTES)
            name, dependency_version = self._wheel_identity(raw)
            artifacts.append(
                PackageArtifact(
                    name=name,
                    version=dependency_version,
                    filename=path.name,
                    sha256=hashlib.sha256(raw).hexdigest(),
                )
            )
        if not artifacts:
            raise PackageResolutionError("pypi_wheel_resolution_empty")
        return self._request(selection, package, source, artifacts)

    def _resolve_mcpb(
        self, selection: InstallationSelection, package: Mapping[str, Any], staging: Path
    ) -> InstallationRequest:
        identifier, _ = self._fixed_identity(package)
        expected = package.get("file_sha256")
        if not isinstance(expected, str):
            raise PackageResolutionError("mcpb_registry_digest_missing")
        payload = self._download_https(identifier)
        digest = hashlib.sha256(payload).hexdigest()
        if not hmac.compare_digest(digest, expected):
            raise PackageResolutionError("mcpb_registry_digest_mismatch")
        filename = f"server-{digest[:16]}.mcpb"
        self._exclusive_bytes(staging / filename, payload)
        artifact = PackageArtifact(
            name=selection.server_name,
            version=selection.server_version,
            filename=filename,
            sha256=digest,
        )
        return self._request(
            selection,
            package,
            str(
                package.get("registry_base_url")
                or urlsplit(identifier)._replace(path="", query="", fragment="").geturl()
            ),
            [artifact],
            registry_sha256=digest,
            archive_path=str(staging / filename),
        )

    def _download_https(self, url: str) -> bytes:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise PackageResolutionError("artifact_url_insecure")
        try:
            import httpx

            with httpx.stream(
                "GET",
                url,
                follow_redirects=False,
                timeout=self.timeout_seconds,
                trust_env=False,
            ) as response:
                if response.status_code != 200:
                    raise PackageResolutionError("artifact_download_failed")
                payload = bytearray()
                for chunk in response.iter_bytes():
                    payload.extend(chunk)
                    if len(payload) > MAX_ARTIFACT_BYTES:
                        raise PackageResolutionError("artifact_size_limit")
        except PackageResolutionError:
            raise
        except Exception as exc:
            raise PackageResolutionError("artifact_download_failed") from exc
        return bytes(payload)

    @staticmethod
    def _fixed_identity(package: Mapping[str, Any]) -> tuple[str, str]:
        identifier, version = package.get("identifier"), package.get("version")
        if not isinstance(identifier, str) or not isinstance(version, str):
            raise PackageResolutionError("registry_package_not_fixed")
        return identifier, version

    @staticmethod
    def _request(
        selection: InstallationSelection,
        package: Mapping[str, Any],
        source: str,
        artifacts: list[PackageArtifact],
        **extra: Any,
    ) -> InstallationRequest:
        identifier, version = DefaultPackageBackend._fixed_identity(package)
        return InstallationRequest(
            registry_id=selection.registry_id,
            server_name=selection.server_name,
            server_version=selection.server_version,
            package_type=package["registry_type"],
            package_identifier=identifier,
            package_version=version,
            package_source=source,
            argv=_registry_argv(package),
            environment_names=list(selection.environment_names),
            artifacts=artifacts,
            **extra,
        )

    @staticmethod
    def _exclusive_bytes(path: Path, raw: bytes) -> None:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise PackageResolutionError("staging_write_failed") from exc

    @classmethod
    def _exclusive_json(cls, path: Path, value: object) -> None:
        cls._exclusive_bytes(path, json.dumps(value, sort_keys=True).encode("utf-8"))

    @staticmethod
    def _bounded_read(path: Path, limit: int) -> bytes:
        try:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "rb") as stream:
                raw = stream.read(limit + 1)
        except OSError as exc:
            raise PackageResolutionError("resolved_artifact_unavailable") from exc
        if len(raw) > limit:
            raise PackageResolutionError("artifact_size_limit")
        return raw

    @staticmethod
    def _wheel_identity(raw: bytes) -> tuple[str, str]:
        try:
            from io import BytesIO

            with zipfile.ZipFile(BytesIO(raw)) as archive:
                names = [
                    name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
                ]
                if len(names) != 1:
                    raise PackageResolutionError("pypi_wheel_metadata_invalid")
                metadata = BytesParser().parsebytes(archive.read(names[0]))
        except PackageResolutionError:
            raise
        except (OSError, KeyError, zipfile.BadZipFile) as exc:
            raise PackageResolutionError("pypi_wheel_invalid") from exc
        name, version = metadata.get("Name"), metadata.get("Version")
        if not name or not version:
            raise PackageResolutionError("pypi_wheel_metadata_invalid")
        return name, version


def _normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _safe_file(directory: Path, filename: str) -> tuple[int, os.stat_result]:
    try:
        root = directory.resolve(strict=True)
        path = directory / filename
        if path.parent.resolve(strict=True) != root:
            raise PackageResolutionError("staged_artifact_path_unsafe")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_size > MAX_ARTIFACT_BYTES
        ):
            os.close(descriptor)
            raise PackageResolutionError("staged_artifact_unsafe")
        return descriptor, info
    except PackageResolutionError:
        raise
    except OSError as exc:
        raise PackageResolutionError("staged_artifact_unavailable") from exc


def _digest_file(directory: Path, filename: str) -> tuple[str, int]:
    descriptor, info = _safe_file(directory, filename)
    digest = hashlib.sha256()
    try:
        with os.fdopen(descriptor, "rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise PackageResolutionError("staged_artifact_unavailable") from exc
    return digest.hexdigest(), info.st_size


def _verify_sri(directory: Path, artifact: PackageArtifact) -> None:
    if artifact.integrity is None:
        raise PackageResolutionError("npm_artifact_integrity_missing")
    try:
        algorithm, encoded = artifact.integrity.split("-", 1)
        expected = base64.b64decode(encoded, validate=True)
        digest = hashlib.new(algorithm)
    except (ValueError, TypeError) as exc:
        raise PackageResolutionError("npm_artifact_integrity_invalid") from exc
    descriptor, _ = _safe_file(directory, artifact.filename)
    with os.fdopen(descriptor, "rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    if not hmac.compare_digest(digest.digest(), expected):
        raise PackageResolutionError("npm_artifact_integrity_mismatch")


class PackageResolver:
    """Convert minimal Registry identity into verified private staged artifacts."""

    def __init__(
        self,
        staging_root: Path,
        *,
        registry_lookup: Callable[[InstallationSelection], Mapping[str, Any]] | None = None,
        backend: ResolutionBackend | None = None,
    ) -> None:
        self.staging_root = Path(staging_root)
        self.registry_lookup = registry_lookup
        self.backend = backend or DefaultPackageBackend()

    def resolve(
        self,
        selection: InstallationSelection,
        registry_detail: Mapping[str, Any] | None = None,
    ) -> ResolvedInstallation | ResolvedRemoteInstallation:
        selection = InstallationSelection.model_validate(selection.model_dump(mode="python"))
        if registry_detail is None:
            if self.registry_lookup is None:
                raise PackageResolutionError("trusted_registry_detail_required")
            detail = self.registry_lookup(selection)
        else:
            detail = registry_detail
        self._validate_registry_identity(selection, detail)
        if selection.remote_index is not None:
            return self._resolve_remote(selection, detail)
        staging_id = f"mcp-stage-{uuid4().hex}"
        staging_directory = self._new_staging_directory(staging_id)
        try:
            request = self.backend.resolve(selection, detail, staging_directory)
            request = InstallationRequest.model_validate(request.model_dump(mode="python"))
            self._validate_request_identity(selection, detail, request)
            request = self._verify_staged_request(staging_directory, request)
        except Exception:
            log.warning(
                "mcp_package_resolution_failed", error_type="resolution_failed", status="failed"
            )
            raise
        log.info("mcp_package_resolution_ready", status="verified")
        return ResolvedInstallation(  # type: ignore[call-arg]
            request, staging_id, self.staging_root, _TRUST_PROOF
        )

    @staticmethod
    def _resolve_remote(
        selection: InstallationSelection, detail: Mapping[str, Any]
    ) -> ResolvedRemoteInstallation:
        assert selection.remote_index is not None
        if selection.environment_names:
            raise PackageResolutionError("remote_environment_passthrough_forbidden")
        remotes = detail.get("remotes")
        if not isinstance(remotes, list) or selection.remote_index >= len(remotes):
            raise PackageResolutionError("registry_remote_not_found")
        remote = remotes[selection.remote_index]
        if not isinstance(remote, Mapping) or remote.get("type") != "streamable-http":
            raise PackageResolutionError("registry_remote_transport_unsupported")
        endpoint = remote.get("url")
        if not isinstance(endpoint, str):
            raise PackageResolutionError("registry_remote_endpoint_invalid")
        parsed = urlsplit(endpoint)
        loopback = parsed.hostname in {"127.0.0.1", "::1"}
        if (
            parsed.scheme not in ({"https"} if not loopback else {"http", "https"})
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise PackageResolutionError("registry_remote_endpoint_insecure")
        return ResolvedRemoteInstallation(  # type: ignore[call-arg]
            selection, endpoint, "streamable-http", _TRUST_PROOF
        )

    @staticmethod
    def _validate_registry_identity(
        selection: InstallationSelection, detail: Mapping[str, Any]
    ) -> None:
        if not isinstance(detail, Mapping) or (
            detail.get("registry_id"),
            detail.get("name"),
            detail.get("version"),
        ) != (selection.registry_id, selection.server_name, selection.server_version):
            raise PackageResolutionError("registry_identity_mismatch")
        if not isinstance(detail.get("packages"), list) or not isinstance(
            detail.get("remotes"), list
        ):
            raise PackageResolutionError("registry_targets_missing")
        if selection.package_index is not None:
            packages = detail["packages"]
            if selection.package_index >= len(packages):
                raise PackageResolutionError("registry_package_not_found")
            package = packages[selection.package_index]
            if (
                not isinstance(package, Mapping)
                or package.get("immutable_reference") is not True
                or package.get("package_type_supported") is not True
                or package.get("transport_type") != "stdio"
            ):
                raise PackageResolutionError("registry_package_not_installable")
            declared = {
                item.get("name")
                for item in package.get("environment_variables", [])
                if isinstance(item, Mapping) and isinstance(item.get("name"), str)
            }
            if set(selection.environment_names) != declared:
                raise PackageResolutionError("registry_environment_names_mismatch")

    @staticmethod
    def _validate_request_identity(
        selection: InstallationSelection,
        detail: Mapping[str, Any],
        request: InstallationRequest,
    ) -> None:
        if (request.registry_id, request.server_name, request.server_version) != (
            selection.registry_id,
            selection.server_name,
            selection.server_version,
        ):
            raise PackageResolutionError("resolved_identity_mismatch")
        assert selection.package_index is not None
        item = detail["packages"][selection.package_index]
        if not (
            isinstance(item, Mapping)
            and item.get("registry_type") == request.package_type
            and item.get("identifier") == request.package_identifier
            and item.get("version") == request.package_version
            and item.get("immutable_reference") is True
            and item.get("package_type_supported") is True
            and list(request.environment_names) == list(selection.environment_names)
        ):
            raise PackageResolutionError("resolved_package_not_in_registry")

    def _new_staging_directory(self, staging_id: str) -> Path:
        try:
            if self.staging_root.exists() or self.staging_root.is_symlink():
                if self.staging_root.is_symlink() or not self.staging_root.is_dir():
                    raise PackageResolutionError("staging_root_unsafe")
                info = self.staging_root.stat()
                if info.st_mode & 0o077:
                    raise PackageResolutionError("staging_root_not_private")
            else:
                self.staging_root.mkdir(parents=True, mode=0o700)
            directory = self.staging_root / staging_id
            directory.mkdir(mode=0o700)
            return directory
        except PackageResolutionError:
            raise
        except OSError as exc:
            raise PackageResolutionError("staging_unavailable") from exc

    def _verify_staged_request(
        self, staging_directory: Path, request: InstallationRequest
    ) -> InstallationRequest:
        verified: list[PackageArtifact] = []
        for artifact in request.artifacts:
            digest, size = _digest_file(staging_directory, artifact.filename)
            if not hmac.compare_digest(digest, artifact.sha256):
                raise PackageResolutionError("staged_artifact_digest_mismatch")
            verified.append(artifact.model_copy(update={"size_bytes": size}, deep=True))
        request = request.model_copy(update={"artifacts": verified}, deep=True)
        if request.package_type == "npm":
            return self._verify_npm(staging_directory, request)
        if request.package_type == "pypi":
            return self._verify_pypi(staging_directory, request)
        artifact = request.artifacts[0]
        if request.registry_sha256 != artifact.sha256:
            raise PackageResolutionError("mcpb_registry_digest_mismatch")
        return request.model_copy(
            update={"archive_path": str(staging_directory / artifact.filename)}, deep=True
        )

    def _verify_npm(
        self, staging_directory: Path, request: InstallationRequest
    ) -> InstallationRequest:
        lock_digest, lock_size = _digest_file(staging_directory, "package-lock.json")
        if lock_size > 8 * 1024 * 1024 or request.package_lock_sha256 != lock_digest:
            raise PackageResolutionError("npm_lock_digest_mismatch")
        try:
            lock = json.loads((staging_directory / "package-lock.json").read_bytes())
            packages = lock["packages"]
            if not isinstance(packages, dict):
                raise TypeError("packages")
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PackageResolutionError("npm_lock_invalid") from exc
        locked: dict[tuple[str, str], str | None] = {}
        for key, value in packages.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                raise PackageResolutionError("npm_lock_invalid")
            if key == "":
                continue
            name = value.get("name")
            if name is None and key.startswith("node_modules/"):
                name = key.rsplit("node_modules/", 1)[-1]
            version = value.get("version")
            if isinstance(name, str) and isinstance(version, str):
                locked[(name, version)] = value.get("integrity")
        artifacts = {(item.name, item.version): item for item in request.artifacts}
        if set(locked) != set(artifacts):
            raise PackageResolutionError("npm_lock_closure_mismatch")
        for identity, artifact in artifacts.items():
            _verify_sri(staging_directory, artifact)
            lock_integrity = locked[identity]
            if lock_integrity is not None and lock_integrity != artifact.integrity:
                raise PackageResolutionError("npm_lock_integrity_mismatch")
            self._reject_npm_hooks(staging_directory, artifact)
        return request

    @staticmethod
    def _reject_npm_hooks(staging_directory: Path, artifact: PackageArtifact) -> None:
        descriptor, _ = _safe_file(staging_directory, artifact.filename)
        try:
            with (
                os.fdopen(descriptor, "rb") as stream,
                tarfile.open(fileobj=stream, mode="r:gz") as archive,
            ):
                members = archive.getmembers()
                if len(members) > MAX_ARCHIVE_MEMBERS:
                    raise PackageResolutionError("npm_archive_member_limit")
                manifests = [item for item in members if item.name == "package/package.json"]
                if len(manifests) != 1 or manifests[0].size > MAX_METADATA_BYTES:
                    raise PackageResolutionError("npm_package_manifest_invalid")
                extracted = archive.extractfile(manifests[0])
                if extracted is None:
                    raise PackageResolutionError("npm_package_manifest_invalid")
                package = json.loads(extracted.read(MAX_METADATA_BYTES + 1))
        except PackageResolutionError:
            raise
        except (OSError, tarfile.TarError, ValueError, json.JSONDecodeError) as exc:
            raise PackageResolutionError("npm_package_archive_invalid") from exc
        scripts = package.get("scripts", {})
        if not isinstance(scripts, dict) or any(scripts.get(name) for name in LIFECYCLE_SCRIPTS):
            raise PackageResolutionError("package_lifecycle_hooks_forbidden")

    def _verify_pypi(
        self, staging_directory: Path, request: InstallationRequest
    ) -> InstallationRequest:
        identities: dict[str, PackageArtifact] = {}
        dependencies: list[tuple[str, str | None]] = []
        for artifact in request.artifacts:
            name, version, requires = self._wheel_metadata(staging_directory, artifact)
            if (
                _normalize_name(name) != _normalize_name(artifact.name)
                or version != artifact.version
            ):
                raise PackageResolutionError("pypi_wheel_identity_mismatch")
            normalized = _normalize_name(name)
            if normalized in identities:
                raise PackageResolutionError("pypi_wheel_duplicate_distribution")
            identities[normalized] = artifact
            dependencies.extend(self._parse_requirements(requires))
        for name, exact_version in dependencies:
            dependency = identities.get(name)
            if dependency is None or (
                exact_version is not None and dependency.version != exact_version
            ):
                raise PackageResolutionError("pypi_wheel_closure_mismatch")
        root = identities.get(_normalize_name(request.package_identifier))
        if root is None or root.version != request.package_version:
            raise PackageResolutionError("root_package_artifact_missing")
        requirements = "".join(
            f"./{item.filename} --hash=sha256:{item.sha256}\n" for item in request.artifacts
        ).encode("utf-8")
        path = staging_directory / "requirements.txt"
        try:
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(requirements)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise PackageResolutionError("pypi_requirements_write_failed") from exc
        return request.model_copy(
            update={"requirements_sha256": hashlib.sha256(requirements).hexdigest()}, deep=True
        )

    @staticmethod
    def _wheel_metadata(
        staging_directory: Path, artifact: PackageArtifact
    ) -> tuple[str, str, list[str]]:
        descriptor, _ = _safe_file(staging_directory, artifact.filename)
        try:
            with os.fdopen(descriptor, "rb") as stream, zipfile.ZipFile(stream) as wheel:
                names = wheel.namelist()
                metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
                wheel_names = [name for name in names if name.endswith(".dist-info/WHEEL")]
                if (
                    len(names) > MAX_ARCHIVE_MEMBERS
                    or len(metadata_names) != 1
                    or len(wheel_names) != 1
                ):
                    raise PackageResolutionError("pypi_wheel_metadata_invalid")
                metadata_raw = wheel.read(metadata_names[0], pwd=None)
                wheel_raw = wheel.read(wheel_names[0], pwd=None)
                if len(metadata_raw) > MAX_METADATA_BYTES or len(wheel_raw) > MAX_METADATA_BYTES:
                    raise PackageResolutionError("pypi_wheel_metadata_invalid")
        except PackageResolutionError:
            raise
        except (OSError, KeyError, zipfile.BadZipFile, RuntimeError) as exc:
            raise PackageResolutionError("pypi_wheel_invalid") from exc
        message = BytesParser().parsebytes(metadata_raw)
        name = message.get("Name")
        version = message.get("Version")
        if not name or not version:
            raise PackageResolutionError("pypi_wheel_metadata_invalid")
        tags = [
            line[5:].strip()
            for line in wheel_raw.decode("utf-8").splitlines()
            if line.startswith("Tag:")
        ]
        if not tags or not any(tag in {"py3-none-any", "py2.py3-none-any"} for tag in tags):
            raise PackageResolutionError("pypi_wheel_platform_unsupported")
        return name, version, message.get_all("Requires-Dist", [])

    @staticmethod
    def _parse_requirements(values: list[str]) -> list[tuple[str, str | None]]:
        parsed: list[tuple[str, str | None]] = []
        pattern = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\s*\(==\s*([^\s)]+)\s*\))?$")
        for value in values:
            if ";" in value or "@" in value or "[" in value:
                raise PackageResolutionError("pypi_dependency_marker_unsupported")
            match = pattern.fullmatch(value.strip())
            if match is None:
                raise PackageResolutionError("pypi_dependency_spec_unsupported")
            parsed.append((_normalize_name(match.group(1)), match.group(2)))
        return parsed
