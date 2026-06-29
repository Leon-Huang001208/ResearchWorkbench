"""Contracts for commentary production context packs."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CommentaryEvidenceItem(BaseModel):
    """A source item used to prepare a market commentary draft."""

    kind: str = Field(description="Evidence confidence kind: confirmed/reported/interpretation")
    title: str = Field(description="Short evidence title")
    summary: str = Field(default="", description="Readable evidence summary")
    source: str = Field(default="", description="Source label or upstream subsystem")
    source_type: str = Field(default="other", description="Source type: market_data/news/research/interpretation")
    verification_status: str = Field(
        default="unverified",
        description="Verification state: verified/source_published/unverified/derived",
    )
    confidence_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Evidence confidence score after source classification",
    )
    display_label: str = Field(default="", description="Human-readable evidence label")
    url: Optional[str] = Field(default=None, description="Optional source URL")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extra source metadata")


class CommentaryAttributionSignal(BaseModel):
    """A ranked explanation candidate for market commentary attribution."""

    rank: int = Field(default=0, description="1-based rank after attribution scoring")
    tag: str = Field(description="Stable attribution tag, e.g. ai_crowding")
    label: str = Field(description="Human-readable attribution label")
    strength: str = Field(
        default="watch",
        description="Attribution strength: primary/secondary/watch/noise",
    )
    score: float = Field(default=0.0, ge=0.0, le=100.0, description="Attribution score")
    confidence_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in this attribution explanation",
    )
    verification_status: str = Field(
        default="derived",
        description="Verification state for the attribution: verified/source_published/derived/unverified",
    )
    rationale: str = Field(default="", description="Short rationale for the attribution score")
    evidence_titles: List[str] = Field(default_factory=list, description="Evidence titles supporting this attribution")


class CommentaryContextPack(BaseModel):
    """Prefill payload for the commentary production center."""

    recipe_id: str = Field(default="daily-close", description="Selected commentary recipe id")
    data_snapshot_text: str = Field(description="Market data facts for textarea prefill")
    evidence_pack_text: str = Field(description="News/research evidence for textarea prefill")
    evidence_items: List[CommentaryEvidenceItem] = Field(
        default_factory=list,
        description="Structured evidence items grouped by confidence kind",
    )
    attribution_signals: List[CommentaryAttributionSignal] = Field(
        default_factory=list,
        description="Ranked attribution signals explaining market movement",
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class CommentaryDraftRequest(BaseModel):
    """Request for generating an editable commentary draft."""

    recipe_id: str = Field(default="daily-close", description="Selected commentary recipe id")
    data_snapshot_text: str = Field(default="", description="Market data facts")
    evidence_pack_text: str = Field(default="", description="Readable evidence package")
    subjective_judgement: str = Field(default="", description="User judgement to incorporate")
    evidence_items: List[CommentaryEvidenceItem] = Field(default_factory=list)
    attribution_signals: List[CommentaryAttributionSignal] = Field(default_factory=list)


class CommentaryDraftResponse(BaseModel):
    """Generated commentary draft with audit-friendly metadata."""

    recipe_id: str = Field(description="Selected commentary recipe id")
    draft_markdown: str = Field(description="Editable markdown draft")
    sections: List[Dict[str, str]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    attribution_signals: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    model: str = Field(default="rule_based_fallback")
    provider: str = Field(default="local")
    tokens_used: int = Field(default=0)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
