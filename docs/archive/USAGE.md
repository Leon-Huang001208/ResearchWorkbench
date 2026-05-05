
# AlphaFoundry 使用说明

## 目录
1. [项目概述](#项目概述)
2. [目录结构](#目录结构)
3. [快速开始](#快速开始)
4. [CLI 命令](#cli-命令)
5. [Python API](#python-api)
6. [信号实验室](#信号实验室)
7. [常见问题](#常见问题)

---

## 项目概述

AlphaFoundry 是一个**本地优先、可企业化的买方投研情报系统**，专为基金研究员设计。

### 核心特性
- **资产分析卡**：标准化资产快照，覆盖8大维度
- **专题研究备忘录**：围绕主题的结构化研究
- **多情景市场分析**：不确定性问题的多情景分析
- **候选信号与回测**：研究 → 信号 → 回测的完整工作流

---

## 目录结构

```
AlphaFoundry/
├── app/                    # 应用层
│   ├── api/                # FastAPI 接口（待完善）
│   ├── cli/                # 命令行工具
│   └── web/                # Web 工作台（待完善）
├── core/                   # 核心层
│   ├── contracts/          # Pydantic 数据契约
│   ├── interfaces/         # 核心接口定义
│   ├── model_gateway/      # 模型网关
│   ├── observability/      # 可观测性（日志、指标、追踪）
│   ├── services/           # 业务服务
│   └── settings/           # 配置管理
├── data_layer/             # 数据层
│   ├── adapters/           # 数据适配器
│   ├── parsers/            # 解析器
│   ├── normalizers/        # 标准化器
│   └── repositories/       # 仓储实现
├── knowledge_layer/        # 知识层
│   ├── entity_resolution/  # 实体解析
│   ├── assertions/         # 断言提取
│   ├── events/             # 事件提取
│   └── retrieval/          # 向量检索
├── reasoning/              # 推理层
│   ├── router/             # 任务路由
│   ├── evidence/           # 证据收集
│   ├── scenarios/          # 情景生成
│   ├── skeptic/            # 怀疑者审查
│   └── traces/             # 推理追踪
├── reporting/              # 报告层
│   ├── composer/           # 报告合成
│   ├── templates/          # 报告模板
│   └── projections/        # 输出投影（Markdown、Word）
├── signal_lab/             # 信号实验室
│   ├── features/           # 特征工程
│   ├── labels/             # 标签生成
│   ├── scoring/            # 信号评分
│   └── backtests/          # 回测引擎
├── storage/                # 存储层
│   ├── migrations/         # Alembic 迁移
│   └── schema.sql          # 数据库 Schema
├── tests/                  # 测试
│   ├── unit/               # 单元测试
│   └── integration/        # 集成测试
├── examples/               # 示例代码
│   ├── test_simple.py      # 基础功能测试
│   ├── test_signal_lab_simple.py  # 信号实验室测试
│   └── signal_lab_demo.py  # 信号实验室完整演示
├── docs/                   # 文档
├── data/                   # 数据目录
├── logs/                   # 日志目录
├── pyproject.toml          # 项目配置
└── README.md               # 项目说明
```

---

## 快速开始

### 前置要求
- Python 3.11+
- pip 包管理器

### 安装步骤

1. **进入项目目录**
```bash
cd ~/Desktop/Projects/AlphaFoundry
```

2. **（可选）创建虚拟环境**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
```

3. **安装依赖**
```bash
pip install -e ".[dev]"
```

### 配置

1. **复制环境变量模板**
```bash
cp .env.example .env
```

2. **（可选）编辑 .env 配置数据库和模型**

### 运行示例

#### 1. 基础功能测试
```bash
python examples/test_simple.py
```

#### 2. 信号实验室测试
```bash
python examples/test_signal_lab_simple.py
```

---

## CLI 命令

AlphaFoundry 提供了 `af` 命令行工具，支持以下命令：

### 1. analyze - 资产分析
生成资产分析快照。

```bash
# 基本用法
af analyze --asset 600000.SH

# 输出报告
af analyze --asset 600000.SH --output report.md
af analyze --asset 600000.SH --output report.docx
```

### 2. scenario - 情景分析
生成多情景分析报告。

```bash
# 基本用法
af scenario --topic "人工智能产业发展对股票市场的影响"

# 输出到文件
af scenario --topic "美联储政策走向" --output scenario.md
```

### 3. ingest - 文档摄入
摄入文档并提取断言和事件。

```bash
af ingest --file report.pdf --source-type report --source-name "券商研报"
```

### 4. review - 审核管理
管理审核队列。

```bash
# 列出待审核项目
af review list

# 批准断言
af review approve assertion_1234

# 查看统计
af review stats
```

### 5. signal - 信号管理
管理投资信号。

```bash
# 创建信号
af signal create --subject 600519.SH --thesis "看好白酒股" --score 0.8

# 列出信号
af signal list
```

### 6. backtest - 回测
运行信号回测。

```bash
# 使用示例数据回测
af backtest --symbol 600519.SH --initial-capital 1000000
```

---

## Python API

### 资产分析服务
```python
from datetime import datetime, UTC
from core.services import AssetAnalysisService
from data_layer.repositories import AssetSnapshotRepositoryImpl
from data_layer.repositories.base import get_db

with get_db() as db:
    repo = AssetSnapshotRepositoryImpl(db)
    service = AssetAnalysisService(repo, use_mock=True)
    snapshot = service.generate_snapshot("600000.SH", datetime.now(UTC))
    print(f"PE TTM: {snapshot.valuation.get('pe_ttm')}")
```

### 情景服务
```python
from core.services import ScenarioService
service = ScenarioService()
scenario_set = service.generate_scenario_set("人工智能产业发展")
```

### 信号服务
```python
from core.services import SignalService
service = SignalService()

# 创建信号
signal = service.create_signal(
    subject_id="600519.SH",
    thesis="白酒行业景气度回升",
    horizon="20d",
    score=0.8,
    confidence=0.7,
)

# 生成交易候选
candidate = service.generate_trade_candidate(signal)
```

---

## 信号实验室

信号实验室是 AlphaFoundry 的核心模块，支持特征工程、标签生成、信号评分和回测。

### 1. 特征工程
```python
import pandas as pd
from signal_lab.features import FeatureBuilder
from signal_lab.features.groups import PriceVolumeFeatures, ValuationFeatures

# 创建特征构建器
builder = FeatureBuilder()
builder.add_group(PriceVolumeFeatures())
builder.add_group(ValuationFeatures())

# 计算特征（假设 prices 是包含价格数据的 DataFrame）
features = builder.compute_features(prices)
```

### 2. 标签生成
```python
from signal_lab.labels import RelativeReturnLabeler

labeler = RelativeReturnLabeler(horizon=20, forward=True)
labels = labeler.compute(prices)
```

### 3. 信号评分
```python
from core.services import SignalService
from signal_lab.scoring import SignalRanker

service = SignalService()
ranker = SignalRanker()

# 创建信号
signal = service.create_signal("600519.SH", "看好白酒股", "20d", 0.8, 0.7)

# 排名
ranked = ranker.rank([signal])
```

### 4. 回测
```python
from signal_lab.backtests import SimpleBacktester

backtester = SimpleBacktester(initial_capital=1000000)
result = backtester.run(prices, [signal])

print(f"总收益率: {result.total_return:.2%}")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
```

---

## 常见问题

### Q: 如何运行完整演示？
```bash
python examples/signal_lab_demo.py
```

### Q: 如何运行测试？
```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/
```

### Q: 必须使用数据库吗？
不需要！默认使用模拟模式，无需配置数据库。

### Q: 支持哪些输出格式？
- Markdown (.md)
- Word (.docx)

---

## 下一步
- 查看 [README.md](../README.md) 了解项目概述
- 阅读 [QUICKSTART.md](./QUICKSTART.md) 详细入门
- 参考 [CLI_GUIDE.md](./CLI_GUIDE.md) 完整 CLI 文档
- 探索 `examples/` 目录下的示例代码
