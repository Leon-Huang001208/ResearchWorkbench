"""Time-aware Temporal Industry Graph"""

from core.contracts.industry_chain import PropagationPath as CorePropagationPath
from core.contracts.industry_chain import PropagationStep

from .contracts import PropagationPath  # deprecated — use CorePropagationPath
from .contracts import IndustryChain, RelationshipType, SupplyChainPosition, TemporalRelation
from .graph_store import IndustryGraphStore
from .propagation import PropagationAnalyzer
from .repository import GraphRepository

__all__ = [
    "RelationshipType",
    "SupplyChainPosition",
    "TemporalRelation",
    "IndustryChain",
    "PropagationPath",  # deprecated
    "CorePropagationPath",
    "PropagationStep",
    "IndustryGraphStore",
    "PropagationAnalyzer",
    "GraphRepository",
]
