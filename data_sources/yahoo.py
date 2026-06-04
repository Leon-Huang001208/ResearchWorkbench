"""Yahoo Finance — 全球股票行情数据源"""
from core.contracts.documents_v1 import SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.YAHOO,
        source_name="Yahoo Finance",
        connector_class="connectors.market.yahoo.YahooMarketConnector",
        adapter_kwargs={},
        connector_dataset="stock_daily",
        pipeline_kind="market",
        interval_minutes=0,
        deep_backfill_enabled=True,
        backfill_family="yahoo",
        retrieval_weight=1.0,
    )
)
