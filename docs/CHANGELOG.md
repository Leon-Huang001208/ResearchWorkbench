# 更新日志

所有 notable 项目变更都记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- **docs**: 完整更新项目文档（README、REFERENCE、ARCHITECTURE、FILE_GUIDE、CHANGELOG、DATA_STORAGE）
  - 新增 `docs/DATA_STORAGE.md`：数据存储设计文档，包含 PostgreSQL 表结构、数据契约、仓储接口说明
- **refactor**: 清理项目根目录，移除重复配置
  - 移除根目录重复的 `alembic.ini` 和 `alembic/` 目录，统一使用 `storage/migrations/`
  - 移动临时脚本到标准目录：`view_db.py` → `scripts/`，`auto_ingest_service.py` → `cron_jobs/`
  - 移除冗余临时脚本：`insert_real_data.py`、`report_cli.py`、`smoke_runner.py`（功能已存在于标准位置）
- **refactor**: 清理 AKShare 集成，移除重复代码，统一使用 crawler 模块的 utils
  - `data_layer/crawlers/akshare/utils.py`: 新增工具函数（clean_symbol, normalize_symbol, parse_date, parse_datetime, safe_float）
  - `data_layer/crawlers/akshare/market.py`: 重构为使用 utils 中的工具函数
  - `data_layer/crawlers/akshare/financial.py`: 重构为使用 utils 中的工具函数
  - `data_layer/crawlers/akshare/news.py`: 重构为使用 utils 中的工具函数
  - `data_layer/adapters/akshare_adapter.py`: 更新为集成新的 crawler 模块
- **Issue #42-47**: 统一文档 Schema、多源采集、知识加工、RAG 检索、模板报告和回测视角
  - 新增完整知识加工管道（DocumentChunker, DocumentClassifier, EntityExtractor, EventExtractor）
  - 新增 RAG 检索服务（RAGRetrieval）
  - 新增报告生成器（ReportGenerator）支持资产分析、估值、每周回顾等多类型报告
  - 新增采集编排器和调度器（CrawlOrchestrator, CrawlScheduler）
  - 新增闭循环服务（ClosedLoopService）
  - 新增去重服务（DeduplicationService）
  - 新增文档丰富服务（DocumentEnrichment）
  - 新增摘要生成器（SummaryGenerator）
  - 新增论点生成和审查服务（ThesisGeneratorService, ThesisReviewService）
  - 新增分类服务（TaxonomyService）
  - 新增图数据服务（GraphDataService）
- **Web Workbench v1**: 完整股票分析 UI，包含 K 线图、资金流向、五面板展示
  - 仪表盘页面：展示研究进度、信号统计、市场状态
  - 股票分析页面：五面板展示，包含行情、资金、财务、新闻、研报
  - 信号实验室页面：特征工程、标签工程、信号评分、回测分析
  - 决策控制台页面：每日候选审核、决策记录、复盘视图
  - 结果日志页面：Outcome Journal、失败记忆、每周回顾
- **Memory Learning Layer**: 完整的记忆与学习层实现
  - Outcome Journal：结果日志持久化存储
  - Failure Memory：标准化失败分类（wrong_thesis / timing_error / crowding_error / regime_misread / mapping_error / evidence_weakness / execution_error / risk_error）
  - Market Episode：市场事件记忆
  - Learning Journal：学习日志，自动检索相似历史案例
  - 每周回顾报告：自动统计成功率和失败分布
- **Signal Lab Enhancements**: 信号实验室功能完善
  - 完整特征工程框架（Feature、FeatureGroup、FeatureBuilder）
  - 特征组实现（price_volume、valuation、financial、fund_flow、industry、macro）
  - 标签工程框架（Labeler、RelativeReturnLabeler、EventDrivenLabeler）
  - 信号评分系统（SignalScorer、CompositeScorer、ConfidenceScorer、StrengthScorer、HistoricalWinRateScorer、MarketTimingScorer）
  - 信号排名（SignalRanker）
  - 回测引擎（SimpleBacktester、EventStudyBacktester、BacktestResult）
- **Governance & Audit**: 治理与审计系统
  - 版本控制（配置、提示词、策略）
  - 审计日志（所有关键操作记录）
  - 审查工作流（断言、事件、信号的批准/拒绝）
- **Monitoring & Alerting**: 监控与告警系统
  - 健康检查端点
  - 指标采集与监控
  - 可配置阈值告警
  - 漂移检测
- **Paper Trading & Portfolio**: 模拟交易与组合管理
  - 模拟交易服务（PaperTradingService）
  - 组合服务（PortfolioService）
  - 基准比较
- **Decision Console**: 分析师人在回路决策控制台
  - 每日候选审核
  - 决策动作记录
  - 理由捕获
  - 复盘视图
  - 审计追踪
