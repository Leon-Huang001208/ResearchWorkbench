"""
Core contracts for reasoning traces.

This module defines the Pydantic model for reasoning traces, which record the complete
reasoning process in AlphaFoundry.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class ReasoningTrace(BaseModel):
    """推理追踪 - 记录完整的推理过程.

    Represents a trace of the complete reasoning process, including trace ID, request type,
    question, subject IDs, retrieved docs/assertions, graph paths, intermediate hypotheses,
    final answer, provider/model info, latency/tokens, team/project IDs, and creation time.

    Attributes:
        trace_id: Unique identifier for the trace.
        request_type: Type of request (e.g., "signal_generation", "thesis_review").
        question: Question that triggered the reasoning.
        subject_ids: List of subject asset/entity IDs involved.
        retrieved_doc_ids: List of retrieved document IDs.
        retrieved_assertion_ids: List of retrieved assertion IDs.
        graph_paths: List of graph paths traversed (each as a dict).
        intermediate_hypotheses: List of intermediate hypotheses generated (each as a dict).
        final_answer: Final answer or output from the reasoning (if available).
        provider: LLM provider used (e.g., "openai", "volcano").
        model_name: Name of the model used (e.g., "gpt-4o", "doubao-pro").
        prompt_version: Version of the prompt used.
        total_latency_ms: Total latency in milliseconds.
        total_tokens: Total tokens used.
        team_id: Optional team ID for multi-tenant environments.
        project_id: Optional project ID for multi-project environments.
        created_at: Timestamp when the trace was created (defaults to UTC now).
    """

    trace_id: str = Field(description="Unique identifier for the trace")
    request_type: str = Field(
        description="Type of request (e.g., signal_generation, thesis_review)"
    )
    question: str = Field(description="Question that triggered the reasoning")
    subject_ids: list[str] = Field(
        default_factory=list, description="List of subject asset/entity IDs involved"
    )
    retrieved_doc_ids: list[str] = Field(
        default_factory=list, description="List of retrieved document IDs"
    )
    retrieved_assertion_ids: list[str] = Field(
        default_factory=list, description="List of retrieved assertion IDs"
    )
    graph_paths: list[dict] = Field(
        default_factory=list, description="List of graph paths traversed (each as a dict)"
    )
    intermediate_hypotheses: list[dict] = Field(
        default_factory=list,
        description="List of intermediate hypotheses generated (each as a dict)",
    )
    final_answer: str | None = Field(
        default=None, description="Final answer or output from the reasoning (if available)"
    )
    provider: str = Field(description="LLM provider used (e.g., openai, volcano)")
    model_name: str = Field(description="Name of the model used (e.g., gpt-4o, doubao-pro)")
    prompt_version: str = Field(description="Version of the prompt used")
    total_latency_ms: int = Field(description="Total latency in milliseconds")
    total_tokens: int = Field(description="Total tokens used")
    team_id: str | None = Field(
        default=None, description="Optional team ID for multi-tenant environments"
    )
    project_id: str | None = Field(
        default=None, description="Optional project ID for multi-project environments"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the trace was created (defaults to UTC now)",
    )
