#!/usr/bin/env python3
"""
Backfill source documents and factual layers from object storage artifacts.

Usage:
    python scripts/backfill_from_objects.py [--scan-only] [--force-reextract]

This script is idempotent: repeated runs will not create duplicates; 
existing records with matching content hashes will be skipped or updated safely.
"""
import hashlib
import json
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.observability import get_logger
from core.settings import settings
from data_layer.repositories.base import check_database_connection, get_db
from data_layer.repositories.document_repository import DocumentRepository
from data_layer.repositories.event_repository import EventRepositoryImpl
from data_layer.repositories.models import Assertion, SourceDocument
from ingestion.structured_event_ingestion import AssertionExtractor, StructuredEventIngestor

logger = get_logger(__name__)


class BackfillReporter:
    """Collect and report backfill statistics."""

    def __init__(self):
        self.stats = {
            "total_artifacts_scanned": 0,
            "source_docs_restored": 0,
            "source_docs_skipped": 0,
            "source_docs_failed": 0,
            "assertions_regenerated": 0,
            "assertions_skipped": 0,
            "events_regenerated": 0,
            "extraction_failed": 0,
            "unrecoverable_artifacts": 0,
        }
        self.details = {"restored": [], "skipped": [], "failed": [], "unrecoverable": []}

    def add_success(self, doc_id: str, path: str, restored: bool):
        if restored:
            self.stats["source_docs_restored"] += 1
            self.details["restored"].append({"doc_id": doc_id, "path": str(path)})
        else:
            self.stats["source_docs_skipped"] += 1
            self.details["skipped"].append({"doc_id": doc_id, "path": str(path)})

    def add_failure(self, path: Path, reason: str, unrecoverable: bool = False):
        if unrecoverable:
            self.stats["unrecoverable_artifacts"] += 1
            self.details["unrecoverable"].append({"path": str(path), "reason": reason})
        else:
            self.stats["source_docs_failed"] += 1
            self.details["failed"].append({"path": str(path), "reason": reason})

    def add_extraction_result(self, assertions: int, events: int, failed: bool):
        self.stats["assertions_regenerated"] += assertions
        self.stats["events_regenerated"] += events
        if failed:
            self.stats["extraction_failed"] += 1

    def print_summary(self):
        """Print summary report to logger."""
        logger.info("=" * 60)
        logger.info("BACKFILL SUMMARY REPORT")
        logger.info("=" * 60)
        for key, value in self.stats.items():
            logger.info(f"{key.replace('_', ' ').title()}: {value}")
        logger.info("=" * 60)

        if self.details["failed"]:
            logger.warning("Failed entries:")
            for entry in self.details["failed"]:
                logger.warning(f"  - {entry['path']}: {entry['reason']}")

        if self.details["unrecoverable"]:
            logger.error("Unrecoverable artifacts:")
            for entry in self.details["unrecoverable"]:
                logger.error(f"  - {entry['path']}: {entry['reason']}")


def compute_content_hash(content: bytes) -> str:
    """Compute SHA-256 content hash for deduplication."""
    return hashlib.sha256(content).hexdigest()


def generate_doc_id(content_hash: str) -> str:
    """Generate stable doc id from content hash."""
    return f"doc_{content_hash[:16]}"


def load_artifact(path: Path) -> Optional[Dict[str, Any]]:
    """
    Load an artifact from storage. Supports:
    - JSON metadata + content artifacts
    - Raw text files (with inferred metadata from filename/path)
    - Raw binary files (PDFs, etc.)
    """
    try:
        if path.suffix.lower() == ".json":
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        elif path.suffix.lower() in [".txt", ".md"]:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                return {
                    "raw_text": content,
                    "source_type": "raw_text",
                    "source_name": path.name,
                    "title": path.stem,
                }
        else:
            # Binary artifact - return raw bytes and basic metadata
            with open(path, "rb") as f:
                content = f.read()
                return {
                    "binary_content": content,
                    "source_type": "binary",
                    "source_name": path.name,
                    "content_type": f"application/{path.suffix.lstrip('.')}"
                    if path.suffix
                    else "application/octet-stream",
                }
    except Exception as e:
        logger.error(f"Failed to load artifact {path}: {str(e)}", exc_info=True)
        return None


