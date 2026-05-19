# PDF Pipeline Gap Analysis — AF-AUTO-006-00

**Date:** 2026-05-18  
**Status:** Complete (Audit Done)

---

## 执行摘要

当前 PDF 管道**已有良好基础**：schema、repository、基本转换策略（raw_text, markitdown）都已实现。

**主要差距**：
1. 转换器在 `data_layer/crawlers/utils/` 而非独立的 `data_layer/converters/`
2. 缺少 Pydantic 契约 `core/contracts/pdf_conversion.py`
3. 缺少 MinerU 策略
4. 缺少 PDFConversionService 核心编排服务
5. 缺少与 DocumentV1/DocumentChunkV1 的集成
6. 缺少管理 API (POST convert, GET stats, POST retry)
7. 缺少 pyproject.toml optional dependencies
8. 缺少端到端集成测试

---

## 已实现部分 ✅

### 1. 数据库 Schema (models.py)
- `pdf_artifact_v1` (line 1330) — PDF 元数据表，含 file_path, file_hash, source_type, parse_status 等 ✅
- `pdf_conversion_v1` (line 1381) — 转换结果表，含 conversion_strategy, markdown_path, quality_score, status 等 ✅
- Migration: `storage/migrations/versions/002_pdf_crawl_state_schema.py` ✅

### 2. Repository (pdf_artifact_repository.py)
- `add_pdf_artifact()`, `get_pdf_by_id()`, `get_pdf_by_doc_id()`, `get_pdf_by_hash()`, `get_pdfs_by_source()` ✅
- `add_conversion()`, `update_conversion_status()`, `get_conversion_stats()`, `get_pending_conversions()` ✅
- **缺失**: 批量操作、按 PDF 列出转换、获取失败转换供重试

### 3. PDF 转换策略 (crawlers/utils/pdf_converter.py)
- `PDFConversionStrategy` ABC — `is_available()`, `convert()`, `get_name()` ✅
- `PDFConversionResult` dataclass（非 Pydantic）✅
- `RawTextStrategy` — 基于 pdfplumber，总是可用 ✅
- `MarkItDownStrategy` — 基于 markitdown，有回退到 raw_text ✅
- `PDFConverter` 策略注册表，自动选择: markitdown → raw_text ✅
- **注意**: `data_layer/crawlers/zq/zhiqiu/processors/report_processor.py` 使用了 `enable_pdf_conversion` 参数引用了此模块

### 4. API Models (app/api/models.py)
- `PDFStats` (line 224) — 用于摄入概览 ✅
- `PDFArtifactResponse` (line 266) — PDF 列表响应 ✅

### 5. API Endpoints (app/api/routes/monitoring.py)
- `GET /ingest/status` — 包含 PDF 统计 ✅
- `GET /ingest/pdfs` — PDF 制品列表 ✅

### 6. DocumentV1 / DocumentChunkV1
- `DocumentV1DB` (models.py:729) — 含 doc_metadata JSON 字段 ✅
- `DocumentChunkV1DB` (models.py:860) — 含 chunk_metadata JSON 字段 ✅
- `core/contracts/documents_v1.py` — Pydantic 契约 ✅

### 7. 依赖
- `pdfplumber>=0.10.0` 已在 pyproject.toml ✅

### 8. 测试
- Repository 测试已存在 ✅

---

## 缺失部分 ❌

### 1. Pydantic 契约 (af-auto-006-01)
- 无 `core/contracts/pdf_conversion.py`
- `PDFConversionResult` 是 dataclass，非 Pydantic model
- 无策略类型枚举 (StrategyType)
- 无转换状态枚举 (ConversionStatus)

### 2. 转换器目录结构 (af-auto-006-01/02/03/04)
- 无 `data_layer/converters/` 目录
- 转换器在 `data_layer/crawlers/utils/pdf_converter.py`（位置不当）
- 无 MinerUStrategy

### 3. PDFConversionService (af-auto-006-05)
- 无核心编排服务
- 状态流转未标准化

### 4. 输出持久化 (af-auto-006-06)
- 目录结构未正式定义
- 文件命名约定不一致

### 5. DocumentV1 集成 (af-auto-006-07)
- 转换成功后无 DocumentV1DB 创建
- 转换成功后无 DocumentChunkV1DB 创建
- 无 pdf_id/conversion_id 写入 doc_metadata

### 6. Admin API (af-auto-006-08)
- 无 POST /api/admin/pdf/convert
- 无 GET /api/admin/pdf/stats (独立端点)
- 无 GET /api/admin/pdf/pending
- 无 POST /api/admin/pdf/retry

### 7. pyproject.toml (af-auto-006-01a)
- 无 `[pdf]` optional dependency group (markitdown)
- 无 `[pdf-full]` optional dependency group (mineru)

### 8. 集成测试 (af-auto-006-09)
- 无真实 PDF fixture
- 无端到端测试

### 9. 文档 (af-auto-006-10)
- 无 `docs/modules/pdf_conversion_pipeline.md`
- ARCHITECTURE.md 未包含 PDF 流
- DATA_SOURCES.md / REFERENCE.md / CHANGELOG.md 未更新

---

## 实施路径

按任务依赖顺序：

1. **af-auto-006-01a** → pyproject.toml optional deps
2. **af-auto-006-01** → Pydantic 契约 + 策略基类重构到 `data_layer/converters/`
3. **af-auto-006-02** → RawTextStrategy 增强（无需新依赖）
4. **af-auto-006-03** → MarkItDownStrategy 增强（可与 02 并行）
5. **af-auto-006-04** → MinerUStrategy 新增（可与 02/03 并行）
6. **af-auto-006-05** → PDFConversionService（依赖 02+03）
7. **af-auto-006-06** → 输出持久化
8. **af-auto-006-07** → DocumentV1/DocumentChunkV1 集成
9. **af-auto-006-08** → Admin API
10. **af-auto-006-09** → 集成测试
11. **af-auto-006-10** → 文档更新

---

## 文件创建/修改清单

**新建文件：**
- `data_layer/converters/__init__.py`
- `data_layer/converters/base.py`
- `data_layer/converters/raw_text.py`
- `data_layer/converters/markitdown.py`
- `data_layer/converters/mineru.py`
- `core/contracts/pdf_conversion.py`
- `core/services/pdf_conversion_service.py`
- `app/api/routes/pdf_admin.py`
- `tests/unit/data_layer/converters/test_*.py`
- `tests/unit/core/services/test_pdf_conversion_service.py`
- `tests/integration/test_pdf_conversion_integration.py`
- `tests/fixtures/sample.pdf`
- `docs/modules/pdf_conversion_pipeline.md`

**修改文件：**
- `pyproject.toml`
- `core/contracts/__init__.py`
- `data_layer/repositories/__init__.py`
- `data_layer/repositories/pdf_artifact_repository.py`
- `app/api/models.py`
- `app/api/routes/monitoring.py` 或新建 admin 路由
- `data_layer/crawlers/utils/__init__.py`（保持向后兼容）
- `data_layer/crawlers/zq/zhiqiu/processors/report_processor.py`（更新导入）
- `docs/ARCHITECTURE.md`, `docs/DATA_SOURCES.md`, `docs/REFERENCE.md`, `docs/CHANGELOG.md`, `README.md`