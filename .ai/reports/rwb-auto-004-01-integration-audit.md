# RWB-AUTO-004-01: 数据集成审计报告

## 概述

本报告审计了现有数据模型与市场概览仪表盘的集成可行性，包括 DocumentV1、CanonicalEvent 和 AlphaSignalDB。

## 1. 数据模型审计

### 1.1 DocumentV1（文档模型）

**表名**: `document_v1`

**关键字段**:
| 字段 | 类型 | 用途 |
|------|------|------|
| `doc_id` | Text PK | 文档唯一标识 |
| `doc_type` | Text (indexed) | 文档类型：telegram, news, commentary, report, wechat, transcript, filing, policy, internal_note |
| `source_type` | Text (indexed) | 来源类型：cailian_she, zhiqiu_reports, zhiqiu_wechat, east_money 等 |
| `title` | Text | 标题 |
| `summary` | Text | 摘要 |
| `content` | Text | 全文内容 |
| `source_name` | Text | 来源名称 |
| `source_url` | Text | 来源URL |
| `language` | Text | 语言，默认 'zh' |
| `content_hash` | Text (indexed) | 内容哈希，用于去重 |

**JSON 字段结构**:

1. **classification** - 分类信息:
   ```python
   {
       "primary_industry": str,
       "secondary_industries": List[str],
       "topics": List[str],
       "event_types": List[str],
       "region": str
   }
   ```

2. **quality** - 质量评分:
   ```python
   {
       "source_reliability_level": str,  # official, established_media, research_institute, specialized_media, opinion_leader, social_media, unknown
       "subjectivity_level": str,      # fact_only, fact_heavy, mixed, opinion_heavy, opinion_only
       "fact_opinion_ratio": float,
       "research_usability_score": float,  # 0.0-1.0
       "content_quality_score": float,     # 0.0-1.0
       "is_fact_source": bool
   }
   ```

3. **timeliness** - 时效性信息:
   ```python
   {
       "publish_time": datetime,
       "crawl_time": datetime,
       "event_time": datetime
   }
   ```

**与 GlobalNewsItem 的映射关系**:
| GlobalNewsItem 字段 | DocumentV1 来源 |
|---------------------|----------------|
| `news_id` | `doc_id` |
| `title` | `title` |
| `source` | `source_name` |
| `importance_score` | `quality.research_usability_score` 或 `content_quality_score` |
| `summary` | `summary` (优先) 或 `content` 的前 200 字 |
| `content_url` | `source_url` |
| `published_at` | `timeliness.publish_time` 或 `created_at` |
| `related_symbols` | 通过 `document_entity_mention_v1` 关联查询 |
| `region` | `classification.region` |

### 1.2 CanonicalEvent（规范事件模型）

**表名**: `canonical_event`

**关键字段**:
| 字段 | 类型 | 用途 |
|------|------|------|
| `event_id` | Text PK | 事件唯一标识 |
| `event_type` | Text | 事件类型 |
| `summary` | Text | 摘要 |
| `event_time` | DateTime | 事件时间 |
| `impact_direction` | Text | 影响方向：positive, negative, mixed, unknown |
| `confidence` | Numeric | 置信度 0.0-1.0 |
| `needs_review` | Boolean | 是否需要人工审核 |
| `source_doc_id` | Text FK | 源文档 ID |
| `payload` | JSON | 扩展数据 |
| `reviewer_status` | Text | 审核状态：draft, pending, approved, rejected |

**payload 结构**:
```python
{
    "source_type": str,
    "source_name": str,
    "title": str,
    "raw_text": str,
    "extracted_assertions": List[dict],
    "impacted_industries": List[str],
    "impacted_symbols": List[str],
    "novelty_score": float,  # 0.0-1.0
    "entities": List[dict],
    "assertions": List[dict],
    "evidence_spans": List[dict]
}
```

**与 GlobalNewsItem 的映射关系**:
| GlobalNewsItem 字段 | CanonicalEvent 来源 |
|---------------------|---------------------|
| `news_id` | `event_id` |
| `title` | `payload.title` 或 `summary` |
| `source` | `payload.source_name` |
| `importance_score` | `payload.novelty_score` 或 `confidence` |
| `summary` | `summary` |
| `content_url` | 从源文档获取 |
| `published_at` | `event_time` |
| `related_symbols` | `payload.impacted_symbols` |
| `region` | 从分类推断 |

