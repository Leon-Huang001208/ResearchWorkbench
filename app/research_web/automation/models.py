"""Strict public contracts for version-locked Research Web automations."""

from __future__ import annotations

from datetime import datetime
from email.utils import parseaddr
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..store import StoreError

DIGEST_PATTERN = r"^[a-f0-9]{64}$"
IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$"


class AutomationError(StoreError):
    """Safe automation-domain failure exposed through the existing API handler."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AutomationSchedule(StrictModel):
    kind: Literal["once", "daily", "weekly", "monthly"]
    timezone: str = Field(min_length=1, max_length=80)
    once_at: str | None = Field(default=None, max_length=64)
    weekday: int | None = Field(default=None, ge=0, le=6)
    day: int | None = Field(default=None, ge=1, le=31)
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone_invalid") from exc
        return value

    @model_validator(mode="after")
    def validate_shape(self) -> AutomationSchedule:
        if self.kind == "once":
            if not self.once_at:
                raise ValueError("once_at_required")
            value = datetime.fromisoformat(self.once_at)
            if value.tzinfo is None:
                raise ValueError("once_at_timezone_required")
            if any(value is not None for value in (self.weekday, self.day, self.hour, self.minute)):
                raise ValueError("once_at_exclusive")
        else:
            if self.hour is None or self.minute is None:
                raise ValueError("schedule_time_required")
            if self.once_at is not None:
                raise ValueError("once_at_not_allowed")
            if self.kind == "weekly" and self.weekday is None:
                raise ValueError("weekday_required")
            if self.kind == "monthly" and self.day is None:
                raise ValueError("day_required")
            if self.kind != "weekly" and self.weekday is not None:
                raise ValueError("weekday_not_allowed")
            if self.kind != "monthly" and self.day is not None:
                raise ValueError("day_not_allowed")
        return self


class MCPToolLock(StrictModel):
    installation_id: str = Field(pattern=IDENTIFIER_PATTERN)
    version: str = Field(pattern=IDENTIFIER_PATTERN)
    tool_name: str = Field(pattern=IDENTIFIER_PATTERN)
    schema_sha256: str = Field(pattern=DIGEST_PATTERN)
    risk_tier: Literal["read_only", "private_data"]
    allow_unattended: bool = False

    @model_validator(mode="after")
    def unattended_is_read_only(self) -> MCPToolLock:
        if self.allow_unattended and self.risk_tier != "read_only":
            raise ValueError("unattended_requires_read_only")
        return self


class DeliveryConfiguration(StrictModel):
    channel_ids: list[str] = Field(default_factory=list, max_length=16)
    include_attachments: bool = False

    @field_validator("channel_ids")
    @classmethod
    def channel_ids_are_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("duplicate_delivery_channel")
        return values


class AutomationCreate(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    target_kind: Literal["skill", "workflow", "report_workflow"]
    target_id: str = Field(pattern=IDENTIFIER_PATTERN)
    target_version: int = Field(ge=1)
    target_sha256: str | None = Field(default=None, pattern=DIGEST_PATTERN)
    input_template: str = Field(min_length=1, max_length=100_000)
    workspace_id: Literal["research"] = "research"
    output_formats: list[Literal["md", "html", "docx", "xlsx", "pptx", "png", "pdf"]] = Field(
        default_factory=list, max_length=7
    )
    mcp_tools: list[MCPToolLock] = Field(default_factory=list, max_length=64)
    schedule: AutomationSchedule
    delivery: DeliveryConfiguration = Field(default_factory=DeliveryConfiguration)

    @model_validator(mode="after")
    def values_are_unique(self) -> AutomationCreate:
        if len(self.output_formats) != len(set(self.output_formats)):
            raise ValueError("duplicate_output_format")
        keys = [(item.installation_id, item.tool_name) for item in self.mcp_tools]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate_mcp_tool")
        return self


class AutomationUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    input_template: str | None = Field(default=None, min_length=1, max_length=100_000)
    output_formats: list[Literal["md", "html", "docx", "xlsx", "pptx", "png", "pdf"]] | None = (
        Field(default=None, max_length=7)
    )
    schedule: AutomationSchedule | None = None
    delivery: DeliveryConfiguration | None = None


class DeliveryChannelPut(StrictModel):
    id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    name: str = Field(min_length=1, max_length=160)
    kind: Literal["smtp", "webhook", "feishu", "wecom", "dingtalk"]
    enabled: bool = True
    endpoint: str | None = Field(default=None, max_length=2048)
    smtp_host: str | None = Field(default=None, max_length=253)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = Field(default=None, max_length=320)
    sender: str | None = Field(default=None, max_length=320)
    recipients: list[str] = Field(default_factory=list, max_length=32)
    secret: str | None = Field(default=None, min_length=1, max_length=4096, repr=False)

    @field_validator("smtp_host")
    @classmethod
    def smtp_host_is_plain(cls, value: str | None) -> str | None:
        if value is not None and (
            any(ord(character) < 33 or ord(character) == 127 for character in value)
            or "/" in value
            or "@" in value
        ):
            raise ValueError("smtp_host_invalid")
        return value

    @field_validator("smtp_username", "sender")
    @classmethod
    def mailbox_is_safe(cls, value: str | None) -> str | None:
        if value is not None:
            cls._validate_mailbox(value)
        return value

    @field_validator("recipients")
    @classmethod
    def recipients_are_safe(cls, values: list[str]) -> list[str]:
        for value in values:
            cls._validate_mailbox(value)
        return values

    @staticmethod
    def _validate_mailbox(value: str) -> None:
        name, address = parseaddr(value)
        if (
            name
            or address != value
            or address.count("@") != 1
            or any(ord(character) < 33 or ord(character) == 127 for character in value)
        ):
            raise ValueError("mailbox_invalid")

    @model_validator(mode="after")
    def validate_channel(self) -> DeliveryChannelPut:
        if self.kind == "smtp":
            if (
                not self.smtp_host
                or self.smtp_port is None
                or not self.sender
                or not self.recipients
            ):
                raise ValueError("smtp_configuration_incomplete")
        elif not self.endpoint:
            raise ValueError("webhook_endpoint_required")
        return self


class MigrationApply(StrictModel):
    workflow_ids: list[str] = Field(min_length=1, max_length=128)

    @field_validator("workflow_ids")
    @classmethod
    def workflow_ids_are_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("duplicate_workflow")
        return values
