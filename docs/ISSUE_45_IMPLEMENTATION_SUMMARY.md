# Issue #45: RAG 检索层设计

## 概述

Issue #45 在 Issues #42 和 #44 的基础上，设计并实现了完整的 RAG（检索增强生成）检索层，包括检索配置、过滤条件、时间衰减、证据包构建，以及报告与回测视角分离。

## 完成的工作

### 1. 检索层契约 (`core/contracts/retrieval.py`)

创建了完整的检索契约，包括：

**枚举类型：**
- `RetrievalProfileType`: 5种预定义检索 Profile 类型（日报、周报、月报、深度研究、回测）
- `EvidenceType`: 证据类型（事实、观点、混合、数据、引述、分析）

**配置模型：**
- `RecencyDecayConfig`: 时间衰减配置（半衰期、最小权重等）
- `SourceWeightConfig`: 来源权重配置
- `DocTypeLookbackConfig`: 文档类型回看时间配置
- `RetrievalProfile`: 完整的检索 Profile 配置

**查询与过滤：**
- `RetrievalFilters`: 多维度过滤条件（时间、来源、行业、主题、实体、质量等）
- `RetrievalQuery`: 检索查询（查询文本、过滤条件、Profile 类型等）

**证据包输出：**
- `EvidenceChunk`: 单个分块的证据信息
- `EvidenceDocument`: 单个文档的证据信息
- `EvidencePackage`: 完整的检索结果包

**便捷函数：**
- `create_daily_report_profile()`: 创建日报 Profile
- `create_weekly_report_profile()`: 创建周报 Profile
- `create_monthly_report_profile()`: 创建月报 Profile
- `create_deep_dive_profile()`: 创建深度研究 Profile
- `create_backtest_replay_profile()`: 创建回测 Profile
- `get_profile(profile_type)`: 获取指定类型的 Profile

### 2. 时间衰减评分器 (`core/services/rag_retrieval.py`)

实现了 `RecencyDecayScorer`：

**功能：**
- 基于半衰期的指数衰减算法
- 最小权重保护（极旧文档也不会完全丢失权重）
- 支持自定义参考时间
- 自动处理未来文档（给满分）

**公式：**
```
decay_factor = 0.5 ^ (days_ago / half_life_days)
```

### 3. 文档过滤器 (`core/services/rag_retrieval.py`)

实现了 `DocumentFilter`：

**支持的过滤维度：**
- 时间过滤（发布时间、可用时间）
- 来源过滤（文档类型、来源类型、来源名称）
- 分类过滤（主行业、次行业、主题、事件类型）
- 质量过滤（研究可用性、来源可信度、证据质量、主观性）
- 证据特征过滤（是否有明确事实、数据点、引述、分析）

**特性：**
- 与 RetrievalProfile 无缝集成
- 支持回测模式（使用 available_time 而非 publish_time）
- 结构化的多条件组合判断

### 4. 证据包构建器 (`core/services/rag_retrieval.py`)

实现了 `EvidencePackageBuilder`：

**功能：**
- 将 DocumentV1 转换为 EvidenceDocument
- 将 DocumentChunkV1 转换为 EvidenceChunk
- 自动检测证据类型（事实/观点/数据/引述/分析）
- 生成引用锚点用于报告生成
- 计算来源分布和行业分布

### 5. RAG 检索服务 (`core/services/rag_retrieval.py`)

实现了 `RAGRetrievalService`：

**核心流程：**
1. 接受检索查询和 Profile
2. 使用 DocumentFilter 过滤文档
3. 使用 RecencyDecayScorer 进行时间衰减评分
4. 综合搜索相关性、时效性、质量、来源权重排序
5. 构建 EvidencePackage 输出结果

**特性：**
- 与现有 VectorStore 和 HybridSearcher 集成
- 内存文档索引（生产环境可扩展为数据库）
- 灵活的 Profile 切换
- 报告与回测视角分离

### 6. 单元测试 (`tests/unit/test_issue45.py`)

创建了完整的测试覆盖：

**测试套件：**
- `TestRecencyDecayScorer`: 测试时间衰减评分
- `TestDocumentFilter`: 测试文档过滤
- `TestEvidencePackageBuilder`: 测试证据包构建
- `TestRetrievalProfiles`: 测试检索 Profile
- `TestRAGRetrievalService`: 测试检索服务
- `TestIssue45Integration`: 集成测试

**测试数量：** 30个测试，全部通过

## 设计特点

### 1. 5种预定义检索 Profiles

**日报 (Daily Report):**
- 短时间窗口（电报仅看1天，新闻看2天）
- 快速时间衰减（半衰期2天）
- 侧重最新、可信度高的信息

**周报 (Weekly Report):**
- 中等时间窗口
- 平衡时效性和深度
- 侧重研报和权威新闻

**月报 (Monthly Report):**
- 长时间窗口
- 侧重深度分析和研究报告
- 较慢时间衰减

