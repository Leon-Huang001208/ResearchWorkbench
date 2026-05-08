# 更新日志

所有 notable 项目变更都记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- **#24** Add `bootstrap_db` one-step database bootstrap script (schema initialization, connectivity check, idempotent seed defaults for alerts)
- 交互式 Web 前端界面
- FastAPI 后端 API
- 审核工作流 API
- 支持 SQLite 零配置启动（无需 PostgreSQL）
- 扩展 AssetAnalysisSnapshot 新增 `technical`（技术指标）和 `sentiment`（情绪）维度
- 实现完整的双源降级路由策略（iFinD → ChinaStock → insufficient_evidence
- 更新 IFinDAdapter 适配器支持技术指标和情绪数据获取
- 更新 ChinaStockAdapter 适配器支持情绪数据获取
- **#12** 模拟交易与组合仿真工作流（Paper Trading + Simulation + 基准比较）
- **#13** Model/Prompt/Strategy 治理与实验追踪（版本管理、实验对比、回滚、审计）
- **#14** 生产级监控、漂移检测和告警系统（健康指标采集、分布漂移检测、可配置阈值告警、事件记录）
- **#15** 分析师人在回路决策控制台（每日候选审核、决策动作记录、理由捕获、复盘视图、审计追踪）
- **#16** 生产级持久化替换内存 fallback（dev/prod 模式，生产环境禁用静默 fallback，所有实体默认持久化到 PostgreSQL）
- **#17** 标准化 A 股 alpha 事件结构化摄入 pipeline（支持政策/公司公告/海外科技映射三类事件，每个类别 20 个示例）
- **#18** 产业链映射和 thesis 生成引擎（最小高价值产业链图谱，传播路径生成结构化投资 thesis，带强度评分）
- **#19** 证据驱动的 Bull/Bear/Skeptic 结构化审查框架（每张 thesis 必须包含多维度对抗性审查，证据可追踪，硬规则强制要求反对意见才能进入候选/验证阶段）
- **#20** 集成择时引擎和事件研究验证，实现统一就绪度评分（分离投资逻辑质量、历史胜率、市场时机匹配度三个维度，低就绪度自动拦截候选生成）
- **#21** Week 7: 将工作台重新设计为研究优先的操作系统式控制台
  - 新首页布局包含五个板块：Today、Research Queue、Candidate Board、Learning、全局搜索
  - 新增 Dashboard API 和数据聚合服务整合 #18/#19/#20 数据
  - 实现完整跨对象全局搜索支持 symbol/event_type/thesis/source_doc/failure_memory/market_episode
- **#22** Week 8: 构建结果反馈循环和失败记忆引擎
  - 新增 Outcome Journal 持久化存储交易结果
  - 标准化失败分类：wrong_thesis / timing_error / crowding_error / regime_misread / mapping_error / evidence_weakness / execution_error / risk_error
  - 失败记忆引擎：基于 thesis 文本相似度自动检索相似历史成功/失败案例
  - 每周回顾报告生成器，自动统计成功率和失败分布
  - 新增完整 API 路由：记录 outcome / 检索相似案例 / 生成周报告
  - 所有单元测试通过

### Changed
- **#23** Migrate default persistence from SQLite to PostgreSQL: PostgreSQL is now the recommended durable default, SQLite remains as zero-config demo option
- 默认启用持久化模式
- 澄清数据存储策略
- 整合文档到 README 和 REFERENCE.md

### Fixed
- Word 文档投影错误
- Pydantic V2 弃用接口警告修复
- CLI 错误处理修复
- 向量搜索结果排序问题修复
- 资产分析服务依赖修复
- 数据摄入服务错误修复
- 导入错误和字段名冲突修复
- 数据库初始化流程修复

## [v0.3.0] - 2025-05-01

### Added
- 信号实验室完整功能
  - 特征工程框架
  - 标签工程框架
  - 信号评分系统
  - 回测框架集成（vectorbt + Backtrader）
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
- CLI 命令行接口
- 基础测试用例
- 快速开始文档

### Changed
- 完成第一个里程碑：事实层与报告骨架

[Unreleased]: https://github.com/leon/AlphaFoundry/compare/v0.3.0...HEAD
[v0.3.0]: https://github.com/leon/AlphaFoundry/compare/v0.2.0...v0.3.0
[v0.2.0]: https://github.com/leon/AlphaFoundry/compare/v0.1.0...v0.2.0
[v0.1.0]: https://github.com/leon/AlphaFoundry/releases/tag/v0.1.0
