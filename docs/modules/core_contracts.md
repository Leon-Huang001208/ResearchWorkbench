# Module: core/contracts

## Responsibility

`core/contracts` defines Pydantic domain contracts and standardizes cross-layer data exchange.

---

## Design Rules

- Contracts should be immutable by default
- Use Pydantic validation for data integrity
- Keep contracts focused on single responsibility
- Document field semantics clearly
- Add examples for complex contract structures
- Add or update tests when contract structure changes

---

## Files

### `core/contracts/*.py`

Purpose:

- Domain model definitions
- API request/response schemas
- Event and assertion structures
- Report templates and structures

Update this section when:

- New contract types are added
- Field definitions change
- Validation rules change
- Enum variants change

---

## Required Tests

- Validation tests for required fields
- Serialization/deserialization tests
- Enum behavior verification
- Edge case handling tests

---

## Required Documentation Updates

When files in this module change, check:

- `docs/modules/core_contracts.md`
- `docs/ARCHITECTURE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`

---

## Key Contract Files

| 文件 | 说明 |
| --- | --- |
| `core/contracts/assets.py` | 资产定义、快照、技术指标、情绪指标；`PriceBar` 暴露 K 线 OHLCV、MA、BOLL、MACD、VWAP、涨跌幅和振幅字段供 API/Web 共用 |
| `core/contracts/documents_v1.py` | 统一文档 v1 契约：`DocumentEnvelope`、`DocumentClassification`、`DocumentQuality`、`SourceType` 等；`SourceType` 覆盖 connector/source registry 使用的数据源枚举 |
| `core/contracts/ingestion_record.py` | 摄入记录契约：`IngestionRecord`、`IngestionStats`、`IngestionRunResult`、`ValidationReport` |
| `core/contracts/retrieval.py` | 检索配置和 Profile：`RetrievalProfile`、`RetrievalFilters`、`RetrievalQuery` |
| `core/contracts/outcome_journal.py` | 结果日志：`SignalOutcomeDB` |
| `core/contracts/monitoring.py` | 生产监控告警、事件和健康指标契约；`Subsystem.RESOURCE_MONITORING` 标识仅属于 AlphaFoundry 资源监控的持久化事件 |
| `core/contracts/research.py` | 通用可恢复研究契约：`ResearchSubject` 统一股票、ETF、指数、商品、宏观和行业对象，`ResearchTemplateDefinition` 暴露模板能力；`ResearchRun` 配套任务、不可变产物、观点、质量门禁、证据输入和决策卡。旧 `target_id` 兼容映射为 security subject，证据分类由模板验证。 |
| `core/contracts/runtime.py` | Runtime-neutral 内核契约：版本化 Tool/Skill/Evaluator/Template/WorkflowSpec、RuntimeDescriptor/Capabilities、统一 ExecutionHandle/Event、EvidenceRecord 以及包含可渲染 Chart 数据的 ReportDocument。该模块不得导入 DSH、Codex 或 Claude SDK。 |
