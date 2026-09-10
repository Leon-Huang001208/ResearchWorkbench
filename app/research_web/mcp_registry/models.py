"""Strict public and upstream contracts for read-only MCP registries."""

from __future__ import annotations

import re
import unicodedata
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

REGISTRY_ID_PATTERN = r"^(official|local-[a-f0-9]{32})$"
SERVER_NAME_PATTERN = r"^[A-Za-z0-9.-]+/[A-Za-z0-9._-]+$"
FIXED_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
FIXED_PYPI_VERSION_PATTERN = re.compile(
    r"^(?:[0-9]+!)?[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?"
    r"(?:\.post[0-9]+)?(?:\.dev[0-9]+)?"
    r"(?:\+[a-z0-9]+(?:[.-][a-z0-9]+)*)?$",
    re.IGNORECASE,
)
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def _has_disallowed_control(value: str) -> bool:
    return any(unicodedata.category(char) in {"Cc", "Cs"} for char in value)


def safe_http_url(value: Any) -> str:
    """Return a canonical HTTP(S) URL without credentials, query, or fragment."""

    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("URL 长度非法")
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or _has_disallowed_control(value)
    ):
        raise ValueError("URL 必须为不含凭据、查询或片段的 HTTP(S) 地址")
    netloc = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, netloc, path, "", ""))


def safe_https_url(value: Any) -> str:
    """Return a canonical HTTPS URL."""

    normalized = safe_http_url(value)
    if urlsplit(normalized).scheme != "https":
        raise ValueError("URL 必须使用 HTTPS")
    return normalized


def validate_registry_transport(base_url: str, auth_type: str) -> str:
    """Allow HTTPS, or unauthenticated HTTP on an explicit loopback host."""

    normalized = safe_http_url(base_url)
    parsed = urlsplit(normalized)
    if parsed.scheme == "https":
        return normalized
    explicit_loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if auth_type == "none" and explicit_loopback:
        return normalized
    raise ValueError("Registry 仅允许 HTTPS，或无认证的显式 loopback HTTP")


def safe_text(value: Any, *, maximum: int = 1000) -> str:
    if not isinstance(value, str):
        raise ValueError("文本字段类型非法")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or _has_disallowed_control(normalized):
        raise ValueError("文本字段为空、过长或包含控制字符")
    return normalized


class AuthNone(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["none"] = "none"


class AuthBearer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["bearer"]
    token: SecretStr | None = Field(default=None, min_length=1, max_length=8192, repr=False)


class AuthOAuth2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["oauth2"]
    authorization_url: str
    token_url: str
    client_id: str = Field(min_length=1, max_length=512)
    scopes: list[str] = Field(default_factory=list, max_length=32)
    access_token: SecretStr | None = Field(default=None, min_length=1, max_length=8192, repr=False)
    client_secret: SecretStr | None = Field(default=None, min_length=1, max_length=8192, repr=False)

    @field_validator("authorization_url", "token_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return safe_https_url(value)

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, value: str) -> str:
        return safe_text(value, maximum=512)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, values: list[str]) -> list[str]:
        result = []
        for value in values:
            normalized = safe_text(value, maximum=128)
            if not re.fullmatch(r"[A-Za-z0-9._:/-]+", normalized):
                raise ValueError("OAuth scope 格式非法")
            if normalized not in result:
                result.append(normalized)
        return result


RegistryAuth = Annotated[AuthNone | AuthBearer | AuthOAuth2, Field(discriminator="type")]


class RegistryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=80)
    base_url: str
    auth: RegistryAuth = Field(default_factory=AuthNone)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return safe_text(value, maximum=80)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return safe_http_url(value)

    @model_validator(mode="after")
    def validate_transport(self):
        self.base_url = validate_registry_transport(self.base_url, self.auth.type)
        return self


class RegistryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str | None = Field(default=None, min_length=1, max_length=80)
    base_url: str | None = None
    auth: RegistryAuth | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return safe_text(value, maximum=80) if value is not None else None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        return safe_http_url(value) if value is not None else None

    @model_validator(mode="after")
    def require_change(self):
        if self.name is None and self.base_url is None and self.auth is None:
            raise ValueError("更新至少包含一个字段")
        if self.base_url is not None and self.auth is not None:
            self.base_url = validate_registry_transport(self.base_url, self.auth.type)
        return self


class SyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    cursor: str | None = Field(default=None, max_length=4096)
    search: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=100, ge=1, le=100, strict=True)

    @field_validator("cursor", "search")
    @classmethod
    def reject_controls(cls, value: str | None) -> str | None:
        if value is not None and any(ord(char) < 32 for char in value):
            raise ValueError("分页或搜索参数包含控制字符")
        return value


class UpstreamMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    next_cursor: str | None = Field(default=None, alias="nextCursor", max_length=4096)
    count: int = Field(ge=0, le=10000, strict=True)

    @field_validator("next_cursor")
    @classmethod
    def validate_cursor(cls, value: str | None) -> str | None:
        if value is not None and any(ord(char) < 32 for char in value):
            raise ValueError("上游 cursor 包含控制字符")
        return value


class UpstreamList(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    servers: list[dict[str, Any]] = Field(max_length=500)
    metadata: UpstreamMetadata


def _safe_optional_text(value: Any, maximum: int) -> str | None:
    if value is None:
        return None
    return safe_text(value, maximum=maximum)


def _safe_repository(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {"url", "source", "id", "subfolder"}:
        raise ValueError("repository 格式非法")
    url = safe_http_url(value.get("url"))
    source = safe_text(value.get("source"), maximum=80)
    result = {"url": url, "source": source}
    for key, maximum in (("id", 256), ("subfolder", 512)):
        if value.get(key) is not None:
            result[key] = safe_text(value[key], maximum=maximum)
    return result


def _immutable_package_reference(
    registry_type: str, version: str | None, file_sha256: str | None
) -> bool:
    if registry_type == "npm":
        return version is not None and FIXED_SEMVER_PATTERN.fullmatch(version) is not None
    if registry_type == "pypi":
        return file_sha256 is not None or (
            version is not None and FIXED_PYPI_VERSION_PATTERN.fullmatch(version) is not None
        )
    if registry_type == "mcpb":
        return file_sha256 is not None and (
            version is None or FIXED_SEMVER_PATTERN.fullmatch(version) is not None
        )
    return False


def _safe_argument(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("type") not in {"named", "positional"}:
        raise ValueError("package argument 格式非法")
    kind = value["type"]
    result: dict[str, Any] = {"type": kind}
    if kind == "named":
        name = safe_text(value.get("name"), maximum=256)
        if any(char.isspace() for char in name):
            raise ValueError("package named argument 格式非法")
        result["name"] = name
    for source, target in (("value", "value"), ("valueHint", "value_hint")):
        if value.get(source) is not None:
            result[target] = safe_text(value[source], maximum=4096)
    if kind == "positional" and not any(key in result for key in ("value", "value_hint")):
        raise ValueError("package positional argument 缺少值")
    repeated = value.get("isRepeated", False)
    if type(repeated) is not bool:
        raise ValueError("package argument isRepeated 格式非法")
    result["is_repeated"] = repeated
    return result


def _safe_arguments(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError("package arguments 格式非法")
    return [_safe_argument(item) for item in value]


def _safe_environment_variables(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError("package environmentVariables 格式非法")
    result = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("package environment variable 格式非法")
        name = safe_text(item.get("name"), maximum=128)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None or name in seen:
            raise ValueError("package environment variable name 格式非法")
        seen.add(name)
        required = item.get("isRequired", False)
        secret = item.get("isSecret", False)
        if type(required) is not bool or type(secret) is not bool:
            raise ValueError("package environment variable flags 格式非法")
        format_name = item.get("format", "string")
        if format_name not in {"string", "number", "boolean", "filepath"}:
            raise ValueError("package environment variable format 格式非法")
        normalized: dict[str, Any] = {
            "name": name,
            "is_required": required,
            "is_secret": secret,
            "format": format_name,
        }
        if item.get("description") is not None:
            normalized["description"] = safe_text(item["description"], maximum=1000)
        # Registry-provided values are never persisted. Runtime values belong in
        # the dedicated credential/configuration boundary introduced in Phase 2B.
        result.append(normalized)
    return result


def _safe_packages(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError("packages 格式非法")
    result = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("package 格式非法")
        registry_type = safe_text(item.get("registryType"), maximum=64)
        identifier = safe_text(item.get("identifier"), maximum=2048)
        version = (
            safe_text(item["version"], maximum=255) if item.get("version") is not None else None
        )
        file_sha256 = (
            safe_text(item["fileSha256"], maximum=64)
            if item.get("fileSha256") is not None
            else None
        )
        if file_sha256 is not None and SHA256_PATTERN.fullmatch(file_sha256) is None:
            raise ValueError("package fileSha256 格式非法")
        transport = item.get("transport")
        if not isinstance(transport, dict) or transport.get("type") not in {
            "stdio",
            "sse",
            "streamable-http",
        }:
            raise ValueError("package transport 格式非法")
        normalized = {
            "registry_type": registry_type,
            "identifier": identifier,
            "version": version,
            "file_sha256": file_sha256,
            "transport_type": transport["type"],
            "runtime_arguments": _safe_arguments(item.get("runtimeArguments")),
            "package_arguments": _safe_arguments(item.get("packageArguments")),
            "environment_variables": _safe_environment_variables(item.get("environmentVariables")),
            "package_type_supported": registry_type in {"npm", "pypi", "mcpb"},
            "immutable_reference": _immutable_package_reference(
                registry_type, version, file_sha256
            ),
        }
        if item.get("registryBaseUrl") is not None:
            normalized["registry_base_url"] = safe_http_url(item["registryBaseUrl"])
        if item.get("runtimeHint") is not None:
            runtime_hint = safe_text(item["runtimeHint"], maximum=128)
            if re.fullmatch(r"[A-Za-z0-9._/-]+", runtime_hint) is None:
                raise ValueError("package runtimeHint 格式非法")
            normalized["runtime_hint"] = runtime_hint
        result.append({key: item for key, item in normalized.items() if item is not None})
    return result


def _safe_remotes(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError("remotes 格式非法")
    result = []
    for item in value:
        if not isinstance(item, dict) or item.get("type") not in {"sse", "streamable-http"}:
            raise ValueError("remote transport 格式非法")
        result.append({"type": item["type"], "url": safe_http_url(item.get("url"))})
    return result


def normalize_upstream_server(registry_id: str, wrapper: dict[str, Any]) -> dict[str, Any]:
    """Project one untrusted Registry response into a bounded plain-text record."""

    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("server"), dict):
        raise ValueError("server wrapper 格式非法")
    server = wrapper["server"]
    name = safe_text(server.get("name"), maximum=200)
    version = safe_text(server.get("version"), maximum=255)
    namespace, server_part = name.split("/", 1) if "/" in name else ("", "")
    if (
        not re.fullmatch(SERVER_NAME_PATTERN, name)
        or any(not label or label in {".", ".."} for label in namespace.split("."))
        or server_part in {".", ".."}
        or "/" in version
        or version == "latest"
    ):
        raise ValueError("server identity 格式非法")
    description = _safe_optional_text(server.get("description"), 10_000)
    if description is None:
        raise ValueError("server description 缺失")
    result: dict[str, Any] = {
        "registry_id": registry_id,
        "name": name,
        "version": version,
        "identity": [registry_id, name, version],
        "title": _safe_optional_text(server.get("title"), 1000) or name,
        "description": description,
        "repository": _safe_repository(server.get("repository")),
        "packages": _safe_packages(server.get("packages")),
        "remotes": _safe_remotes(server.get("remotes")),
    }
    metadata = wrapper.get("_meta")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("registry metadata 格式非法")
    official_value = (metadata or {}).get("io.modelcontextprotocol.registry/official", {})
    if official_value is not None and not isinstance(official_value, dict):
        raise ValueError("official metadata 格式非法")
    official = official_value or {}
    result["status"] = safe_text(official.get("status", "unknown"), maximum=64)
    for source_key, target_key in (
        ("publishedAt", "published_at"),
        ("updatedAt", "updated_at"),
        ("statusChangedAt", "status_changed_at"),
    ):
        if official.get(source_key) is not None:
            result[target_key] = safe_text(official[source_key], maximum=128)
    result["is_latest"] = official.get("isLatest") is True
    return result
