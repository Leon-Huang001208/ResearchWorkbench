"""Pure server.json generation and validation; never invokes publisher binaries."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .models import SERVER_NAME_PATTERN, safe_http_url, safe_text

SERVER_SCHEMA = "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
PUBLISHER_ARGV = {
    "validate": ["mcp-publisher", "validate", "server.json"],
    "publish": ["mcp-publisher", "publish", "server.json"],
}


class StdioTransport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["stdio"]


class NetworkTransport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["sse", "streamable-http"]
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return safe_http_url(value)


Transport = Annotated[StdioTransport | NetworkTransport, Field(discriminator="type")]


class PublisherRepository(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    url: str
    source: str = Field(min_length=1, max_length=80)
    id: str | None = Field(default=None, max_length=256)
    subfolder: str | None = Field(default=None, max_length=512)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return safe_http_url(value)


class PublisherPackage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    registry_type: str = Field(alias="registryType", min_length=1, max_length=64)
    registry_base_url: str | None = Field(default=None, alias="registryBaseUrl")
    identifier: str = Field(min_length=1, max_length=2048)
    version: str | None = Field(default=None, min_length=1, max_length=255)
    file_sha256: str | None = Field(default=None, alias="fileSha256", pattern=r"^[a-f0-9]{64}$")
    runtime_hint: str | None = Field(default=None, alias="runtimeHint", max_length=128)
    transport: Transport

    @field_validator("registry_base_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        return safe_http_url(value) if value is not None else None

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str | None) -> str | None:
        if value is not None and (
            value == "latest" or re.search(r"[~^*><=]", value) or value.endswith((".x", ".X"))
        ):
            raise ValueError("package version 必须为固定版本")
        return value

    @model_validator(mode="after")
    def require_immutable_npm_version(self):
        if self.registry_type == "npm" and self.version is None:
            raise ValueError("npm package 必须提供固定版本")
        return self


class PublisherProvidedMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    tool: Literal["research-workbench"]
    version: Literal["phase2a"]


class PublisherMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    publisher_provided: PublisherProvidedMetadata = Field(
        alias="io.modelcontextprotocol.registry/publisher-provided"
    )


class PublisherServer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)
    schema_url: str = Field(default=SERVER_SCHEMA, alias="$schema")
    name: str = Field(min_length=3, max_length=200, pattern=SERVER_NAME_PATTERN)
    description: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=100)
    website_url: str | None = Field(default=None, alias="websiteUrl")
    repository: PublisherRepository | None = None
    packages: list[PublisherPackage] = Field(default_factory=list, max_length=64)
    remotes: list[NetworkTransport] = Field(default_factory=list, max_length=64)
    metadata: PublisherMeta | None = Field(default=None, alias="_meta")

    @field_validator("schema_url", "website_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        return safe_http_url(value) if value is not None else None

    @field_validator("name", "description", "version", "title")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        return safe_text(value, maximum=255) if value is not None else None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        namespace, server = value.split("/", 1)
        if any(not label or label in {".", ".."} for label in namespace.split(".")):
            raise ValueError("server name 命名空间非法")
        if server in {".", ".."}:
            raise ValueError("server name 非法")
        return value

    @model_validator(mode="after")
    def validate_fixed_version(self):
        if self.version == "latest" or re.search(r"[~^*><=]", self.version):
            raise ValueError("server version 必须为固定版本")
        return self


class PublisherMetadata:
    @staticmethod
    def _input(value: dict[str, Any]) -> dict[str, Any]:
        if set(value) == {"server_json"} and isinstance(value["server_json"], dict):
            return value["server_json"]
        return value

    @staticmethod
    def canonical_json(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def digest(self, value: dict[str, Any]) -> str:
        return hashlib.sha256(self.canonical_json(value).encode("utf-8")).hexdigest()

    def preview(self, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("server.json 根节点必须为对象")
        raw = self.canonical_json(value).encode("utf-8")
        if len(raw) > 256 * 1024:
            raise ValueError("server.json 超过 256 KiB")
        server = PublisherServer.model_validate(self._input(value))
        payload = server.model_dump(by_alias=True, exclude_none=True)
        payload["_meta"] = {
            "io.modelcontextprotocol.registry/publisher-provided": {
                "tool": "research-workbench",
                "version": "phase2a",
            }
        }
        canonical = self.canonical_json(payload)
        return {
            "valid": True,
            "server_json": payload,
            "canonical_json": canonical,
            "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "argv": PUBLISHER_ARGV,
            "executed": False,
        }

    def validate(self, value: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.preview(value)
        except (ValidationError, TypeError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                issues = [
                    {"path": ".".join(str(item) for item in error["loc"]), "message": error["msg"]}
                    for error in exc.errors(include_url=False, include_input=False)
                ]
            else:
                issues = [{"path": "", "message": str(exc)}]
            return {"valid": False, "issues": issues, "argv": PUBLISHER_ARGV, "executed": False}
