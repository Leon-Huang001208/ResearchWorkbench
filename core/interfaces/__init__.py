"""
Core interfaces (abstract base classes) for AlphaFoundry components.

This package defines abstract base classes (interfaces) for key AlphaFoundry components,
including data adapters, model gateways, reasoning engines, report composers, repositories,
and signal validators.
"""
from .data_adapter import DataAdapter
from .model_gateway import EmbeddingResponse, ModelGateway, ModelResponse
from .reasoning_engine import ReasoningEngine
from .report_composer import ReportComposer
from .repository import (
    AssertionRepository,
    AssetSnapshotRepository,
    DocumentRepository,
    EntityRepository,
    EventRepository,
    Repository,
    TraceRepository,
)
from .signal_validator import SignalValidator

__all__ = [
    "DataAdapter",
    "ModelGateway",
    "ModelResponse",
    "EmbeddingResponse",
    "ReasoningEngine",
    "ReportComposer",
    "SignalValidator",
    "Repository",
    "EntityRepository",
    "DocumentRepository",
    "AssertionRepository",
    "EventRepository",
    "TraceRepository",
    "AssetSnapshotRepository",
]
