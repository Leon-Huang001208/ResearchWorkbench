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