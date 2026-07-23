"""知丘 — 会议纪要"""

from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.ZHIQIU_TRANSCRIPT,
        source_name="知丘纪要",
        connector_class="connectors.document.zq.ZQDocumentConnector",
        adapter_kwargs={
            "source_type": "zhiqiu_transcript",
            "doc_types": "ZQMEETING",
        },
        connector_dataset="meeting",
        pipeline_kind="document",
        interval_minutes=60,
        days_per_crawl=3,
        deep_backfill_enabled=True,
        doc_type=DocType.REPORT,
        reliability=SourceReliabilityLevel.RESEARCH_INSTITUTE,
        backfill_family="zq",
        retrieval_weight=1.3,
    )
)
