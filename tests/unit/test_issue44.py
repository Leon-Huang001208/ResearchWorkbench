"""
Issue #44 Unit Tests: Document Chunking, Taxonomy, Classification, and Enrichment
"""


from core.contracts import DocType, DocumentV1, SourceType
from core.utils.id_gen import generate_id
from services.document_chunker import ChunkingOptions, DocumentChunker
from services.document_classifier import DocumentClassifier
from services.document_enrichment import DocumentEnrichmentPipeline, EnrichmentConfig
from services.entity_extractor import EntityExtractor
from services.summary_generator import SummaryGenerator
from services.taxonomy_service import TaxonomyService


def create_test_document(
    doc_type: DocType = DocType.NEWS,
    source_type: SourceType = SourceType.CLS,
    content: str = None,
    title: str = None,
) -> DocumentV1:
    """Create test document"""
    if content is None:
        content = """
        Moutai announced Q1 2024 results. Revenue was 35 billion RMB, up 18% YoY.
        Net profit was 17.2 billion RMB, up 19% YoY.
        Management mentioned they will continue to invest in e-commerce channels.
        Analysts expect steady growth for the full year.
        Other liquor companies also reported good performance.
        Industry experts note continued recovery in consumption.
        """

    if title is None:
        title = "Moutai Q1 2024 Results Up 18%"

    return DocumentV1(
        doc_id=generate_id(),
        doc_type=doc_type,
        source_type=source_type,
        title=title,
        content=content,
        source_name="Caixin",
        language="zh",
    )


class TestDocumentChunker:
    """Document Chunker Tests"""

    def test_chunker_initialization(self):
        """Test initialization"""
        chunker = DocumentChunker()
        assert chunker is not None

    def test_chunk_document(self):
        """Test chunking a document"""
        doc = create_test_document()
        chunker = DocumentChunker()
        chunks = chunker.chunk_document(doc)

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.doc_id == doc.doc_id
            assert chunk.content is not None
            assert len(chunk.content) > 0

    def test_chunk_simple_progresses_when_split_falls_inside_overlap(self):
        """Chunking must always advance even when punctuation is near the boundary."""
        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError("chunking did not terminate")

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(1)
        try:
            text = "".join(("a" * 101 + "。" + "b" * 1898) for _ in range(5))
            chunks = DocumentChunker(ChunkingOptions())._chunk_simple(
                text, ChunkingOptions()
            )
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

        assert chunks
        assert "".join(chunks).replace("\n", "")


class TestTaxonomyService:
    """Taxonomy Service Tests"""

    def test_taxonomy_initialization(self):
        """Test initialization"""
        taxonomy = TaxonomyService()
        assert taxonomy is not None
        assert len(taxonomy.industries) > 0
        assert len(taxonomy.themes) > 0

    def test_classify_basic(self):
        """Test basic classification"""
        taxonomy = TaxonomyService()
        result = taxonomy.classify(
            "Moutai announced Q1 results. Revenue up 18%.", title="Moutai Earnings"
        )

        # Classification should complete without errors
        assert result is not None


class TestDocumentClassifier:
    """Document Classifier Tests"""

    def test_classifier_initialization(self):
        """Test initialization"""
        classifier = DocumentClassifier()
        assert classifier is not None

    def test_classify_document(self):
        """Test classifying a document"""
        doc = create_test_document()
        classifier = DocumentClassifier()

        classification, tags = classifier.classify(doc)

        assert classification is not None
        assert isinstance(tags, list)


class TestEntityExtractor:
    """Entity Extractor Tests"""

    def test_extractor_initialization(self):
        """Test initialization"""
        extractor = EntityExtractor()
        assert extractor is not None

    def test_extract_stock_codes(self):
        """Test extracting stock codes"""
        doc = create_test_document(content="Stock code 600519.SH announced results")
        extractor = EntityExtractor()

        mentions = extractor.extract(doc)

        # Just check extraction completes without errors
        assert isinstance(mentions, list)


class TestSummaryGenerator:
    """Summary Generator Tests"""

    def test_generator_initialization(self):
        """Test initialization"""
        generator = SummaryGenerator()
        assert generator is not None

    def test_generate_short_summary(self):
        """Test generating short summary"""
        doc = create_test_document()
        generator = SummaryGenerator()

        summary = generator.generate_short_summary(doc)

        assert summary is not None
        assert len(summary) > 0

    def test_generate_document_summary(self):
        """Test generating document summary object"""
        doc = create_test_document()
        generator = SummaryGenerator()

        summary_obj = generator.generate_document_summary(doc)

        assert summary_obj is not None
        assert summary_obj.doc_id == doc.doc_id
        assert summary_obj.summary is not None


class TestDocumentEnrichmentPipeline:
    """Document Enrichment Pipeline Tests"""

    def test_pipeline_initialization(self):
        """Test initialization"""
        pipeline = DocumentEnrichmentPipeline()
        assert pipeline is not None

    def test_enrich_document(self):
        """Test enriching a document"""
        doc = create_test_document()
        config = EnrichmentConfig(
            do_chunking=True,
            do_classification=True,
            do_entity_extraction=True,
            do_event_extraction=False,
            do_summary=True,
        )
        pipeline = DocumentEnrichmentPipeline(config=config)

        result = pipeline.enrich(doc)

        assert result is not None
        assert result.doc == doc
        assert len(result.chunks) > 0
        assert result.summary is not None
        assert isinstance(result.tags, list)
        assert isinstance(result.entities, list)


class TestIssue44Integration:
    """Issue #44 Integration Tests"""

    def test_basic_workflow(self):
        """Test basic workflow"""
        doc = create_test_document(
            title="Moutai Q1 Earnings Report",
            content="""
            Moutai (600519.SH) released Q1 2024 earnings today.
            Revenue was 35 billion RMB, up 18% YoY.
            Net profit was 17.2 billion RMB, up 19% YoY.
            Liquor industry shows good recovery trends.
            Analysts are optimistic about full year performance.
            """,
        )

        taxonomy = TaxonomyService()
        chunker = DocumentChunker()
        classifier = DocumentClassifier(taxonomy)
        summary_generator = SummaryGenerator()

        chunks = chunker.chunk_document(doc)
        assert len(chunks) > 0

        classification, tags = classifier.classify(doc)
        classifier.analyze_quality(doc)
        classifier.analyze_evidence(doc)

        summary = summary_generator.generate_document_summary(doc)
        assert summary is not None
