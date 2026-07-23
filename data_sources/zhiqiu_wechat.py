"""知丘 — 公众号文章"""

from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.ZHIQIU_WECHAT,
        source_name="知丘公众号",
        connector_class="connectors.document.zq.ZQDocumentConnector",
        adapter_kwargs={
            "source_type": "zhiqiu_wechat",
            "doc_types": "NEWS",
        },
        connector_dataset="news",
        pipeline_kind="document",
        interval_minutes=30,
        deep_backfill_enabled=True,
        doc_type=DocType.NEWS,
        reliability=SourceReliabilityLevel.SPECIALIZED_MEDIA,
        backfill_family="zq",
        retrieval_weight=1.0,
    )
)
