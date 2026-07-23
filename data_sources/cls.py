"""财联社 — 电报/快讯来源"""

from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.CLS,
        source_name="财联社",
        connector_class="connectors.document.cls.CLSDocumentConnector",
        adapter_kwargs={
            "source_type": "cls",
            "state_path": "./data/crawlers/cls/.dedup_state.json",
            "use_incremental": True,
        },
        connector_dataset="telegram",
        pipeline_kind="document",
        interval_minutes=15,
        doc_type=DocType.NEWS,
        reliability=SourceReliabilityLevel.ESTABLISHED_MEDIA,
        backfill_family="cls",
        deep_backfill_enabled=True,
        retrieval_weight=1.0,
    )
)
