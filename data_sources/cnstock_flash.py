"""中国证券网·快讯"""

from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.CNSTOCK_FLASH,
        source_name="中国证券网·快讯",
        connector_class="connectors.document.cnstock.CNStockDocumentConnector",
        adapter_kwargs={
            "source_type": "cnstock_flash",
            "default_channel": "快讯",
            "max_pages": 2,
            "fetch_content": False,
        },
        connector_dataset="flash",
        pipeline_kind="document",
        interval_minutes=30,
        deep_backfill_enabled=False,
        doc_type=DocType.NEWS,
        reliability=SourceReliabilityLevel.ESTABLISHED_MEDIA,
        backfill_family="cnstock",
        retrieval_weight=1.0,
    )
)
