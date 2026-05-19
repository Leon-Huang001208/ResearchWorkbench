"""核心服务模块"""
from .asset_analysis_service import AssetAnalysisService
from .crawler_ingestion_bridge import CrawlerIngestionBridge
from .data_tier_service import DataTierService
from .document_chunker import ChunkingOptions, ChunkingStrategy, DocumentChunker
from .document_classifier import DocumentClassifier
from .document_enrichment import DocumentEnrichmentPipeline, EnrichmentConfig, EnrichmentResult
from .entity_extractor import EntityExtractor, EntityType
from .event_extractor import EventExtractor, ExtractedSignalParams

# Issue #47: 回测视角服务
from .historical_replay_service import HistoricalReplayService
from .ingest_service import IngestService
from .news_feature_service import NewsFeatureService
from .outcome_service import OutcomeService
from .rag_retrieval import (
    DocumentFilter,
    EvidencePackageBuilder,
    RAGRetrievalService,
    RecencyDecayScorer,
)
from .review_service import ReviewService
from .scenario_service import ScenarioService
from .signal_service import SignalService
from .signal_validator_impl import SignalValidatorImpl
from .summary_generator import SummaryGenerator
from .system_event_bus import SystemEventBus, event_bus
from .taxonomy_service import TaxonomyService

__all__ = [
    "AssetAnalysisService",
    "CrawlerIngestionBridge",
    "DocumentChunker",
    "ChunkingOptions",
    "ChunkingStrategy",
    "DocumentClassifier",
    "DocumentEnrichmentPipeline",
    "EnrichmentConfig",
    "EnrichmentResult",
    "EntityExtractor",
    "EntityType",
    "EventExtractor",
    "ExtractedSignalParams",
    "IngestService",
    "OutcomeService",
    "ReviewService",
    "ScenarioService",
    "SignalService",
    "SignalValidatorImpl",
    "SummaryGenerator",
    "TaxonomyService",
    # RAG Retrieval (Issue #45)
    "RecencyDecayScorer",
    "DocumentFilter",
    "EvidencePackageBuilder",
    "RAGRetrievalService",
    # Issue #47: 回测视角服务
    "HistoricalReplayService",
    "NewsFeatureService",
    "DataTierService",
    "SystemEventBus",
    "event_bus",
]
