"""巨潮资讯网 — 上市公司公告"""
from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.CNINFO,
        source_name="巨潮资讯网",
        adapter_class="connectors.document.cninfo.CninfoDocumentConnector",
        adapter_kwargs={
            "plate": "all",
            "page_size": 30,
            "max_pages": 5,
        },
        interval_minutes=60,
        deep_backfill_enabled=True,
        doc_type=DocType.FILING,
        reliability=SourceReliabilityLevel.OFFICIAL,
        backfill_family="cninfo",
        retrieval_weight=1.0,
    )
)
