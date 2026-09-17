# Research Workbench 文档门户

本页是仓库文档的唯一人工导航入口。项目当前交付面是 Research Web；旧 FastAPI／PostgreSQL、桌面壳和历史实施方案仍可检索，但不会与现役产品并列。

文档状态由 [`documentation-governance.json`](documentation-governance.json) 管理：`current` 表示现役答案，`generated` 表示机器生成，`historical` 表示历史证据，`package-internal` 表示随能力包维护，`cleanup-candidate` 表示等待人工确认的残留。

## 用户入门

| 文档 | 状态 | 受众 | 权威范围 | 更新触发 |
| --- | --- | --- | --- | --- |
| [根 README](../README.md) | current | 使用者 | 产品定位、安装、启动、导航 | 用户入口或安装行为变化 |
| [Research Web 一键安装](research-web-installation.md) | current | 使用者、运维 | 锁定依赖、Doctor、跨平台安装 | 安装器或依赖基线变化 |
| [Research Web UI](research-web-ui.md) | current | 使用者、前端开发 | 页面、交互与 DOM 合同 | 用户流程或 UI 合同变化 |
| [能力与版本](research-web-capabilities.md) | current | 使用者、能力开发 | Skill、Method、Tool、Workflow | 能力目录或版本规则变化 |

## 当前架构

| 文档 | 状态 | 受众 | 权威范围 | 更新触发 |
| --- | --- | --- | --- | --- |
| [系统架构总览](ARCHITECTURE.md) | current | 所有开发者 | 当前系统边界与兼容面 | 顶层边界变化 |
| [Research Web 架构](architecture/research-web/README.md) | current | Research Web 开发者 | 当前产品的唯一详细架构入口 | Research Web 拓扑或合同变化 |
| [Development Map](DEVELOPMENT_MAP.md) | current | 开发者、Agent | 源码区域、文档、测试和更新触发 | 模块所有权变化 |
| [DataHub](research-web-datahub.md) | current | 数据能力开发者 | 15 项能力、22 个来源、Provider 与快照 | DataHub 合同或来源变化 |
| [研究框架](architecture/research-web/08-research-frameworks.md) | current | 框架开发者 | Gold／Dollar 专用合同与共享边界 | 框架生命周期变化 |

## 开发

- [Agent 工作流](AGENT_WORKFLOW.md)：本地快环、worktree、后台／远程和交付证据。
- [参考入口](REFERENCE.md)：当前 CLI、API Atlas、生成索引与兼容平台参考。
- [文件指南兼容入口](FILE_GUIDE.md)：旧文件级手册的退役说明与替代入口。
- [Research Web 文档门禁](research-web-documentation.md)：架构清单、图文检查和安全 Web 入口。
- [前端工作流](frontend/FRONTEND_WORKFLOW.md)：旧兼容 UI 的前端约定；Research Web 以 `app/research_web/ui/` 和其专项文档为准。

## 运维

- [Research Web 运行与用量](research-web-operations.md)：只读健康、用量和存储聚合。
- [GitHub Actions 额度治理](actions-budget.md)：免费分钟、冻结状态、workflow 路由与 artifact 保留。
- [备份、恢复与迁移](backup_restore.md)：当前 Research Web 数据目录、迁移和凭据边界。
- [Research Web 文件交付](research-web-delivery.md)：产物格式、校验和交付状态。
- [桌面打包历史](desktop_packaging.md)：只有明确重启桌面工作时才适用的跨平台门禁。

## 参考与生成物

- [数据源入口](DATA_SOURCES.md)：当前 DataHub 与旧 Connector 平台的分流说明。
- [数据存储](DATA_STORAGE.md)：旧兼容 PostgreSQL 平台的表、契约和迁移参考，不是 Research Web 前置条件。
- [Python 文件索引](generated/py_file_index.md)：由脚本生成，不得手工编辑。
- `outputs/research-web-architecture/`：由架构图源生成的交互式图和校验回执。
- `.ai/reports/`：每个任务的实现、验证和架构影响凭证，不是现役产品说明。

## 历史

历史材料统一从 [归档索引](archive/README.md) 进入。归档内容用于追溯当时的方案和证据，不得作为当前启动、接口、架构或支持状态的依据。

## 维护规则

1. 同一主题只有一个 `current` 权威文档；其他位置只写受众专属摘要或链接。
2. 当前事实优先来自代码、配置、测试和真实运行证据；日期型验收进入 `.ai/reports/` 或归档。
3. 新增 Markdown 必须被治理清单分类；生成文档只能由对应生成器更新。
4. 用户可见变化才进入 `CHANGELOG.md`；实现过程、任务状态和评审流水不进入现役说明。
