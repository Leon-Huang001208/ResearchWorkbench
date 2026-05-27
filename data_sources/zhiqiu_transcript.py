"""知丘 — 会议纪要"""
from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.ZHIQIU_TRANSCRIPT,
        source_name="知丘纪要",
        adapter_class="data_layer.adapters.zq_adapter.ZQAdapter",
        adapter_kwargs={
            "doc_types": "ZQMEETING",
        },
        interval_minutes=60,
        deep_backfill_enabled=True,
        doc_type=DocType.REPORT,
        reliability=SourceReliabilityLevel.RESEARCH_INSTITUTE,
        backfill_family="zq",
        retrieval_weight=1.3,
    )
)
