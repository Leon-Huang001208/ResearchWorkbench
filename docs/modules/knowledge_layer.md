# Module: knowledge_layer

## Responsibility

`knowledge_layer` provides entity resolution, assertion management, event database, graph projection, and retrieval capabilities.

---

## Design Rules

- Keep entity resolution logic consistent
- Assertions should be traceable to sources
- Event timestamps should be precise
- Graph operations should be efficient
- Add or update tests when knowledge layer behavior changes

---

## Files

### `knowledge_layer/*.py`

Purpose:
- Entity extraction and resolution
- Assertion management
- Event storage and querying
- Graph projection operations
- Vector and keyword retrieval
- Concurrent LLM extraction (text chunking + ThreadPoolExecutor)
- `knowledge_layer/retrieval/vector_store.py` honors `ALPHAFOUNDRY_DISABLE_LOCAL_EMBEDDINGS=1`; tests set this by default. Runtime local embeddings use `ALPHAFOUNDRY_LOCAL_EMBEDDING_MODEL_PATH` first, otherwise sentence-transformers is called with `local_files_only=True`; set `ALPHAFOUNDRY_ALLOW_EMBEDDING_DOWNLOAD=1` only when first-time Hugging Face download is intentional.

Update this section when:
- Entity resolution logic changes
- Assertion handling changes
- Event schema changes
- Retrieval algorithms change

---

## Required Tests

- Entity resolution accuracy tests
- Assertion creation and retrieval tests
- Event storage and query tests
- Graph projection tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/knowledge_layer.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`

---

## Related Subsystems

- `core/connectors/` — 连接器负责数据采集和基础解析，产出的 `IngestionRecord` 通过 `IngestionQueue` 传递给本模块的 `KnowledgeWorker` 进行 LLM 知识提取
- `connectors/` — 文档连接器（`CLSDocumentConnector` 等）在 `persist()` 阶段将摄入记录入队
