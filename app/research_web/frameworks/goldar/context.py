"""Framework-specific DSH context builder for Goldar."""

from .contracts import GoldSnapshot
from .definition import DEFINITION


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
        "allocation": snapshot.allocation_context.model_dump(mode="json"),
        "events": [item.model_dump(mode="json") for item in snapshot.events],
        "evidence": [item.model_dump(mode="json") for item in snapshot.evidence],
        "gaps": [item.model_dump(mode="json") for item in snapshot.gaps],
    }
