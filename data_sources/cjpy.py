"""天软 (Tinysoft) 数据源注册"""

from core.contracts.documents_v1 import SourceType
from core.source_registry import SourceSpec, register

register(
    SourceSpec(
        source_type=SourceType.CJPY,
        source_name="Tinysoft (天软)",
        adapter_class="connectors.market.cjpy.CjpyMarketConnector",
        adapter_kwargs={},
        interval_minutes=0,
        backfill_family="tinysoft",
        retrieval_weight=1.0,
        fallback_group="daily_quotes_cn",
        fallback_priority=0,  # 主源 — 最快、最可靠
    )
)
