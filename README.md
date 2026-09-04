# Research Workbench

本地优先、可企业化的 AI Alpha Research Engine。

## 概述

Research Workbench 是一个面向基金研究员和量化研究员的 **AI-native Investment Operating System**。它不把"量化"理解为预测 K 线或明天收盘价，而是把 AI 的信息理解能力转化为可交易、可回测、可审计、可学习的事件型 Alpha 信号。

系统定位为 **AI Alpha Research Engine**：AI 负责发现事件、理解产业链、识别预期差和传播路径；Timing Engine 负责判断市场现在是否认可这个逻辑；Signal Lab 负责验证事件是否产生可重复收益、构建评分、控制风险并输出研究级交易候选。系统采用模块化单体架构，使用 PostgreSQL + pgvector 作为核心事实存储，Markdown/Wiki 仅作为人类可读的投影层。

长期形态是 **World Model + Agent Swarm**，但 Agent 不作为架构主体。Agent 是认知插件层：它们按统一 ontology 写入共享黑板，形成多视角认知竞争，再由量化验证层判断哪些观点有历史收益证据。

更长期的目标不是"最终架构"，而是 **Evolutionary Architecture**：系统通过市场反馈积累记忆、修正失败原因、调整 Agent/Timing/Signal 权重，提高发现稳定 alpha 的速度。

## 核心特性

### 事实层与知识加工

- **资产分析卡**：对股票、ETF、指数、商品、外汇、债券、基金等资产形成标准化快照，覆盖财务、资金、量价、估值、股东、产业、事件、宏观八大维度
- **文档摄入管道**：支持 PDF、网页、研报等多格式文档，自动分块、分类、实体提取、事件提取
- **多源数据采集**：财联社电报、中国证券网、知丘研报、AKShare 开源数据、Wind 专业终端、BaoStock、Yahoo Finance、Cjpy 等数据源，通过统一的 Connector 架构（DocumentConnector / MarketDataConnector）自动采集和降级切换
- **实体解析与归一化**：自动消歧，确保同一实体在不同数据源中被统一标识
- **向量检索与 RAG**：基于 pgvector 的语义检索，支持知识召回和增强生成

### 信号实验室

- **特征工程框架**：模块化特征定义，支持价量、估值、财务、资金流、行业、宏观等特征组
- **标签工程框架**：支持相对收益、事件驱动等多种标签定义
- **信号评分系统**：多维度评分，包括置信度、历史胜率、市场时机匹配度
- **回测引擎**：事件研究回测、简单回测，计算超额收益、胜率、衰减等指标

### 认知与决策

- **专题研究备忘录**：围绕产业链、政策变化、地缘冲突、供需错配、AI compute 等主题形成结构化研究
- **多情景市场分析报告**：对不确定性问题输出 3-4 个情景，每个情景包含概率、关键假设、触发条件、失效信号
- **项目级模板报告**：`report_projects/` 工作台支持 Word 占位符、Excel 底稿、YAML 映射和 Markdown Prompt 模板联动；生成时先检索 evidence，再通过 ModelGateway 写作，自动嵌入配置图表并提供 Word HTML 预览和 runs 审计日志
- **事件数据库**：沉淀事件发生时间、事件类型、产业影响、公司映射、传播阶段与后续收益
- **认知 Agent 黑板**：Fundamental、Macro、Policy、Industry Chain、Bull、Bear、Skeptic 等 Agent 通过统一 schema 写入结构化观点
- **Timing Engine**：融合 regime、flow、theme diffusion、sentiment、crowding、liquidity、expectation gap 等模型
- **事件型 Alpha 信号**：将"全球事件 → 产业链传播 → A股映射"转为可验证信号

### 生产级工作台

- **Web 工作台**：研究优先的操作系统式控制台，包含 Today、Research Queue、Candidate Board、Learning、全局搜索五个板块
- **决策控制台**：每日候选审核、决策动作记录、理由捕获、复盘视图、审计追踪
- **模拟交易系统**：Paper Trading + Simulation + 基准比较
- **治理与审计**：Model/Prompt/Strategy 版本管理、实验对比、回滚、审计
- **监控与告警**：健康指标采集、分布漂移检测、可配置阈值告警

### 学习与闭环