- **AKShare Integration**: 新增 AKShare 开源数据源作为 macOS 降级数据源
  - 自动降级链：iFinD → AKShare → Local → Mock
  - 完整的 AKShare 采集器（市场、财务、新闻、宏观）
  - 统一的工具函数库
  - 数据适配器集成
- **Real Data Ingestion**: 真实数据集成
  - 财联社电报：292条 + 608条30天存档（共900条）
  - 中国证券网新闻：24条
  - 知丘研报：A股、AI、市场、策略、成长、价值、指数等专题（共约747条）
  - 知丘公众号：53条
  - 知丘会议纪要：92条
  - 示例真实事件：5条精选事件
- **Auto Ingest Service**: 全自动数据抓取服务
  - 定时自动抓取财联社、中国证券网、知丘研报、股票数据
  - 内置防爬机制
  - 守护进程模式支持
- **Disaster Recovery**: 灾难恢复系统
  - `scripts/backup_db.py`: 数据库备份脚本
  - `scripts/restore_db.py`: 数据库恢复脚本
  - `scripts/bootstrap_db.py`: 数据库初始化脚本
  - `scripts/import_real_data.py`: 导入真实数据脚本
  - `scripts/minimal_reingest_bootstrap.py`: 最小重摄入引导脚本
  - `scripts/backfill_from_objects.py`: 从对象存储回填脚本
  - `scripts/rebuild_derived_state.py`: 重建派生状态脚本
  - `scripts/smoke_runner.py`: 冒烟测试脚本
- **FastAPI Backend**: 完整的后端 API
  - `/health`: 健康检查
  - `/api/dashboard`: 仪表盘 API
  - `/api/search`: 全局搜索 API
  - `/api/asset`: 资产分析 API
  - `/api/ingest`: 数据摄入 API
  - `/api/events`: 事件 API
  - `/api/signals`: 信号 API
  - `/api/backtest`: 回测 API
  - `/api/signal-lab`: 信号实验室 API
  - `/api/outcomes`: 结果日志 API
  - `/api/memory`: 记忆 API
  - `/api/governance`: 治理 API
  - `/api/monitoring`: 监控 API
- **Alembic Integration**: 数据库迁移系统
  - 初始化 Alembic 配置
  - 初始迁移脚本
- **CLI Enhancements**: 增强的命令行工具
  - `akshare`: AKShare 数据管理命令
  - `ingest`: 数据摄入命令
  - `memory`: 记忆管理命令
  - `review`: 审核管理命令
  - `signal`: 信号管理命令
  - `timing`: 择时分析命令
- **utils**: 修复所有数据源时间解析逻辑，确保所有发布日期精确到秒，只有日期的默认补 00:00:00

### Changed
- **db**: 移除导入时数据库连接副作用，启动检查显式化
  - 数据库连接检查现在在 API 启动和引导/恢复脚本中显式执行，而不是在模块导入时无条件执行
  - 这允许测试、脚本和离线工具导入仓储模块而不需要活动的实时数据库连接，同时在启动入口点保留相同的可操作错误检查
- **docs**: 组织文档到 docs/ 目录
  - `ARCHITECTURE.md` 移到 docs/
  - `CHANGELOG.md` 移到 docs/
  - 新增 `FILE_GUIDE.md`
  - 新增 `backup_restore.md`
  - 新增 `DATA_SOURCES.md`
- **default persistence**: 默认持久化从 SQLite 迁移到 PostgreSQL，SQLite 保留为零配置演示选项
- **mock removed**: 移除模拟数据逻辑，默认使用真实数据，仪表盘显示真实新闻数据，降级情况返回演示数据
- **ingest pipeline**: ingest API 现在对接持久化的文档/断言/事件仓库和共享向量库，所有摄入数据自动持久化并索引到向量库
- **pull sources**: 所有实时源拉取接口现在走完整 envelope ingestion 流程，不再返回原始拉取计数，而是经过完整摄入管道后返回实际成功摄入的文档数量
- **auto signal generation**: 实现已批准事件自动生成候选信号功能，支持审批即时触发和定时扫描自动生成，不需要手动调用流水线
- **outcomes API**: outcomes API 默认使用持久化仓储，新增带信号详情的查询接口，关联信号评估记录和信号详情
- **core contracts**: 大幅扩展核心契约，新增 20+ 契约文件
- **core services**: 核心服务从几个扩展到 40+ 个
- **crawler refactor**: 重构 AKShare 采集器，分离 utils 到独立模块，避免代码重复

