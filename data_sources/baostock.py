"""BaoStock — A股日线/分钟线行情数据源"""
from core.contracts.documents_v1 import SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.BAOSTOCK,
        source_name="BaoStock",
        adapter_class="connectors.market.baostock.BaostockMarketConnector",
        adapter_kwargs={},
        interval_minutes=0,
        deep_backfill_enabled=True,
        backfill_family="baostock",
        retrieval_weight=1.0,
        fallback_group="daily_quotes_cn",
        fallback_priority=2,  # 第二备源
    )
)
