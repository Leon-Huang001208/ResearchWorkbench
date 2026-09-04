# RWB-AUTO-002-07: 数据库 Schema 审计与扩展报告

## 概述

本报告审计了现有文档、断言、事件及相关持久化 schema，并扩展了它们以支持爬虫状态、来源标识符、解析元数据、Markdown 输出和抓取谱系。

## 一、现有 Schema 审计

### 1.1 核心表审计

| 表名 | 状态 | 说明 |
|------|------|------|
| `entity` | ✅ 良好 | 实体表，包含规范的索引 |
| `source_document` | ✅ 良好 | 源文档表，已有基本元数据字段 |
| `assertion` | ✅ 良好 | 断言表，完整的关系映射 |
| `canonical_event` | ✅ 良好 | 规范事件表 |
| `reasoning_trace` | ✅ 良好 | 推理追踪表 |

### 1.2 Document V1 表审计

| 字段 | 状态 | 说明 |
|------|------|------|
| `doc_id` | ✅ | 主键 |
| `doc_type` | ✅ | 文档类型索引 |
| `source_type` | ✅ | 来源类型索引 |
| `title` | ✅ | 标题 |
| `summary` | ✅ | 摘要 |
| `content` | ✅ | 内容 |
| `doc_metadata` | ✅ | 文档元数据 JSON |
| `source_metadata` | ✅ | 来源元数据 JSON |
| `classification` | ✅ | 分类 JSON |
| `quality` | ✅ | 质量 JSON |
| `evidence_profile` | ✅ | 证据概况 JSON |
| `timeliness` | ✅ | 时效性 JSON |
| `processing` | ✅ | 处理状态 JSON |
| `review` | ✅ | 审核状态 JSON |
| `extra` | ✅ | 额外 JSON |
| `content_hash` | ✅ | 内容哈希索引 |

**审计结论**：Document V1 表设计良好，已覆盖大部分摄取元数据需求。

### 1.3 辅助表审计

| 表名 | 用途 | 状态 |
|------|------|------|
| `document_chunk_v1` | 文档分块 | ✅ 良好 |
| `document_tag_v1` | 文档标签 | ✅ 良好 |
| `document_summary_v1` | 文档摘要 | ✅ 良好 |
| `document_event_v1` | 文档事件 | ✅ 良好 |
| `entity_mention_v1` | 实体提及 | ✅ 良好 |
| `crawl_run_v1` | 抓取运行 | ⚠️ 需要补充 |
| `source_cursor_v1` | 来源游标 | ⚠️ 需要补充 |
| `report_run_v1` | 报告运行 | ✅ 良好 |

**审计发现**：
- `crawl_run_v1` 和 `source_cursor_v1` 已存在，但缺少 PDF 和去重状态持久化
- 缺少对 PDF 制品元数据的支持
- 缺少对 PDF 转换结果的支持
- 缺少通用的已处理项目表

## 二、已扩展 Schema

### 2.1 PDF 制品表 (`pdf_artifact_v1`)

```python
class PDFArtifactV1DB(Base):
    """PDF 制品表 - 存储下载的 PDF 文件元数据"""
    # 主键与关联
    pdf_id = Column(Text, primary_key=True)
    doc_id = Column(Text, ForeignKey("document_v1.doc_id"), nullable=True, index=True)
    source_obj_id = Column(Text, nullable=True, index=True)

    # 文件信息
    file_path = Column(Text, nullable=False)
    file_name = Column(Text, nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_hash_sha256 = Column(Text, nullable=False, index=True)
    file_hash_md5 = Column(Text, nullable=True)

    # 来源信息
    source_type = Column(Text, nullable=False, index=True)
    source_name = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    source_broker = Column(Text, nullable=True)
    source_author = Column(Text, nullable=True)
    source_publish_date = Column(DateTime(timezone=True), nullable=True)

    # 抓取元数据
    fetch_timestamp = Column(DateTime(timezone=True), nullable=False)
    fetch_config = Column(JSON, nullable=False, default=dict)
    fetch_strategy = Column(Text, nullable=True)
    fetch_duration_ms = Column(Integer, nullable=True)

    # 解析元数据
    parse_version = Column(Text, nullable=True)
    parse_config = Column(JSON, nullable=False, default=dict)
    parse_status = Column(Text, nullable=False, default="pending")
    parse_error = Column(Text, nullable=True)
    parsed_at = Column(DateTime(timezone=True), nullable=True)

    # 额外元数据
    pdf_metadata = Column(JSON, nullable=False, default=dict)
    extra = Column(JSON, nullable=False, default=dict)
```

