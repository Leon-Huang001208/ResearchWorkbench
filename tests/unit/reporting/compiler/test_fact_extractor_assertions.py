"""FactExtractor.extract_from_assertions 单元测试 - 第二阶段 2.4.

验证 assertion → FactRecord 快速路径（跳过 LLM）：predicate/object_value 映射、
claim_type 启发式、数值与单位提取、reliability→tier、去重。
"""

from core.contracts import (
    Assertion,
    ClaimType,
    SourceReliabilityLevel,
)
from reporting.compiler.fact_extractor import FactExtractor


def _assertion(predicate="has_revenue", obj=None, confidence=0.85, aid="a1", doc_id="d1"):
    return Assertion(
        assertion_id=aid,
        predicate=predicate,
        object_value=obj if obj is not None else {"text": "100亿元", "value": 100.0},
        confidence=confidence,
        source_doc_id=doc_id,
        source_span={"chunk_index": 0, "chunk_text": "某公司营收100亿元"},
        extractor_version="v",
    )


class TestAssertionToFact:
    def test_basic_conversion(self):
        facts = FactExtractor().extract_from_assertions(
            [_assertion()], {SourceReliabilityLevel.OFFICIAL.value: SourceReliabilityLevel.OFFICIAL}
        )
        # reliability_map 按 source_doc_id 查
        facts = FactExtractor().extract_from_assertions(
            [_assertion(doc_id="d1")], {"d1": SourceReliabilityLevel.OFFICIAL}
        )
        assert len(facts) == 1
        f = facts[0]
        assert f.value == 100.0
        assert f.unit == "亿元"
        assert f.provenance.source_tier.value == "tier_a"
        assert f.confidence == 0.85
        assert "has_revenue" in f.claim_text
        assert f.provenance.doc_id == "d1"

    def test_claim_type_inference(self):
        fe = FactExtractor()
        assert fe._infer_claim_type("has_revenue") == ClaimType.METRIC
        assert fe._infer_claim_type("placed_order") == ClaimType.EVENT
        assert fe._infer_claim_type("key_risk") == ClaimType.RISK
        assert fe._infer_claim_type("forward_guidance") == ClaimType.GUIDANCE

    def test_unit_inference(self):
        assert FactExtractor._infer_unit("100亿元") == "亿元"
        assert FactExtractor._infer_unit("45%") == "%"
        assert FactExtractor._infer_unit("800Gbps") == "Gbps"
        assert FactExtractor._infer_unit("无单位文本") is None

    def test_unknown_reliability_maps_tier_d(self):
        facts = FactExtractor().extract_from_assertions([_assertion()], {})
        assert facts[0].provenance.source_tier.value == "tier_d"

    def test_evidence_span_from_chunk_text(self):
        facts = FactExtractor().extract_from_assertions([_assertion()], {})
        assert facts[0].evidence_span == "某公司营收100亿元"

    def test_dedup(self):
        # 同 claim_text+value+unit+doc_id 去重
        a1 = _assertion(aid="a1")
        a2 = _assertion(aid="a2")  # 完全相同
        facts = FactExtractor().extract_from_assertions([a1, a2], {})
        assert len(facts) == 1

    def test_empty_assertions(self):
        assert FactExtractor().extract_from_assertions([], {}) == []
