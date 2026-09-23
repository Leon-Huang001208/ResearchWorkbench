---
name: data-connector-development
description: Use when adding or maintaining ResearchWorkbench legacy ingestion Connectors under core/connectors; not for current Research Web DataHub Provider contracts.
license: MIT
---

# Data Connector 开发规范

ResearchWorkbench 的 legacy ingestion 层使用统一 Connector 架构：**BaseConnector ABC → DocumentConnector / MarketDataConnector 分型**。当前 Research Web DataHub Provider 由 `docs/research-web-datahub.md` 和 `app/research_web/datahub/` 管理；不要用本 Skill 把旧 Connector 误报成当前 Runtime 可调用 Provider。

---

## 1. 架构概览

```
core/connectors/base.py
├── BaseConnector (ABC)              # 统一生命周期
│   ├── DocumentConnector            # 非结构化数据（新闻、研报、公告）
│   └── MarketDataConnector          # 结构化市场数据（OHLCV、财务、估值）

connectors/
├── document/                        # DocumentConnector 实现
│   ├── cls.py                       # 财联社电报
│   ├── cnstock.py                   # 中国证券网
│   └── zq.py                        # 证券时报
└── market/                          # MarketDataConnector 实现
    ├── akshare.py                   # AKShare A股
    ├── wind.py                      # Wind 终端 (xlwings)
    └── yahoo.py                     # Yahoo Finance
```

### 生命周期

```
health_check → discover → fetch → save_raw → parse → normalize → validate → persist
```

### CLI 入口

```bash
./rwb data list                          # 列出所有数据源
./rwb data ingest -s <src> -d <dataset>  # 摄入数据
./rwb data validate -s <src> -d <dset>   # 校验数据
./rwb data status                        # 查看状态
./rwb data backfill -s <src>             # 历史回填
```

---

## 2. BaseConnector 接口

所有 connector 必须实现的核心方法：

```python
from core.connectors.base import BaseConnector, DiscoveryItem, RawObject, ParsedTable
from core.contracts.ingestion_record import HealthStatus, IngestionRecord
from typing import List, Any

class MyConnector(BaseConnector):
    @property
    def source(self) -> str:
        """数据源唯一标识（用于 registry、CLI、persist）。"""
        return "my_source"

    @property
    def datasets(self) -> List[str]:
        """此 connector 支持的数据集列表。"""
        return ["dataset_a", "dataset_b"]

    def health_check(self) -> HealthStatus:
        """检查数据源是否可用。返回 HEALTHY / DEGRADED / UNAVAILABLE。"""
        ...

    def discover(self, dataset: str, **params: Any) -> List[DiscoveryItem]:
        """发现可抓取的数据对象。每个 item 代表一个独立抓取单元。"""
        ...

    def fetch(self, dataset: str, item: DiscoveryItem, **params: Any) -> RawObject:
        """获取单个数据对象的原始数据。返回 RawObject (JSON bytes/str)。"""
        ...

    def parse_table(self, raw: RawObject) -> ParsedTable:
        """解析原始 JSON 为结构化表格 (columns + rows)。"""
        ...

    def normalize_bars(
        self, dataset: str, table: ParsedTable, raw_uri: str, content_hash: str
    ) -> List[IngestionRecord]:
        """将表格转为统一 IngestionRecord 列表。"""
        ...
```

---

## 3. 分型 Connector

### 3.1 DocumentConnector（非结构化数据）

**基类提供的能力：** `persist()` 已实现，通过 `IngestionQueueService.enqueue()` 入队。

```python
from core.connectors.base import DocumentConnector

class MyDocConnector(DocumentConnector):
    @property
    def source(self) -> str:
        return "my_doc_source"

    @property
    def datasets(self) -> List[str]:
        return ["news", "reports"]

    # 实现 discover / fetch / parse_table / normalize_bars
    # persist() 由基类提供，无需覆盖
```

**persist() 行为：** 每条 IngestionRecord → `EnqueueRequest` → `IngestionQueueService.enqueue()` → 去重入队。

### 3.2 MarketDataConnector（结构化市场数据）

**基类提供的能力：** `persist()` 使用 Template Method 模式 + 静态工具方法。

**你需要覆盖的 Hook 方法：**

```python
from core.connectors.base import MarketDataConnector

class MyMarketConnector(MarketDataConnector):
    # === 必须覆盖 ===
    @property
    def source(self) -> str:
        return "my_market"

    @property
    def datasets(self) -> List[str]:
        return ["stock_daily", "index_daily"]

    # === Hook 方法 ===

    def _daily_bar_datasets(self) -> tuple[str, ...]:
        """返回哪些 dataset 需要按 OHLCV 模板持久化。"""
        return ("stock_daily", "index_daily")

    def _build_daily_bar_row(self, record: IngestionRecord) -> Dict[str, Any]:
        """构造单行日线数据（默认从 MarketBarPayload 提取 OHLCV）。"""
        p = record.payload
        return {
            "symbol": record.entity_id,
            "trade_date": p.get("trade_date"),
            "open": self._to_decimal(p.get("open")),
            "high": self._to_decimal(p.get("high")),
            "low": self._to_decimal(p.get("low")),
            "close": self._to_decimal(p.get("close")),
            "volume": self._to_decimal(p.get("volume")),
            "amount": self._to_decimal(p.get("amount")),
            "turnover": self._to_decimal(p.get("turnover")),
            "source": self.source,
            "raw_payload": p,
        }

    def _persist_extra_records(
        self, records: List[IngestionRecord], repo
    ) -> int:
        """处理非日线的额外记录（如 stock_master）。返回持久化数量。"""
        return 0  # 默认不处理额外记录
```

