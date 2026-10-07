# Research Workbench Research Web 当前架构

这是当前研究产品的唯一架构主入口。Research Web 组织研究页面、框架、能力与文件，专属 DSH 是唯一研究执行循环。当前任务按 macOS Native / Mac Docker Desktop 与 Windows/Linux 对应设备分工验收；源码同时保留 `app/research_web/`、`research_workbench_entrypoint/`、`docker/` 与共用运行合同，Docker 实现按运行宿主与镜像架构分别验收；未验证项见 [支持矩阵](../../research-web-platform-support.md)。Native 双宿主进程与 Docker 单容器是互斥运行方式，顺序共享产品数据。旧 `app/api`、量化业务和 merged-platform 图文保持历史身份，不作为本入口依赖。

当前固定 DSH 为 Fork 提交 `48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0`（0.2.1-alpha.1），版本以 `runtimes/research_web.json` 为唯一来源。owned overlay 通过原生声明式 preset registry 挂载既有 research-web、framework-explain、framework-verify；仍由同一 Host、Runtime、DataHub 和协调器执行，Automation 不另建调度路径。升级验收针对独立 macOS Native 实例，不表示生产实例已经更新。

设置中的模型服务只展示固定DSH实际支持目录，保存与显式生成分别验收。配置和测试共用ResearchService串行边界；既有Automation仍通过相同create/send执行，新会话采用新默认值，活动任务阻止共享凭据变化。macOS Native 的固定模型 ref 由产品 provider/私有进程桥接存入系统 Keychain；Host 认证 record 保留固定 DSH 的独立文件实现。没有新增执行器、调度器或凭据中心。

研究布局、能力中心与架构更新检查已实施。当前 Web 包含研究台按需数据入口、独立资产观察、Claw 具体报告 Workflow、会话快照交接、实际产物及只读“运行与用量”聚合；DataHub 同时迁入天软 CJPY 的四项已实现能力，并加入只复用现有 WindAdapter 封闭方法的受限 Wind binding，缺少本机依赖、登录或等价字段口径时仍失败关闭。东方财富基金和财联社是当前无需专业配置即可真实调用的来源。研究脚本由宿主 FIFO 串行、Python 3.12 readiness 和 `cpu_bounded_v1` 公共预算约定共同约束；不依赖 GPU，Seatbelt 仍仅支持 macOS。Phase 2A 提供只读 MCP Registry；Phase 2B 增加不可变安装、官方 SDK Host、OAuth、工具分级、会话授权、人工审批和 DSH 原子激活回滚；Phase 2C 增加锁定版本的通用 Automation、独立 Claw Run 与研究/投递双状态。当前限制见 [架构状态](status.md)，逐任务证据进入 `.ai/reports/`。图形通过不替代产品、数据覆盖或真实连接审查。

## 阅读顺序

首次阅读先打开[交互图册](../../../outputs/research-web-architecture/index.html)：产品/系统总览 → 运行结构与部署 → 子系统分图 → 关键业务流程 → API 与代码细节。重要模块的阅读卡片使用稳定标识，将职责、分图、说明、API、源码和测试放在同一入口。

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
11. [Web Native/Docker 安装](../../research-web-installation.md)：共用依赖合同、模式切换、固定 DSH/CJPY、Doctor 与分模式平台门禁。

可交互图文位于仓库 `outputs/research-web-architecture/`，也可从 Web 设置的「架构文档」打开。JSON 图源在本目录 `diagrams/`。既有十图与新增 `00-system-overview` 均以实际源码为依据；`01-deployment` 展示单一源码与数据模型下的 Native/Docker 分支。各图的自动 showcase、四视口和人工截图结论以各自当前哈希回执为准；图形证据与产品、镜像和平台验收分开保存。

## 不在本轮范围

不新增 PostgreSQL 前置条件、Evidence/Claim、第二研究引擎、线上 Skill 商店或桌面适配。MCP Registry 身份保持 `(registry_id, server_name, version)`；第三方字段按有界纯文本处理且不热链图标。Publisher 只生成外部 CLI 交接材料并明确 `executed:false`。MCP 不实现 sampling、elicitation、实验性 Tasks、任意 shell、版本范围、隐式环境继承或无人值守高风险调用；Automation 不静默升级目标、不自动重试研究，也不批量追赶遗漏。研究台市场页是按需查询和快照入口，不是旧市场首页或后台行情管线。

## 启动与验收基线

新用户可优先运行 `./setup-web.sh --runtime docker`；`./setup-web.sh --runtime native` 与无参数入口保留 Native。Windows 对应 `setup-web.cmd --runtime native|docker`，但真实 Windows Docker 生命周期未在本轮验证。安装器不会写入全局 Python/Node。随后从仓库根目录使用项目命令。管理器仅处理所有权可证实的项目进程或容器，端口已有其他服务时直接失败：

```bash
./rwb runtime status --json
./rwb runtime use docker
./rwb web start
./rwb web status
./rwb web restart
./rwb web stop
```

模型仅在产品设置中授权。Native 专属运行时使用宿主回环 3081，Web 使用 8088；Docker 只向宿主回环发布 8088，DSH 3081 留在容器内。用户原 3080 不被更改。后台状态、凭据和日志按运行模式隔离；研究数据位于共用 `~/.research-workbench/research-web/`。切换前需安全停止旧模式，不在两个模式下并发访问数据。

旧研究目录先用 `rwb migrate-research-data --dry-run` 查看迁移摘要，再执行复制。凭据不会迁移；新实例需在设置页重新填写。Web 恢复验证通过后可使用 `--archive-source` 将旧目录改为只读迁移备份。

日期型验收、具体会话和任务命令位于 `.ai/reports/`；历史 Research Web 验收已进入 [归档](../../archive/acceptance/research-web-acceptance-2026-09-02.md)。这些记录只证明当时的环境和路径，不能替代当前任务复验。

## 当前验收原则

- 文件结构有效不等于报告内容合同完整；运行、交付和内容质量分别记录。
- 外部数据、模型、Office/Wind、浏览器和平台支持只对本次实际验证的环境成立。
- 旧分支、会话、产物或验收记录不决定当前 Git 交付状态；每次交付以本次 Harness、CI 和任务报告为准。

## 历史证据

日期型稳定性核对已移至[阶段一任务报告](../../../.ai/reports/2026-10-06-architecture-reading-stage1.md)。

## 设置闭环阶段3：当前能力范围

现有Host/DataHub私有通道同时承担能力准入；DSH通过工具执行与原生用户技能注入的既有事件重检。没有新增研究引擎、来源注册中心或Vault。


## 单一兼容模型连接

单一兼容文本/流式模型适配位于既有Runtime，私有非秘密配置沿同一Host/DataHub通道读取，系统ref仍沿原进程桥接；没有新增研究引擎、模型代理daemon或Vault。Native macOS合成冷启动与真实供应商验收分别记录；本模型连接任务未执行其他平台验收，项目总平台范围以支持矩阵为准。
