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
| `core/contracts/platform_shared.py` | 合并平台共享核：稳定资产身份、来源引用、六字段事实响应、新鲜度、Observation、持久领域事件与单飞调度契约。 |
| `core/contracts/theme_research.py` | Research Pack Manifest、统一主题 Observation、主题快照与数据健康契约；插件权限限定为 normalize/validate/derive。 |
| `core/contracts/research_workspace.py` | Workspace/Session/Message、RuntimeProvider、声明式 Skill、Agent Team/预算/日程和版本化 Research Note。 |
| `core/contracts/market_home.py` | facts-only 市场首页五区块、交易状态、透明主线分项和不可变快照契约。 |
| `core/contracts/asset_observation.py` | 四类资产统一快照、PeerSet、Watchlist、Alert 边沿状态与站内通知契约。 |
