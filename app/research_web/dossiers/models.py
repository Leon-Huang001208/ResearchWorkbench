"""Closed, bounded dossier write contracts; identity always comes from the Host."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Subject(Closed):
    kind: Literal["company", "industry", "theme"]
    key: str = Field(min_length=2, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]+$")
    label: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def company_identity(self):
        import re

        if self.kind == "company" and not re.fullmatch(
            r"(?:6[0-9]{5}\.SH|[03][0-9]{5}\.SZ|[489][0-9]{5}\.BJ|[0-9]{5}\.HK|[A-Z][A-Z0-9.]{0,14}\.US)",
            self.key,
        ):
            raise ValueError("company requires a canonical exchange-qualified security identity")
        return self


class Create(Closed):
    title: str = Field(min_length=1, max_length=200)
    subject: Subject
    idempotency_key: str = Field(min_length=8, max_length=128)


class Mutation(Closed):
    expected_revision: int = Field(ge=1, strict=True)
    idempotency_key: str = Field(min_length=8, max_length=128)


class Patch(Mutation):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    archived: bool | None = Field(default=None, strict=True)


class Record(Mutation):
    record_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    kind: Literal["opinion", "catalyst", "risk", "note", "signal"]
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    state: Literal["open", "supported", "refuted", "resolved", "dismissed"] = "open"
    reason: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    watch_from: datetime | None = None
    watch_until: datetime | None = None

    @model_validator(mode="after")
    def interval(self):
        if (
            self.watch_from
            and self.watch_until
            and (
                self.watch_from.tzinfo != self.watch_until.tzinfo
                or self.watch_from > self.watch_until
            )
        ):
            raise ValueError("invalid observation window")
        return self


class Reference(Closed):
    type: Literal["dataset", "file", "source"]
    id: str = Field(min_length=1, max_length=500)


class Evidence(Mutation):
    source_session_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    reference: Reference
    locator: str | None = Field(default=None, max_length=2000)


class Link(Mutation):
    type: Literal["session", "report", "file"]
    source_session_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    reference_id: str | None = Field(default=None, max_length=500)


class Handoff(Mutation):
    mode: Literal["fingpt", "claw"]
    action: Literal[
        "company", "industry", "research_prep", "update_view", "check_risk", "earnings_gap"
    ]
