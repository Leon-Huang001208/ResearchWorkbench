# Module: PDF Conversion Pipeline

## Responsibility

PDF 到 Markdown/文本的完整转换管道。支持多策略自动降级、磁盘持久化、以及自动创建 DocumentV1 和分块。

## Architecture

```
ZQ Crawler (ReportProcessor._download_and_record_pdf)
    │
    ├── 下载 PDF 到磁盘 (data/crawlers/zq/pdfs/)
    ├── 保存 JSON 元数据
    └── 注册 PDFArtifactV1DB (parse_status=pending)  ← NEW
        │
        ▼
CrawlScheduler (每 5 分钟)  ← NEW
    │
    ▼
PDFConversionService (services/pdf_conversion_service.py)
    │
    ├── 策略选择 (mineru → markitdown → raw_text)
    │
    ├── 执行转换 (ingestion/converters/)
    │   ├── MinerUStrategy     (mineru.py)  - opendatalab/mineru
    │   ├── MarkItDownStrategy (markitdown.py) - microsoft/markitdown
    │   └── RawTextStrategy    (raw_text.py) - pdfplumber (always available)
    │
    ├── 磁盘持久化 (ingestion/converters/persistence.py)
    │   ├── data/markdown/{pdf_id}.md
    │   └── data/raw_text/{pdf_id}.txt
    │
    ├── 状态更新 (pdf_conversion_v1 + pdf_artifact_v1.parse_status)
    │
    └── DocumentV1 创建 (自动)
        ├── DocumentV1 (document_v1)
        ├── DocumentChunkV1 (document_chunk_v1)
        └── 入队 IngestionBridge → KnowledgePipeline (LLM 提取)  ← NEW
```

## Strategy Priority

| 优先级 | 策略 | 质量 | 依赖 | 描述 |
|--------|------|------|------|------|
| 1 (最高) | MinerU | 最高 | `mineru[all]` + `magic-pdf` CLI | opendatalab/mineru, 保留表格结构和文档布局 |
| 2 | MarkItDown | 高 | `markitdown[pdf]` | microsoft/markitdown, Markdown 转换 + 特征检测 |
| 3 (始终可用) | Raw Text | 基线 | `pdfplumber` | 纯文本提取, `<!-- page: N -->` 页面标记 |

策略选择逻辑：
- 指定 `preferred_strategy` 时优先使用指定策略
- 指定策略不可用时按优先级自动降级
- `StrategyType.AUTO` (默认) 自动选择最高可用策略

## Key Files

| 文件 | 职责 |
|------|------|
| `core/contracts/pdf_conversion.py` | Pydantic 契约: ConversionResult, StrategyType, ConversionStatus |
| `ingestion/converters/base.py` | PDFConversionStrategy 抽象基类 |
| `ingestion/converters/raw_text.py` | RawTextStrategy (pdfplumber) |
| `ingestion/converters/markitdown.py` | MarkItDownStrategy (microsoft/markitdown) |
| `ingestion/converters/mineru.py` | MinerUStrategy (opendatalab/mineru) |
| `ingestion/converters/persistence.py` | 磁盘持久化工具 |
| `services/pdf_conversion_service.py` | PDFConversionService 核心编排 |
| `services/document_chunker.py` | DocumentChunker 分块器 |
| `app/api/routes/pdf_admin.py` | Admin API 路由 |
| `data_layer/repositories/pdf_artifact_repository.py` | PDF artifact CRUD |
| `data_layer/repositories/documents_v1.py` | DocumentV1 + ChunkV1 CRUD |
| `data_layer/repositories/models.py` | ORM: PDFArtifactV1DB, PDFConversionV1DB, DocumentV1DB, DocumentChunkV1DB |

## Admin API

| 方法 | 路由 | 描述 |
|------|------|------|
| POST | `/api/admin/pdf/convert` | 触发指定 PDF 转换 |
| GET | `/api/admin/pdf/stats` | 获取转换统计 |
| GET | `/api/admin/pdf/pending` | 列出待转换的 PDF |
| POST | `/api/admin/pdf/retry` | 重试失败的转换 |

## Installation

```bash
# 基础安装 (pdfplumber only, always works)
pip install -e .

# 安装 MarkItDown 支持
pip install -e ".[pdf]"

# 安装完整 PDF 转换支持 (包括 MinerU)
pip install -e ".[pdf-full]"
```

## Quality Scoring

每个策略实现 `_compute_quality_score()` 启发式评分:

- **MinerU**: 基准 0.7 + 表格(+0.15) + 图片(+0.05) + 标题层级(+0.10)
- **MarkItDown**: 基准 0.6 + 表格(+0.10) + 图片(+0.05) + 标题层级(+0.15) + 代码块(+0.05)
- **Raw Text**: 基于平均字符/页 + 结构化标记

所有评分限制在 `[0.0, 1.0]` 范围内。

## Data Flow

1. PDF 下载后存入 `data/objects/`，创建 `pdf_artifact_v1` 记录 (parse_status=pending)
2. `PDFConversionService.convert_pdf()` 被调用
3. 根据优先级选择可用策略
4. 策略执行转换，返回 `ConversionResult`
5. Markdown/raw_text 持久化到 `data/markdown/` 和 `data/raw_text/`
6. 小文件内联到数据库 (threshold=256KB)
7. 更新 `pdf_conversion_v1` 和 `pdf_artifact_v1.parse_status`
8. 自动创建 `DocumentV1` 和分块 `DocumentChunkV1` (可通过 `create_document=False` 禁用)
9. 内容哈希去重防止重复创建

## References

- MinerU: https://github.com/opendatalab/MinerU
- MarkItDown: https://github.com/microsoft/markitdown
- pdfplumber: https://github.com/jsvine/pdfplumber