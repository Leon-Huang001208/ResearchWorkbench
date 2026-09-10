"""Strict non-secret contracts for immutable MCP installation plans."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import unicodedata
from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.research_web.mcp_registry.models import (
    FIXED_PYPI_VERSION_PATTERN,
    FIXED_SEMVER_PATTERN,
    REGISTRY_ID_PATTERN,
    SERVER_NAME_PATTERN,
)

PackageType = Literal["npm", "pypi", "mcpb"]
MAX_ARGUMENT_LENGTH = 64 * 1024
MAX_TOTAL_ARGUMENT_BYTES = 256 * 1024
SAFE_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+@-]{0,254}$")
FIXED_GENERIC_VERSION = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._+!-]{0,254})$")


class InstallationSelection(BaseModel):
    """The complete browser-facing installation request."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    registry_id: str = Field(pattern=REGISTRY_ID_PATTERN)
    server_name: str = Field(pattern=SERVER_NAME_PATTERN)
    server_version: str = Field(min_length=1, max_length=255)
    package_index: int | None = Field(default=None, ge=0, le=63, strict=True)
    remote_index: int | None = Field(default=None, ge=0, le=63, strict=True)
    environment_names: list[str] = Field(default_factory=list, max_length=128)

    @field_validator("server_version")
    @classmethod
    def validate_server_version(cls, value: str) -> str:
        normalized = _safe_text(value, maximum=255)
        if FIXED_SEMVER_PATTERN.fullmatch(normalized) is None:
            raise ValueError("server_version_not_fixed")
        return normalized

    @field_validator("environment_names")
    @classmethod
    def validate_environment_names(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            if SAFE_ENVIRONMENT_NAME.fullmatch(value) is None:
                raise ValueError("environment_name_invalid")
            if value not in result:
                result.append(value)
        return result

    @model_validator(mode="after")
    def select_exactly_one_target(self) -> InstallationSelection:
        if (self.package_index is None) == (self.remote_index is None):
            raise ValueError("installation_target_selection_required")
        return self


def _has_control(value: str) -> bool:
    return any(unicodedata.category(char) in {"Cc", "Cs"} for char in value)


def _safe_text(value: str, *, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or _has_control(normalized):
        raise ValueError("unsafe_text")
    return normalized


def _fixed_version(value: str, package_type: PackageType) -> str:
    normalized = _safe_text(value, maximum=255)
    pattern = FIXED_PYPI_VERSION_PATTERN if package_type == "pypi" else FIXED_SEMVER_PATTERN
    if pattern.fullmatch(normalized) is None:
        raise ValueError("package_version_not_fixed")
    return normalized


class PackageArtifact(BaseModel):
    """One fully resolved package artifact, including transitive dependencies."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    name: str = Field(min_length=1, max_length=512)
    version: str = Field(min_length=1, max_length=255)
    filename: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    integrity: str | None = Field(default=None, min_length=8, max_length=512)
    size_bytes: int | None = Field(default=None, ge=1, le=256 * 1024 * 1024, strict=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _safe_text(value, maximum=512)

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        normalized = _safe_text(value, maximum=255)
        if FIXED_GENERIC_VERSION.fullmatch(normalized) is None or any(
            marker in normalized.lower() for marker in ("latest", "*", "^", "~", ">", "<", "||")
        ):
            raise ValueError("artifact_version_not_fixed")
        return normalized

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        normalized = _safe_text(value, maximum=255)
        if SAFE_FILENAME.fullmatch(normalized) is None:
            raise ValueError("unsafe_artifact_filename")
        return normalized

    @field_validator("integrity")
    @classmethod
    def validate_integrity(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = _safe_text(value, maximum=512)
        if re.fullmatch(r"sha(?:256|384|512)-[A-Za-z0-9+/]+={0,2}", normalized) is None:
            raise ValueError("artifact_integrity_invalid")
        return normalized


class InstallationRequest(BaseModel):
    """Internal resolver output; browser routes must use InstallationSelection."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    registry_id: str = Field(pattern=REGISTRY_ID_PATTERN)
    server_name: str = Field(pattern=SERVER_NAME_PATTERN)
    server_version: str = Field(min_length=1, max_length=255)
    package_type: PackageType
    package_identifier: str = Field(min_length=1, max_length=2048)
    package_version: str = Field(min_length=1, max_length=255)
    package_source: str = Field(min_length=1, max_length=2048)
    argv: list[str] = Field(min_length=1, max_length=128)
    environment_names: list[str] = Field(default_factory=list, max_length=128)
    inherit_environment: Literal[False] = False
    lifecycle_hooks: list[str] = Field(default_factory=list, max_length=32)
    artifacts: list[PackageArtifact] = Field(min_length=1, max_length=1024)
    package_lock_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    archive_path: str | None = Field(default=None, min_length=1, max_length=4096)
    registry_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    requirements_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @field_validator("server_version")
    @classmethod
    def validate_server_version(cls, value: str) -> str:
        normalized = _safe_text(value, maximum=255)
        if FIXED_SEMVER_PATTERN.fullmatch(normalized) is None:
            raise ValueError("server_version_not_fixed")
        return normalized

    @field_validator("package_identifier")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        normalized = _safe_text(value, maximum=2048)
        if any(char in normalized for char in ("\n", "\r", "\x00")):
            raise ValueError("unsafe_package_identifier")
        return normalized

    @field_validator("package_source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        normalized = _safe_text(value, maximum=2048)
        parsed = urlsplit(normalized)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("package_source_requires_https")
        host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        return urlunsplit(("https", host, parsed.path.rstrip("/"), "", ""))

    @field_validator("argv")
    @classmethod
    def validate_argv(cls, values: list[str]) -> list[str]:
        total = 0
        result: list[str] = []
        for value in values:
            if not isinstance(value, str) or not value or len(value) > MAX_ARGUMENT_LENGTH:
                raise ValueError("argv_invalid")
            if "\x00" in value or "\r" in value or "\n" in value:
                raise ValueError("argv_control_character")
            total += len(value.encode("utf-8"))
            result.append(value)
        if total > MAX_TOTAL_ARGUMENT_BYTES:
            raise ValueError("argv_too_large")
        executable = result[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
        if executable in {
            "sh",
            "bash",
            "zsh",
            "fish",
            "cmd",
            "cmd.exe",
            "powershell",
            "powershell.exe",
            "pwsh",
            "pwsh.exe",
        }:
            raise ValueError("shell_executable_forbidden")
        return result

    @field_validator("environment_names")
    @classmethod
    def validate_environment_names(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            if SAFE_ENVIRONMENT_NAME.fullmatch(value) is None:
                raise ValueError("environment_name_invalid")
            if value not in result:
                result.append(value)
        return result

    @field_validator("lifecycle_hooks")
    @classmethod
    def validate_lifecycle_hooks(cls, values: list[str]) -> list[str]:
        return [_safe_text(value, maximum=128) for value in values]

    @model_validator(mode="after")
    def validate_package_fields(self) -> InstallationRequest:
        object.__setattr__(
            self, "package_version", _fixed_version(self.package_version, self.package_type)
        )
        if self.package_type == "mcpb":
            if self.archive_path is None or self.registry_sha256 is None:
                raise ValueError("mcpb_archive_metadata_required")
        elif self.archive_path is not None or self.registry_sha256 is not None:
            raise ValueError("archive_metadata_only_for_mcpb")
        if self.package_type != "pypi" and self.requirements_sha256 is not None:
            raise ValueError("requirements_metadata_only_for_pypi")
        return self


class InstallationPlan(BaseModel):
    """Canonical package plan shown in full before confirmation."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    target_kind: Literal["local"] = "local"
    registry_id: str
    server_name: str
    server_version: str
    package_type: PackageType
    staging_id: str = Field(pattern=r"^mcp-stage-[a-f0-9]{32}$")
    package_identifier: str
    package_version: str
    package_source: str
    argv: list[str]
    install_argv: list[str]
    environment_names: list[str]
    artifacts: list[PackageArtifact]
    package_lock_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    registry_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    requirements_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    canonical_summary: dict[str, Any]
    summary_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    def assert_integrity(self) -> None:
        """Reject any deep mutation that happened after the preview was issued."""
        expected = {
            "schema_version": 1,
            "target_kind": self.target_kind,
            "registry_id": self.registry_id,
            "server_name": self.server_name,
            "server_version": self.server_version,
            "package_type": self.package_type,
            "staging_id": self.staging_id,
            "package_identifier": self.package_identifier,
            "package_version": self.package_version,
            "package_source": self.package_source,
            "argv": list(self.argv),
            "install_argv": list(self.install_argv),
            "environment_names": list(self.environment_names),
            "artifacts": [
                artifact.model_dump(mode="json", exclude_none=False) for artifact in self.artifacts
            ],
            "package_lock_sha256": self.package_lock_sha256,
            "registry_sha256": self.registry_sha256,
            "requirements_sha256": self.requirements_sha256,
        }
        raw = json.dumps(
            expected,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        if expected != self.canonical_summary or digest != self.summary_sha256:
            raise ValueError("installation_plan_digest_mismatch")


def _canonical_remote_endpoint(value: str) -> str:
    normalized = _safe_text(value, maximum=2048)
    parsed = urlsplit(normalized)
    explicit_loopback = parsed.hostname in {"127.0.0.1", "::1"}
    if (
        parsed.scheme not in ({"https"} if not explicit_loopback else {"http", "https"})
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("remote_endpoint_insecure")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path.rstrip("/"), "", ""))


class RemoteInstallationPlan(BaseModel):
    """Immutable non-secret Streamable HTTP target selected from Registry detail."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    target_kind: Literal["remote"] = "remote"
    registry_id: str = Field(pattern=REGISTRY_ID_PATTERN)
    server_name: str = Field(pattern=SERVER_NAME_PATTERN)
    server_version: str = Field(min_length=1, max_length=255)
    remote_index: int = Field(ge=0, le=63, strict=True)
    transport: Literal["streamable-http"]
    endpoint: str
    environment_names: list[str] = Field(default_factory=list, max_length=128)
    canonical_summary: dict[str, Any]
    summary_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        return _canonical_remote_endpoint(value)

    @field_validator("environment_names")
    @classmethod
    def validate_environment_names(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            if SAFE_ENVIRONMENT_NAME.fullmatch(value) is None:
                raise ValueError("environment_name_invalid")
            if value not in result:
                result.append(value)
        return result

    def assert_integrity(self) -> None:
        expected = {
            "schema_version": 1,
            "target_kind": self.target_kind,
            "registry_id": self.registry_id,
            "server_name": self.server_name,
            "server_version": self.server_version,
            "remote_index": self.remote_index,
            "transport": self.transport,
            "endpoint": self.endpoint,
            "environment_names": list(self.environment_names),
        }
        raw = json.dumps(
            expected, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if expected != self.canonical_summary or not hmac.compare_digest(
            hashlib.sha256(raw).hexdigest(), self.summary_sha256
        ):
            raise ValueError("installation_plan_digest_mismatch")


InstallationPlanUnion = Annotated[
    InstallationPlan | RemoteInstallationPlan, Field(discriminator="target_kind")
]


class InstallationManifest(BaseModel):
    """Immutable non-secret installation record."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^mcp-installation-[a-f0-9]{32}$")
    created_at: datetime
    status: Literal["installed"] = "installed"
    plan: InstallationPlanUnion
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
