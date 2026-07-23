"""事实抽取器单元测试.

验证 FactRecord 抽取、Provenance 绑定（含 source_tier 映射）、LLM 失败回退到
规则抽取、以及按 (claim_text, value, unit, doc_id) 去重逻辑。

对应 deep-research-report.md 第一阶段 "证据抽取器" 技能。
"""

from core.contracts import (
    ClaimType,
    EvidenceDocument,
    EvidencePackage,
    RetrievalQuery,
    SourceReliabilityLevel,
    SourceTier,
    SourceType,
)
from reporting.compiler.fact_extractor import FactExtractor


class TestFactExtractionWithStub:
    """使用 StubModelGateway 的 LLM 抽取路径."""

    def test_extracts_facts_and_binds_provenance(self, stub_gateway, sample_evidence_package):
        extractor = FactExtractor(stub_gateway)
        facts = extractor.extract([sample_evidence_package])

        # stub 返回 2 条 claim（营收100亿元 / 毛利率45%），均应被抽取
        assert len(facts) == 2
        for f in facts:
            assert f.fact_id.startswith("fact_") or len(f.fact_id) > 0
            assert f.claim_text
            assert f.provenance is not None
            # 官方源应映射到 TIER_A
            assert f.provenance.source_tier == SourceTier.TIER_A
            assert f.provenance.source_reliability == SourceReliabilityLevel.OFFICIAL
            assert f.provenance.doc_id == "d1"
            assert f.provenance.source_name == "巨潮资讯网"

    def test_numeric_value_and_unit_preserved(self, stub_gateway, sample_evidence_package):
        extractor = FactExtractor(stub_gateway)
        facts = extractor.extract([sample_evidence_package])
        by_text = {f.claim_text: f for f in facts}
        assert by_text["营收100亿元"].value == 100.0
        assert by_text["营收100亿元"].unit == "亿元"
        assert by_text["毛利率45%"].value == 45.0
        assert by_text["毛利率45%"].unit == "%"

    def test_confidence_carried_through(self, stub_gateway, sample_evidence_package):
        extractor = FactExtractor(stub_gateway)
        facts = extractor.extract([sample_evidence_package])
        # stub 设置的 confidence 为 0.9 / 0.8
        confidences = sorted(f.confidence for f in facts)
        assert confidences == [0.8, 0.9]


class TestRuleBasedFallback:
    """无 LLM 或 LLM 失败时的规则抽取."""

    def test_no_gateway_uses_rule_based(self, sample_evidence_package):
        extractor = FactExtractor(model_gateway=None)
        facts = extractor.extract([sample_evidence_package])
        # chunk "某公司营收100亿元，毛利率45%" → 规则匹配 100亿元 / 45%
        assert len(facts) == 2
        values = {f.value for f in facts}
        assert 100.0 in values
        assert 45.0 in values
        for f in facts:
            assert f.claim_type == ClaimType.METRIC
            assert f.confidence == 0.4  # 规则抽取置信度低
            assert f.provenance.source_tier == SourceTier.TIER_A

    def test_llm_failure_falls_back_to_rule_based(self, sample_evidence_package, monkeypatch):
        """LLM 抛异常时应回退到规则抽取，不中断流水线."""

        class BrokenGateway:
            def structured_output(self, messages, output_schema, **kw):
                raise RuntimeError("LLM unavailable")

        extractor = FactExtractor(model_gateway=BrokenGateway())
        facts = extractor.extract([sample_evidence_package])
        # 回退规则抽取仍应得到 100亿元 / 45%
        assert len(facts) == 2
        assert {f.value for f in facts} == {100.0, 45.0}


class TestDeduplication:
    """去重逻辑测试."""

    def test_duplicate_facts_across_chunks_deduped(self, stub_gateway):
        """同一文档两个 chunk 抽出相同事实应去重."""
        from datetime import datetime

        from core.contracts import EvidenceChunk, EvidenceType

        chunk = EvidenceChunk(
            chunk_id="c1",
            doc_id="d1",
            content="某公司营收100亿元，毛利率45%",
            chunk_index=0,
            evidence_type=EvidenceType.FACT,
            combined_score=0.9,
        )
        doc = EvidenceDocument(
            doc_id="d1",
            title="年报",
            summary="",
            source_type=SourceType.CNINFO,
            source_name="巨潮",
            source_url="http://example.com",
            publish_time=datetime(2024, 5, 9),
            source_reliability=SourceReliabilityLevel.OFFICIAL,
            citation_anchor="[1]",
            evidence_quality=0.9,
            chunks=[chunk, chunk],  # 两个相同 chunk
        )
        package = EvidencePackage(
            query=RetrievalQuery(query_text="q"),
            total_documents_found=1,
            total_chunks_found=2,
            documents=[doc],
        )
        extractor = FactExtractor(stub_gateway)
        facts = extractor.extract([package])
        # 两个相同 chunk 抽出相同 2 条 claim，去重后仍为 2 条
        assert len(facts) == 2

    def test_empty_packages_returns_empty(self, stub_gateway):
        extractor = FactExtractor(stub_gateway)
        assert extractor.extract([]) == []

    def test_doc_without_chunks_uses_summary(self, stub_gateway):
        """无 chunk 但有 summary 时应从 summary 抽取."""
        doc = EvidenceDocument(
            doc_id="d2",
            title="简报",
            summary="营收100亿元，毛利率45%",
            source_type=SourceType.CNINFO,
            source_name="巨潮",
            source_url="http://example.com",
            publish_time=None,
            source_reliability=SourceReliabilityLevel.OFFICIAL,
            citation_anchor="[1]",
            evidence_quality=0.9,
            chunks=[],
        )
        package = EvidencePackage(
            query=RetrievalQuery(query_text="q"),
            total_documents_found=1,
            total_chunks_found=0,
            documents=[doc],
        )
        extractor = FactExtractor(stub_gateway)
        facts = extractor.extract([package])
        assert len(facts) == 2
