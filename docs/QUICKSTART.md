# 快速开始指南

本指南将帮助您快速上手 AlphaFoundry。

## 目录

- [安装](#安装)
- [配置](#配置)
- [第一个资产分析](#第一个资产分析)
- [生成报告](#生成报告)

## 安装

### 前置要求

- Python 3.11 或更高版本
- pip 包管理器

### 安装步骤

1. **克隆或进入项目目录**

```bash
cd AlphaFoundry
```

2. **创建虚拟环境（推荐）**

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

3. **安装依赖**

```bash
pip install -e ".[dev]"
```

这将安装：
- 核心运行时依赖
- 开发工具 (pytest, black, isort, mypy, ruff)
- 文档和报告功能 (python-docx)

## 配置

### 环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，根据您的需求配置：

```env
# 数据库（可选，模拟模式不需要）
DATABASE_URL=postgresql://user:password@localhost:5432/alphafoundry

# 模型网关（可选，报告生成使用）
MODEL_PROVIDER=openai_compatible
OPENAI_API_KEY=your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# 日志
LOG_LEVEL=INFO
LOG_DIR=./logs
```

### 数据库设置（可选）

如果您想使用真实的数据库存储：

1. 安装 PostgreSQL 15+
2. 安装 pgvector 扩展
3. 创建数据库
4. 运行迁移：

```bash
cd storage/migrations
alembic upgrade head
```

## 第一个资产分析

### 使用 CLI

最简单的方式是使用 CLI 命令：

```bash
# 使用模拟数据分析一支股票
af analyze --asset 600000.SH
```

这将：
- 生成资产分析快照
- 显示估值、价格等关键指标
- 使用模拟数据（无需外部数据源）

### 使用 Python API

您也可以直接使用 Python API：

```python
from datetime import datetime, UTC
from core.services import AssetAnalysisService
from data_layer.repositories import AssetSnapshotRepositoryImpl
from data_layer.repositories.base import get_db

# 创建服务实例
with get_db() as db:
    repo = AssetSnapshotRepositoryImpl(db)
    service = AssetAnalysisService(repo, use_mock=True)

    # 生成快照
    snapshot = service.generate_snapshot(
        canonical_id="600000.SH",
        as_of=datetime.now(UTC),
    )

    # 访问数据
    print(f"资产代码: {snapshot.canonical_id}")
    print(f"估值 - PE TTM: {snapshot.valuation.get('pe_ttm')}")
    print(f"价格 - 收盘价: {snapshot.price_volume.get('close_price')}")
    print(f"财务 - 净利润 YoY: {snapshot.financial.get('net_profit', {}).get('yoy')}")
```

## 生成报告

### Markdown 报告

```bash
af analyze --asset 600000.SH --output analysis.md
```

### Word 文档

```bash
af analyze --asset 600000.SH --output analysis.docx
```

### 自定义报告（Python API）

```python
from reporting.projections import MarkdownProjection
from core.contracts import SectionOutput

# 创建章节
sections = [
    SectionOutput(
        key="summary",
        content="# 600000.SH 分析摘要\n\n这是一个示例摘要...",
        evidence_refs=["doc1"],
        warnings=[],
    ),
]

# 渲染并保存
projection = MarkdownProjection()
projection.save("report.md", "资产分析报告", sections)
```

## 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/unit/test_asset_analysis_service.py

# 查看覆盖率
pytest --cov=core --cov=data_layer --cov-report=html
```

## 下一步

- 阅读 [CLI 使用指南](CLI_GUIDE.md) 了解更多命令
- 查看 [API 文档](API.md) 了解 Python API
- 探索代码示例在 `examples/` 目录
