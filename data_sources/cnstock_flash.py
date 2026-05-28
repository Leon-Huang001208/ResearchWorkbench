"""中国证券网·快讯"""
from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.CNSTOCK_FLASH,
        source_name="中国证券网·快讯",
        adapter_class="data_layer.adapters.cnstock_adapter.CNStockAdapter",
        adapter_kwargs={
            "channel": "快讯",
        },
        interval_minutes=30,
        deep_backfill_enabled=True,
        doc_type=DocType.NEWS,
        reliability=SourceReliabilityLevel.ESTABLISHED_MEDIA,
        backfill_family="cnstock",
        retrieval_weight=1.0,
    )
)