**设计要点**：
- ✅ 支持与 Document V1 关联
- ✅ 记录完整的文件哈希（SHA-256 优先）
- ✅ 支持来源券商信息（为 ZQ 研报定制）
- ✅ 抓取策略记录（RWB-AUTO-002-05）
- ✅ 解析状态追踪
- ✅ 索引覆盖常用查询模式

### 2.2 PDF 转换结果表 (`pdf_conversion_v1`)

```python
class PDFConversionV1DB(Base):
    """PDF 转换结果表 - 存储 PDF 转换为 Markdown 或文本的结果"""
    conversion_id = Column(Text, primary_key=True)
    pdf_id = Column(Text, ForeignKey("pdf_artifact_v1.pdf_id"), nullable=False, index=True)

    # 转换策略信息
    conversion_strategy = Column(Text, nullable=False, index=True)
    strategy_version = Column(Text, nullable=True)
    strategy_config = Column(JSON, nullable=False, default=dict)

    # 转换结果 - 支持路径或内联
    markdown_path = Column(Text, nullable=True)
    markdown_content = Column(Text, nullable=True)
    raw_text_path = Column(Text, nullable=True)
    raw_text_content = Column(Text, nullable=True)

    # 转换统计
    page_count = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    conversion_duration_ms = Column(Integer, nullable=True)

    # 质量指标
    quality_score = Column(Numeric, nullable=True)
    has_tables = Column(Boolean, nullable=True)
    has_images = Column(Boolean, nullable=True)
    has_code_blocks = Column(Boolean, nullable=True)

    # 状态
    status = Column(Text, nullable=False, default="pending", index=True)
    error_log = Column(Text, nullable=True)
```

**设计要点**：
- ✅ 可插拔转换策略（RWB-AUTO-002-06）
- ✅ 支持路径或内联存储（灵活应对大小文件）
- ✅ 质量指标记录
- ✅ 完整的状态追踪

### 2.3 爬虫状态表 (`crawl_state_v1`)

```python
class CrawlStateV1DB(Base):
    """爬虫状态表 - 持久化存储爬虫状态、水位线、去重信息"""
    state_id = Column(Text, primary_key=True)
    source_type = Column(Text, nullable=False, index=True)
    source_name = Column(Text, nullable=True, index=True)

    # 水位线信息
    watermark_id = Column(Text, nullable=True)
    watermark_timestamp = Column(DateTime(timezone=True), nullable=True)
    watermark_metadata = Column(JSON, nullable=False, default=dict)

    # 去重信息
    dedupe_key = Column(Text, nullable=True, index=True)
    dedupe_count = Column(Integer, nullable=False, default=0)

    # 爬虫统计
    total_fetched = Column(Integer, nullable=False, default=0)
    total_skipped = Column(Integer, nullable=False, default=0)
    total_failed = Column(Integer, nullable=False, default=0)

    # 爬虫配置
    crawl_config = Column(JSON, nullable=False, default=dict)
    crawl_mode = Column(Text, nullable=False, default="incremental")

    # 会话信息
    last_run_id = Column(Text, nullable=True)
    last_run_start = Column(DateTime(timezone=True), nullable=True)
    last_run_end = Column(DateTime(timezone=True), nullable=True)

    # 暂停控制
    is_paused = Column(Boolean, nullable=False, default=False)
    pause_reason = Column(Text, nullable=True)
```

**设计要点**：
- ✅ 支持水位线持久化（RWB-AUTO-002-03）
- ✅ 支持完整/增量模式切换
- ✅ 暂停控制（为 RWB-AUTO-002-08 准备）
- ✅ 抓取统计聚合

### 2.4 已处理项目表 (`processed_item_v1`)

```python
class ProcessedItemV1DB(Base):
    """已处理项目表 - 用于去重，支持快速检查项目是否已处理"""
    item_id = Column(Text, primary_key=True)
    source_type = Column(Text, nullable=False, index=True)
    source_name = Column(Text, nullable=True, index=True)

    # 项目元数据
    item_type = Column(Text, nullable=False, index=True)
    title = Column(Text, nullable=True)
    content_preview = Column(Text, nullable=True)
    content_hash = Column(Text, nullable=True, index=True)

    # 处理信息
    first_seen_at = Column(DateTime(timezone=True), nullable=False)
    first_processed_at = Column(DateTime(timezone=True), nullable=True)
    process_count = Column(Integer, nullable=False, default=1)

    # 来源关联
    crawl_run_id = Column(Text, nullable=True, index=True)
    doc_id = Column(Text, nullable=True, index=True)
```

**设计要点**：
- ✅ 支持按来源类型/名称分区
- ✅ 内容哈希去重（可检测内容变化）
- ✅ 处理次数追踪（幂等性保证）
- ✅ 与 Crawl Run 和 Document 关联

## 三、Schema 变更清单

