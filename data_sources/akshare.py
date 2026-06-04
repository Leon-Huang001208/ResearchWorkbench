"""AKShare — A股/指数行情数据源"""
from core.contracts.documents_v1 import SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.AKSHARE,
        source_name="AKShare",
        adapter_class="connectors.market.akshare.AkShareMarketConnector",
        adapter_kwargs={},
        interval_minutes=0,
        deep_backfill_enabled=True,
        backfill_family="akshare",
        retrieval_weight=1.0,
    )
)
