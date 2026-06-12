"""知丘 — 券商研报"""
from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.ZHIQIU_REPORTS,
        source_name="知丘研报",
        connector_class="connectors.document.zq.ZQDocumentConnector",
        adapter_kwargs={
            "source_type": "zhiqiu_reports",
            "doc_types": "REPORT",
            "use_homepage_search": False,
            "enable_pdf": False,
        },
        connector_dataset="report",
        pipeline_kind="document",
        interval_minutes=60,
        days_per_crawl=2,
        deep_backfill_enabled=True,
        doc_type=DocType.REPORT,
        reliability=SourceReliabilityLevel.RESEARCH_INSTITUTE,
        backfill_family="zq",
        retrieval_weight=1.3,
    )
)
