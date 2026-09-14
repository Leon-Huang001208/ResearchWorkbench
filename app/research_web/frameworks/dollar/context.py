"""Framework-specific DSH context builder for dollar liquidity."""

from .contracts import DollarSnapshot
from .definition import DEFINITION


def build_context(snapshot: DollarSnapshot) -> dict:
    return {
        "research_question": DEFINITION.question,
        "chain": DEFINITION.chain,
        "counter_evidence": DEFINITION.counter_evidence,
        "state": snapshot.research_state.model_dump(mode="json"),
        "dimensions": {
            "Q": snapshot.quantity_q.model_dump(mode="json"),
            "P": snapshot.price_p.model_dump(mode="json"),
            "g": snapshot.fiscal_g.model_dump(mode="json"),
            "M": snapshot.plumbing_m.model_dump(mode="json"),
            "X": snapshot.cross_border_x.model_dump(mode="json"),
        },
        "transmission": snapshot.transmission.model_dump(mode="json"),
        "events": [item.model_dump(mode="json") for item in snapshot.events],
        "evidence": [item.model_dump(mode="json") for item in snapshot.evidence],
        "gaps": [item.model_dump(mode="json") for item in snapshot.gaps],
    }
