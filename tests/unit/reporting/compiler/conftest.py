"""报告编译器测试共享 fixtures."""

from datetime import datetime
from typing import List

import pytest

from core.contracts import (
    ClaimType,
    EvidenceChunk,
    EvidenceDocument,
    EvidencePackage,
    EvidenceType,
    FactRecord,
    Provenance,
    RetrievalQuery,
    SourceReliabilityLevel,
    SourceTier,
    SourceType,
)
from core.interfaces import ModelGateway, ModelResponse


class StubModelGateway(ModelGateway):
    """可控的 model gateway stub，按请求 schema 返回预设结构."""

    def __init__(self):
        self.chat_calls: List[dict] = []
        self.structured_calls: List[dict] = []

    def chat(self, messages, model=None, temperature=0.7, max_tokens=None, **kw):
        self.chat_calls.append({"messages": messages, "temperature": temperature})
        user_msg = messages[-1]["content"] if messages else ""
        # 从 prompt 提取 fact_id 并写入正文（模拟 writer 标注引用）
        import re

        fids = re.findall(r"\[(fact_[A-Za-z0-9_\-]+)\]", user_msg)
        body = "本节核心结论："
        for fid in fids[:5]:
            body += f" 关键数据见 [{fid}]。"
        if not fids:
            body += " 证据不足，暂无可用数据。"
        return ModelResponse(
            content=body, model_name="stub", provider="stub", tokens_used=10, latency_ms=1
        )

    def structured_output(self, messages, output_schema, model=None, temperature=0.1, **kw):
        self.structured_calls.append({"schema": output_schema.__name__, "messages": messages})
        name = output_schema.__name__
        if name == "_FactExtractionResult":
            data = {
                "claims": [
                    {
                        "claim_text": "营收100亿元",
                        "claim_type": "metric",
                        "entities": ["某公司"],
                        "value": 100.0,
                        "unit": "亿元",
                        "confidence": 0.9,
                        "evidence_span": "营收100亿元",
                    },
                    {
                        "claim_text": "毛利率45%",
                        "claim_type": "metric",
                        "value": 45.0,
                        "unit": "%",
                        "confidence": 0.8,
                        "evidence_span": "毛利率45%",
                    },
                ]
            }
        elif name == "_ResearchPlanLLM":
            data = {
                "research_questions": ["某公司营收分析", "毛利率变化"],
                "required_claim_types": ["metric", "risk"],
                "required_evidence_types": ["fact", "data"],
                "max_documents": 30,
                "max_chunks": 100,
            }
        elif name == "_OutlineLLM":
            data = {
                "report_title": "某公司研究",
                "thesis": "营收增长稳健",
                "sections": [
                    {
                        "title": "营收分析",
                        "goal": "分析营收",
                        "must_answer": ["营收增速"],
                        "required_claim_types": ["metric"],
                        "counterpoints": ["增速放缓风险"],
                        "target_words": 400,
                    },
                    {
                        "title": "风险与反证",
                        "goal": "覆盖风险",
                        "must_answer": ["主要风险"],
                        "required_claim_types": ["risk"],
                        "counterpoints": ["利多不成立"],
                        "target_words": 300,
                    },
                ],
            }
        elif name == "_ClaimExtractionResult":
            data = {
                "claims": [
                    {"claim_text": "营收100亿元", "claim_type": "metric", "confidence": 0.9},
                    {"claim_text": "毛利率45%", "claim_type": "metric", "confidence": 0.85},
                    {"claim_text": "行业景气度较高", "claim_type": "event", "confidence": 0.7},
                ]
            }
        else:
            data = {}
        return output_schema(**data)

    def embed(self, text, model=None, **kw):
        raise NotImplementedError("stub does not embed")


@pytest.fixture
def stub_gateway():
    return StubModelGateway()


@pytest.fixture
def sample_evidence_package():
    """单个证据包，含一个官方源文档与一个 chunk."""
    doc = EvidenceDocument(
        doc_id="d1",
        title="某公司年报",
        summary="某公司营收100亿元，毛利率45%",
        source_type=SourceType.CNINFO,
        source_name="巨潮资讯网",
        source_url="http://example.com",
        publish_time=datetime(2024, 5, 9),
        source_reliability=SourceReliabilityLevel.OFFICIAL,
        citation_anchor="[1] 巨潮",
        evidence_quality=0.9,
        chunks=[
            EvidenceChunk(
                chunk_id="c1",
                doc_id="d1",
                content="某公司营收100亿元，毛利率45%",
                chunk_index=0,
                evidence_type=EvidenceType.FACT,
                combined_score=0.9,
            )
        ],
    )
    return EvidencePackage(
        query=RetrievalQuery(query_text="某公司营收分析"),
        total_documents_found=1,
        total_chunks_found=1,
        documents=[doc],
    )


@pytest.fixture
def sample_fact_record():
    """单个 FactRecord，带完整 Provenance."""
    return FactRecord(
        fact_id="fact_test1",
        claim_text="营收100亿元",
        claim_type=ClaimType.METRIC,
        value=100.0,
        unit="亿元",
        confidence=0.9,
        evidence_span="营收100亿元",
        provenance=Provenance(
            doc_id="d1",
            chunk_id="c1",
            source_type=SourceType.CNINFO,
            source_name="巨潮资讯网",
            source_url="http://example.com",
            published_at=datetime(2024, 5, 9),
            source_reliability=SourceReliabilityLevel.OFFICIAL,
            source_tier=SourceTier.TIER_A,
        ),
    )
