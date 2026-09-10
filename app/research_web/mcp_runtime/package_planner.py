"""Deterministic, no-execution package planning for MCP server installation."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath

from .models import (
    InstallationPlan,
    InstallationRequest,
    PackageArtifact,
    RemoteInstallationPlan,
)
from .package_resolver import (
    STAGING_ID,
    ResolvedInstallation,
    ResolvedRemoteInstallation,
)

MAX_MCPB_MEMBERS = 4096
MAX_MCPB_EXPANDED_BYTES = 256 * 1024 * 1024


class PackagePlanError(ValueError):
    """A stable install planning failure code."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _artifact_rows(artifacts: list[PackageArtifact]) -> list[dict[str, object]]:
    return [artifact.model_dump(mode="json", exclude_none=False) for artifact in artifacts]


class PackagePlanner:
    """Validate resolver output and create the exact user confirmation summary."""

    def plan(
        self, resolution: ResolvedInstallation | ResolvedRemoteInstallation
    ) -> InstallationPlan | RemoteInstallationPlan:
        if isinstance(resolution, ResolvedRemoteInstallation):
            return self._plan_remote(resolution)
        if not isinstance(resolution, ResolvedInstallation) or not resolution.trusted():
            raise PackagePlanError("trusted_resolution_required")
        if not STAGING_ID.fullmatch(resolution.staging_id):
            raise PackagePlanError("trusted_resolution_invalid")
        request = InstallationRequest.model_validate(
            resolution.request.model_dump(mode="python"), strict=True
        )
        if request.lifecycle_hooks:
            raise PackagePlanError("package_lifecycle_hooks_forbidden")
        if request.inherit_environment:
            raise PackagePlanError("implicit_environment_inheritance_forbidden")
        if not request.artifacts:
            raise PackagePlanError("package_artifacts_missing")
        if any(artifact.size_bytes is None for artifact in request.artifacts):
            raise PackagePlanError("verified_artifact_size_missing")

        self._assert_unique_artifacts(request.artifacts)
        if request.package_type == "npm":
            install_argv = self._plan_npm(request)
        elif request.package_type == "pypi":
            install_argv = self._plan_pypi(request)
        else:
            install_argv = self._plan_mcpb(request)

        summary = {
            "schema_version": 1,
            "target_kind": "local",
            "registry_id": request.registry_id,
            "server_name": request.server_name,
            "server_version": request.server_version,
            "package_type": request.package_type,
            "staging_id": resolution.staging_id,
            "package_identifier": request.package_identifier,
            "package_version": request.package_version,
            "package_source": request.package_source,
            "argv": list(request.argv),
            "install_argv": install_argv,
            "environment_names": list(request.environment_names),
            "artifacts": _artifact_rows(request.artifacts),
            "package_lock_sha256": request.package_lock_sha256,
            "registry_sha256": request.registry_sha256,
            "requirements_sha256": request.requirements_sha256,
        }
        digest = hashlib.sha256(_canonical_bytes(summary)).hexdigest()
        return InstallationPlan(
            target_kind="local",
            registry_id=request.registry_id,
            server_name=request.server_name,
            server_version=request.server_version,
            package_type=request.package_type,
            staging_id=resolution.staging_id,
            package_identifier=request.package_identifier,
            package_version=request.package_version,
            package_source=request.package_source,
            argv=list(request.argv),
            install_argv=install_argv,
            environment_names=list(request.environment_names),
            artifacts=list(request.artifacts),
            package_lock_sha256=request.package_lock_sha256,
            registry_sha256=request.registry_sha256,
            requirements_sha256=request.requirements_sha256,
            canonical_summary=summary,
            summary_sha256=digest,
        )

    @staticmethod
    def _plan_remote(resolution: ResolvedRemoteInstallation) -> RemoteInstallationPlan:
        if not resolution.trusted() or resolution.selection.remote_index is None:
            raise PackagePlanError("trusted_resolution_required")
        summary = {
            "schema_version": 1,
            "target_kind": "remote",
            "registry_id": resolution.selection.registry_id,
            "server_name": resolution.selection.server_name,
            "server_version": resolution.selection.server_version,
            "remote_index": resolution.selection.remote_index,
            "transport": resolution.transport,
            "endpoint": resolution.endpoint,
            "environment_names": list(resolution.selection.environment_names),
        }
        digest = hashlib.sha256(_canonical_bytes(summary)).hexdigest()
        return RemoteInstallationPlan(
            registry_id=resolution.selection.registry_id,
            server_name=resolution.selection.server_name,
            server_version=resolution.selection.server_version,
            remote_index=resolution.selection.remote_index,
            transport="streamable-http",
            endpoint=resolution.endpoint,
            environment_names=list(resolution.selection.environment_names),
            canonical_summary=summary,
            summary_sha256=digest,
        )

    @staticmethod
    def _assert_unique_artifacts(artifacts: list[PackageArtifact]) -> None:
        identities: set[tuple[str, str, str]] = set()
        for artifact in artifacts:
            identity = (artifact.name, artifact.version, artifact.filename)
            if identity in identities:
                raise PackagePlanError("duplicate_package_artifact")
            identities.add(identity)

    @staticmethod
    def _plan_npm(request: InstallationRequest) -> list[str]:
        if request.package_lock_sha256 is None:
            raise PackagePlanError("npm_lock_digest_missing")
        if any(artifact.integrity is None for artifact in request.artifacts):
            raise PackagePlanError("npm_artifact_integrity_missing")
        if not any(
            artifact.name == request.package_identifier
            and artifact.version == request.package_version
            for artifact in request.artifacts
        ):
            raise PackagePlanError("root_package_artifact_missing")
        return [
            "npm",
            "ci",
            "--ignore-scripts",
            "--offline",
            "--cache",
            ".npm-cache",
        ]

    @staticmethod
    def _plan_pypi(request: InstallationRequest) -> list[str]:
        if request.requirements_sha256 is None:
            raise PackagePlanError("pypi_requirements_digest_missing")
        if any(not artifact.filename.lower().endswith(".whl") for artifact in request.artifacts):
            raise PackagePlanError("pypi_wheel_required")
        if not any(
            artifact.name.replace("_", "-").lower()
            == request.package_identifier.replace("_", "-").lower()
            and artifact.version == request.package_version
            for artifact in request.artifacts
        ):
            raise PackagePlanError("root_package_artifact_missing")
        return [
            "python",
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            ".",
            "--require-hashes",
            "--no-deps",
            "-r",
            "requirements.txt",
            "--target",
            ".install",
        ]

    @staticmethod
    def _plan_mcpb(request: InstallationRequest) -> list[str]:
        if len(request.artifacts) != 1:
            raise PackagePlanError("mcpb_single_artifact_required")
        assert request.archive_path is not None
        assert request.registry_sha256 is not None
        path = Path(request.archive_path)
        if path.is_symlink() or not path.is_file() or path.name != request.artifacts[0].filename:
            raise PackagePlanError("mcpb_archive_unsafe")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != request.registry_sha256 or digest != request.artifacts[0].sha256:
            raise PackagePlanError("mcpb_digest_mismatch")
        try:
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                if not members or len(members) > MAX_MCPB_MEMBERS:
                    raise PackagePlanError("mcpb_archive_member_limit")
                expanded = 0
                normalized_names: set[str] = set()
                for member in members:
                    PackagePlanner._validate_mcpb_member(member)
                    normalized = member.filename.rstrip("/").casefold()
                    if normalized in normalized_names:
                        raise PackagePlanError("mcpb_archive_duplicate_path")
                    normalized_names.add(normalized)
                    expanded += member.file_size
                    if expanded > MAX_MCPB_EXPANDED_BYTES:
                        raise PackagePlanError("mcpb_archive_expanded_size_limit")
        except (OSError, zipfile.BadZipFile) as exc:
            raise PackagePlanError("mcpb_archive_invalid") from exc
        return ["internal:mcpb-safe-extract", request.artifacts[0].filename]

    @staticmethod
    def _validate_mcpb_member(member: zipfile.ZipInfo) -> None:
        name = member.filename
        if not name or len(name) > 1024 or "\\" in name or "\x00" in name:
            raise PackagePlanError("mcpb_archive_path_unsafe")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or any(":" in part for part in path.parts):
            raise PackagePlanError("mcpb_archive_path_unsafe")
        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise PackagePlanError("mcpb_archive_symlink_forbidden")
        file_type = stat.S_IFMT(mode)
        if file_type and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise PackagePlanError("mcpb_archive_special_file_forbidden")
        reserved = {
            "con",
            "prn",
            "aux",
            "nul",
            *(f"com{number}" for number in range(1, 10)),
            *(f"lpt{number}" for number in range(1, 10)),
        }
        for part in path.parts:
            basename = part.rstrip(". ").split(".", 1)[0].casefold()
            if part != part.rstrip(". ") or basename in reserved:
                raise PackagePlanError("mcpb_archive_path_unsafe")
