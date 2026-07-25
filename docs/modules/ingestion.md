# Module: ingestion

## Responsibility

`ingestion` provides structured event ingestion, input normalization, and event conversion into internal representation.

## Current maintenance note

The structured-ingestion module received repository-wide formatting baseline updates only in this task. Its normalization and event-conversion behavior is unchanged.

---

## Design Rules

- Input validation should be strict
- Normalization should be consistent
- Conversion should be traceable
- Add or update tests when ingestion behavior changes

---

## Files

### `ingestion/__init__.py`

Purpose:
- Package initialization for the ingestion module.
- Makes ingestion a proper Python package for importing submodules.

### `ingestion/*.py`

Purpose:
- Structured ingestion pipelines
- Input normalization
- Event conversion
- Pipeline orchestration

Update this section when:
- New ingestion types are added
- Event conversion changes
- Input schema changes
- Validation behavior changes

### `ingestion/knowledge_pipeline.py`

Purpose:

- 知识加工深模块（KnowledgePipeline），对外只暴露 `process(doc)` 一个主接口。
- 内部步骤（分块、分类、实体提取、事件提取、去重）是私有实现细节。
- 支持长文本（>1000字符）并发 LLM 提取路径：注入 `ModelGateway` 后自动走 `ConcurrentLLMExtractor` 对 chunk 并发调用 LLM。
- 通过 `PipelineConfig` 控制各步骤开关。

Related service:

- `services/event_extractor.py`
- `services/document_chunker.py`
- `services/document_classifier.py`
- `services/entity_extractor.py`
- `services/deduplication_service.py`

Update this section when:

- Pipeline 步骤变更。
- 长文本并发提取逻辑变更。
- PipelineConfig 配置项变更。

---

## Required Tests

- Ingestion input tests
- Conversion verification tests
- Invalid input handling tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/ingestion.md`
- `docs/DATA_SOURCES.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`