"""中国证券网 — 正文新闻"""
from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(SourceSpec(
    source_type=SourceType.CNSTOCK,
    source_name="中国证券网",
    adapter_class="data_layer.adapters.cnstock_adapter.CNStockAdapter",
    adapter_kwargs={
        "channel": ["证券", "公司", "产经", "金融", "时政"],
    },
    interval_minutes=30,
    deep_backfill_enabled=True,
    doc_type=DocType.NEWS,
    reliability=SourceReliabilityLevel.OFFICIAL,
    backfill_family="cnstock",
    retrieval_weight=1.0,
))
