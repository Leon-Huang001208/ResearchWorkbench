"""SourceGrader 单元测试 - 第二阶段来源分级.

验证 reliability→tier 映射、trust_score 计算、freshness_score 衰减、
grade_inplace 回填。不依赖数据库（SourceGrader 不直接读 DB，reliability
从文档或 SourceSpec 推导；这里用文档自身 reliability 测）。
"""

from datetime import datetime, timedelta, timezone

from core.contracts import DocType, DocumentV1, SourceType
from core.contracts.documents_v1 import DocumentQuality, DocumentTimeliness
from core.services.source_grader import SourceGrader


def _make_doc(reliability, publish_time=None, is_fact_source=True):
    return DocumentV1(
        doc_id="d1",
        doc_type=DocType.REPORT,
        source_type=SourceType.CNINFO,
        title="t",
        content="x",
        quality=DocumentQuality(
            source_reliability_level=reliability, is_fact_source=is_fact_source
        ),
        timeliness=DocumentTimeliness(publish_time=publish_time),
    )


class TestTierMapping:
    def test_official_maps_to_tier_a(self):
        from core.contracts import SourceReliabilityLevel

        graded = SourceGrader().grade(_make_doc(SourceReliabilityLevel.OFFICIAL))
        assert graded.source_tier == "tier_a"

    def test_research_institute_maps_to_tier_b(self):
        from core.contracts import SourceReliabilityLevel

        graded = SourceGrader().grade(_make_doc(SourceReliabilityLevel.RESEARCH_INSTITUTE))
        assert graded.source_tier == "tier_b"

    def test_social_media_maps_to_tier_d(self):
        from core.contracts import SourceReliabilityLevel

        graded = SourceGrader().grade(_make_doc(SourceReliabilityLevel.SOCIAL_MEDIA))
        assert graded.source_tier == "tier_d"


class TestTrustScore:
    def test_trust_in_zero_one_range(self):
        from core.contracts import SourceReliabilityLevel

        graded = SourceGrader().grade(_make_doc(SourceReliabilityLevel.OFFICIAL))
        assert 0.0 <= graded.trust_score <= 1.0

    def test_tier_a_higher_than_tier_d(self):
        from core.contracts import SourceReliabilityLevel

        a = SourceGrader().grade(_make_doc(SourceReliabilityLevel.OFFICIAL)).trust_score
        d = SourceGrader().grade(_make_doc(SourceReliabilityLevel.SOCIAL_MEDIA)).trust_score
        assert a > d

    def test_non_fact_source_penalized(self):
        from core.contracts import SourceReliabilityLevel

        fact = (
            SourceGrader()
            .grade(_make_doc(SourceReliabilityLevel.OFFICIAL, is_fact_source=True))
            .trust_score
        )
        opinion = (
            SourceGrader()
            .grade(_make_doc(SourceReliabilityLevel.OFFICIAL, is_fact_source=False))
            .trust_score
        )
        assert opinion < fact


class TestFreshnessScore:
    def test_recent_doc_high_freshness(self):
        from core.contracts import SourceReliabilityLevel

        recent = datetime.now(timezone.utc)
        graded = SourceGrader().grade(
            _make_doc(SourceReliabilityLevel.OFFICIAL, publish_time=recent)
        )
        assert graded.freshness_score > 0.9

    def test_old_doc_low_freshness(self):
        from core.contracts import SourceReliabilityLevel

        old = datetime.now(timezone.utc) - timedelta(days=60)
        graded = SourceGrader().grade(_make_doc(SourceReliabilityLevel.OFFICIAL, publish_time=old))
        assert graded.freshness_score < 0.5

    def test_no_publish_time_neutral(self):
        from core.contracts import SourceReliabilityLevel

        graded = SourceGrader().grade(_make_doc(SourceReliabilityLevel.OFFICIAL, publish_time=None))
        assert graded.freshness_score == 0.5


class TestGradeInplace:
    def test_grade_inplace_fills_quality(self):
        from core.contracts import SourceReliabilityLevel

        doc = _make_doc(SourceReliabilityLevel.OFFICIAL)
        SourceGrader().grade_inplace(doc)
        assert doc.quality.source_tier == "tier_a"
        assert doc.quality.trust_score is not None
        assert doc.quality.freshness_score is not None
