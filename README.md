
# AlphaFoundry

本地优先、可企业化的 AI Alpha Research Engine。

## 概述

AlphaFoundry 是一个面向基金研究员和量化研究员的 **AI-native Investment Operating System**。它不把“量化”理解为预测 K 线或明天收盘价，而是把 AI 的信息理解能力转化为可交易、可回测、可审计、可学习的事件型 Alpha Signal。

系统定位为 **AI Alpha Research Engine**：AI 负责发现事件、理解产业链、识别预期差和传播路径；Timing Engine 负责判断市场现在是否会认可这个逻辑；Signal Lab 负责验证事件是否产生可重复收益、构建评分、控制风险并输出研究级交易候选。系统采用模块化单体架构，使用 PostgreSQL + pgvector 作为核心事实存储，Markdown/Wiki 仅作为人类可读的投影层。

长期形态是 **World Model + Agent Swarm**，但 Agent 不作为架构主体。Agent 是认知插件层：它们按统一 ontology 写入共享黑板，形成多视角认知竞争，再由量化验证层判断哪些观点有历史收益证据。

更长期的目标不是“最终架构”，而是 **Evolutionary Architecture**：系统通过市场反馈积累记忆、修正失败原因、调整 Agent/Timing/Signal 权重，提高发现稳定 alpha 的速度。

## 核心特性

- **资产分析卡**：对股票、ETF、指数、商品、外汇、债券、基金等资产形成标准化快照，覆盖财务、资金、量价、估值、股东、产业、事件、宏观八大维度
- **专题研究备忘录**：围绕产业链、政策变化、地缘冲突、供需错配、AI compute 等主题形成结构化研究
- **多情景市场分析报告**：对不确定性问题输出 3-4 个情景，每个情景包含概率、关键假设、触发条件、失效信号
- **事件数据库**：沉淀事件发生时间、事件类型、产业影响、公司映射、传播阶段与后续收益
- **认知 Agent 黑板**：Fundamental、Macro、Policy、Industry Chain、Bull、Bear、Skeptic 等 Agent 通过统一 schema 写入结构化观点，避免自由聊天式失控
- **Timing Engine**：融合 regime、flow、theme diffusion、sentiment、crowding、liquidity、expectation gap 等模型，判断“现在能不能交易”
- **Memory & Learning Layer**：沉淀 Event → Return、策略有效性、Agent 长期观点和失败原因，避免系统每次从零推理
- **事件型 Alpha 信号**：将“全球事件 → 产业链传播 → A股映射”转为可验证信号，而不是直接预测 K 线
- **候选信号与回测说明**：将研究观察转为 thesis，再转为 scored signal，并通过 event study / excess return / win rate / decay 验证

---

## 核心闭环

```text
全球事件流
→ AI 理解
→ 产业链传播
→ A股映射
→ Agent Swarm / Cognitive Blackboard
→ Event Alpha Signal
→ Timing Engine / Market Clock
→ Statistical Validation
→ Memory & Learning
→ Portfolio / Risk / Sizing
→ Execution-ready Candidate
→ Feedback Learning
```

AlphaFoundry 当前不直接自动下单；交易执行与实盘风控作为后续可插拔模块接入。

## 快速开始

### 前置要求

- Python 3.11+

### 安装

```bash
cd ~/Desktop/Projects/AlphaFoundry

# 安装依赖
pip install -e ".[dev]"
```

### 配置数据库

AlphaFoundry 默认使用 PostgreSQL，也支持 SQLite。

#### 方式一：SQLite（零配置，快速开始）
修改 `.env` 文件：
```env
DATABASE_URL=sqlite:///./data/alphafoundry.db
```

Then bootstrap the database:
```bash
python scripts/bootstrap_db.py
```

#### 方式二：PostgreSQL（推荐）
1. 确保本地运行 PostgreSQL 15+
2. 创建数据库 `alphafoundry`
3. 修改 `.env` 文件中的 `DATABASE_URL`
4. Bootstrap the database (one-step initialization, connectivity check, seed defaults):
```bash
python scripts/bootstrap_db.py
```

The script is idempotent and can be run multiple times safely.

### 复制环境变量模板
```bash
cp .env.example .env
```

### 运行测试

```bash
# 基础功能测试
python examples/test_simple.py

# Run smoke test for recovery pipeline
python -m pytest tests/scripts/test_minimal_reingest.py -v
```

## Disaster Recovery

If you lose your local database **and** object storage, you can recover the system to a working minimal state using the fallback re-ingestion path:

### Minimal Recovery Steps

1.  Clone the repository to the new environment
2.  Copy your `.env` configuration (or reconfigure from `.env.example`)
3.  Bootstrap the database and ingest the minimal sample:
    ```bash
    python scripts/minimal_reingest_bootstrap.py --sample-size 20
    ```
4.  After recovery completes successfully, you can run replay and validation:
    ```bash
    # Run smoke validation
    python scripts/minimal_reingest_bootstrap.py --skip-bootstrap --dry-run
    ```

The minimal bootstrap includes:
- Full database schema initialization
- Default configuration seeding
- Ingestion of bounded historical sample (3+ events)
- Full rebuild of all derived state: signals → timing decisions → outcomes → replay
- End-to-end smoke validation to confirm the system is working

This recovery path requires **no existing local artifacts** - everything is rebuilt from upstream/benchmark assets.
# 信号实验室测试
python examples/test_signal_lab_simple.py
```

### 使用 CLI

```bash
# 资产分析
af analyze --asset 600000.SH

# 情景分析
af scenario --topic "人工智能产业发展对股票市场的影响"

# 更多命令请参考参考手册
```

---

## 项目结构

```
AlphaFoundry/
├── app/                    # 应用层（CLI、API、Web）
├── core/                   # 核心层（契约、接口、服务、网关）
├── data_layer/             # 数据层（适配器、解析器、仓储）
├── knowledge_layer/        # 知识层（实体、断言、事件、检索）
├── reasoning/              # 推理层（状态机、情景、证据）
├── cognitive_agents/       # 认知 Agent 插件层（统一观点契约、黑板、冲突检测）
├── timing_engine/          # 择时层（市场状态、资金流、拥挤度、认知传播时钟）
├── memory_learning/        # 记忆与学习层（事件记忆、策略记忆、失败记忆）
├── reporting/              # 报告层（模板、合成、输出）
├── signal_lab/             # 信号实验室（特征、标签、回测）
├── storage/                # 存储层（迁移、Schema）
├── tests/                  # 测试
├── examples/               # 示例代码
└── docs/                   # 文档
```

---

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

---

## 实施进度

- ✅ 第 1 个月：事实层与报告骨架
- ✅ 第 2 个月：事件、断言与多情景
- ✅ 第 3 个月：信号验证与团队工作台（核心功能完成）
- ⬜ Web Workbench v1

---

## 文档

- **[docs/REFERENCE.md](docs/REFERENCE.md)** - 完整参考手册（CLI、API、信号实验室）

---

## 开发指南

### 运行测试
```bash
pytest
```

### 代码格式化
```bash
black .
isort .
ruff check .
```

---

## 设计原则

1. **本地优先**：数据本地处理，保证数据安全
2. **模块化单体**：清晰的模块边界，可替换基础设施
3. **事实层**：PostgreSQL 作为单一事实源
4. **接口隔离**：数据源、模型后端、向量库等都通过接口隔离
5. **可审计**：所有操作都可追溯，支持审核流程
