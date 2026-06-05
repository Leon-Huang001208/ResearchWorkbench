"""巨潮资讯网 — 上市公司公告"""
from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.CNINFO,
        source_name="巨潮资讯网",
        connector_class="connectors.document.cninfo.CninfoDocumentConnector",
        adapter_kwargs={
            "source_type": "cninfo",
            "plate": "all",
            "page_size": 30,
            "max_pages": 5,
            "trust_env": False,
            # 巨潮公告是官方事实源，默认抽取 PDF 正文；下载有超时和大小保护。
            "fetch_attachment_text": True,
            "preferred_converter": "auto",
        },
        connector_dataset="announcements",
        pipeline_kind="document",
        interval_minutes=60,
        deep_backfill_enabled=True,
        doc_type=DocType.FILING,
        reliability=SourceReliabilityLevel.OFFICIAL,
        backfill_family="cninfo",
        retrieval_weight=1.0,
    )
)
