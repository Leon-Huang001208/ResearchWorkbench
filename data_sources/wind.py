"""Wind — 万得终端行情/财务/一致预期数据源"""
from core.contracts.documents_v1 import SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.WIND,
        source_name="Wind",
        connector_class="connectors.market.wind.WindMarketConnector",
        adapter_kwargs={},
        connector_dataset="daily_quotes",
        pipeline_kind="market",
        interval_minutes=0,
        backfill_family="wind",
        retrieval_weight=0.0,
        fallback_group="daily_quotes_cn",
        fallback_priority=1,  # 第一备源 — 慢但数据完整（当可用时）
    )
)
