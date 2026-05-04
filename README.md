# AlphaFoundry

本地优先、可企业化的买方投研情报系统。

## 概述

AlphaFoundry 是一个面向基金研究员工作流的 AI 产业情报与 Alpha 发现系统。系统采用模块化单体架构，使用 PostgreSQL + pgvector 作为核心事实存储，Markdown/Wiki 仅作为人类可读的投影层。

## 核心特性

- **资产分析卡**：对股票、ETF、指数、商品、外汇、债券、基金等资产形成标准化快照，覆盖财务、资金、量价、估值、股东、产业、事件、宏观八大维度
- **专题研究备忘录**：围绕产业链、政策变化、地缘冲突、供需错配、AI compute 等主题形成结构化研究
- **多情景市场分析报告**：对不确定性问题输出 3-4 个情景，每个情景包含概率、关键假设、触发条件、失效信号
- **候选信号与回测说明**：将研究观察转为 thesis，再转为 scored signal

## 快速开始

### 前置要求

- Python 3.11+
- PostgreSQL 15+ (可选，用于完整功能)
- pgvector 扩展 (可选)

### 安装

```bash
# 克隆项目
cd AlphaFoundry

# 安装依赖
pip install -e ".[dev]"
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，配置数据库和模型提供商
```

### 数据库初始化 (可选)

```bash
cd storage/migrations
alembic upgrade head
```

### 使用 CLI 生成资产分析

```bash
# 使用模拟数据生成资产分析
af analyze --asset 600000.SH

# 生成并保存为 Markdown 报告
af analyze --asset 600000.SH --output report.md

# 生成并保存为 Word 文档
af analyze --asset 600000.SH --output report.docx
```

### 使用 CLI 生成多情景分析

```bash
# 生成专题研究报告
af scenario --topic "人工智能产业发展对股票市场的影响"

# 生成并保存为 Markdown 报告
af scenario --topic "美联储政策走向" --output scenario.md
```

### 使用 CLI 摄入文档

```bash
# 摄入一个文档并提取断言和事件
af ingest --file report.pdf --source-type report --source-name "券商研报"
```

### 使用 CLI 管理审核队列

```bash
# 列出待审核的项目
af review list

# 批准一个断言
af review approve <assertion_id>

# 拒绝一个断言
af review reject <assertion_id>

# 查看审核统计
af review stats
```

### 使用 CLI 管理信号

```bash
# 创建信号
af signal create --subject 600519.SH --thesis "看好白酒股" --score 0.8 --confidence 0.7

# 列出信号
af signal list

# 验证信号
af signal validate --id <signal_id>

# 升级信号状态
af signal promote --id <signal_id> --status candidate

# 生成交易候选
af signal candidate --id <signal_id>
```

### 使用 CLI 运行回测

```bash
# 使用示例数据运行回测
af backtest --symbol 600519.SH --initial-capital 1000000

# 从文件加载数据运行回测
af backtest --file prices.csv --position-size 0.2 --output result.json
```

### 运行完整演示

```bash
# 运行完整功能演示
python examples/demo_all_features.py

# 运行简单测试
python examples/test_simple.py
```

### 使用 Python API

```python
from datetime import datetime, UTC
from core.services import AssetAnalysisService, SignalService
from data_layer.repositories import AssetSnapshotRepositoryImpl
from data_layer.repositories.base import get_db

# 使用模拟数据生成快照
with get_db() as db:
    repo = AssetSnapshotRepositoryImpl(db)
    service = AssetAnalysisService(repo, use_mock=True)

    snapshot = service.generate_snapshot(
        canonical_id="600000.SH",
        as_of=datetime.now(UTC),
    )

    print(f"PE TTM: {snapshot.valuation.get('pe_ttm')}")
    print(f"Close Price: {snapshot.price_volume.get('close_price')}")
```

### 使用 Signal Lab API

```python
import pandas as pd
import numpy as np
from core.services import SignalService
from signal_lab.features import FeatureBuilder
from signal_lab.features.groups import PriceVolumeFeatures, ValuationFeatures
from signal_lab.labels import RelativeReturnLabeler
from signal_lab.backtests import SimpleBacktester

# 创建信号服务
signal_service = SignalService()

# 创建信号
signal = signal_service.create_signal(
    subject_id="600519.SH",
    thesis="白酒行业景气度回升",
    horizon="20d",
    score=0.8,
    confidence=0.7,
)

# 验证信号
validation = signal_service.validate_signal(signal)

# 生成交易候选
candidate = signal_service.generate_trade_candidate(signal)

# 运行回测
backtester = SimpleBacktester()
result = backtester.run(prices, [signal])
print(f"Total Return: {result.total_return:.2%}")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
```

## 项目结构

