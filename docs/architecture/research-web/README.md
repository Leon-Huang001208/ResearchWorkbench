# Research Workbench Research Web 当前架构

这是当前研究产品的唯一架构主入口。源码范围为 `app/research_web/`；旧 `app/api`、量化业务和 merged-platform 图文属于历史，不是此入口的依赖。

研究布局、能力中心与架构更新检查已实施。当前 Web 包含研究台按需数据入口、独立资产观察、Claw 具体报告 Workflow、会话快照交接、实际产物及只读“运行与用量”聚合；DataHub 同时迁入天软 CJPY 的四项已实现能力，并加入只复用现有 WindAdapter 封闭方法的受限 Wind binding，缺少本机依赖、登录或等价字段口径时仍失败关闭。东方财富基金和财联社是当前无需专业配置即可真实调用的来源。研究脚本由宿主 FIFO 串行、Python 3.12 readiness 和 `cpu_bounded_v1` 公共预算约定共同约束；不依赖 GPU，Seatbelt 仍仅支持 macOS。Phase 2A 提供只读 MCP Registry；Phase 2B 增加不可变安装、官方 SDK Host、OAuth、工具分级、会话授权、人工审批和 DSH 原子激活回滚；Phase 2C 增加锁定版本的通用 Automation、独立 Claw Run 与研究/投递双状态。当前限制见 [架构状态](status.md)，逐任务证据进入 `.ai/reports/`。图形通过不替代产品、数据覆盖或真实连接审查。

## 阅读顺序

前端外观以 [Research Web 外观与主题](../../research-web-appearance.md) 为准：Codex 风格、Light/Dark 与用户原图符号；不改变下述服务部署和研究契约。

1. [部署与职责](01-system.md)：启动路径、模块边界和存储归属。
2. [研究协议与状态](02-research-runtime.md)：提交、SSE、恢复、审批、停止及页面交接。
3. [数据与文件](03-data-files.md)：研究台、DataHub 静态目录、路由、资料快照、附件、产物和独立交付。
4. [接口清单](04-api.md)：当前路由与请求边界。
5. [安全与验证](05-security-validation.md)：可执行边界、测试层次与未覆盖部署。
6. [文档清单契约](06-documentation-contract.md)：仓库内门禁、更新标记与负向验收。
7. [能力管理](07-capabilities.md)：Skill、Tool、Workflow、数据目录，及包、版本、原生发现和会话只读资源。
8. [运行与用量](../../research-web-operations.md)：真实 usage、Agent、工具、DataHub、服务健康和项目存储聚合。
9. [研究框架](08-research-frameworks.md)：Gold/Dollar Hub、连续专属画布、真实采集、快照 Bot 与渐进抽象边界。
10. [统一集成协调器](09-integration-coordinator.md)：数据源与本机能力的五阶段状态、启动/手动探测、授权和持久证据。
11. [Web 一键本地安装](../../research-web-installation.md)：项目专属依赖、固定 DSH/CJPY、Doctor 与 macOS/Windows 持续安装门禁。

可交互图文位于仓库 `outputs/research-web-architecture/`，也可从 Web 设置的「架构文档」打开。JSON 图源在本目录 `diagrams/`。十图均以实际源码为依据；本轮新增报告运行序列与 Excel 数据流，并更新模块依赖、运行状态和交付状态。最终图均达到 showcase 9/9、零错误零警告，并通过四视口检查与人工截图核对。图形证据与产品验收分开保存。

## 不在本轮范围

不新增 PostgreSQL 前置条件、Evidence/Claim、第二研究引擎、线上 Skill 商店或桌面适配。MCP Registry 身份保持 `(registry_id, server_name, version)`；第三方字段按有界纯文本处理且不热链图标。Publisher 只生成外部 CLI 交接材料并明确 `executed:false`。MCP 不实现 sampling、elicitation、实验性 Tasks、任意 shell、版本范围、隐式环境继承或无人值守高风险调用；Automation 不静默升级目标、不自动重试研究，也不批量追赶遗漏。研究台市场页是按需查询和快照入口，不是旧市场首页或后台行情管线。

## 启动与验收基线

新用户先运行 `./setup-web.sh`（macOS）或 `setup-web.cmd`（Windows）；安装器不会写入全局
Python/Node。随后从仓库根目录使用项目命令。管理器只启动和停止指纹匹配的项目进程，端口已有其他服务时直接失败：

```bash
rwb web start
rwb web status
rwb web restart
rwb web stop
```

模型仅在产品设置中授权。专属运行时使用 3081，Web 使用 8088；用户原 3080 不被更改。后台状态和日志保存在 `~/.research-workbench/`，终端退出不结束服务。

旧研究目录先用 `rwb migrate-research-data --dry-run` 查看迁移摘要，再执行复制。凭据不会迁移；新实例需在设置页重新填写。Web 恢复验证通过后可使用 `--archive-source` 将旧目录改为只读迁移备份。

日期型验收、具体会话和任务命令位于 `.ai/reports/`；历史 Research Web 验收已进入 [归档](../../archive/acceptance/research-web-acceptance-2026-09-02.md)。这些记录只证明当时的环境和路径，不能替代当前任务复验。

## 当前验收原则

- 文件结构有效不等于报告内容合同完整；运行、交付和内容质量分别记录。
- 外部数据、模型、Office/Wind、浏览器和平台支持只对本次实际验证的环境成立。
- 旧分支、会话、产物或验收记录不决定当前 Git 交付状态；每次交付以本次 Harness、CI 和任务报告为准。

## 2026-09-23 稳定性变更回执

本轮只收紧非强制重启的活动会话授权、会话/子 Agent 目录的并发有界读取，以及前端每个目录独立的
pending count、generation、逐资源 settled 与 latest-request-wins 账本。只有 runtime pending 和
settled runtime failure 分别投影为可见 connecting/offline。阅读顺序、文档权威关系、十图清单、
模块边界、Automation 与信息架构均未变化；外部 CI 和真实浏览器验收另由后续交付阶段记录。
