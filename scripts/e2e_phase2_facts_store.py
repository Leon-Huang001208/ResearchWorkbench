"""第二阶段 2.1+2.2 端到端 DB 验证（一次性脚本，验证后清理）.

验证内容：
1. SourceGrader 对 DocumentV1 回填 source_tier/trust_score/freshness_score
2. worker._persist_extraction_artifacts 真实落库 chunks/entity_mentions/assertions
3. assertion.source_span 含 chunk_text/offset（_enrich_assertion_spans 产出）

不依赖外部 LLM：直接构造 artifact 调用持久化函数，绕过并发抽取的 ModelGateway 依赖。
"""

import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, ".")

from core.contracts import (
    Assertion,
    DocType,
    DocumentChunkV1,
    DocumentV1,
    EntityMentionV1,
    SourceType,
)
from core.contracts.documents_v1 import (
    DocumentClassification,
    DocumentQuality,
    DocumentTimeliness,
)
from core.services.source_grader import SourceGrader
from data_layer.repositories.base import SessionLocal
from data_layer.repositories.models import Assertion as AssertionModel
from data_layer.repositories.models import (
    DocumentChunkV1DB,
    DocumentV1DB,
    EntityMentionV1DB,
    SourceDocument,
)

DOC_ID = f"e2e_test_{uuid.uuid4().hex[:8]}"
ITEM_ID = f"e2e_item_{uuid.uuid4().hex[:8]}"


def main() -> None:
    db = SessionLocal()
    try:
        # ── 1. SourceGrader 验证 ──
        doc = DocumentV1(
            doc_id=DOC_ID,
            doc_type=DocType.REPORT,
            source_type=SourceType.ZHIQIU_REPORTS,
            title="e2e 测试研报",
            content="某公司2024年营收100亿元，毛利率45%，同比增长20%。",
            classification=DocumentClassification(),
            quality=DocumentQuality(),
            timeliness=DocumentTimeliness(publish_time=datetime.now(timezone.utc)),
        )
        graded = SourceGrader().grade(doc)
        assert graded.source_tier == "tier_b", f"expected tier_b, got {graded.source_tier}"
        assert graded.trust_score is not None and 0 <= graded.trust_score <= 1
        assert graded.freshness_score is not None and graded.freshness_score > 0.9
        print(
            f"[1] grader OK: tier={graded.source_tier} trust={graded.trust_score:.2f} fresh={graded.freshness_score:.2f}"
        )

        # 先落 document_v1 + source_document（满足 FK）
        db.add(DocumentV1DB.from_contract(doc))

        class _FakeItem:
            item_id = ITEM_ID
            source_id = DOC_ID
            source_type = "zq"
            title = "e2e 测试研报"
            url = None
            raw_content = doc.content
            published_at = None

        db.add(
            SourceDocument(
                doc_id=DOC_ID,
                source_type="zq",
                title=doc.title,
                published_at=None,
                source_name="zq",
                content_hash="e2ehash",
                parser_version="e2e",
                object_uri=f"test://{DOC_ID}",
            )
        )
        db.flush()

        # ── 2. 构造 artifacts 调用持久化 ──
        chunk = DocumentChunkV1(
            chunk_id=f"chunk_{DOC_ID}",
            doc_id=DOC_ID,
            chunk_index=0,
            content="某公司2024年营收100亿元，毛利率45%。",
            start_offset=0,
            end_offset=20,
        )
        mention = EntityMentionV1(
            mention_id=f"ment_{DOC_ID}",
            doc_id=DOC_ID,
            entity_id=None,
            entity_name="600000.SH",
            entity_type="stock_code",
            start_offset=0,
            end_offset=10,
            confidence=0.95,
        )
        assertion = Assertion(
            assertion_id=f"asrt_{DOC_ID}",
            predicate="has_revenue",
            object_value={"text": "100亿元", "value": 100.0},
            confidence=0.85,
            source_doc_id=DOC_ID,
            source_span={
                "chunk_index": 0,
                "chunk_text": "某公司2024年营收100亿元",
                "offset_start": 0,
                "offset_end": 20,
                "extracted": {"object": "100亿"},
            },
            extractor_version="e2e_v1",
        )
        result = {
            "doc_id": DOC_ID,
            "doc": doc,
            "chunk_list": [chunk],
            "entity_list": [mention.model_dump()],
            "assertion_list": [assertion],
        }
        from workers.knowledge_worker import _persist_extraction_artifacts

        _persist_extraction_artifacts(db, result)
        db.commit()

        # ── 3. 断言落库 ──
        c = db.query(DocumentChunkV1DB).filter_by(doc_id=DOC_ID).all()
        m = db.query(EntityMentionV1DB).filter_by(doc_id=DOC_ID).all()
        a = db.query(AssertionModel).filter_by(source_doc_id=DOC_ID).all()
        assert len(c) == 1, f"chunks: expected 1, got {len(c)}"
        assert len(m) == 1, f"mentions: expected 1, got {len(m)}"
        assert len(a) == 1, f"assertions: expected 1, got {len(a)}"
        assert a[0].source_span.get("chunk_text") == "某公司2024年营收100亿元"
        assert "offset_start" in a[0].source_span
        print(f"[2] persist OK: chunks={len(c)} mentions={len(m)} assertions={len(a)}")
        print(f"    assertion span keys: {sorted(a[0].source_span.keys())}")
        print(f"    assertion predicate: {a[0].predicate}, object_value: {a[0].object_value}")

        print("\nALL E2E CHECKS PASSED")
    finally:
        # 清理测试数据
        db.query(AssertionModel).filter_by(source_doc_id=DOC_ID).delete()
        db.query(EntityMentionV1DB).filter_by(doc_id=DOC_ID).delete()
        db.query(DocumentChunkV1DB).filter_by(doc_id=DOC_ID).delete()
        db.query(SourceDocument).filter_by(doc_id=DOC_ID).delete()
        db.query(DocumentV1DB).filter_by(doc_id=DOC_ID).delete()
        db.commit()
        db.close()
        print("(test data cleaned up)")


if __name__ == "__main__":
    main()