### 1.3 AlphaSignalDB（Alpha 信号模型）

**表名**: `alpha_signal`

**关键字段**:
| 字段 | 类型 | 用途 |
|------|------|------|
| `signal_id` | Text PK | 信号唯一标识 |
| `discriminator` | Text | 区分子类型：'alpha_signal' 或 'event_alpha_signal' |
| `subject_id` | Text (indexed) | 标的 ID |
| `horizon` | Text | 时间周期：1d, 5d, 20d, 60d |
| `thesis` | Text | 投资论点 |
| `score` | Numeric | Alpha 评分 |
| `confidence` | Numeric | 置信度 0.0-1.0 |
| `scenario_refs` | JSON List | 情景引用 |
| `evidence_refs` | JSON List | 证据引用 |
| `status` | Text | 状态：research_only, candidate, paper_trading |

**EventAlphaSignal 特有字段**:
| 字段 | 类型 | 用途 |
|------|------|------|
| `event_id` | Text (indexed) | 关联事件 ID |
| `event_type` | Text | 事件类型 |
| `event_time` | DateTime | 事件时间 |
| `impact_path` | JSON List | 影响传播路径 |
| `industry_impacts` | JSON List | 受影响行业列表 |
| `bullish_companies` | JSON List | 看多公司列表 |
| `bearish_companies` | JSON List | 看空公司列表 |
| `diffusion_stage` | Text | 传播阶段：discovery, early_awareness, theme_trading, institutional_coverage, consensus, decay, unknown |
| `market_regime` | Text | 市场状态 |
| `validation_status` | Text | 验证状态：pending_backtest, validated, rejected, paper_trade |
| `validation_metrics` | JSON | 验证指标 |

**与 SectorChangeItem 的映射关系**:
| SectorChangeItem 字段 | AlphaSignalDB 来源 |
|------------------------|--------------------|
| `sector_id` | 行业名称的哈希或 slug |
| `name` | `industry_impacts` 中的行业名称 |
| `change_pct` | 从 `bullish_companies` 和 `bearish_companies` 计算得出 |
| `leading_stocks` | `bullish_companies` 或 `bearish_companies` |
| `related_news_count` | 关联事件/文档数量 |
| `is_concept` | 行业名称是否为概念 |

## 2. 可用仓库方法审计

### 2.1 DocumentV1Repository

**路径**: `data_layer/repositories/documents_v1.py:DocumentV1Repository`

**可用方法**:
| 方法 | 用途 | 可复用性 |
|------|------|---------|
| `list(source_type, doc_type, limit, offset)` | 列出文档，按创建时间倒序 | ✅ 高 |
| `search_by_keyword(keyword, limit)` | 按关键词搜索标题和内容 | ✅ 高 |
| `get_by_content_hash(content_hash)` | 按内容哈希获取 | ⚠️ 中 |
| `list_by_time_range(start_time, end_time, source_type, limit)` | 按时间范围查询 | ⚠️ 中（需修复字段名） |
| `count()` | 统计总数 | ✅ 高 |

**注意**: `list_by_time_range` 引用了不存在的 `available_time` 字段，需要修复为使用 `created_at` 或 `timeliness.publish_time`。

### 2.2 EventRepositoryImpl

**路径**: `data_layer/repositories/event_repository.py:EventRepositoryImpl`

**可用方法**:
| 方法 | 用途 | 可复用性 |
|------|------|---------|
| `list(limit, offset)` | 列出事件 | ✅ 高 |
| `get_by_time_range(start, end)` | 按时间范围查询（接受 ISO 字符串） | ✅ 高 |
| `list_by_event_type(event_type, limit)` | 按事件类型查询 | ✅ 高 |
| `list_by_impacted_symbol(symbol, limit)` | 按影响标的查询 | ✅ 高 |
| `get_pending_review()` | 获取待审核事件 | ⚠️ 中 |

### 2.3 SignalRepositoryImpl

**路径**: `data_layer/repositories/signal_repository.py:SignalRepositoryImpl`

**可用方法**:
| 方法 | 用途 | 可复用性 |
|------|------|---------|
| `list(status, subject_id, limit)` | 列出信号，按创建时间倒序 | ✅ 高 |
| `get(signal_id)` | 获取单个信号 | ✅ 高 |
| `update_status(signal_id, new_status)` | 更新信号状态 | ⚠️ 中 |