### Fixed
- **dashboard**: 修复仪表盘数据问题，给 SignalOutcomeDB 添加 event_type 字段，dashboard 添加空数据降级返回模拟演示数据
- **service startup**: 修复服务启动错误，补全 Query 导入，修改 AssetAnalysisService 参数为可选，现在 Web 可以正常打开
- **asset analysis**: 修复资产分析功能，自动数据源降级，前端隐藏数据源选择
- **signal list**: 修复信号列表 500 错误，修复资产/情景/图按钮绑定
- **AKShare financial**: 修复 AKShare 财务数据解析（新浪财经接口）
- **frontend**: 添加 AKShare 选项到资产源选择器，默认为自动降级
- **Word export**: 修复 Word 文档投影错误
- **Pydantic v2**: 修复 Pydantic v2 弃用接口警告
- **CLI error handling**: 修复 CLI 错误处理
- **vector search ordering**: 修复向量搜索结果排序问题
- **import errors**: 修复导入错误和字段名冲突
- **db initialization**: 修复数据库初始化流程
- **ruff issues**: 修复 ruff 检查问题（未使用导入等）
- **500 errors**: 修复多个 500 错误

## [v0.4.0] - 2025-05-10

### Added
- Web Workbench v1 完整实现
- Memory Learning Layer（记忆与学习层）
- 完整的数据采集管道（AKShare、财联社、中国证券网、知丘）
- RAG 检索服务
- 报告生成器
- 闭循环服务
- 灾难恢复系统
- 监控与告警系统
- 治理与审计系统
- 模拟交易与组合管理
- 决策控制台
- Alembic 数据库迁移

### Changed
- 默认数据库从 SQLite 改为 PostgreSQL
- 移除模拟数据，默认使用真实数据
- 重构数据摄入管道
- 重构 AKShare 集成

## [v0.3.0] - 2025-05-01

### Added
- 信号实验室完整功能
  - 特征工程框架
  - 标签工程框架
  - 信号评分系统
  - 回测引擎集成（vectorbt + Backtrader）
- 候选信号管理与回测说明文档

### Changed
- 完成第三个里程碑：信号验证与核心功能闭环

## [v0.2.0] - 2025-04-01

### Added
- 事件模型与事件存储
- 事实断言模型
- 多情景分析引擎
  - 支持 3-4 个情景输出
  - 每个情景包含概率、关键假设、触发条件、失效信号
- 推理状态机基于 LangGraph 实现
- 怀疑论验证模块

### Changed
- 完成第二个里程碑：事件、断言与多情景分析

## [v0.1.0] - 2025-03-22

### Added
- 🎉 初始提交
- 模块化单体分层架构
- 核心领域契约（Pydantic v2）
- PostgreSQL + pgvector 事实存储
- 资产分析卡功能（覆盖八大维度：财务、资金、量价、估值、股东、产业、事件、宏观）
- 专题研究备忘录功能
- 数据层适配器框架
- Model Gateway 抽象（支持多模型提供商）
- 可观测性三件套（logging/metrics/tracer）
- CLI 命令行工具
- 基础测试用例
- 快速开始文档

### Changed
- 完成第一个里程碑：事实层与报告骨架

---

## 开发路线图

### ✅ 已完成
- [x] v0.1.0: 事实层与报告骨架
- [x] v0.2.0: 事件、断言与多情景分析
- [x] v0.3.0: 信号验证与核心功能闭环
- [x] v0.4.0: Web Workbench v1 + Memory Learning + 完整数据采集

### 🔄 进行中
- [ ] Portfolio OS：风险预算、exposure、factor neutrality、theme exposure、liquidity
- [ ] Evaluation OS：Agent/Signal/Timing/Narrative 系统级评估
- [ ] Feedback Learning：根据市场结果更新权重和模型
- [ ] Ontology Layer：行业、事件、因子、regime 分类体系

### 📋 计划中
- [ ] Market Simulation：模拟游资、机构、北向、ETF、散户对事件的反应
- [ ] Causal Engine：counterfactual、intervention、propagation dynamics
- [ ] Orchestration：DAG workflow、event routing、agent scheduling
- [ ] Execution OS：order routing、slippage、liquidity、execution scheduling
- [ ] Alternative Data：招聘、GPU shipment、GitHub velocity、电力、卫星、海运等
- [ ] Temporal Industry Graph：时间化产业链图谱

---

## 相关文档

- **[README.md](../README.md)** - 项目概述与快速开始
- **[REFERENCE.md](REFERENCE.md)** - 完整参考手册
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - 架构文档
- **[FILE_GUIDE.md](FILE_GUIDE.md)** - 文件指南
- **[backup_restore.md](backup_restore.md)** - 备份恢复文档
- **[DATA_SOURCES.md](DATA_SOURCES.md)** - 数据源文档