def upsert_source_document(
    db, artifact_path: Path, artifact: Dict[str, Any], force_reextract: bool = False
) -> Tuple[bool, Optional[SourceDocument]]:
    """
    Upsert source document into database. Idempotent: existing document with
    matching content hash will not be recreated unless content changed.

    Returns (is_new_or_updated, source_doc)
    """
    # Extract content for hashing
    if "raw_text" in artifact:
        content_bytes = artifact["raw_text"].encode("utf-8")
    elif "binary_content" in artifact:
        content_bytes = artifact["binary_content"]
    else:
        # If artifact has content uri, but we have the metadata anyway
        content_bytes = json.dumps(artifact, sort_keys=True).encode("utf-8")

    content_hash = compute_content_hash(content_bytes)
    doc_id = generate_doc_id(content_hash)

    # Check existing
    existing = db.query(SourceDocument).filter_by(doc_id=doc_id).first()

    try:
        object_uri = f"file://{artifact_path.relative_to(settings.PROJECT_ROOT)}"
    except ValueError:
        # If path is outside project root (tests, etc), use absolute path
        object_uri = f"file://{artifact_path.absolute()}"

    # Extract metadata
    source_type = artifact.get("source_type", "unknown")
    source_name = artifact.get("source_name", artifact_path.name)
    title = artifact.get("title", artifact_path.stem)
    published_at = artifact.get("published_at")
    rights_ref = artifact.get("rights_ref")
    parser_version = artifact.get("parser_version", "backfill-v1")
    doc_metadata = artifact.get("doc_metadata", artifact.get("metadata", {}))

    if existing:
        if existing.content_hash == content_hash and not force_reextract:
            # No changes needed
            logger.debug(f"Source document already exists with same content: {doc_id}, skipping")
            return False, existing
        else:
            # Update existing record (content changed or forced re-extract)
            logger.debug(f"Updating existing source document: {doc_id}")
            existing.source_type = source_type
            existing.title = title
            existing.published_at = published_at
            existing.source_name = source_name
            existing.content_hash = content_hash
            existing.rights_ref = rights_ref
            existing.parser_version = parser_version
            existing.object_uri = object_uri
            existing.doc_metadata = doc_metadata
            return True, existing
    else:
        # Create new
        source_doc = SourceDocument(
            doc_id=doc_id,
            source_type=source_type,
            title=title,
            published_at=published_at,
            source_name=source_name,
            content_hash=content_hash,
            rights_ref=rights_ref,
            parser_version=parser_version,
            object_uri=object_uri,
            doc_metadata=doc_metadata,
        )
        db.add(source_doc)
        return True, source_doc


def generate_assertion_id(doc_id: str, assertion_index: int, content_hash: str) -> str:
    """Generate deterministic assertion id for deduplication based on source doc and content"""
    combined = f"{doc_id}:{assertion_index}:{content_hash[:16]}"
    return f"assert_{hashlib.sha256(combined.encode('utf-8')).hexdigest()[:16]}"


def run_extraction(
    db,
    source_doc: SourceDocument,
    artifact: Dict[str, Any],
    assertion_extractor: AssertionExtractor,
    event_ingestor: StructuredEventIngestor,
    force_reextract: bool = False,
) -> Tuple[int, int, int, bool]:
    """
    Re-run extraction pipeline from restored source content.
    Returns (num_assertions_regenerated, num_assertions_persisted, num_events, extraction_failed)
    """
    failed = False
    assertions_extracted = 0
    assertions_persisted = 0
    events_created = 0
    content_hash = source_doc.content_hash
    extractor_version = f"backfill-{assertion_extractor.__class__.__name__}-v1"

    try:
        raw_text = artifact.get("raw_text")
        if not raw_text:
            if "binary_content" in artifact:
                # If it's a PDF we would need a parser, but for backfill
                # we just skip and note that extraction isn't possible
                logger.debug(
                    f"Binary artifact {source_doc.doc_id} requires external parsing, skipping extraction"
                )
                return 0, 0, 0, False

            logger.debug(f"No raw text available for extraction for doc {source_doc.doc_id}")
            return 0, 0, 0, False

        # Extract assertions
        raw_assertions = assertion_extractor.extract_assertions(
            raw_text, {"doc_id": source_doc.doc_id, "source_type": source_doc.source_type}
        )

        assertions_extracted = len(raw_assertions)

        # Persist each assertion to database with idempotency
        for idx, raw_assertion in enumerate(raw_assertions):
            # Generate stable assertion id for deduplication
            assertion_id = generate_assertion_id(source_doc.doc_id, idx, content_hash)

            # Check if assertion already exists
            existing = db.query(Assertion).filter_by(assertion_id=assertion_id).first()

            if existing and not force_reextract:
                logger.debug(f"Assertion {assertion_id} already exists, skipping")
                continue

            # Map extracted fields to Assertion model
            # Extract core triple if available
            subject = raw_assertion.get("subject")
            predicate = raw_assertion.get(
                "predicate", raw_assertion.get("impact_direction", "mentions")
            )
            obj = raw_assertion.get("object")

            # Build assertion object
            assertion = Assertion(
                assertion_id=assertion_id,
                subject_entity_id=subject if subject else None,
                predicate=predicate,
                object_entity_id=obj if obj else None,
                object_value=raw_assertion if not obj else None,
                confidence=raw_assertion.get("confidence", 0.5),
                source_doc_id=source_doc.doc_id,
                source_span={
                    "start": raw_assertion.get("evidence_start", 0),
                    "end": raw_assertion.get("evidence_end", 0),
                    "text": raw_assertion.get("text", ""),
                },
                extractor_version=extractor_version,
                trace_ref=raw_assertion.get("trace_ref"),
                team_id=source_doc.team_id,
                project_id=source_doc.project_id,
            )

            if existing:
                # Update existing assertion if forced
                existing.subject_entity_id = assertion.subject_entity_id
                existing.predicate = assertion.predicate
                existing.object_entity_id = assertion.object_entity_id
                existing.object_value = assertion.object_value
                existing.confidence = assertion.confidence
                existing.source_span = assertion.source_span
                existing.extractor_version = assertion.extractor_version
                existing.trace_ref = assertion.trace_ref
            else:
                # Add new assertion
                db.add(assertion)

            assertions_persisted += 1

        # If we have a raw_event structure, ingest as canonical event
        if "event_type" in artifact:
            # Add doc reference to raw event
            artifact["source_doc_id"] = source_doc.doc_id
            result = event_ingestor.ingest(artifact)
            if result.status == "success":
                events_created = 1

        logger.debug(
            f"Extraction complete for doc {source_doc.doc_id}: "
            f"{assertions_extracted} extracted, {assertions_persisted} persisted"
        )

    except Exception as e:
        logger.error(f"Extraction failed for doc {source_doc.doc_id}: {str(e)}", exc_info=True)
        failed = True

    return assertions_extracted, assertions_persisted, events_created, failed


