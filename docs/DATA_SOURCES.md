# 数据源配置指南

AlphaFoundry支持多数据源，按优先级自动切换。

## 支持的数据源

### 行情/财务数据（Connector 架构 + 三级降级）

| 优先级 | 数据源 | 连接器 | 状态 | 说明 |
| --- | --- | --- | --- | --- |
| 0 (最高) | Wind (万得) | `WindMarketConnector` | ✅ 专业源 | 专业金融数据终端，一致预期/两融/龙虎榜等独有数据 |
| 1 | iFinD | — (内部 adapter) | ✅ 主源 | 专业金融数据终端，高质量行情/财务数据 |
| 2 | AKShare | `AkShareMarketConnector` | ✅ 开源 | 开源免费，iFinD 不可用时自动切换 |
| 3 | ChinaStock | — (内部 adapter) | ✅ 兜底 | 最后降级选择 |

> **Connector 架构**：`WindMarketConnector`、`AkShareMarketConnector`、`BaostockMarketConnector`、`CjpyMarketConnector`、`YahooMarketConnector` 均继承 `MarketDataConnector` ABC，通过 `ConnectorRegistry.run_with_fallback()` 自动降级切换。Wrapper-first 策略：connector 内部委托给现有 `data_layer/adapters/` 实现。

Wind 适配器通过 xlwings 操控 macOS Excel 中的 Wind 插件获取数据，是项目唯一能获取**一致预期（分析师预测）**、**融资融券**、**龙虎榜**、**日行情（含 adj_close/adj_factor/vwap）**、**财务报表**、**行业分类（申万）**、**资金流向**、**持有人结构**八类高价值投研数据的来源。使用前需确保 Excel 已启动且 Wind 插件已登录。
降级策略由 `core/connectors/registry.py` 的 `ConnectorRegistry.run_with_fallback()` 实现，按注册优先级依次尝试，所有数据源都失败时返回 `insufficient_evidence` 标记。

### 新闻/研报数据源（源注册表 + 自动发现）

所有爬取数据源通过 `core/source_registry.py` 的 `SourceSpec` 自描述注册，`data_sources/__init__.py` 使用 `pkgutil.iter_modules` 自动发现模块。添加新来源 = 在 `data_sources/` 下新建一个 `.py` 文件，无需修改任何其他代码。

| 来源类型 (source_type) | 数据源 | 连接器 | 内容类型 | 频率 |
|------------------------|--------|--------|----------|------|
| `cls` | 财联社 | `CLSDocumentConnector` | 电报、快讯 | 15min |
| `cnstock` | 中国证券网 | `CNStockDocumentConnector` | 正文新闻 | 30min |
| `cnstock_flash` | 中国证券网·快讯 | `CNStockDocumentConnector` | 快讯 | 30min |

> **CNStock WAF 说明**：cnstock.com 于 2026年5月升级阿里云 WAF，`requests` 直接调用 API 被拦截（`10304`）。爬虫已切换为 Playwright 方案：快讯通过 `__NEXT_DATA__` SSR 数据提取，普通频道通过拦截页面 `channelNewsList` XHR 响应获取。Playwright 不可用时自动回退到 requests 方案。详见 `data_layer/crawlers/cnstock/cnstock.py`。
| `zhiqiu_reports` | 知丘研报 | `ZQDocumentConnector` | 券商研报 (PDF) | 60min |
| `zhiqiu_wechat` | 知丘公众号 | `ZQDocumentConnector` | 公众号文章 | 60min |
| `zhiqiu_transcript` | 知丘纪要 | `ZQDocumentConnector` | 会议纪要 | 60min |

> **注意**：上表中的"连接器"列指向 `connectors/document/` 下的 `DocumentConnector` 实现。连接器内部通过 Wrapper-first 策略委托给旧 `data_layer/adapters/` 下的适配器（如 `CLSAdapter`、`CNStockAdapter`、`ZQAdapter`）。

### 添加新数据源

在 `data_sources/` 下创建新文件（如 `my_source.py`），使用 Connector 架构：

```python
from core.contracts.documents_v1 import DocType, SourceReliabilityLevel, SourceType
from core.source_registry import SourceSpec, register

register(SourceSpec(
    source_type=SourceType.OTHER,      # 或新增的 SourceType 枚举值
    source_name="我的数据源",
    adapter_class="connectors.document.my_source.MyDocumentConnector",
    adapter_kwargs={"key": "value"},
    interval_minutes=60,
    doc_type=DocType.NEWS,
    reliability=SourceReliabilityLevel.ESTABLISHED_MEDIA,
    backfill_family=None,
    retrieval_weight=1.0,
))
```

文件保存后，自动发现机制会在下次启动时加载该来源。所有下游模块（调度器、编排器、仪表盘、分类器、PDF 转换）都会自动感知。详见 `core/source_registry.py` 中的 `SourceSpec` 完整字段定义。

### 其他数据源