### 3.1 新增表

| 表名 | 迁移文件 | 任务关联 |
|------|----------|----------|
| `pdf_artifact_v1` | 002 | RWB-AUTO-002-05 |
| `pdf_conversion_v1` | 002 | RWB-AUTO-002-06 |
| `crawl_state_v1` | 002 | RWB-AUTO-002-03, -08 |
| `processed_item_v1` | 002 | RWB-AUTO-002-03 |

### 3.2 现有表字段补充

| 表名 | 已存在字段 | 满足需求 |
|------|----------|---------|
| `document_v1` | `source_metadata`, `doc_metadata` | ✅ 无需补充 |
| `crawl_run_v1` | `config`, `status`, `success_count` | ✅ 无需补充 |
| `source_cursor_v1` | `last_source_doc_id`, `config` | ✅ 无需补充 |

### 3.3 索引规划

| 表名 | 索引 | 用途 |
|------|------|------|
| `pdf_artifact_v1` | `idx_pdf_artifact_hash` | 快速去重检测 |
| `pdf_artifact_v1` | `idx_pdf_artifact_source_obj_id` | 来源对象查询 |
| `pdf_conversion_v1` | `idx_pdf_conversion_status` | 待处理队列查询 |
| `crawl_state_v1` | `idx_crawl_state_source_type` | 按来源查询状态 |
| `processed_item_v1` | `idx_processed_item_hash` | 内容哈希去重 |

## 四、去重键、抓取时间戳、解析策略存储设计

### 4.1 去重键存储

**存储位置**：`processed_item_v1.item_id` + `content_hash`

**去重策略**：
1. **ID 去重**：`item_id` 主键保证唯一性
2. **内容去重**：`content_hash` 索引支持内容变化检测
3. **来源分区**：`source_type` + `source_name` 支持按来源独立去重

**使用流程**：
```
1. 生成 content_hash
2. 查询 processed_item_v1 是否存在
3. 不存在：处理并插入
4. 存在：比较 hash → 相同跳过 / 不同更新
```

### 4.2 抓取时间戳存储

**存储位置**：
- `pdf_artifact_v1.fetch_timestamp` - PDF 抓取时间
- `crawl_state_v1.last_run_start/end` - 爬虫运行时间窗口
- `processed_item_v1.first_seen_at` - 首次发现时间

**时间序列查询**：
```sql
-- 查询最近 24 小时新增的 PDF
SELECT * FROM pdf_artifact_v1
WHERE fetch_timestamp > NOW() - INTERVAL '24 hours'
ORDER BY fetch_timestamp DESC;
```

### 4.3 解析策略存储

**存储位置**：
- `pdf_artifact_v1.parse_version` + `parse_config`
- `pdf_conversion_v1.conversion_strategy` + `strategy_version` + `strategy_config`

**策略可追溯性**：
- 记录使用的策略版本
- 记录策略配置参数
- 支持按策略重新处理

### 4.4 原始资产元数据存储

**存储位置**：
- `pdf_artifact_v1.pdf_metadata` - PDF 自身元数据
- `pdf_artifact_v1.source_metadata`（关联 document_v1）
- `pdf_artifact_v1.fetch_config` - 抓取配置快照

**元数据来源**：
1. PDF 内部：作者、标题、创建时间等
2. 抓取上下文：请求头、代理、重试信息
3. 来源网站：发布时间、来源 URL、券商信息

## 五、数据库迁移文件

**迁移文件**：`storage/migrations/versions/002_pdf_crawl_state_schema.py`

**迁移内容**：
1. 创建 `pdf_artifact_v1` 表及索引
2. 创建 `pdf_conversion_v1` 表及索引
3. 创建 `crawl_state_v1` 表及索引
4. 创建 `processed_item_v1` 表及索引

**回滚支持**：完整的 `downgrade()` 函数

## 六、总结与后续建议

### 6.1 完成情况

| 成功标准 | 状态 |
|----------|------|
| Schema 审计完成 | ✅ |
| 缺失摄取元数据字段识别并实现 | ✅ |
| 去重键、抓取时间戳、解析策略存储文档 | ✅ |
| Schema 扩展报告创建 | ✅ |

### 6.2 后续建议

1. **RWB-AUTO-002-08**：基于 `crawl_state_v1` 和 `processed_item_v1` 构建监控和管理 API
2. **索引优化**：根据实际查询模式补充部分索引
3. **数据归档**：设计历史数据归档策略
4. **去重键自动生成**：集成内容哈希自动计算

## 附录：数据模型完整定义

完整的模型定义请参考：
- `data_layer/repositories/models.py` - SQLAlchemy 模型
- `storage/migrations/versions/002_pdf_crawl_state_schema.py` - 迁移文件