## 3. 实体关系映射

```
DocumentV1 (doc_id)
    ├─→ DocumentEventV1 (doc_id, canonical_event_id)
    │       └─→ CanonicalEvent (event_id)
    │                   └─→ EventAlphaSignal (event_id)
    │                           ├─→ industry_impacts: List[str]
    │                           ├─→ bullish_companies: List[str]
    │                           └─→ bearish_companies: List[str]
    │
    ├─→ DocumentEntityMentionV1 (doc_id, entity_id, entity_name, entity_type)
    │       └─→ Entity (entity_id, canonical_id, canonical_name)
    │
    └─→ DocumentTagV1 (doc_id, tag, tag_type, confidence)
```

## 4. 数据提取策略

### 4.1 GlobalNewsItem 提取策略

**优先级 1: CanonicalEvent** (推荐)
- 使用 `payload.novelty_score` 作为重要性评分
- 使用 `payload.impacted_symbols` 作为相关标的
- 按 `event_time` 倒序
- 筛选 `reviewer_status != rejected`

**优先级 2: DocumentV1**
- 使用 `quality.research_usability_score` 或 `content_quality_score` 作为重要性评分
- 筛选 `doc_type in ['news', 'report', 'commentary']`
- 按 `created_at` 或 `timeliness.publish_time` 倒序
- 通过 `document_entity_mention_v1` 获取相关标的

**混合策略**:
- 优先展示事件类新闻（CanonicalEvent）
- 补充文档类新闻（DocumentV1）
- 合并后按重要性评分排序取 Top 10

### 4.2 SectorChangeItem 提取策略

**聚合策略**:
1. 从 EventAlphaSignal 获取最近的信号（例如过去 7 天）
2. 按 `industry_impacts` 中的行业分组
3. 对每个行业:
   - 统计 bullish_companies 和 bearish_companies
   - 计算看多/看空比例作为 change_pct
   - 列出前 N 个 leading_stocks
4. 按 change_pct 排序取 Top 5 (up) 和 Bottom 5 (down)

**需要增强的功能**:
- 行业/概念分类器（区分传统行业和概念）
- 行业名称标准化（不同来源可能有不同名称）
- 板块变化百分比的合理计算（基于真实市场数据或信号强度）

## 5. 发现的问题

### 5.1 DocumentV1Repository 的问题
- `list_by_time_range` 方法引用了不存在的 `available_time` 字段

### 5.2 数据缺失处理
- DocumentV1 的 `summary` 字段可能为空，需要回退到 `content` 摘要
- Entity 提及需要额外查询，可能影响性能
- 行业名称不统一，需要标准化

### 5.3 性能考虑
- 当前 EventRepositoryImpl 的 `list_by_impacted_symbol` 和 `get_by_entity` 方法是全表扫描
- 频繁查询相关实体可能需要添加索引

## 6. 建议的实现方案

### 6.1 新增 DashboardDataRepository
```
data_layer/repositories/dashboard_data.py
├── get_global_news(limit=10)
├── get_sector_changes(days=7, limit_per_direction=5)
└── helper methods for entity resolution
```

### 6.2 增强现有仓库
- 为 DocumentV1Repository 添加按质量评分排序的方法
- 为 SignalRepositoryImpl 添加按时间范围查询的方法
- 优化查询性能（添加必要的索引）

### 6.3 数据回退机制
- 当数据库没有足够数据时，回退到 mock 数据
- 记录日志表明使用了回退数据
- 提供数据新鲜度指标

## 7. 总结

✅ **现有数据模型完全支持市场概览仪表盘需求**
- DocumentV1 和 CanonicalEvent 均可作为 GlobalNewsItem 数据源
- AlphaSignalDB (EventAlphaSignal) 包含完整的行业影响数据
- 现有仓库方法大部分可复用

⚠️ **需要少量修复和增强**
- 修复 DocumentV1Repository 的字段引用问题
- 添加一些便利查询方法
- 实现行业名称标准化和分类

📋 **下一步**: 开始实现任务 RWB-AUTO-004-02 - 从现有文档提取新闻

---

**报告生成时间**: 2026-05-13
**审计任务**: RWB-AUTO-004-01