**基类提供的静态工具方法：**

```python
MarketDataConnector._format_date(value)  # → "YYYY-MM-DD" str
MarketDataConnector._to_decimal(value)   # → Decimal 或 None
MarketDataConnector._parse_date(value)   # → date 或 None
```

**persist() 模板方法流程（由基类实现，不要覆盖）：**
```
1. _daily_bar_datasets() → 过滤日线 records
2. _build_daily_bar_row() → 逐条构造日线行
3. MarketDataRepository.upsert_daily_bars(rows) → 入库
4. _persist_extra_records() → 处理额外 records（stock_master 等）
```

---

## 4. Wrapper-First 策略

**新 connector 是现有模块的包装器，不立即重写内部逻辑：**

```python
class AkShareMarketConnector(MarketDataConnector):
    def __init__(self, config=None):
        super().__init__(config)
        # 内部委托给现有 data_layer/crawlers/akshare/
        from data_layer.crawlers.akshare.base import AkShareAdapter
        self._adapter = AkShareAdapter(config=...)

    def health_check(self) -> HealthStatus:
        """委托给现有 adapter。"""
        result = self._adapter.health_check()
        ...

    def fetch(self, dataset, item, **params) -> RawObject:
        """委托给现有 crawler 方法。"""
        data = self._adapter.market.get_historical_data(...)
        return RawObject(data=json.dumps(...), ...)
```

**原则：** Connector 是门面（Facade），内部委托给 `data_layer/` 的现有模块。未来可以渐进替换内部实现，不影响外部接口。

---

## 5. 注册新 Connector

### 5.1 文件位置

```text
connectors/
├── document/<source>.py    # DocumentConnector 子类
└── market/<source>.py      # MarketDataConnector 子类
```

### 5.2 自动注册

所有 `connectors/document/*.py` 和 `connectors/market/*.py` 会被：
- `mcp/server.py` `_ensure_registry()`
- `app/cli/commands/data.py` `_ensure_registry()`

自动发现并加载。无需额外注册步骤。

### 5.3 验证注册成功

```bash
./rwb data list
# 应该看到你的新 source 出现在列表中
```

---

## 6. CLI 快速验证

```bash
# 1. 确认注册
./rwb data list

# 2. 测试健康检查
./rwb data status -s <source>

# 3. 测试摄入
./rwb data ingest -s <source> -d <dataset> --days 1 --max-items 5

# 4. 测试校验
./rwb data validate -s <source> -d <dataset>
```

---

## 7. 检查清单

新增 connector 时确认：

- [ ] 继承 `DocumentConnector` 或 `MarketDataConnector`
- [ ] 实现 `source` property
- [ ] 实现 `datasets` property
- [ ] 实现 `health_check()`
- [ ] 实现 `discover()` — 返回合理的 `DiscoveryItem` 列表
- [ ] 实现 `fetch()` — 返回 `RawObject`
- [ ] 实现 `parse_table()` — 返回 `ParsedTable`
- [ ] 实现 `normalize_bars()` — 返回 `List[IngestionRecord]`
- [ ] **MarketDataConnector**: 覆盖 `_daily_bar_datasets()` hook
- [ ] **MarketDataConnector**: 如有非日线数据，覆盖 `_persist_extra_records()` hook
- [ ] **不要覆盖 `persist()`** — 基类已实现
- [ ] Wrapper-first: 内部委托给现有 adapter/crawler
- [ ] 在 `./rwb data list` 中可见
- [ ] `./rwb data status -s <source>` 返回正确健康状态
- [ ] 添加单元测试
- [ ] 导入错误时优雅降级（try/except ImportError）

---

## 8. 反模式（避免）

| ❌ 反模式 | ✅ 正确 |
|----------|--------|
| 覆盖 `persist()` 方法 | 覆盖 hook 方法（`_daily_bar_datasets` / `_persist_extra_records`） |
| 在 connector 中重写全部 crawler 逻辑 | Wrapper-first：委托给现有 `data_layer/` 模块 |
| 硬编码 `_format_date` / `_to_decimal` | 使用基类静态方法 |
| 在 connector 中做 LLM 提取 | LLM 处理归 `KnowledgePipeline`；connector 只负责数据获取 |
| 一个 connector 覆盖多个完全不相关的源 | 每个源一个 connector 文件 |
| `except:` 裸捕获 | 使用 `except Exception as e:` + 日志 |
