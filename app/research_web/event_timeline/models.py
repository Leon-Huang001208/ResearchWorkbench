"""Public event mutations contain intent, never trusted provenance or permissions."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Key(Closed):
    idempotency_key: str = Field(min_length=8, max_length=128)


class Mutation(Key):
    expected_revision: int = Field(ge=1, strict=True)


class EventFields(Closed):
    title: str = Field(min_length=1, max_length=300)
    category: Literal[
        "macro",
        "policy",
        "geopolitics",
        "war",
        "sports",
        "disaster",
        "unexpected",
        "calendar",
        "other",
    ]
    occurrence_start: str = Field(min_length=7, max_length=40)
    occurrence_end: str | None = Field(default=None, max_length=40)
    date_precision: Literal["month", "day", "minute", "interval", "unknown"] = "day"
    markets: list[Literal["CN", "US", "HK"]] = Field(min_length=1, max_length=3)
    lifecycle: Literal["announced", "occurred", "ongoing", "postponed", "cancelled", "scenario"] = (
        "occurred"
    )
    description: str = Field(default="", max_length=10000)

    @model_validator(mode="after")
    def valid_dates(self):
        values = [self.occurrence_start] + ([self.occurrence_end] if self.occurrence_end else [])
        parsed = []
        for value in values:
            if self.date_precision == "month":
                parsed.append(datetime.strptime(value, "%Y-%m").replace(tzinfo=UTC))
            elif self.date_precision in {"day", "interval", "unknown"}:
                parsed.append(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC))
            else:
                date = datetime.fromisoformat(value)
                if date.tzinfo is None:
                    raise ValueError("minute precision requires an explicit timezone")
                parsed.append(date)
        if (
            any(value.year < 1990 for value in parsed)
            or (len(parsed) == 2 and parsed[1] < parsed[0])
            or len(set(self.markets)) != len(self.markets)
        ):
            raise ValueError("invalid occurrence interval or duplicate markets")
        return self


class Create(EventFields, Key):
    pass


class Revise(EventFields, Mutation):
    reason: str = Field(min_length=1, max_length=2000)


class VersionRef(Closed):
    id: str = Field(pattern="^[a-f0-9]{32}$")
    revision: int = Field(ge=1, strict=True)


class Decision(Key):
    events: list[VersionRef] = Field(min_length=1, max_length=200)
    decision: Literal["confirmed", "rejected"]
    reason: str = Field(min_length=1, max_length=2000)


class Freeze(Key):
    events: list[VersionRef] = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=300)


class Merge(Key):
    events: list[VersionRef] = Field(min_length=2, max_length=30)
    title: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=2000)


class Split(Mutation):
    children: list[EventFields] = Field(min_length=2, max_length=30)
    reason: str = Field(min_length=1, max_length=2000)


class Refresh(Key):
    source: Literal["fed_fomc", "bls_cpi", "bls_jobs", "gdelt", "ucdp"]
    year: int | None = Field(default=None, ge=1990, le=2200)
    page: int = Field(default=0, ge=0, le=10000)
    offset: int = Field(default=0, ge=0, le=50000000)


class Schedule(Mutation):
    enabled: bool = Field(strict=True)
    interval_hours: int = Field(default=24, ge=1, le=720, strict=True)
