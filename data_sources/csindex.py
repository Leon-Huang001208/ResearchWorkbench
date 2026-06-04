"""中证指数 — 指数成分股、权重、估值"""
from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.CSINDEX,
        source_name="中证指数",
        adapter_class="connectors.market.csindex.CsindexMarketConnector",
        adapter_kwargs={
            "timeout": 30,
        },
        interval_minutes=120,
        deep_backfill_enabled=False,
        doc_type=DocType.FILING,
        reliability=SourceReliabilityLevel.OFFICIAL,
        backfill_family="csindex",
        retrieval_weight=0.8,
    )
)
