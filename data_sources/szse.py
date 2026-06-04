"""深圳证券交易所 — 深市上市公司数据"""
from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.SZSE,
        source_name="深圳证券交易所",
        adapter_class="connectors.market.szse.SzseMarketConnector",
        adapter_kwargs={
            "timeout": 30,
            "catalog_id": "1110",
        },
        interval_minutes=120,
        deep_backfill_enabled=False,
        doc_type=DocType.FILING,
        reliability=SourceReliabilityLevel.OFFICIAL,
        backfill_family="szse",
        retrieval_weight=1.0,
    )
)