def main():
    parser = ArgumentParser()
    parser.add_argument(
        "--scan-only", action="store_true", help="Only scan, do not modify database"
    )
    parser.add_argument(
        "--force-reextract", action="store_true", help="Force re-extraction even if document exists"
    )
    args = parser.parse_args()

    reporter = BackfillReporter()
    logger.info(f"Starting backfill from object storage: {settings.OBJECT_STORAGE_PATH}")
    logger.info(f"Scan-only: {args.scan_only}, force-reextract: {args.force_reextract}")

    # Check database connectivity
    try:
        check_database_connection()
        logger.info("✅ Database connectivity verified")
    except Exception as e:
        logger.critical(f"Database connection failed: {str(e)}", exc_info=True)
        sys.exit(1)

    # Check that object storage exists
    if not settings.OBJECT_STORAGE_PATH.exists():
        logger.error(f"Object storage path {settings.OBJECT_STORAGE_PATH} does not exist")
        reporter.stats["unrecoverable_artifacts"] = 0
        reporter.print_summary()
        sys.exit(1)

    # Initialize services
    doc_repo = DocumentRepository()
    event_repo = EventRepositoryImpl()
    assertion_extractor = AssertionExtractor()
    event_ingestor = StructuredEventIngestor(event_repo)

    # Scan all files in object storage (recursive)
    artifact_paths = list(settings.OBJECT_STORAGE_PATH.rglob("*"))
    artifact_paths = [p for p in artifact_paths if p.is_file()]
    logger.info(f"Found {len(artifact_paths)} files to scan")

    # Process each artifact
    with get_db() as db:
        for artifact_path in artifact_paths:
            reporter.stats["total_artifacts_scanned"] += 1

            if artifact_path.name == ".DS_Store":
                reporter.stats["source_docs_skipped"] += 1
                continue

            logger.debug(f"Processing {artifact_path}")
            artifact = load_artifact(artifact_path)

            if not artifact:
                reporter.add_failure(artifact_path, "Failed to load artifact", unrecoverable=True)
                continue

            try:
                changed, source_doc = upsert_source_document(
                    db, artifact_path, artifact, args.force_reextract
                )

                if changed:
                    reporter.add_success(source_doc.doc_id, artifact_path, restored=True)
                else:
                    reporter.add_success(source_doc.doc_id, artifact_path, restored=False)

                if not args.scan_only and source_doc and (changed or args.force_reextract):
                    assertions_extracted, assertions_persisted, events, failed = run_extraction(
                        db,
                        source_doc,
                        artifact,
                        assertion_extractor,
                        event_ingestor,
                        force_reextract=args.force_reextract,
                    )
                    # Report all regenerated assertions, but track actual persistence
                    # For future: we could add a separate counter for skipped assertions
                    reporter.stats["assertions_skipped"] = reporter.stats.get(
                        "assertions_skipped", 0
                    ) + (assertions_extracted - assertions_persisted)
                    reporter.add_extraction_result(assertions_persisted, events, failed)

            except Exception as e:
                logger.error(f"Failed to process {artifact_path}: {str(e)}", exc_info=True)
                reporter.add_failure(artifact_path, f"Processing failed: {str(e)}")

        if not args.scan_only:
            logger.info("Committing database changes...")
            db.commit()
            logger.info("✅ Changes committed")

    reporter.print_summary()

    if reporter.stats["source_docs_failed"] > 0 or reporter.stats["unrecoverable_artifacts"] > 0:
        logger.warning("Backfill completed with some failures. See summary above.")
        # Exit with 0 anyway, just warn - partial success is still okay
        sys.exit(0)
    else:
        logger.info("🚀 Backfill completed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
