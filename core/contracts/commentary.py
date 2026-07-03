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


class CommentaryRecipe(BaseModel):
    """A commentary writing recipe shared by frontend and backend generation."""

    id: str = Field(description="Stable recipe id")
    title: str = Field(description="Human-readable recipe title")
    tag: str = Field(description="Short recipe category")
    tone: str = Field(description="Default writing tone guidance")
    sections: List[str] = Field(description="Suggested section headings")


class CommentaryRecipeCatalog(BaseModel):
    """Available commentary recipes and default selection."""

    default_recipe_id: str = Field(default="daily-close")
    recipes: List[CommentaryRecipe] = Field(default_factory=list)


class CommentaryDraftRequest(BaseModel):
    """Request for generating an editable commentary draft."""

    recipe_id: str = Field(default="daily-close", description="Selected commentary recipe id")
    data_snapshot_text: str = Field(default="", description="Market data facts")
    evidence_pack_text: str = Field(default="", description="Readable evidence package")
    subjective_judgement: str = Field(default="", description="User judgement to incorporate")
    evidence_items: List[CommentaryEvidenceItem] = Field(default_factory=list)
    attribution_signals: List[CommentaryAttributionSignal] = Field(default_factory=list)
    writing_preferences: Dict[str, str] = Field(
        default_factory=dict,
        description="Audience, length, and tone controls selected in the workbench",
    )


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


class CommentarySectionRewriteRequest(CommentaryDraftRequest):
    """Request for rewriting one generated commentary section."""

    section_heading: str = Field(description="Heading of the section being rewritten")
    section_content: str = Field(description="Current editable section content")
    action: str = Field(
        default="rewrite",
        description="Rewrite action: shorten/soften/risk/rewrite",
    )


class CommentarySectionRewriteResponse(BaseModel):
    """Response for one rewritten commentary section."""

    recipe_id: str = Field(description="Selected commentary recipe id")
    section_heading: str = Field(description="Heading of the rewritten section")
    rewritten_content: str = Field(description="Rewritten editable section content")
    action: str = Field(description="Rewrite action that was applied")
    warnings: List[str] = Field(default_factory=list)
    model: str = Field(default="rule_based_fallback")
    provider: str = Field(default="local")
    tokens_used: int = Field(default=0)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class CommentaryQualityIssue(BaseModel):
    """One publish-gate issue found in a generated commentary draft."""

    code: str = Field(description="Stable quality issue code")
    severity: str = Field(description="blocker/warning/info")
    title: str = Field(description="Short human-readable issue title")
    detail: str = Field(description="Actionable issue detail")
    excerpt: str = Field(default="", description="Optional draft excerpt related to the issue")


class CommentaryQualityCheckRequest(CommentaryDraftRequest):
    """Request for checking a generated commentary draft before publishing."""

    draft_markdown: str = Field(description="Generated or edited commentary draft")


class CommentaryQualityCheckResponse(BaseModel):
    """Publish-gate quality check result for a commentary draft."""

    status: str = Field(description="passed/warning/blocked")
    summary: Dict[str, int] = Field(default_factory=dict)
    issues: List[CommentaryQualityIssue] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class CommentaryRunRecordRequest(BaseModel):
    """Request to persist one commentary generation run."""

    recipe_id: str = Field(description="Selected commentary recipe id")
    recipe_title: str = Field(default="", description="Human-readable recipe title")
    draft_markdown: str = Field(default="", description="Generated or edited draft markdown")
    model: str = Field(default="", description="Generation model name")
    provider: str = Field(default="", description="Generation provider")
    warnings: List[str] = Field(default_factory=list)
    evidence_count: int = Field(default=0, ge=0)
    selected_evidence_count: int = Field(default=0, ge=0)
    quality_status: str = Field(default="unknown")
    quality_summary: Dict[str, int] = Field(default_factory=dict)


class CommentaryRunRecord(CommentaryRunRecordRequest):
    """Persisted commentary generation run."""

    run_id: str = Field(description="Stable run id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CommentaryRunRecordResponse(BaseModel):
    """Response after writing a commentary run record."""

    run_id: str = Field(description="Stable run id")
    log_path: str = Field(description="Path to the JSONL log file")
    record: CommentaryRunRecord
