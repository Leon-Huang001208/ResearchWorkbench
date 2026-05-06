# 更新日志

所有 notable 项目变更都记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- 交互式 Web 前端界面
- FastAPI 后端 API
- 审核工作流 API
- 支持 SQLite 零配置启动（无需 PostgreSQL）
- 扩展 AssetAnalysisSnapshot 新增 `technical`（技术指标）和 `sentiment`（情绪）维度
- 实现完整的双源降级路由策略（iFinD → ChinaStock → insufficient_evidence
- 更新 IFinDAdapter 适配器支持技术指标和情绪数据获取
- 更新 ChinaStockAdapter 适配器支持情绪数据获取

### Changed
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
