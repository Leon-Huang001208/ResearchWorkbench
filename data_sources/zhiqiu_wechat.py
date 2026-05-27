"""知丘 — 公众号文章"""
from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.ZHIQIU_WECHAT,
        source_name="知丘公众号",
        adapter_class="data_layer.adapters.zq_adapter.ZQAdapter",
        adapter_kwargs={
            "doc_types": "NEWS",
        },
        interval_minutes=30,
        deep_backfill_enabled=True,
        doc_type=DocType.NEWS,
        reliability=SourceReliabilityLevel.SPECIALIZED_MEDIA,
        backfill_family="zq",
        retrieval_weight=1.0,
    )
)
