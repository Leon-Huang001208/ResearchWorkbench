"""
实体解析模块
"""

from knowledge_layer.entity_resolution.alias_manager import (
    AliasManager,
    create_default_alias_manager,
)
from knowledge_layer.entity_resolution.canonicalizer import Canonicalizer, Market, Venue
from knowledge_layer.entity_resolution.resolver import EntityResolver
from knowledge_layer.entity_resolution.types import EntityCandidate, EntityType, ResolvedEntity

__all__ = [
    "EntityType",
    "EntityCandidate",
    "ResolvedEntity",
    "Canonicalizer",
    "Market",
    "Venue",
    "EntityResolver",
    "AliasManager",
    "create_default_alias_manager",
]
