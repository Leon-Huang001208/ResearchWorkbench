# Issue #42: 统一 Document Schema 实施总结

## 概述

Issue #42 要求为 Research Workbench v1 设计统一的文档 schema，使所有来源类型（电报、新闻、研报、公众号、会议纪要等）都能映射到同一个主模型。

## 完成的工作

### 1. 核心 Pydantic 模型 (`core/contracts/documents_v1.py`)

创建了完整的 v1 文档契约，包括：

#### 枚举类型
- `DocType`: 文档类型 (telegram, news, commentary, report, wechat, transcript 等)
- `SourceType`: 来源类型 (cls, cnstock, zhiqiu_reports 等)
- `SourceReliabilityLevel`: 来源可信度等级 (official, established_media, research_institute 等)
- `SubjectivityLevel`: 主观性等级 (fact_only, mixed, opinion_only)
- `DocumentProcessingStatus`: 处理状态
- `DocumentReviewStatus`: 审核状态

#### 主模型
- `DocumentV1`: 统一的文档模型，包含所有必填字段和可选字段
- `DocumentChunkV1`: 文档分块
- `DocumentTagV1`: 文档标签
- `DocumentSummaryV1`: 文档摘要
- `EntityMentionV1`: 实体提及
- `DocumentEventV1`: 文档事件
- `CrawlRunV1`: 抓取运行记录
- `SourceCursorV1`: 来源游标（用于增量抓取）
- `ReportRunV1`: 报告运行记录

#### 元数据模型
- `DocumentClassification`: 分类信息
- `DocumentQuality`: 质量评分
- `DocumentTimeliness`: 时效性信息（publish_time, crawl_time, available_time）
- `DocumentEvidenceProfile`: 证据概况
- `DocumentProcessingMeta`: 处理元数据
- `DocumentReview`: 审核信息

### 2. SQLAlchemy ORM 模型 (`data_layer/repositories/models.py`)

添加了完整的 v1 文档表：

- `document_v1`: 主文档表
- `document_chunk_v1`: 分块表
- `document_tag_v1`: 标签表
- `document_summary_v1`: 摘要表
- `document_entity_mention_v1`: 实体提及表
- `document_event_v1`: 文档事件表
- `crawl_run_v1`: 抓取运行记录表
- `source_cursor_v1`: 来源游标表（支持增量抓取、补漏、失败重试）
- `report_run_v1`: 报告运行记录表

每个 ORM 模型都包含 `from_contract()` 和 `to_contract()` 方法，支持与 Pydantic 模型的相互转换。

### 3. Repository 层 (`data_layer/repositories/documents_v1.py`)

实现了完整的数据访问层：

- `DocumentV1Repository`: 文档 CRUD、查询、去重
- `DocumentChunkV1Repository`: 分块管理、批量操作
- `DocumentTagV1Repository`: 标签管理
- `DocumentSummaryV1Repository`: 摘要管理
- `EntityMentionV1Repository`: 实体提及管理
- `DocumentEventV1Repository`: 事件管理
- `CrawlRunV1Repository`: 抓取记录管理
- `SourceCursorV1Repository`: 游标管理（支持 `get_or_create()`, `record_success()`, `record_failure()`）
- `ReportRunV1Repository`: 报告运行记录管理

### 4. 测试 (`tests/unit/test_documents_v1.py`)

创建了 17 个单元测试，覆盖：
- 文档模型的创建和验证
- 所有支持模型的功能
- 枚举值的完整性
- 模型序列化
- Repository 导入验证

所有测试通过：`17 passed, 1 warning in 0.04s`

### 5. 数据库初始化

通过 `scripts/bootstrap_db.py` 成功创建了所有 v1 文档表（共 9 个新表）。

## 设计特点

### 1. 统一的 JSON 主 Schema
- 所有来源类型都映射到同一个 `DocumentV1` 模型
- 支持来源特定的扩展字段通过 `source_metadata`
- 完整的元数据支持，包括可信度、主观性评分

### 2. 时间字段设计 (Issue #42 要求)
明确区分：
- `publish_time`: 发布时间
- `crawl_time`: 抓取时间
- `available_time`: 系统可用时间
- `event_time`: 事件发生时间
- `publish_time_precision`: 发布时间精度

