# Module: scripts

## Responsibility

`scripts` provides operational scripts, database bootstrap, backup/restore, smoke tests, and development governance checks.

---

## Design Rules

- Scripts should be self-documenting
- Provide --help for all scripts
- Make destructive operations explicit
- Add dry-run mode when feasible
- Add or update tests when script behavior changes

---

## Files

### `scripts/generate_py_file_index.py`

Purpose:
- Generates Python file index documentation
- Parses source files for classes, functions, imports
- Outputs to docs/generated/py_file_index.md

Update this section when:
- Parsing logic changes
- Output format changes
- Included directories change

### `scripts/check_task_completion.py`

Purpose:
- Verifies source changes have corresponding tests/docs/reports
- Checks git diff and untracked files for changes (via shared `core/utils/git.py`)
- Ensures CHANGELOG is updated

Update this section when:
- Check logic changes
- Required file patterns change
- Failure criteria change

### `scripts/check_doc_sync.py`

Purpose:
- Verifies source changes have corresponding documentation updates
- Maps source directories to required docs
- Ensures generated index is updated
- Detects changes via shared `core/utils/git.py` (includes untracked files)

Update this section when:
- DOC_RULES mapping changes
- Check logic changes
- Required docs change

### `scripts/backfill_missing_llm_extraction.py`

Purpose:
- Finds documents in `document_v1` missing corresponding LLM extraction results in `canonical_event`.
- Enqueues them into the ingestion queue via `CrawlOrchestrator._enqueue_items()` so KnowledgePipeline can perform LLM extraction.
- Supports `--dry-run` preview and `--batch` for batch size control.
- Related: `services/crawl_orchestrator.py`, `ingestion/knowledge_pipeline.py`.

Update this section when:
- Backfill query logic changes
- Enqueue batching behavior changes

---

### `scripts/cleanup_dedup_orphans.py`

Purpose:
- Cleans orphan entries from file-based CLS crawler dedup state (`DeduplicationStore`)
- Queries `document_v1` for valid `source_doc_id`s, removes any dedup entries without matching DB rows
- Prevents permanent crawl skip when documents are deleted from DB but dedup file retains IDs
- Supports `--dry-run` preview

Update this section when:
- Dedup state file paths change
- Cleanup logic changes

---

### `scripts/backfill_pdf_artifacts.py`

Purpose:
- Scans `data/crawlers/zq/pdfs/` for existing PDF files not yet registered in `pdf_artifact_v1`
- Computes SHA-256 hash for each file, creates `PDFArtifactV1DB` records with `parse_status='pending'`
- Skip files already registered (hash-based dedup)
- Registered PDFs are automatically picked up by `CrawlScheduler` → `PDFConversionService` within 5 minutes
- Supports `--dry-run` preview

Update this section when:
- PDF root directory changes
- Registration fields change

---

### Other `scripts/*.py`

Purpose:
- Database bootstrap and migration
- Backup and restore operations
- Smoke tests and verification
- Data import and export
- Operational utilities

Update this section when:
- New scripts are added
- Script behavior changes
- Operational workflow changes
- Backup/restore behavior changes

---

## Required Tests

- Script behavior tests when feasible
- Dry-run mode tests
- Error path tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/scripts.md`
- `docs/REFERENCE.md` (when user-facing)
- `docs/backup_restore.md` (when backup/restore changes)
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`