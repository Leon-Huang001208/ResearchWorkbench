"""Configuration source of truth for the Daily Market Commentary workflow."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from core.observability import get_logger

logger = get_logger(__name__)

_SPEC_PATH = Path(__file__).resolve().parents[1] / "workflow_specs" / "daily_market_commentary.yaml"


class CommentarySchedule(BaseModel):
    enabled: bool = True
    timezone: str = "Asia/Shanghai"
    trading_days_only: bool = True
    hour: int = Field(default=16, ge=0, le=23)
    minute: int = Field(default=15, ge=0, le=59)


class CommentarySectionSpec(BaseModel):
    key: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    max_paragraphs: int = Field(ge=1, le=12)
    requirement: str = Field(min_length=1)


class CommentaryChartSpec(BaseModel):
    chart_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    chart_type: Literal["bar", "line"] = "bar"
    enabled: bool = True


class CommentaryDataPolicy(BaseModel):
    source_priority: list[str] = Field(min_length=1)
    news_source_priority: list[str] = Field(min_length=1)
    focus_direction_count: int = Field(default=3, ge=2, le=3)
    attribution_priority: list[str] = Field(min_length=1)


class CommentaryRenderingPolicy(BaseModel):
    primary_artifact: Literal["document_block"] = "document_block"
    exports: list[Literal["markdown", "word"]] = Field(min_length=1)


class CommentaryQualityPolicy(BaseModel):
    block_on_unresolved_numeric_date_source_conflict: bool = True
    conditional_risk_for_interpretive_conflict: bool = True
    min_evidence_count: int = Field(default=1, ge=0)
    target_length_chars: tuple[int, int] = (1000, 1500)

    @model_validator(mode="after")
    def validate_length(self) -> CommentaryQualityPolicy:
        if self.target_length_chars[0] > self.target_length_chars[1]:
            raise ValueError("target_length_chars 必须按从小到大排列")
        return self


class DailyMarketCommentarySpec(BaseModel):
    workflow_id: Literal["daily-market-commentary"] = "daily-market-commentary"
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    runtime_id: str = Field(min_length=1)
    schedule: CommentarySchedule = Field(default_factory=CommentarySchedule)
    data_policy: CommentaryDataPolicy
    sections: list[CommentarySectionSpec] = Field(min_length=1, max_length=8)
    charts: list[CommentaryChartSpec] = Field(default_factory=list)
    rendering: CommentaryRenderingPolicy = Field(default_factory=CommentaryRenderingPolicy)
    quality_policy: CommentaryQualityPolicy = Field(default_factory=CommentaryQualityPolicy)

    @model_validator(mode="after")
    def validate_unique_names(self) -> DailyMarketCommentarySpec:
        if len({section.key for section in self.sections}) != len(self.sections):
            raise ValueError("section key 必须唯一")
        if len({chart.chart_id for chart in self.charts}) != len(self.charts):
            raise ValueError("chart_id 必须唯一")
        return self


def daily_market_commentary_spec_path() -> Path:
    return _SPEC_PATH


def load_daily_market_commentary_spec(path: Path | None = None) -> DailyMarketCommentarySpec:
    target = path or _SPEC_PATH
    try:
        with target.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return DailyMarketCommentarySpec.model_validate(payload)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        logger.exception("daily market commentary spec load failed", path=str(target))
        raise ValueError("每日市场点评工作流配置无效") from exc


def save_daily_market_commentary_spec(
    spec: DailyMarketCommentarySpec, path: Path | None = None
) -> None:
    """Atomically persist only schema-validated configuration."""
    target = path or _SPEC_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
            yaml.safe_dump(
                spec.model_dump(mode="json"), handle, allow_unicode=True, sort_keys=False
            )
            temporary = Path(handle.name)
        temporary.replace(target)
        logger.info("daily market commentary spec saved", path=str(target), version=spec.version)
    except OSError as exc:
        logger.exception("daily market commentary spec save failed", path=str(target))
        raise RuntimeError("每日市场点评工作流配置保存失败") from exc