- **Memory & Learning Layer**：记录 Event → Return、策略有效性、Agent 长期观点和失败原因
- **结果反馈循环**：Outcome Journal 持久化存储交易结果
- **失败记忆引擎**：标准化失败分类，基于 thesis 文本相似度自动检索相似历史成功/失败案例
- **每周回顾报告**：自动统计成功率和失败分布

## 完整流程使用指南

### 1. 初始化数据库

```bash
python scripts/bootstrap_db.py
```

这将：

- 验证数据库连接
- 创建所有必需的表
- 验证 schema 完整性
- 植入默认配置

### 2. 导入真实数据

项目已包含真实数据存档，无需模拟数据：

```bash
python scripts/import_real_data.py
```

导入内容包括：

- **财联社电报**：292条 + 608条30天存档（共900条）
- **中国证券网新闻**：24条
- **知丘研报**：A股、AI、市场、策略、成长、价值、指数等专题（共约747条）
- **知丘公众号**：53条
- **知丘会议纪要**：92条
- **示例真实事件**：5条精选事件（贵州茅台财报、降准政策、新能源销量、光伏价格、科创政策）

导入后查看数据：

```bash
python view_db.py all
```

### 3. 启动研究 Web

安装当前仓库后，由项目级管理器持久启动专属 DSH 3081 与 Web 8088：

```bash
rwb web start
rwb web status
```

启动成功后访问 <http://127.0.0.1:8088/#/fingpt>。命令退出或关闭终端不会终止服务；`rwb web stop` 只停止指纹匹配的 8088/3081，不操作其他 DSH 实例。日志和进程状态位于 `~/.research-workbench/logs/` 与 `~/.research-workbench/run/`。

首次从旧研究 Web 切换时执行 `rwb migrate-research-data --dry-run`，确认摘要后再执行 `rwb migrate-research-data`。迁移保留会话、附件、能力版本、数据集和产物，但不复制模型密钥；需要在设置页重新填写。

### 4. 启动历史业务 API（可选）

```bash
uvicorn app.api.main:app --reload
```

或后台运行：

```bash
nohup python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 > logs/web_server.log 2>&1 &
```

### 分支桌面端预览

功能分支位于独立 Git worktree 时，可在该 worktree 中运行下面的命令进行桌面端验收，稳定版桌面端继续使用 `8765`：

```bash
npm run desktop:preview
```

预览实例默认使用 `8766` 和独立的临时运行数据；关闭预览窗口后会停止。需要在原有数据库配置下验收完整工作台时，显式传入 `-- --use-stable-data`；预览不会初始化数据库或启动重复的后台任务。详见 `docs/desktop_packaging.md`。

### 5. 验证历史业务 API

检查健康状态：

```bash
curl http://127.0.0.1:8000/health
```

查看仪表盘数据：

```bash
curl http://127.0.0.1:8000/api/dashboard
```

访问 Web 界面：

- 首页：http://127.0.0.1:8000/
- API 文档：http://127.0.0.1:8000/docs

### 6. 启动自动数据抓取

如需持续获取最新数据：

```bash
python auto_ingest_service.py
```

定时任务配置：

- 财联社电报：每15分钟抓取一次
- 中国证券网新闻：每30分钟抓取一次
- 知丘研报：每1小时抓取一次
- 股票分析数据：每天15:30收盘后抓取
- 健康检查：每10分钟一次

后台运行：

```bash
python auto_ingest_service.py --daemon
```

### 7. 使用 CLI 命令

```bash
# 资产分析
rwb analyze --asset 600000.SH

# 情景分析
rwb scenario --topic "人工智能产业发展对股票市场的影响"

# 数据摄入
rwb ingest --file report.pdf

# 生成研报
rwb report --asset 600519.SH --type full
```

### 8. 播种因子数据

运行因子数据种子管线，播种市场数据并计算技术面和财务面因子：

```bash
# AKShare 数据源（默认，含限流保护）
python scripts/seed_factor_data.py --stock-count 200

# Wind Excel 数据源（需 Wind 终端 + Excel 插件，速度更快）
python scripts/seed_factor_data.py --stock-count 200 --source wind

# 自动选择（Wind 优先，不可用时降级 AKShare）
python scripts/seed_factor_data.py --stock-count 200 --source auto

# 断点续传（中断后恢复）
python scripts/seed_factor_data.py --stock-count 200 --source auto --resume .ai/checkpoints/seed_auto_200.json
```

