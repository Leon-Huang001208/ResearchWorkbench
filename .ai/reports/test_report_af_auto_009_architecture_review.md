# Test Report: AF-AUTO-009 Architecture Review + Full Gate Cleanup

## Task ID

af-auto-009-architecture-review

## Scope

Review connector/adapter architecture and documentation drift; harden connector-first ingestion, KnowledgeWorker persistence/recovery, repository field mapping, and remove the remaining full-gate blockers called out after the architecture review.

## Changed Source Files

- `core/connectors/base.py`
- `core/connectors/registry.py`
- `core/model_gateway/local_embedding_config.py`
- `core/source_registry.py`
- `core/model_gateway/providers/local_embedding.py`
- `knowledge_layer/retrieval/vector_store.py`
- `services/crawl_orchestrator.py`
- `workers/knowledge_worker.py`
- `data_layer/repositories/document_repository.py`
- `data_layer/repositories/ingestion_repository.py`
- `app/cli/commands/data.py`
- `pyproject.toml`

## Changed Tests

- `tests/conftest.py`
- `tests/e2e/test_asset_search.py`
- `tests/test_template_api.py`
- `tests/test_template_endpoints.py`
- `tests/unit/test_asset_kline_interaction.py`
- `tests/unit/test_connectors/test_registry.py`
- `tests/unit/test_local_embedding_config.py`
- `tests/unit/test_source_connector_contracts.py`
- `tests/unit/workers/test_knowledge_worker.py`

## Changed Docs

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/CHANGELOG.md`
- `docs/DATA_SOURCES.md`
- `docs/DATA_STORAGE.md`
- `docs/DEVELOPMENT_MAP.md`
- `docs/FILE_GUIDE.md`
- `docs/REFERENCE.md`
- `docs/generated/py_file_index.md`
- `docs/modules/app_cli.md`
- `docs/modules/core_connectors.md`
- `docs/modules/data_layer_crawlers.md`
- `docs/modules/data_layer_repositories.md`
- `docs/modules/knowledge_layer.md`
- `docs/modules/services.md`
- `docs/superpowers/plans/2026-06-04-stable-connector-ingestion.md`

## Commands Run

```bash
/Users/leon/opt/anaconda3/bin/python3.11 -m py_compile core/connectors/base.py workers/knowledge_worker.py data_layer/repositories/document_repository.py data_layer/repositories/ingestion_repository.py app/cli/commands/data.py
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/workers/test_knowledge_worker.py tests/unit/test_source_connector_contracts.py tests/unit/test_ingestion_queue.py -q
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_source_connector_contracts.py tests/unit/test_ingestion_queue.py tests/unit/workers/test_knowledge_worker.py tests/unit/core/services/test_crawl_scheduler.py tests/unit/data_layer/crawlers/test_cls_crawler.py tests/unit/data_layer/repositories/test_market_data_repository.py -q
/Users/leon/opt/anaconda3/bin/python3.11 -m ruff check .
/Users/leon/opt/anaconda3/bin/python3.11 -m black --check core/connectors/base.py workers/knowledge_worker.py data_layer/repositories/document_repository.py data_layer/repositories/ingestion_repository.py app/cli/commands/data.py tests/unit/workers/test_knowledge_worker.py
/Users/leon/opt/anaconda3/bin/python3.11 -m isort --check-only core/connectors/base.py workers/knowledge_worker.py data_layer/repositories/document_repository.py data_layer/repositories/ingestion_repository.py app/cli/commands/data.py tests/unit/workers/test_knowledge_worker.py
/Users/leon/opt/anaconda3/bin/python3.11 scripts/generate_py_file_index.py
/Users/leon/opt/anaconda3/bin/python3.11 scripts/check_doc_sync.py
/Users/leon/opt/anaconda3/bin/python3.11 -m mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/ -q
/Users/leon/opt/anaconda3/bin/python3.11 -m py_compile core/source_registry.py core/connectors/registry.py services/crawl_orchestrator.py knowledge_layer/retrieval/vector_store.py core/model_gateway/providers/local_embedding.py tests/conftest.py tests/test_template_api.py tests/test_template_endpoints.py tests/e2e/test_asset_search.py
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_source_connector_contracts.py tests/unit/test_ingestion_queue.py tests/unit/workers/test_knowledge_worker.py -q
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/test_template_api.py tests/test_template_endpoints.py tests/e2e/test_asset_search.py -q
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_ingest_service.py tests/unit/test_golden_path.py -q
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/unit/test_local_embedding_config.py -q
/Users/leon/opt/anaconda3/bin/python3.11 -m pytest tests/ -q
/Users/leon/opt/anaconda3/bin/python3.11 -m black tests/unit/test_asset_kline_interaction.py core/model_gateway/providers/local_embedding.py
/Users/leon/opt/anaconda3/bin/python3.11 -m black --check .
/Users/leon/opt/anaconda3/bin/python3.11 -m isort core/model_gateway/providers/local_embedding.py
/Users/leon/opt/anaconda3/bin/python3.11 -m isort --check-only .
/Users/leon/opt/anaconda3/bin/python3.11 -m ruff check .
/Users/leon/opt/anaconda3/bin/python3.11 -m mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/
/Users/leon/opt/anaconda3/bin/python3.11 scripts/check_doc_sync.py
/Users/leon/opt/anaconda3/bin/python3.11 scripts/check_task_completion.py
```

## Results

- `py_compile`: PASS.
- Focused queue/worker/connector tests: PASS, 33 passed.
- Focused connector/scheduler/worker regression: PASS, 60 passed.
- `ruff check .`: PASS.
- Touched-file `black --check`: PASS after formatting touched files.
- Touched-file `isort --check-only`: PASS after sorting touched test imports.
- `scripts/generate_py_file_index.py`: PASS.
- `scripts/check_doc_sync.py`: PASS.
- Full `black --check .`: PASS after formatting `tests/unit/test_asset_kline_interaction.py` and touched imports.
- Full `isort --check-only .`: PASS.
- Full `mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/`: PASS, 364 source files checked after replacing package-level `ignore_errors` with an explicit error-code debt list and `ignore_missing_imports` for third-party stub gaps; mypy now walks every checked project source file instead of skipping whole legacy packages.
- Live API/E2E isolation smoke: PASS, 3 skipped by default unless the live-test environment variables are set.
- Offline embedding isolation regression: PASS, ingest/golden-path tests no longer attempt local model download/load by default.
- Local embedding config regression: PASS, local model directory is preferred, Hugging Face model ids are cache-only by default, and downloads require `ALPHAFOUNDRY_ALLOW_EMBEDDING_DOWNLOAD=1`.
- Runtime dirty cleanup: generated ZQ account state, E2E screenshots, and test docx artifacts were restored to the repository version.
- `scripts/check_doc_sync.py`: PASS.
- `scripts/check_task_completion.py`: PASS.
- Full `pytest tests/ -q`: PASS, 1619 passed, 4 skipped, 31 warnings.

## Architecture Review Notes

- Connector and adapter are not duplicate if their roles stay separate: Connector is the unified scheduler/CLI/API entry and lifecycle boundary; adapter/crawler code should remain an internal vendor-specific delegate or legacy fallback only.
- `SourceSpec.connector_class` is now the canonical field. `adapter_class` remains as a legacy compatibility alias and is normalized to the same value in `SourceSpec.__post_init__()`.
- DataSourceRouter and old adapter paths should not be used for new ingestion work; new sources should enter through Connector and then split by `pipeline_kind`.

## Decision

PASS for the connector/worker/repository/documentation scope and the previously documented full-suite/type/format blockers.
