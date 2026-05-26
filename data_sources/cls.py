"""财联社 — 电报/快讯来源"""
from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(SourceSpec(
    source_type=SourceType.CLS,
    source_name="财联社",
    adapter_class="data_layer.adapters.cls_adapter.CLSAdapter",
    adapter_kwargs={
        "state_path": "./data/crawlers/cls/.dedup_state.json",
        "use_incremental": True,
    },
    interval_minutes=15,
    doc_type=DocType.NEWS,
    reliability=SourceReliabilityLevel.ESTABLISHED_MEDIA,
    backfill_family="cls",
    retrieval_weight=1.0,
))