## Web 工作台功能

### 首页五板块

1. **Today**：今日概览、市场快照、待办事项
2. **Research Queue**：研究队列、待分析事件、候选生成
3. **Candidate Board**：候选看板、信号评分、回测结果
4. **Learning**：学习中心、失败记忆、历史案例、每周回顾
5. **全局搜索**：跨对象搜索 symbol/event_type/thesis/source_doc/failure_memory/market_episode

### 核心页面

- **仪表盘**：聚合显示研究进度、信号统计、市场状态
- **股票分析**：五面板展示，包含 K 线图、资金流向、财务数据、新闻、研报
- **信号实验室**：特征工程、标签工程、信号评分、回测分析
- **决策控制台**：每日候选审核、决策记录、复盘视图
- **结果日志**：Outcome Journal、失败记忆、每周回顾

## 快速开始

### 前置要求

- Python 3.11+
- PostgreSQL 15+ 与 pgvector 扩展（桌面端由用户自行安装；网页生产环境使用受管 PostgreSQL）

### 安装

```bash
cd ~/Desktop/Projects/ResearchWorkbench

# 安装依赖
pip install -e ".[dev]"

# 可选：PDF 转换支持
pip install -e ".[pdf]"        # MarkItDown 支持 (microsoft/markitdown)
pip install -e ".[pdf-full]"   # 完整支持 (含 MinerU, opendatalab/mineru)
```

### 配置数据库

1. 安装并启动本地 PostgreSQL 15+，安装 pgvector 扩展。
1. 创建数据库 `research_workbench`，在该库中执行 `CREATE EXTENSION IF NOT EXISTS vector;`。
1. 复制 `.env.example` 为 `.env`，并配置：

```env
DATABASE_URL=postgresql+psycopg://user:password@127.0.0.1:5432/research_workbench
```

1. 初始化数据库：

```bash
python scripts/bootstrap_db.py
```

桌面端用户配置文件位于 `%LOCALAPPDATA%\Research Workbench\.env`（Windows）或 `~/Library/Application Support/Research Workbench/.env`（macOS）。迁移时复制该目录，并使用 `pg_dump` / `pg_restore` 迁移 PostgreSQL 数据库；详见 `docs/desktop_packaging.md`。

### 复制环境变量模板

```bash
cp .env.example .env
```

### 运行测试

```bash
# 基础功能测试
python examples/test_simple.py

# 信号实验室测试
python examples/test_signal_lab_simple.py

# 冒烟测试
python scripts/smoke_runner.py
```

## 数据备份与恢复

### 备份数据库

```bash
python scripts/backup_db.py --output backups/
```

### 恢复数据库

```bash
python scripts/restore_db.py --input backups/backup_20250510_120000.sql.gz
```

详细文档请参考 `docs/backup_restore.md`。

## 灾难恢复

如果丢失本地数据库和对象存储，可以使用以下路径恢复系统：

### 最小恢复路径

1. 克隆项目到新环境
2. 复制 `.env` 配置（或从 `.env.example` 重新配置）
3. 使用最小样本重新引导系统：

```bash
python scripts/minimal_reingest_bootstrap.py --sample-size 20
```

4. 恢复完成后，运行回放和验证：

```bash
python scripts/minimal_reingest_bootstrap.py --skip-bootstrap --dry-run
```

### 从对象存储回填

如果对象存储幸存但数据库丢失：

```bash
python scripts/backfill_from_objects.py
```

### 重建派生状态

从恢复的事实记录重建派生系统状态：

```bash
python scripts/rebuild_derived_state.py
```

## 项目结构

