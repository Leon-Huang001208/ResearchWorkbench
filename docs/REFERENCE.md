
# AlphaFoundry 参考手册

## 目录
1. [CLI 命令](#cli-命令)
2. [Python API](#python-api)
3. [信号实验室](#信号实验室)
4. [项目结构详解](#项目结构详解)
5. [常见问题](#常见问题)

---

## CLI 命令

### 1. analyze - 资产分析
生成资产分析快照。

#### 基本用法
```bash
af analyze --asset &lt;资产代码&gt;
```

#### 参数说明
| 参数 | 必需 | 说明 |
|------|------|------|
| `--asset` | ✅ | 资产代码，例如：600000.SH, 000001.SZ |
| `--output`, `-o` | ❌ | 输出文件路径，支持 .md 和 .docx |
| `--as-of` | ❌ | 指定快照时间，ISO 格式，例如：2026-05-03 |
| `--use-mock` / `--no-mock` | ❌ | 是否使用模拟数据，默认 `--use-mock` |

#### 使用示例
```bash
# 基本分析
af analyze --asset 600000.SH

# 输出报告
af analyze --asset 600000.SH --output report.md
af analyze --asset 600000.SH --output report.docx
```

---

### 2. scenario - 情景分析
生成多情景分析报告。

#### 基本用法
```bash
af scenario --topic &lt;研究主题&gt;
```

#### 参数说明
| 参数 | 必需 | 说明 |
|------|------|------|
| `--topic`, `-t` | ✅ | 研究主题，例如："人工智能产业发展" |
| `--output`, `-o` | ❌ | 输出文件路径，支持 .md |
| `--subject`, `-s` | ❌ | 主题 ID，可多次指定 |

#### 使用示例
```bash
af scenario --topic "人工智能产业发展对股票市场的影响"
af scenario --topic "美联储政策走向" --output scenario.md
```

---

### 3. ingest - 文档摄入
摄入文档并提取断言和事件。

#### 基本用法
```bash
af ingest --file &lt;文件路径&gt;
```

#### 参数说明
| 参数 | 必需 | 说明 |
|------|------|------|
| `--file`, `-f` | ✅ | 输入文件路径，支持 .pdf, .txt, .md |
| `--source-type`, `-t` | ❌ | 来源类型：report, news, filing, note |
| `--source-name`, `-s` | ❌ | 来源名称，例如："券商研报" |
| `--title` | ❌ | 文档标题 |

#### 使用示例
```bash
af ingest --file report.pdf --source-type report --source-name "券商研报"
```

---

### 4. review - 审核管理
管理审核队列。

#### 子命令
- `review list` - 列出待审核项目
- `review approve &lt;id&gt;` - 批准断言
- `review reject &lt;id&gt;` - 拒绝断言
- `review stats` - 查看审核统计

#### 使用示例
```bash
af review list
af review approve assertion_1234 --reviewer "研究员A"
af review stats
```

---

### 5. signal - 信号管理
管理投资信号。

#### 子命令
- `signal create` - 创建信号
- `signal list` - 列出信号
- `signal validate` - 验证信号
- `signal promote` - 升级信号状态
- `signal candidate` - 生成交易候选

---

### 6. backtest - 回测
运行信号回测。

#### 基本用法
```bash
af backtest --symbol 600519.SH --initial-capital 1000000
```

---

## Python API

### 1. 资产分析服务
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
    print(f"收盘价: {snapshot.price_volume.get('close_price')}")
```

---

### 2. 情景服务
```python
from core.services import ScenarioService

service = ScenarioService()
scenario_set = service.generate_scenario_set("人工智能产业发展对股票市场的影响")
```

---

### 3. 信号服务
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

### 1. 特征工程
```python
import pandas as pd
from signal_lab.features import FeatureBuilder
from signal_lab.features.groups import PriceVolumeFeatures, ValuationFeatures

# 创建特征构建器
builder = FeatureBuilder()
builder.add_group(PriceVolumeFeatures())
builder.add_group(ValuationFeatures())

# 计算特征
features = builder.compute_features(prices)

print(f"总特征数: {len(builder.get_all_feature_names())}")
```

---

### 2. 标签生成
```python
from signal_lab.labels import RelativeReturnLabeler

labeler = RelativeReturnLabeler(horizon=20, forward=True)
labels = labeler.compute(prices)

print(f"标签数: {len(labels.dropna())}")
```

---

### 3. 信号评分与排名
```python
from core.services import SignalService
from signal_lab.scoring import SignalRanker

service = SignalService()
ranker = SignalRanker()

# 创建信号
signal1 = service.create_signal("600519.SH", "看好白酒股", "20d", 0.8, 0.7)
signal2 = service.create_signal("000001.SZ", "银行估值修复", "60d", 0.6, 0.5)

# 排名
ranked = ranker.rank([signal1, signal2])
for signal, score, rank in ranked:
    print(f"{rank}. {signal.subject_id} - 评分: {score:.3f}")
```

---

### 4. 回测
```python
from signal_lab.backtests import SimpleBacktester

backtester = SimpleBacktester(initial_capital=1000000)
result = backtester.run(prices, [signal])

print(f"总收益率: {result.total_return:.2%}")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2%}")
```

---

## 项目结构详解

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
│   ├── migrations/         # Alembic 数据库迁移
│   └── schema.sql          # 数据库 Schema
├── tests/                  # 测试
├── examples/               # 示例代码
└── docs/                   # 文档
```

---

## 常见问题

### Q: 如何运行完整演示？
```bash
python examples/test_simple.py
python examples/test_signal_lab_simple.py
python examples/signal_lab_demo.py
```

### Q: 如何运行测试？
```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 查看覆盖率
pytest --cov=core --cov=data_layer --cov-report=html
```

### Q: 必须使用数据库吗？
不需要！默认使用模拟模式，无需配置数据库。

### Q: 支持哪些输出格式？
- Markdown (.md)
- Word (.docx)

---

## 相关资源
- [README.md](../README.md) - 项目概述和快速开始
