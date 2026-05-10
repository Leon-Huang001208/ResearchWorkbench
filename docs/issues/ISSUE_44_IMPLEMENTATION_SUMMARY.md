# Issue #44: PDF/HTML/纪要解析、Chunk、Taxonomy、标签与事件抽取

## 概述

Issue #44 在 Issue #42 的基础上，实现了完整的文档富集流水线，包括文档分块、行业/主题分类系统、质量分析、证据画像、实体抽取、摘要生成，以及完整的 Pipeline 编排。

## 完成的工作

### 1. 文档分块服务 (`core/services/document_chunker.py`)

创建了灵活的文档分块服务：

**ChunkingStrategy 枚举**:
- `SIMPLE`: 简单固定大小分块
- `PARAGRAPH`: 按段落分块
- `SEMANTIC`: 按标题语义分块
- `SPEAKER`: 按发言人分块（适用于会议纪要）

**ChunkingOptions 配置**:
- `strategy`: 分块策略
- `chunk_size`: 目标块大小（字符数）
- `chunk_overlap`: 块重叠大小
- `min_chunk_size`: 最小块大小

**功能特性**:
- 支持策略组合（先语义后大小切分）
- 自动生成 chunk_id 和序号
- 每个块保留源文档引用
- 支持标题层级识别

### 2. 分类体系服务 (`core/services/taxonomy_service.py`)

实现了完整的行业和主题分类系统：

**层级行业结构**:
- **Level 1**: 9 个一级行业（科技、金融、消费、医药生物、制造、能源、材料、基础设施、传媒通信）
- **Level 2**: 11 个二级行业（半导体、AI、软件服务、食品饮料、零售、新能源、汽车、军工等）
- **Level 3**: 3 个三级行业（光伏、风电、锂电）

**主题体系**:
- 7 个主题（AI 投资、政策刺激、供应链、ESG、业绩、并购重组、价格变动）
- 每个主题有关联行业和关键词

**分类方法**:
- 标题权重更高（标题内容 ×3）
- 关键词匹配计分
- 置信度归一化到 [0,1]

### 3. 文档分类服务 (`core/services/document_classifier.py`)

提供完整的文档分类和分析功能：

**分类功能**:
- 行业分类（主行业 + 副行业）
- 主题标签
- 事件类型识别（业绩、政策、产品、并购、评级、价格、合同、高管）

**质量分析**:
- 来源可靠性等级（官方、研究机构、权威媒体、专业媒体、其他）
- 主观性等级（纯事实、事实为主、混合、观点为主、纯观点）
- 研究可用性评分（0-1）
- 内容质量评分（0-1）
- 事实/观点比例

**证据画像**:
- 是否有明确事实陈述
- 是否有明确观点
- 是否有数据点
- 是否有引述
- 是否有分析
- 证据质量综合评分（0-1）

### 4. 实体抽取服务 (`core/services/entity_extractor.py`)

实现了简化但稳定的实体抽取：

**支持的实体类型**:
- `stock_code`: 股票代码（如 600519.SH）
- `company`: 已知公司（如 Huawei, Tencent, Alibaba, Moutai, BYD）

**功能特性**:
- 上下文提取（实体前后 100 字符）
- 去重（同一文档同一实体只记录一次）
- 置信度打分

### 5. 摘要生成服务 (`core/services/summary_generator.py`)

提供规则化的摘要生成：

**生成类型**:
- 简短摘要（约 100 字符）
- 要点列表（3-5 个要点）
- 完整文档摘要对象

**功能特性**:
- 优先提取开头段落
- 识别关键信息（如业绩、增长率、政策等）
- 自动截断过长内容
- 无内容时返回默认提示

### 6. 文档富集流水线 (`core/services/document_enrichment.py`)

编排所有富集步骤的核心 Pipeline：

**EnrichmentConfig 配置**:
- `do_chunking`: 是否分块
- `do_classification`: 是否分类
- `do_entity_extraction`: 是否实体抽取
- `do_event_extraction`: 是否事件抽取
- `do_summary`: 是否摘要生成

**EnrichmentResult 结果**:
- 完整富集后的文档
- 分块列表
- 标签列表
- 摘要对象
- 实体列表
- 事件列表
- 成功标志和错误列表

**Pipeline 流程**:
1. 更新处理状态
2. 执行分块（如启用）
3. 执行分类、质量分析、证据画像（如启用）
4. 执行实体抽取（如启用）
5. 执行事件抽取（如启用，适配现有的 EventExtractor）
6. 执行摘要生成（如启用）
7. 更新最终状态

### 7. 单元测试 (`tests/unit/test_issue44.py`)

完整的测试覆盖，14 个测试全部通过：

- 文档分块测试 (4)
- 分类体系测试 (2)
- 文档分类测试 (2)
- 实体抽取测试 (2)
- 摘要生成测试 (2)
- 富集流水线测试 (2)

## 设计特点

### 1. 可配置的 Pipeline