| 数据源 | 连接器 | 状态 | 说明 |
| --- | --- | --- | --- |
| BaoStock | `BaostockMarketConnector` | ⚡️ 可选 | 证券专业数据，`pip install baostock` |
| Yahoo Finance | `YahooMarketConnector` | ⚡️ 可选 | 全球市场数据，通过 `yfinance` |
| Cjpy | `CjpyMarketConnector` | ✅ 内置 | 交易日历和基准行情 |
| 本地缓存 | — | ✅ 兜底 | 预填充的历史数据 |

## 快速设置

### 方式一：仅使用AKShare（推荐新手）

```bash
pip install akshare
```

AKShare已包含在项目依赖中，开箱即用。

### 方式二：安装全部数据源

```bash
# 安装Tushare
pip install tushare

# 安装BaoStock
pip install baostock
```

### 方式三：配置Tushare Token（可选）

如需使用Tushare的高级数据，获取token：

1. 访问 https://tushare.pro/register 注册
2. 获取你的token
3. 设置环境变量或配置文件

```python
import tushare as ts
ts.set_token('your_token_here')
```

## 本地缓存设置

预填充历史数据（即使在线源不可用也能运行）：

```bash
python scripts/setup_price_cache.py
```

这会为以下股票创建真实历史模式数据：
- 600519.SH (贵州茅台)
- 000001.SZ (平安银行)
- 002594.SZ (比亚迪)
- 601012.SH (隆基绿能)
- 000300.SH (沪深300)

## 数据获取流程

系统自动按以下顺序尝试：

```
请求数据
    ↓
AKShare可用? → 是 → 获取 → 缓存到本地
    ↓ 否
Tushare可用? → 是 → 获取 → 缓存到本地
    ↓ 否
BaoStock可用? → 是 → 获取 → 缓存到本地
    ↓ 否
本地缓存有数据? → 是 → 返回缓存
    ↓ 否
返回空
```

## 验证数据源

```bash
# 测试数据源连接
python scripts/test_akshare.py

# 查看当前缓存数据
python scripts/view_db.py
```

## 数据源对比

| 特性 | AKShare | Tushare | BaoStock |
|------|---------|---------|----------|
| 免费 | ✅ | ✅ (基础) | ✅ |
| 需注册 | ❌ | ✅ | ❌ |
| A股数据 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| 港股数据 | ✅ | ✅ | ❌ |
| 财务数据 | ✅ | ✅ | ✅ |
| 实时行情 | ✅ | ✅ | ✅ |
| 安装难度 | 简单 | 中等 | 简单 |
| 推荐度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

## 故障排查

### AKShare连接失败
```
症状: Connection aborted, Remote end closed
原因: AKShare数据源不稳定
解决: 自动降级到本地缓存，无需手动处理
```

### Tushare Token无效
```
症状: 提示需要token
解决: 免费注册获取，或只使用AKShare
```

### 本地缓存为空
```
解决: 运行 python scripts/setup_price_cache.py
```

## 扩展其他数据源

如需添加QStock、东方财富等数据源，参考：

- `data_layer/adapters/multi_source_adapter.py`
- `data_layer/adapters/akshare_adapter.py`

PR欢迎！

## PDF 转换

AlphaFoundry 支持将 PDF 研报自动转换为 Markdown/文本，支持三种策略自动降级。

### 架构

PDF 转换已从爬虫层 (`data_layer/crawlers/utils/pdf_converter.py`) 重构为服务层自动化：

1. **下载阶段**：ZQ 爬虫下载 PDF 后自动注册到 `pdf_artifact_v1` 表（`parse_status='pending'`）
2. **转换阶段**：`CrawlScheduler` 每 5 分钟自动调用 `PDFConversionService.convert_pending(limit=5)` 并重试失败项
3. **提取阶段**：转换成功后自动创建 `DocumentV1` + 分块，并送入摄取队列由 `KnowledgePipeline` 做 LLM 提取

### 转换策略升降级

| 优先级 | 策略 | 质量 | 依赖 | 描述 |
|--------|------|------|------|------|
| 1 (最高) | MinerU | 最高 | `mineru[all]` + `magic-pdf` CLI | opendatalab/mineru, 保留表格结构和文档布局 |
| 2 | MarkItDown | 高 | `markitdown[pdf]` | microsoft/markitdown, Markdown 转换 + 特征检测 |
| 3 (始终可用) | Raw Text | 基线 | `pdfplumber` | 纯文本提取, 内置页面标记 |

### 安装

```bash
# 基础安装 (pdfplumber only, always works)
pip install -e .

# 安装 MarkItDown 支持
pip install -e ".[pdf]"

# 安装完整 PDF 转换支持 (包括 MinerU)
pip install -e ".[pdf-full]"
```

### Admin API

| 方法 | 路由 | 描述 |
|------|------|------|
| POST | `/api/admin/pdf/convert` | 触发指定 PDF 转换 |
| GET | `/api/admin/pdf/stats` | 获取转换统计 |
| GET | `/api/admin/pdf/pending` | 列出待转换的 PDF |
| POST | `/api/admin/pdf/retry` | 重试失败的转换 |

详见 `docs/modules/pdf_conversion_pipeline.md`。