```
Research Workbench/
├── app/                          # 应用层
│   ├── api/                      # FastAPI 后端 API
│   │   ├── main.py               # API 入口
│   │   ├── models.py             # API 模型
│   │   └── routes/               # API 路由
│   │       ├── audit.py          # 审计 API
│   │       ├── dashboard.py      # 仪表盘 API
│   │       ├── governance.py     # 治理 API
│   │       ├── ingest.py         # 数据摄入 API
│   │       ├── memory.py         # 记忆 API
│   │       ├── monitoring.py     # 监控 API
│   │       ├── outcome_journal.py # 结果日志 API
│   │       ├── pipeline.py       # 管道 API
│   │       ├── report.py         # 报告 API
│   │       ├── report_projects.py # 报告项目 API（源码保存、生成、预览、下载）
│   │       ├── scenarios.py      # 情景 API
│   │       ├── search.py         # 搜索 API
│   │       └── signal_lab.py     # 信号实验室 API
│   ├── cli/                      # 命令行工具
│   │   ├── commands/             # CLI 命令
│   │   │   ├── akshare.py        # AKShare 命令
│   │   │   ├── ingest.py         # 数据摄入命令
│   │   │   ├── memory.py         # 记忆命令
│   │   │   ├── review.py         # 审核命令
│   │   │   ├── signal.py         # 信号命令
│   │   │   └── timing.py         # 择时命令
│   │   └── main.py               # CLI 入口
│   └── web/                      # Web 工作台界面
├── core/                         # 核心层
│   ├── contracts/                # Pydantic 数据契约
│   │   ├── assertions.py         # 断言结构
│   │   ├── assets.py             # 资产定义
│   │   ├── backtest.py           # 回测结构
│   │   ├── dashboard.py          # 仪表盘结构
│   │   ├── decision_console.py   # 决策控制台结构
│   │   ├── documents_v1.py       # 文档结构 v1
│   │   ├── events.py             # 事件结构
│   │   ├── governance.py         # 治理结构
│   │   ├── industry_chain.py     # 产业链结构
│   │   ├── ingestion.py          # 摄入结构
│   │   ├── monitoring.py         # 监控结构
│   │   ├── outcome_journal.py    # 结果日志结构
│   │   ├── outcomes.py           # 结果结构
│   │   ├── paper_trading.py      # 模拟交易结构
│   │   ├── portfolio.py          # 组合结构
│   │   ├── raw_storage.py        # 原始存储结构
│   │   ├── replay.py             # 回放结构
│   │   ├── reporting.py          # 报告结构
│   │   ├── retrieval.py          # 检索结构
│   │   ├── review_framework.py   # 审查框架结构
│   │   ├── scenarios.py          # 情景结构
│   │   ├── signals.py            # 信号结构
│   │   ├── timing_engine.py      # 择时引擎结构
│   │   ├── timing_types.py       # 择时/结果共享类型
│   │   ├── agent_types.py        # Agent 共享类型
│   │   └── traces.py             # 推理追踪结构
│   ├── interfaces/               # 核心接口定义
│   ├── model_gateway/            # 模型网关
│   │   └── providers/            # 模型提供商
│   │       └── volcano.py        # 火山引擎提供商
│   ├── observability/            # 可观测性（日志、指标、追踪）
│   │   └── metrics.py            # 指标
│   ├── services/                 # 废弃重导出 → services/
│   └── settings/                 # 配置管理
├── connectors/                   # 数据源连接器实现
│   ├── document/                 # 文档类连接器 (CLS, CNStock, ZQ)
│   └── market/                   # 行情类连接器 (AKShare, Baostock, Cjpy, Wind, Yahoo)
├── services/                    # 业务服务层
│   ├── asset_analysis_service.py
│   ├── crawl_scheduler.py
│   ├── crawl_orchestrator.py
│   ├── document_chunker.py
│   ├── document_classifier.py
│   ├── ingest_service.py
│   ├── monitoring_service.py
│   ├── pdf_conversion_service.py
│   ├── pipeline_service.py
│   ├── report_generator.py
│   ├── search_service.py
│   ├── signal_service.py
│   └── ...                      # 共 47 个服务文件
├── data_layer/                 # 数据层
│   ├── adapters/               # 数据适配器
│   │   ├── akshare_adapter.py # AKShare 适配器
│   │   ├── data_source_router.py # 多源路由（Wind / AKShare / ChinaStock）
│   │   └── wind/              # Wind Excel 适配器（xlwings → AppleScript）
│   │       ├── client.py      # WindExcelClient：WSD 时间序列 / 批量公式 / 保活
│   │       ├── formulas.py    # 78 个 Wind 公式生成器
│   │       ├── wind_adapter.py # 8 个 fetch 方法 + parse()
│   │       └── exceptions.py  # Wind 自定义异常
│   ├── crawlers/              # 数据采集器
│   │   ├── akshare/           # AKShare 采集器
│   │   │   ├── base.py       # 基础类
│   │   │   ├── config.py     # 配置
│   │   │   ├── financial.py  # 财务数据
│   │   │   ├── macro.py      # 宏观数据
│   │   │   ├── market.py     # 市场数据
│   │   │   ├── news.py       # 新闻数据
│   │   │   └── utils.py      # 工具函数
│   │   ├── cls/              # 财联社采集器
│   │   ├── cnstock/          # 中国证券网采集器
│   │   └── zq/               # 知丘采集器
│   ├── parsers/              # 解析器
│   ├── normalizers/          # 归一化器
│   └── repositories/         # 仓储实现
├── knowledge_layer/          # 知识层
│   ├── entity_resolution/    # 实体解析
│   ├── assertions/           # 断言管理
│   ├── events/               # 事件管理
│   └── retrieval/            # 向量检索
├── reasoning/                # 推理层
│   ├── evidence/             # 证据链管理
│   ├── scenarios/            # 情景分析
│   ├── skeptic/              # 怀疑论验证
│   └── traces/               # 推理追踪
├── cognitive_agents/         # 认知 Agent 插件层
│   ├── contracts.py          # 统一观点契约
│   └── blackboard.py         # 认知黑板
├── timing_engine/            # 择时层
│   ├── contracts.py          # 择时契约
│   └── meta.py              # Meta 择时引擎
├── memory_learning/          # 记忆与学习层
│   ├── contracts.py          # 记忆契约
│   └── journal.py           # 学习日志
├── reporting/                # 报告层
│   ├── composer/             # 报告合成
│   ├── projects/             # 项目级报告生成（evidence 检索、LLM 生成、图表嵌入、run logs）
│   ├── templates/            # 报告模板
│   └── projections/          # 输出投影
├── report_projects/          # 报告项目资产（project.yaml、模板、Excel 底稿、report_config、prompt_templates）
├── signal_lab/               # 信号实验室
│   ├── features/             # 特征工程
│   │   └── indicators/        # 技术指标引擎（TA-Lib, pandas-ta）
│   ├── labels/               # 标签工程
│   ├── scoring/              # 信号评分
│   └── backtests/            # 回测引擎
├── storage/                  # 存储层
│   └── migrations/           # Alembic 数据库迁移
├── ingestion/                # 结构化摄入模块
│   ├── converters/           # PDF 转换策略链（MinerU → MarkItDown → RawText）
│   ├── knowledge_pipeline.py # 知识管道
│   └── structured_event_ingestion.py  # 结构化事件摄入器
├── cron_jobs/                # 定时任务
│   ├── auto_ingest_service.py  # 自动数据摄入服务
│   └── auto_generate_signals.py # 自动信号生成
├── workers/                   # 后台 Worker 进程
│   ├── crawl_scheduler_worker.py  # 爬虫调度 Worker
│   └── knowledge_worker.py    # 知识处理 Worker (LLM 管道)
├── scripts/                  # 脚本工具
│   ├── seed_factor_data.py   # 因子数据播种（AKShare/Wind 双源 + 限流重试 + 断点续传）
│   ├── backup_db.py          # 数据库备份
│   ├── restore_db.py         # 数据库恢复
│   ├── bootstrap_db.py       # 数据库初始化
│   ├── import_real_data.py   # 导入真实数据
│   ├── minimal_reingest_bootstrap.py  # 最小重摄入引导
│   ├── backfill_from_objects.py        # 从对象存储回填
│   ├── rebuild_derived_state.py        # 重建派生状态
│   ├── smoke_runner.py       # 冒烟测试
│   └── view_db.py            # 数据库查看工具
├── benchmarks/               # 基准数据
├── examples/                 # 示例代码
├── tests/                    # 测试
├── docs/                     # 文档
│   ├── REFERENCE.md          # 完整参考手册
│   ├── ARCHITECTURE.md       # 架构文档
│   ├── FILE_GUIDE.md         # 文件指南
│   ├── CHANGELOG.md          # 更新日志
│   ├── DATA_STORAGE.md       # 数据存储文档
│   ├── backup_restore.md     # 备份恢复文档
│   └── DATA_SOURCES.md       # 数据源文档
├── data/                     # 数据目录
├── logs/                     # 日志目录
├── backups/                  # 备份目录
├── .env.example              # 环境变量示例
├── .gitignore                # Git 忽略
├── pyproject.toml            # 项目配置
└── pytest.ini                # Pytest 配置
```