### 3. 来源可信度层级
- `official`: 官方来源（最高可信度）
- `established_media`: 权威媒体
- `research_institute`: 研究机构
- `specialized_media`: 专业媒体
- `opinion_leader`: 意见领袖
- `social_media`: 社交媒体（最低可信度）
- `unknown`: 未知

### 4. 增量抓取支持
- `SourceCursorV1` 跟踪上次抓取位置
- `CrawlRunV1` 记录每次抓取状态
- 支持失败重试、连续失败计数
- 支持暂停/恢复机制

### 5. 与现有系统集成
- 新表与现有表（`entity`, `canonical_event` 等）通过外键关联
- 支持通过 `canonical_event_id` 链接到现有事件表
- 保持向后兼容性

## 文件变更清单

### 新增文件
1. `core/contracts/documents_v1.py`: v1 文档 Pydantic 模型
2. `data_layer/repositories/documents_v1.py`: v1 文档 Repository 层
3. `tests/unit/test_documents_v1.py`: 单元测试
4. `docs/ISSUE_42_IMPLEMENTATION_SUMMARY.md`: 本总结文档

### 修改文件
1. `core/contracts/__init__.py`: 导出 v1 文档模型
2. `data_layer/repositories/models.py`: 添加 v1 文档 ORM 模型

## 使用示例

### 创建文档

```python
from core.contracts import (
    DocumentV1, DocType, SourceType,
    DocumentClassification, DocumentQuality,
    DocumentTimeliness
)
from data_layer.repositories.documents_v1 import DocumentV1Repository
from data_layer.repositories.base import get_db

# 创建文档
doc = DocumentV1(
    doc_id="doc-001",
    doc_type=DocType.NEWS,
    source_type=SourceType.CLS,
    title="市场新闻",
    summary="新闻摘要",
    content="新闻内容...",
    classification=DocumentClassification(
        primary_industry="金融",
        topics=["market", "analysis"]
    ),
    quality=DocumentQuality(
        source_reliability_level=SourceReliabilityLevel.ESTABLISHED_MEDIA,
        subjectivity_level=SubjectivityLevel.FACT_ONLY,
        is_fact_source=True
    ),
    timeliness=DocumentTimeliness(
        publish_time=datetime(2024, 5, 10),
        crawl_time=datetime(2024, 5, 10, 0, 5)
    )
)

# 保存到数据库
db = next(get_db())
repo = DocumentV1Repository(db)
saved_doc = repo.create(doc)
```

### 使用游标进行增量抓取

```python
from core.contracts import SourceCursorV1, SourceType
from data_layer.repositories.documents_v1 import SourceCursorV1Repository

# 获取或创建游标
cursor_repo = SourceCursorV1Repository(db)
cursor = cursor_repo.get_or_create(SourceType.CLS, "财联社")

# 抓取完成后记录成功
cursor_repo.record_success(cursor.cursor_id, "last-doc-id-123")

# 失败时记录
cursor_repo.record_failure(cursor.cursor_id)
```

## 验收标准对照

Issue #42 的所有验收标准已达成：

- [x] 定义了统一的 JSON 主 schema
- [x] 为各来源设计了扩展 schema
- [x] 设计了完整的 PostgreSQL 表结构（9个新表）
- [x] 明确定义了关键时间字段
- [x] 定义了可信度与主观性层级
- [x] 创建了完整的 Repository 层
- [x] 添加了全面的单元测试（17个测试，全部通过）
- [x] 支持去重、增量抓取、补漏等功能

## 下一步

- Issue #43: 多源采集、原始落盘、增量调度与补漏机制
- Issue #44: PDF/HTML/纪要解析、chunk、taxonomy、标签与事件抽取
- Issue #45: RAG 检索层设计
- Issue #46: 模板化研报生成
- Issue #47: 回测视角

## 总结

Issue #42 "统一 Document Schema" 已完整实施。这为 Research Workbench v1 奠定了坚实的基础，使系统能够统一处理所有来源类型的文档，并为后续的采集、解析、检索、研报生成和回测功能提供了数据基础设施。

