# Changelog

本文件只记录用户可见的现役产品变化。实现过程、任务状态、架构评审流水和验收细节进入 `.ai/reports/`；2026-09-17 以前的完整历史流水保存在 [历史 Changelog](archive/history/changelog-through-2026-09-17.md)。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。仓库当前仍使用 `0.1.0` 包版本，因此未正式发布的变化统一记录在 `Unreleased`。

## [Unreleased]

### Changed

- 2026-09-17：`Research Web Tabbit Verify` 暂停普通 push／pull request 自动触发，仅保留手动运行；双平台合同套件保持不变，轻量触发器契约继续由 Project Constraints 自动验证。
- 2026-09-17：建立唯一文档门户和机器可读治理清单；当前、生成、历史、包内与待清理文档不再混用。
- 2026-09-17：Research Web 成为 README、架构和开发映射中的唯一当前产品入口；旧 FastAPI／PostgreSQL 与桌面说明降级为兼容参考或历史。
- 2026-09-17：文档同步门禁改为按源码区域更新权威文档，并增加未分类 Markdown、重复权威、断链、退役命令和生成索引漂移检查。
- 2026-09-17：根 README 改为 Web-only 安装、启动、迁移和产品导航入口，并加入可复核的 README 影响回执。
- 2026-09-16：Web 一键环境固定项目专属 Python/Node/DSH/CJPY 依赖，并提供 `rwb web doctor`。
- 2026-09-16：DataHub Provider 与统一集成协调器完成现有公开来源闭环；专业来源仍按真实授权和探测结果显示状态。
- 2026-09-14 至 2026-09-16：加入 Gold／Dollar 研究框架、Method 层和 CPU 有界研究 Skill；框架定义和快照保持领域专用。

### Security

- 密钥继续只进入产品设置和操作系统凭据库；文档、迁移、日志和备份说明均不复制秘密。
- Research Web、DataHub、MCP 和文件读取继续使用回环、固定目录、路径身份与显式授权边界。

## 历史版本

- [2026-09-17 以前的实现流水与 v0.1.0–v0.4.0 记录](archive/history/changelog-through-2026-09-17.md)

路线图不属于 Changelog。只有已经批准且仍有负责人、验收和当前状态的计划，才应进入独立的现役规划入口；本轮未发现满足该条件的统一路线图。
