"""中国证券网 — 正文新闻"""
from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.CNSTOCK,
        source_name="中国证券网",
        connector_class="connectors.document.cnstock.CNStockDocumentConnector",
        adapter_kwargs={
            "source_type": "cnstock",
            "default_channel": "证券",
            "all_channels": False,
            "max_pages": 2,
            "fetch_content": False,
        },
        connector_dataset="news",
        pipeline_kind="document",
        interval_minutes=30,
        deep_backfill_enabled=False,
        doc_type=DocType.NEWS,
        reliability=SourceReliabilityLevel.OFFICIAL,
        backfill_family="cnstock",
        retrieval_weight=1.0,
    )
)