**深度研究 (Deep Dive):**
- 最长时间窗口（研报看180天）
- 最小时间衰减
- 全面检索所有相关信息

**回测 (Backtest Replay):**
- 使用 `available_time` 而非 `publish_time`
- 确保不使用未来信息
- 支持自定义截止时间

### 2. 报告与回测视角分离

**报告视角（默认）：**
- 使用 `publish_time`
- 侧重最新和最相关信息
- 可以包含观点源

**回测视角：**
- 使用 `available_time`（实际可用时间）
- 防止未来信息泄露
- 更严格的过滤条件

### 3. 结构化过滤维度

10+种过滤条件：
- 时间范围
- 来源类型/名称
- 行业（主/次）
- 主题/事件类型
- 实体（ID/名称/类型）
- 质量（可用性/可信度/证据质量）
- 主观性（仅事实/仅观点/混合）

### 4. 证据包输出

**结构：**
```
EvidencePackage
├── query
├── profile_used
├── total_documents_found
├── total_chunks_found
├── documents (List[EvidenceDocument])
│   ├── doc_id
│   ├── title/summary
│   ├── source info
│   ├── time info
│   ├── classification info
│   ├── quality info
│   ├── chunks (List[EvidenceChunk])
│   └── citation_anchor
└── distributions (source/industry)
```

**用途：**
- 直接用于报告生成
- 可用于回测分析
- 包含完整元数据和引用信息

## 文件变更清单

### 新增文件

1. `core/contracts/retrieval.py`: 检索层契约
2. `core/services/rag_retrieval.py`: RAG 检索服务
3. `tests/unit/test_issue45.py`: 单元测试
4. `docs/ISSUE_45_IMPLEMENTATION_SUMMARY.md`: 本文档

### 修改文件

1. `core/contracts/__init__.py`: 导出新增契约
2. `core/services/__init__.py`: 导出新增服务

## 使用示例

### 基本检索（日报 Profile）

```python
from core.contracts.retrieval import RetrievalQuery, RetrievalProfileType
from core.services.rag_retrieval import RAGRetrievalService

service = RAGRetrievalService()

query = RetrievalQuery(
    query_text="茅台业绩分析",
    profile_type=RetrievalProfileType.DAILY_REPORT
)

package = service.retrieve(query)

print(f"找到 {package.total_documents_found} 个文档")
for doc in package.documents:
    print(f"- [{doc.citation_anchor}] {doc.title}")
```

### 回测模式检索

```python
from datetime import datetime, timedelta
from core.contracts.retrieval import RetrievalQuery, RetrievalFilters, RetrievalProfileType

cutoff = datetime.utcnow() - timedelta(days=30)

query = RetrievalQuery(
    query_text="茅台业绩分析",
    profile_type=RetrievalProfileType.BACKTEST_REPLAY,
    filters=RetrievalFilters(available_time_before=cutoff)
)

package = service.retrieve(query)
```

### 自定义过滤条件

```python
from core.contracts.documents_v1 import DocType, SourceType
from core.contracts.retrieval import RetrievalFilters, RetrievalQuery

filters = RetrievalFilters(
    doc_types=[DocType.REPORT, DocType.NEWS],
    primary_industries=["tech", "finance"],
    min_research_usability=0.5,
    has_data_points=True
)

query = RetrievalQuery(
    query_text="市场分析",
    filters=filters
)
```

### 创建自定义 Profile

```python
from core.contracts.retrieval import (
    RetrievalProfile,
    RetrievalProfileType,
    DocTypeLookbackConfig,
    RecencyDecayConfig,
)

custom_profile = RetrievalProfile(
    profile_type=RetrievalProfileType.DEEP_DIVE,
    name="My Custom Research Profile",
    description="My custom research profile",
    lookback_config=DocTypeLookbackConfig(
        lookback_days={DocType.REPORT: 365},
        default_lookback_days=180
    ),
    recency_decay=RecencyDecayConfig(
        half_life_days=60.0,
        min_score_weight=0.05
    ),
    min_research_usability=0.4,
    max_documents=100
)
```

## 验收标准对照

Issue #45 的所有验收标准已达成：

- [x] **检索流程设计**: 完整的检索 pipeline
- [x] **过滤维度支持**: 10+种过滤条件
- [x] **5种 Retrieval Profiles**: 日报、周报、月报、深度研究、回测
- [x] **时间衰减机制**: 基于半衰期的指数衰减
- [x] **证据包构建**: 结构化 EvidencePackage 输出
- [x] **报告与回测分离**: publish_time vs available_time

## 下一步

- Issue #46: 模板化研报生成
- Issue #47: 回测视角与消息面特征

## 总结

Issue #45 构建了完整的 RAG 检索层，支持多种检索场景，提供结构化过滤、时间衰减评分，以及报告与回测视角的明确分离。所有功能均已实现并测试通过，共包含 30 个单元测试，全部通过。
