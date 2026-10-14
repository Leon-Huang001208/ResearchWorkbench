"""Framework-specific DSH context builder for embedded frameworks."""

from .contracts import EmbeddedSnapshot
from .definition import DEFINITION


def build_context(snapshot: EmbeddedSnapshot) -> dict:
    return {
        "research_question": DEFINITION.question,
        "chain": DEFINITION.chain,
        "counter_evidence": DEFINITION.counter_evidence,
        "state": snapshot.research_state.model_dump(mode="json"),
        "external_app": snapshot.external_app.model_dump(mode="json"),
        "overview": snapshot.overview.model_dump(mode="json"),
        "gaps": [item.model_dump(mode="json") for item in snapshot.gaps],
    }
