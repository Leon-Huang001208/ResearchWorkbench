
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

### 4. 事件型 Alpha 信号
```python
from core.contracts import EventAlphaSignal

signal = EventAlphaSignal(
    signal_id="event_sig_001",
    subject_id="300000.SZ",
    horizon="20d",
    thesis="AI推理需求扩散至国产服务器链",
    score=0.82,
    confidence=0.74,
    event_id="event_gpt6_launch",
    event_type="global_ai_model_launch",
    impact_path=[
        "OpenAI新模型",
        "推理需求上升",
        "ASIC和液冷需求提升",
        "A股服务器链映射",
    ],
    industry_impacts=["ASIC", "液冷", "IDC", "铜连接"],
    diffusion_stage="early_awareness",
    market_regime="AI成长",
)
```

### 5. 认知 Agent 黑板
```python
from cognitive_agents import AgentView, CognitiveBlackboard

blackboard = CognitiveBlackboard()

blackboard.add_view(AgentView(
    view_id="view_fundamental_001",
    agent_name="fundamental_agent",
    agent_role="fundamental",
    target_id="300308.SZ",
    event_id="event_ai_inference",
    view="bullish",
    thesis="800G需求超预期，盈利弹性提升",
    reasoning=["订单能见度提高", "产能利用率改善"],
    evidence_refs=["assertion_001"],
    confidence=0.72,
))

blackboard.add_view(AgentView(
    view_id="view_flow_001",
    agent_name="flow_agent",
    agent_role="sentiment",
    target_id="300308.SZ",
    event_id="event_ai_inference",
    view="bearish",
    thesis="机构仓位过高，短期交易拥挤",
    evidence_refs=["assertion_002"],
    confidence=0.64,
))

conflicts = blackboard.find_conflicts()
print(conflicts[0].summary)
```

### 6. Timing Engine 择时决策
```python
from timing_engine import MetaTimingEngine, TimingModelScore

engine = MetaTimingEngine()

decision = engine.evaluate(
    [
        TimingModelScore(
            model_name="regime",
            score=0.82,
            confidence=0.80,
            rationale="AI成长风格重新占优",
        ),
        TimingModelScore(
            model_name="flow",
            score=0.76,
            confidence=0.70,
            rationale="资金开始流入AI产业链",
        ),
        TimingModelScore(
            model_name="theme_diffusion",
            score=0.81,
            confidence=0.75,
            rationale="主题从光模块扩散到铜连接和液冷",
        ),
        TimingModelScore(
            model_name="crowding",
            score=0.24,
            confidence=0.70,
            rationale="交易拥挤度仍低",
        ),
    ],
    signal_id="event_sig_001",
    market_regime="ai_growth",
)

print(decision.action)
print(decision.readiness_score)
print(decision.blockers)
```

### 7. Memory & Learning 事件记忆
```python
from memory_learning import FailureMemory, LearningJournal, MarketEpisode

journal = LearningJournal()

journal.record_episode(MarketEpisode(
    episode_id="episode_gpt6_001",
    event_id="event_gpt6_launch",
    event_type="ai_model_launch",
    market_regime="ai_growth",
    initial_reaction="光模块和铜连接上涨",
    outcome_horizon="30d",
    outcome_return=0.18,
    outcome_excess_return=0.11,
    timing_action="enter",
    lesson="AI推理叙事在AI成长regime下扩散速度快",
))

journal.record_failure(FailureMemory(
    failure_id="failure_crowding_001",
    source_id="event_sig_001",
    failure_type="timing_error",
    root_cause="高拥挤阶段追高",
    corrective_action="提高crowding blocker权重",
))

summary = journal.summarize_event_type("ai_model_launch")
print(summary["average_excess_return"])
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

### 5. 事件研究回测
```python
import pandas as pd
from signal_lab.backtests import EventStudyBacktester

events = pd.DataFrame({
    "event_date": ["2024-01-02", "2024-02-05"],
    "event_type": ["ai_model_launch", "export_control"],
})

backtester = EventStudyBacktester(horizon=20)
result = backtester.run(prices, events=events, benchmark=benchmark_prices)

print(f"事件数: {result.metadata['event_count']}")
print(f"平均超额收益: {result.metadata['average_excess_return']:.2%}")
print(f"胜率: {result.win_rate:.2%}")
print(f"D+20 衰减收益: {result.metadata['decay_by_day'][20]:.2%}")
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
- **默认模式**：不需要！默认使用模拟数据，信号存储在内存中（程序关闭后会丢失），适合演示和测试。
- **持久化模式**：如果需要永久保存数据，需要配置 PostgreSQL 数据库（参考 README 配置说明）。

### Q: 支持哪些输出格式？
- Markdown (.md)
- Word (.docx)

---

## 相关资源
- [README.md](../README.md) - 项目概述和快速开始
