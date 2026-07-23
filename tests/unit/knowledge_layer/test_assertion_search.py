"""AssertionSearchService 单元测试 - 第二阶段检索统一.

测纯逻辑部分（关键词命中评分、ORM→契约转换）。完整 DB 检索由
scripts/e2e_phase2_facts_store.py 与 2.4 端到端脚本覆盖。
"""

from core.contracts import Assertion
from knowledge_layer.retrieval.assertion_search import AssertionSearchService


class _FakeRow:
    """模拟 AssertionModel 行（仅用于纯逻辑测试）."""

    def __init__(self, predicate, object_value, confidence=0.8):
        self.assertion_id = "a1"
        self.subject_entity_id = None
        self.predicate = predicate
        self.object_entity_id = None
        self.object_value = object_value
        self.observed_at = None
        self.valid_from = None
        self.valid_to = None
        self.confidence = confidence
        self.source_doc_id = "d1"
        self.source_span = {"chunk_text": "某公司营收100亿元"}
        self.extractor_version = "v"
        self.reviewer_status = "draft"
        self.reviewer = None
        self.reviewed_at = None
        self.trace_ref = None
        self.team_id = None
        self.project_id = None


class TestKeywordHits:
    def test_predicate_hit(self):
        row = _FakeRow("has_revenue", {"text": "100亿", "value": 100.0})
        hits = AssertionSearchService._count_keyword_hits(row, ["revenue"])
        assert hits == 1

    def test_object_value_hit(self):
        row = _FakeRow("has_metric", {"text": "毛利率45%", "value": 45.0})
        hits = AssertionSearchService._count_keyword_hits(row, ["毛利率"])
        assert hits == 1

    def test_no_hit(self):
        row = _FakeRow("has_revenue", {"text": "100亿", "value": 100.0})
        hits = AssertionSearchService._count_keyword_hits(row, ["加息"])
        assert hits == 0

    def test_multi_keyword(self):
        row = _FakeRow("has_revenue", {"text": "营收100亿", "value": 100.0})
        hits = AssertionSearchService._count_keyword_hits(row, ["revenue", "营收"])
        assert hits == 2


class TestToAssertion:
    def test_full_field_mapping(self):
        row = _FakeRow("has_revenue", {"text": "100亿元", "value": 100.0}, confidence=0.85)
        a = AssertionSearchService._to_assertion(row)
        assert isinstance(a, Assertion)
        assert a.assertion_id == "a1"
        assert a.predicate == "has_revenue"
        assert a.object_value == {"text": "100亿元", "value": 100.0}
        assert a.confidence == 0.85
        assert a.source_doc_id == "d1"
        assert a.source_span.get("chunk_text") == "某公司营收100亿元"


class TestSearchEmpty:
    def test_empty_query_returns_empty(self):
        # search 需要 session_factory；用 None 构造仅测 query 为空早返回
        svc = AssertionSearchService(session_factory=None)
        assert svc.search("", top_k=5) == []
        assert svc.search("   ", top_k=5) == []
