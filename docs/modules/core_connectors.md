# Module: core/connectors

## Responsibility

`core/connectors` 定义了统一的数据源连接器抽象，取代旧的 `data_layer/adapters/DataSourceAdapter` 模式：

- `BaseConnector` (ABC)：统一生命周期 `discover → fetch → save_raw → parse → normalize → validate → persist`
- `DocumentConnector(BaseConnector)`：非结构化文档连接器（公告、研报、新闻、纪要）
- `MarketDataConnector(BaseConnector)`：结构化时序数据连接器（日线、估值、成分股）
- `ConnectorRegistry`：连接器发现、注册和生命周期管理

具体连接器实现在顶层 `connectors/` 包下，分 `connectors/document/` 和 `connectors/market/` 两个子包。

---

## Design Rules

- 连接器使用 Template Method + Hook 模式（`persist()` 为具体方法，子类覆盖轻量级 hook）
- 连接器实现采用 Wrapper-first 策略：内部委托给旧 `data_layer/adapters/` 的实现，不立即重写适配器内部逻辑
- 连接器产出 `IngestionRecord`（shell + typed payload）
- 连接器只负责数据采集与基础解析；LLM 提取属于 KnowledgePipeline 职责
- `BaseConnector.run()` 模板不应被子类覆盖；子类覆盖 `discover`, `fetch`, `parse`, `normalize`, `validate` 等 hook

---

## Key Files & Types

### `core/connectors/base.py`

核心抽象层：

| 类/类型 | 说明 |
|----------|------|
| `BaseConnector(ABC)` | 统一连接器基类，`run()` 模板方法编排完整生命周期 |
| `DocumentConnector(BaseConnector)` | 文档连接器，`persist()` 通过 `IngestionQueue` 入队 |
| `MarketDataConnector(BaseConnector)` | 市场数据连接器，`persist()` 执行数据库 upsert |
| `DiscoveryItem` | 发现阶段产出的数据项描述 |
| `RawObject` | 原始获取数据（二进制/文本） |
| `ParsedDocument` | 解析后的文档结构 |
| `ParsedTable` | 解析后的表格结构 |

生命周期（`run()` 模板方法）：
```
discover → fetch → save_raw → parse → normalize → validate → persist
```

### `core/connectors/registry.py`

| 类/类型 | 说明 |
|----------|------|
| `ConnectorRegistry` | 连接器注册表：`register`, `discover_all`, `get_connector`, `health_check`, 生命周期管理 |
| `DatasetRouter` | 数据集级多源降级路由，按 `SourceSpec.fallback_group` 与 `fallback_priority` 构建优先级链 |
| `get_connector_registry()` | 模块级单例获取 |
| `reset_connector_registry()` | 模块级单例重置（测试用） |

---

## Concrete Connector Implementations

所有具体实现在 `connectors/` 顶层包中。

### `connectors/document/` — 文档连接器

| 文件 | 类 | 数据源 | 委托适配器 |
|------|-----|--------|------------|
| `cls.py` | `CLSDocumentConnector` | 财联社电报 | `CLSAdapter` |
| `cninfo.py` | `CninfoDocumentConnector` | 巨潮资讯网公告 | `CninfoAdapter` |
| `cnstock.py` | `CNStockDocumentConnector` | 中国证券网新闻 | `CNStockAdapter` |
| `zq.py` | `ZQDocumentConnector` | 知丘（研报/微信/纪要） | `ZQAdapter` |

### `connectors/market/` — 市场数据连接器

| 文件 | 类 | 数据源 | 委托适配器 |
|------|-----|--------|------------|
| `akshare.py` | `AkShareMarketConnector` | AKShare 公开数据 | `AKShareAdapter` |
| `wind.py` | `WindMarketConnector` | Wind 金融终端 | `WindAdapter` |
| `baostock.py` | `BaostockMarketConnector` | BaoStock 证券数据 | `BaoStockAdapter` |
| `cjpy.py` | `CjpyMarketConnector` | 天软 Tinysoft | `CjpyAdapter` |
| `yahoo.py` | `YahooMarketConnector` | Yahoo Finance | `YahooAdapter` |

---

## Data Source Registration

数据源在 `data_sources/` 中通过 `SourceSpec` 注册，自动发现：

```python
from core.source_registry import register, SourceSpec

register(SourceSpec(
    source_type=SourceType.CLS,
    source_name="CLS Telegram",
    connector_class="connectors.document.cls.CLSDocumentConnector",
    connector_dataset="telegram",
    pipeline_kind="document",
    ...
))
```

`data_sources/__init__.py` 通过 `pkgutil.iter_modules` 自动导入所有数据源文件，触发注册。

`connector_class` 是 Connector 架构下的 canonical 字段，必须指向 `BaseConnector` 子类；`adapter_class` 仅作为历史兼容别名保留。`connector_dataset` 声明调度时传给 `connector.run()` 的 dataset，`pipeline_kind` 声明 `document` 或 `market` 分流。`SourceSpec` 也可声明 `fallback_group` 与 `fallback_priority`。`core.source_registry.get_fallback_groups()` 会按优先级升序返回每个组，`DatasetRouter` 再据此构建如 `daily_quotes_cn -> cjpy -> wind -> baostock` 的降级链。

CLI 通过 `ConnectorRegistry` 统一调度：
- `af data list` — 列出已注册数据源
- `af data ingest` — 执行数据摄入
- `af data backfill` — 历史数据回填
- `af data validate` — 数据验证
- `af data status` — 数据源状态

---

## Testing Strategy

- **连接器基类单元测试**：验证 `run()` 模板方法正确调用各 hook
- **Registry 测试**：注册/发现/生命周期/健康检查
- **具体连接器集成测试**：mock 外部依赖，验证端到端流程
- **Health check 测试**：验证各数据源健康状态报告

---

## Required Documentation Updates

当此模块文件变更时，检查：
- `docs/modules/core_connectors.md`（本文）
- `docs/ARCHITECTURE.md` — 架构层描述
- `docs/FILE_GUIDE.md` — 文件级说明
- `docs/DEVELOPMENT_MAP.md` — 子系统路由
- `docs/CHANGELOG.md` — 变更记录
- `docs/generated/py_file_index.md` — 自动索引


## DataHub / CJPY 增量（2026-09-03）

CjpyMarketConnector 扩展至 17 数据集，复用 BaseConnector.run，通过单批事务落库完整快照、typed 投影与批次记录。日线、分钟、因子日期按有界窗口拆批；重试仅补失败批次。 详见 [DataHub 模块说明](datahub.md)。