## 技术栈

| 领域 | 技术选型 |
| --- | --- |
| 编程语言 | Python 3.11+ |
| 数据采集 | DocumentConnector / MarketDataConnector |
| 数据源 | AKShare、财联社、中国证券网、知丘、Wind、BaoStock、Yahoo |
| 数据验证 | Pydantic v2 |
| Web 框架 | FastAPI |
| 命令行 | Click |
| 数据库 | PostgreSQL 15+ + pgvector（核心事实存储；SQLite 仅保留非权威缓存兼容） |
| 向量存储   | pgvector                |
| ORM        | SQLAlchemy 2.0          |
| 数据库迁移 | Alembic                 |
| 状态机     | LangGraph               |
| 回测       | vectorbt, Backtrader    |
| 日志       | structlog               |
| 代码格式化 | black, isort, ruff      |

## 实施进度

- ✅ **第 1 个月**：事实层与报告骨架
- ✅ **第 2 个月**：事件、断言与多情景分析
- ✅ **第 3 个月**：信号验证与核心功能闭环
- ✅ **第 4 个月**：Web Workbench v1、多源采集、知识加工、RAG 检索、模板报告、回测视角
- ✅ **第 5 个月**：闭循环服务、失败记忆、结果反馈、每周回顾
- 🔄 **进行中**：持续优化与迭代
  - 报告项目工作台：以 `report_config.yaml` 和必需的 `prompt_templates.md` 作为唯一配置来源，支持源码保存、配置驱动生成、图表嵌入、Word HTML 预览和 runs 审计日志
  - Scheduler 稳定性改进：启动回填改为异步后台任务，支持 per-source 和全局超时保护
  - 数据管道修复：知丘公众号和会议纪要内容现已正确进入 LLM 提取管道