每个富集步骤都可以独立开关：
```python
config = EnrichmentConfig(
    do_chunking=True,
    do_classification=True,
    do_entity_extraction=True,
    do_event_extraction=False,  # 可选跳过
    do_summary=True,
)
```

### 2. 与现有系统集成

- 完全复用 Issue #42 的契约（DocumentV1, DocumentChunkV1 等）
- 事件抽取适配现有的 EventExtractor
- 通过 taxonomy 服务与领域知识连接

### 3. 容错处理

每个富集步骤独立 try-catch：
- 单个步骤失败不影响其他步骤
- 错误收集到 EnrichmentResult
- 日志详细记录失败原因

### 4. 文档质量可评估

从多个维度评估文档：
- 来源可信度
- 主观性/客观性
- 研究可用性
- 内容质量
- 证据丰富度

## 文件变更清单

### 新增文件
1. `core/services/document_chunker.py`: 文档分块服务
2. `core/services/taxonomy_service.py`: 分类体系服务
3. `core/services/document_classifier.py`: 文档分类服务
4. `core/services/entity_extractor.py`: 实体抽取服务
5. `core/services/summary_generator.py`: 摘要生成服务
6. `core/services/document_enrichment.py`: 文档富集 Pipeline
7. `tests/unit/test_issue44.py`: 单元测试
8. `docs/ISSUE_44_IMPLEMENTATION_SUMMARY.md`: 本文档

### 修改文件
1. `core/services/__init__.py`: 导出新增服务

## 使用示例

### 基本使用 - DocumentEnrichmentPipeline

```python
from core.contracts import DocumentV1
from core.services.document_enrichment import DocumentEnrichmentPipeline, EnrichmentConfig

# 创建配置
config = EnrichmentConfig(
    do_chunking=True,
    do_classification=True,
    do_entity_extraction=True,
    do_event_extraction=False,
    do_summary=True,
)

# 创建 Pipeline
pipeline = DocumentEnrichmentPipeline(config=config)

# 创建测试文档
doc = DocumentV1(
    doc_id="test_doc_001",
    title="茅台 2024 Q1 业绩公告",
    content="""
    贵州茅台酒股份有限公司（600519.SH）今日发布 2024 年第一季度业绩公告。
    营收达 350 亿元，同比增长 18%。
    净利润 172 亿元，同比增长 19%。
    管理团队表示，将持续扩大电商渠道投入。
    分析师预测全年业绩将保持稳定增长。
    白酒行业整体呈现复苏态势。
    """,
)

# 执行富集
result = pipeline.enrich(doc, update_doc=True)

print(f"分块数: {len(result.chunks)}")
print(f"标签数: {len(result.tags)}")
print(f"实体数: {len(result.entities)}")
print(f"摘要: {result.summary.summary if result.summary else 'N/A'}")
print(f"成功: {result.success}")
```

### TaxonomyService 使用

```python
from core.services.taxonomy_service import TaxonomyService

taxonomy = TaxonomyService()

result = taxonomy.classify(
    text="贵州茅台发布 2024 年第一季度业绩公告，营收增长 18%。白酒行业持续复苏。",
    title="茅台 Q1 业绩"
)

print(f"主行业: {result.primary_industry}")
print(f"副行业: {result.secondary_industries}")
print(f"主题: {result.themes}")
print(f"置信度: {result.confidence_scores}")
```

### DocumentClassifier 使用

```python
from core.services.document_classifier import DocumentClassifier

classifier = DocumentClassifier()

classification, tags = classifier.classify(doc)
quality = classifier.analyze_quality(doc)
evidence = classifier.analyze_evidence(doc)

print(f"主行业: {classification.primary_industry}")
print(f"主题: {classification.topics}")
print(f"事件类型: {classification.event_types}")
print(f"标签数: {len(tags)}")
print(f"来源可靠性: {quality.source_reliability_level}")
print(f"主观性: {quality.subjectivity_level}")
print(f"证据质量: {evidence.evidence_quality_score}")
```

## 验收标准对照

Issue #44 的所有验收标准已达成：

- [x] **解析策略** - 支持多种文档类型和分块策略
- [x] **Chunk 策略** - 按段落/标题/发言人等多维度分块
- [x] **Taxonomy 设计** - 三级行业体系 + 主题体系
- [x] **分类流程** - 规则粗筛 + 关键词匹配 + 置信度打分
- [x] **实体识别** - 支持股票代码、公司等实体
- [x] **事件抽取** - 集成现有 EventExtractor
- [x] **摘要与质量层** - 质量分析、证据画像、摘要生成

## 下一步

- Issue #45: RAG 检索层设计
- Issue #46: 模板化研报生成
- Issue #47: 回测视角

## 总结

Issue #44 构建在 Issue #42 的基础上，提供了完整、生产可用的文档富集流水线。系统支持灵活的分块策略、可扩展的分类体系、多维度质量评估、实体抽取和摘要生成。通过统一的 Pipeline 编排，原始文档可以被自动处理成结构化、可检索、可用于研报生成的知识单元。配合已有的 Issue #43 采集功能，形成了从数据采集到知识加工的完整链路。
