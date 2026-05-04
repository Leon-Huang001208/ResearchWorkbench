from datetime import datetime

from pydantic import BaseModel, Field


class ReasoningTrace(BaseModel):
    """推理追踪 - 记录完整的推理过程"""

    trace_id: str
    request_type: str
    question: str
    subject_ids: list[str] = Field(default_factory=list)
    retrieved_doc_ids: list[str] = Field(default_factory=list)
    retrieved_assertion_ids: list[str] = Field(default_factory=list)
    graph_paths: list[dict] = Field(default_factory=list)
    intermediate_hypotheses: list[dict] = Field(default_factory=list)
    final_answer: str | None = None
    provider: str
    model_name: str
    prompt_version: str
    total_latency_ms: int
    total_tokens: int
    team_id: str | None = None
    project_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