```
AlphaFoundry/
├── app/
│   ├── api/              # FastAPI 接口 (待实现)
│   ├── cli/              # 命令行工具
│   └── web/              # Web 界面 (待实现)
├── core/
│   ├── contracts/        # Pydantic 数据契约
│   ├── interfaces/       # 核心接口定义
│   ├── model_gateway/    # 模型网关
│   ├── observability/    # 可观测性（日志、指标、追踪）
│   ├── services/         # 业务服务
│   └── settings/        # 配置管理
├── data_layer/
│   ├── adapters/         # 数据适配器
│   ├── parsers/          # 解析器
│   ├── normalizers/      # 标准化器
│   └── repositories/     # 仓储实现
├── knowledge_layer/      # 知识层
│   ├── entity_resolution/  # 实体解析
│   ├── assertions/         # 断言提取与验证
│   ├── events/            # 事件提取
│   └── retrieval/         # 向量检索
├── reasoning/            # 推理引擎
│   ├── router/           # 任务路由
│   ├── evidence/         # 证据收集
│   ├── scenarios/        # 情景生成与校准
│   ├── skeptic/          # 反证审查
│   ├── traces/           # 推理追踪
│   ├── state.py          # 状态定义
│   └── graph.py          # LangGraph 状态机
├── reporting/
│   ├── composer/         # 报告合成
│   ├── templates/        # 报告模板
│   └── projections/      # 输出投影 (Markdown, Word)
├── signal_lab/           # 信号实验室
│   ├── features/         # 特征工程
│   │   ├── groups/      # 特征组（价量、估值、财务等）
│   │   ├── base.py      # 特征基类
│   │   └── builder.py   # 特征构建器
│   ├── labels/          # 标签生成
│   │   ├── base.py      # 标签基类
│   │   ├── relative_return.py  # 相对收益标签
│   │   └── event_driven.py     # 事件驱动标签
│   ├── scoring/         # 信号评分
│   │   ├── scorer.py    # 评分器
│   │   └── ranker.py    # 排名器
│   └── backtests/       # 回测引擎
│       ├── base.py      # 回测基类
│       └── simple.py    # 简单回测器
├── storage/
│   ├── migrations/       # Alembic 数据库迁移
│   └── schema.sql       # 数据库 Schema
├── tests/
│   └── unit/            # 单元测试
├── docs/                # 文档
├── examples/            # 示例代码
├── data/                # 数据目录
│   └── samples/         # 示例数据
└── logs/                # 日志目录
```

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 语言 | Python 3.11+ |
| 数据验证 | Pydantic v2 |
| Web框架 | FastAPI |
| 数据库 | PostgreSQL 15+ |
| 向量扩展 | pgvector |
| ORM | SQLAlchemy 2.0 |
| 迁移 | Alembic |
| CLI | Click |
| 状态机 | LangGraph |
| 回测 | vectorbt, Backtrader |
| 日志 | structlog |

## 开发指南

### 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 显示覆盖率
pytest --cov=core --cov=data_layer --cov=reporting
```

### 代码格式化

```bash
black .
isort .
ruff check .
```

### 类型检查

```bash
mypy core/ data_layer/ reporting/ app/
```

## 实施进度

### 第 1 个月（5月）：事实层与报告骨架

- ✅ 项目基础配置与目录结构
- ✅ Core Contracts（Pydantic 数据契约）
- ✅ Core Interfaces（核心接口定义）
- ✅ Storage Schema（PostgreSQL + pgvector）
- ✅ Model Gateway（模型网关）
- ✅ Observability（日志、metrics、trace）
- ✅ Data Layer 基础适配器
- ✅ Report Composer v1（模板段落生成）
- ✅ Asset Analysis Card（资产分析快照）
- ✅ CLI 命令工具

### 第 2 个月（6月）：事件、断言与多情景

- ✅ Knowledge Layer（实体解析、断言、事件）
- ✅ Event/Assertion extraction 闭环
- ✅ Reasoning Engine（LangGraph 状态机）
- ✅ Scenario Engine（情景生成）
- ✅ Reasoning Trace 记录与回放
- ✅ 审核队列

### 第 3 个月（7月）：信号验证与团队工作台

- ✅ Signal Lab（FeatureBuilder、Labeler）
- ✅ 信号评分与排名（Scoring、Ranking）
- ✅ 回测引擎（Simple Backtester，vectorbt 集成基础）
- ✅ 信号服务（SignalService）
- ✅ SignalValidator 接口实现
- ✅ CLI 信号与回测命令
- ✅ 完整信号工作流演示
- ⬜ Web Workbench v1

## 设计原则

1. **本地优先**：数据本地处理，保证数据安全
2. **模块化单体**：清晰的模块边界，可替换基础设施
3. **事实层**：PostgreSQL 作为单一事实源
4. **接口隔离**：数据源、模型后端、向量库等都通过接口隔离
5. **可审计**：所有操作都可追溯，支持审核流程

## 文档

- [快速开始指南](docs/QUICKSTART.md) - 更详细的入门指导
- [CLI 使用指南](docs/CLI_GUIDE.md) - 命令行工具完整说明
- [API 文档](docs/API.md) - Python API 使用说明

## 许可证

本项目用于研究用途。
