"""Framework-specific DSH context builder for Goldar."""

from urllib.parse import urlsplit

from core.observability import get_logger

from .contracts import GoldSnapshot
from .definition import DEFINITION

log = get_logger(__name__)


def _allocation_context(snapshot: GoldSnapshot) -> dict:
    block = snapshot.allocation_context
    connected = block.status not in {"fixture", "missing"} and bool(block.sources)
    for source in block.sources:
        try:
            url = urlsplit(source.url)
            host = url.hostname or ""
            connected = connected and (
                url.scheme in {"http", "https"}
                and bool(host)
                and not host.endswith(".invalid")
                and host != "invalid"
                and "fixture" not in source.method.casefold()
            )
        except ValueError:
            log.warning("gold_allocation_source_invalid")
            connected = False
    if connected:
        return block.model_dump(mode="json")
    log.info("gold_allocation_not_connected", status=block.status)
    return {
        "status": "missing",
        "availability": "not_connected",
        "reason": "尚未接入：缺少带来源、观测窗口与计算口径的配置研究数据。",
        "gaps": [item.model_dump(mode="json") for item in block.gaps],
    }


def build_context(snapshot: GoldSnapshot) -> dict:
    return {
        "research_question": DEFINITION.question,
        "chain": DEFINITION.chain,
        "counter_evidence": DEFINITION.counter_evidence,
        "state": snapshot.research_state.model_dump(mode="json"),
        "market_context": snapshot.market_context.model_dump(mode="json"),
        "drivers": snapshot.pricing_drivers.model_dump(mode="json"),
        "supply_demand": snapshot.supply_demand.model_dump(mode="json"),
        "cycle_macro": snapshot.cycle_macro.model_dump(mode="json"),
        "options": snapshot.options.model_dump(mode="json"),
        "allocation": _allocation_context(snapshot),
        "events": [item.model_dump(mode="json") for item in snapshot.events],
        "evidence": [item.model_dump(mode="json") for item in snapshot.evidence],
        "gaps": [item.model_dump(mode="json") for item in snapshot.gaps],
    }
