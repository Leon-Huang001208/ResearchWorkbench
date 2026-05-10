"""核心服务模块"""
from .asset_analysis_service import AssetAnalysisService
from .document_chunker import ChunkingOptions, ChunkingStrategy, DocumentChunker
from .document_classifier import DocumentClassifier
from .document_enrichment import DocumentEnrichmentPipeline, EnrichmentConfig, EnrichmentResult
from .entity_extractor import EntityExtractor, EntityType
from .event_extractor import EventExtractor, ExtractedSignalParams
from .ingest_service import IngestService
from .outcome_service import OutcomeService
from .review_service import ReviewService
from .scenario_service import ScenarioService
from .signal_service import SignalService
from .signal_validator_impl import SignalValidatorImpl
from .summary_generator import SummaryGenerator
from .taxonomy_service import TaxonomyService
from .rag_retrieval import (
    RecencyDecayScorer,
    DocumentFilter,
    EvidencePackageBuilder,
    RAGRetrievalService,
)
# Issue #47: 回测视角服务
from .historical_replay_service import HistoricalReplayService
from .news_feature_service import NewsFeatureService
from .data_tier_service import DataTierService

__all__ = [
    "AssetAnalysisService",
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
]