## 文档索引

- **[README.md](README.md)** - 本文档，项目概述与快速开始
- **[docs/REFERENCE.md](docs/REFERENCE.md)** - 完整参考手册（CLI、API、信号实验室）
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - 架构文档
- **[docs/FILE_GUIDE.md](docs/FILE_GUIDE.md)** - 文件指南，每个文件的详细说明
- **[docs/CHANGELOG.md](CHANGELOG.md)** - 更新日志
- **[docs/backup_restore.md](docs/backup_restore.md)** - 备份与恢复文档
- **[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)** - 数据源文档

## 开发指南

### 运行测试

```bash
pytest
```

默认测试环境会禁用本地 embedding 模型加载。运行时可用 `RESEARCH_LOCAL_EMBEDDING_MODEL_PATH=/path/to/model` 指向已下载的 sentence-transformers 模型目录；未设置本地路径时只读本机 Hugging Face cache，只有设置 `RESEARCH_ALLOW_EMBEDDING_DOWNLOAD=1` 才允许联网下载。需要访问已启动 API 服务的 smoke 测试请设置 `RESEARCH_RUN_LIVE_API_TESTS=1`；需要运行浏览器 E2E smoke 请设置 `RESEARCH_RUN_LIVE_E2E_TESTS=1`。

### 代码格式化

```bash
black .
isort .
ruff check .
```

### 数据库迁移

```bash
# 创建新迁移
alembic revision -m "description of change" --autogenerate

# 升级到最新版本
alembic upgrade head

# 查看当前版本
alembic current

# 查看迁移历史
alembic history --verbose
```

## 设计原则

1. **本地优先**：数据本地处理，保证数据安全
2. **模块化单体**：清晰的模块边界，可替换基础设施
3. **事实层**：PostgreSQL 作为单一事实源
4. **接口隔离**：数据源、模型后端、向量库等都通过接口隔离
5. **可审计**：所有操作都可追溯，支持审计流程

## 许可证

MIT License
