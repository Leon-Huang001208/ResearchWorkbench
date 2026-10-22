# Research Workbench

资产观察提供单一沪深北A股代码／名称／简拼搜索、真实专题页签和按需区块缓存；已有观察先显示快照，新证券自动概览与近期前复权历史，图表选择日和累计筹码独立于视区；已完成全历史的过期锚点按新交易日生成独立完整版本，不缩成recent两年。天软封闭结构化数据覆盖估值、按报告期财务、股东汇总／明细、行业分类、两融及公告事件；缺字段、单位和币种不补造，财务partial保留真实缺口。目录按账号与授权指纹隔离，旧观察、不可变快照和唯一DSH保持；源码、局部／真实预检、浏览器、同候选Mac CI及常驻部署分别验收。详见[资产工作台](docs/research-web-ui.md#资产观察工作台)、[数据合同](docs/research-web-datahub.md#资产目录与结构化区块)和[本轮验收记录](.ai/reports/test_report_asset_interaction_data_20261022.md)。

全市场概览提供沪深北A股总览、完整行情表、行业／概念及资金排行；使用东财当前官网股票池，显示实际来源、时间、待上市及覆盖缺口，行情浏览不创建研究会话。详见[市场页面](docs/research-web-ui.md#全市场概览)与[数据合同](docs/research-web-datahub.md#无会话全市场数据)。

FinGPT 自由分析中的数字和推导通过系统引用绑定，正文采用约定长度的中文分析与去重数据表；英文取证底稿保存在同版本审计附件。Host 同时核对实际文件内容与版本，资料和解释证据不足时继续显示质量未通过。

FinGPT 网页研究从取证到交付统一使用系统报告配方：系统处理计算、数字声明、引用笔记、真实数据表和冻结的输出格式，Host 再从实际资料独立核验并绑定版本。缺证据的分析和完整性错误继续保持明确状态，研究仍由 DSH 执行。

FinGPT 的网页数字证据现在经 Host 从有明确期间、核算版本和单位的原文布局提取；历史列表保留当前及旧稿，未绑定检查仍标未核验。误拼回环 origin 的报告 URL 只在文件确属当前检查归档时转回同源；质量门、DSH 与数据根不变。

业务报告有真实数值规范观测时，首次执行和一次补查统一使用现有数据配方生成报告，避免与手写payload指令冲突；真实分析缺口和严格质量门保持。

FinGPT 保留 DSH；正文显式算式由 Host 有界复算，最终回答使用本轮检查归档链接。未绑定或与检查版字节不同的报告别名不会成为已核验交付，旧原件仍保留。

经单独授权的[FinGPT三组隔离比较](docs/research-web-fingpt-comparison.md)可对照DSH、原分支Node与两种模型；实验独立数据、凭据和端口，默认不开启，不改变生产引擎。

FinGPT 可从本会话真实检索登记的公开 HTTPS 来源读取正文，保留身份、内容哈希及报告版本；取证、质量验收和文件交付分别显示，资料不足仍可交付明确标缺口的报告。

“AI资讯”保留完整站内阅读，并接入固定原版自主采编引擎、独立数据库及[采编管理](docs/research-web-ai-news.md)。默认零模型与付费调用；从自主库重新起刊，不读取外站运营数据。当前常驻版切换须完成后续真实模型与预算验收。

macOS Native 新增显式选择的[私网邀请制多用户模式](docs/research-web-installation.md#私网邀请制多用户macos-native)：管理员开账号，Tailscale HTTPS 登录；每位用户独立保存 FinGPT/Claw 会话、附件、产物和模型凭据，研究继续使用唯一 DSH 引擎。首版最多两个同时驻留的用户实例，关闭浏览器后研究继续运行。原单用户入口保留；不自动迁移数据或部署常驻服务。

已有 Mac 常驻实例可在单独授权部署后绑定唯一所有者管理员，原会话、模型配置和钥匙串命名空间原位保留；新用户仍使用独立实例。见[保留既有常驻实例](docs/research-web-installation.md#显式保留既有常驻实例)。

FinGPT 的快速、深入与 Agent 模式统一使用 DSH。研究步骤可调整，用户要求与证据检查保持固定；报告有缺口时可查看、下载并补资料续研，执行结束、质量通过和文件交付分别显示。

Claw 与 FinGPT 共用 Codex 式会话导航：各自保存项目、置顶和排序，支持会话菜单与顶部折叠。
原生提问逐题回答，可明确跳过；收起问题不取消研究，成功答复后保留可展开的问答摘要。

macOS Native 可显式启用[登录后常驻与自动部署](docs/research-web-installation.md#macos-登录后常驻与自动部署)。
保留 FileVault；仅接收已合并、评审和 exact-tree CI 均通过的受管交付，活动研究结束后再更新。
失败恢复上一版本；数据、模型凭据与 Tailscale Serve 保留，敏感或未分类升级暂停人工处理。


Native 可按[安装指南](docs/research-web-installation.md#可选tailscale-私网-https-访问native)
显式启用单个 Tailscale 私网 HTTPS origin；默认仍只接受本机访问，不自动开放公网。
浏览器点击外部链接可打开首页；例外仅限用户触发的顶层 GET 导航，不放开跨站 API。

模型设置按服务商管理多个命名连接，提供 DeepSeek 官方和自定义兼容服务；独立保存凭据，切换只影响新研究默认连接，旧会话及显式选模的研究任务日程保留绑定。见[模型服务设置](docs/research-web-ui.md#模型服务商与连接)。
外部资料源由连接中心显示配置与准入状态，失败会保留明确状态；已保存或已配置不代表实际调用通过。
详见[连接中心](docs/research-web-datahub.md)与[能力合同](docs/research-web-capabilities.md)。

资产观察采用 Wind 风格平面工作区，保留交易/估值、自选、财务、资金、股东、新闻、公告和个人资料。日线历史支持近期2年、续取更早和全部加载，不复权/前复权/后复权保存固定锚点与来源证据；副图默认VOL＋MACD，账号内可选0至4栏。筹码按所选日期的已载入日线前缀估算，缩放不改变同日统计；缺口、失败和取消排空如实显示。详见[资产观察](docs/research-web-ui.md#资产观察工作台)与[批准计划](docs/plans/2026-10-22-wind-asset-workspace.md)。实现、有限厂商预检、最终浏览器/CI和常驻部署分别验收。

Wind工作区v4固定版本部署合同已绑定PR180合并产品`9b436613aad9136f4959c992c89dd72fc7354ed5`，旧版固定5495；产品三项CI已通过，v4操作员的最终测试、评审、CI及实际切换仍须分别验收。旧v3切换失败后已正式恢复5495并保全数据、解除网关fence；旧v1/v2/v3身份和恢复、不可变控制器及严格保全门保持，详见[部署说明](docs/research-web-gateway-upgrade.md#资产观察固定版本联合部署)。

“研究情报”统一本地热点与事件、六个外部栏目，证券新闻/公告迁入资产观察并兼容旧地址；沿AIHOT开源阅读模式适配主题、
日期时间轴和来源卡片，保留工作台品牌。Hot来源配置、频道、关注和周期计划由原PG引擎负责，
与旧Automation开关独立；页面刷新不发起付费请求。

官方来源支持同源声明next的三页有界补抓，部分失败保留原页与待处理材料，覆盖如实显示。
来源页提供启停、间隔与明确目录接入；旧冻结源可经`rwb hot source-configure SOURCE
--expected-revision REV --use-catalog --reason "恢复官方采集"`激活，先停机setup刷新权限。
事件发生/生效日期绑定原材料版本与摘录，未知保持null，日精度不补午夜。

schema21的周期任务会冻结简报，调用既有报告机制生成一次性站内MD/Word，先保存原件及
回执再完成任务；恢复复用回执，下载只读已存字节。升级先停止Hot并setup，保留所有卷。
研究报告、执行终态和报告交付分别显示：已有真实报告的执行仍可因预算终止而failed。
当前验收scope达20calls/79894tokens，100000tokens/USD1上限保持，不再追加模型调用。

真实关系运行包含误判保留、人工纠错、same_occurrence/direct_followup及综合稿跨年关联；
旧v1样本的四条NOT_RUN参考不篡改。回顾留出有候选上下文交叉，不声称独立盲测准确率。
新PG备份按精确数据库文本核验；旧未标记归档保留但须从原库重备份，不改签名绕过。
Native/Docker、联合恢复与干净Mac CI分别绑定候选，旧证据不认证新源；完整交付状态见
[权威进度](.ai/reports/2026-10-12-hot-intel-resume-PROGRESS.md)及[完整合同审计](.ai/reports/2026-10-15-hot-final-contract-audit.md)。

持久文本验收预算仅供显式受管 AES 候选：最多 3 次、每次 512 输出 tokens。旧政策已过期，当前不会启动真实验收或续期；普通运行不发现账本。见[预算设计](docs/superpowers/specs/2026-10-14-pr88-budget-port-design.md)。

Research Workbench 当前交付的是本地优先的 **Research Web**：一个由 FinGPT、Claw、数据能力和研究框架组成的研究工作台。

Claw 在同一研究引擎上组织本地项目、成员会话、带来源的文件与显式引用，并提供日程、技能和 MCP 入口；研究任务须用户“确认创建并启用”后保存生效，创建不立即运行。既有能力任务确认保存后默认停用，另行启用。工作区侧栏保留当前聊天，项目聚合有独立入口。见[Claw 页面合同](docs/research-web-ui.md#claw-项目与日程)。

Claw 搜索可读取原生 DSH 的会话正文匹配片段，仅展示本产品持有的未删除会话；搜索不会启动研究或将其他会话内容自动加入当前问题。原生匹配较多时需缩小关键词，不提供虚构分页。

当前 Web 入口为 `app.research_web.main:app`。Research Web 通过 FastAPI 轻量适配层连接专属 DSH；**DSH 是唯一的研究引擎**，负责研究执行循环、会话历史、Skill 与子 Agent。基础 Research Web 不启动旧 API 生命周期，也不要求 PostgreSQL、pgvector 或桌面预览。

统一「研究情报」入口包含本地热点与事件及六个外部只读栏目；按证券阅读的新闻/公告由资产观察承接。本地部分连接独立 Hot Node 服务及指定 PostgreSQL，提供事件、来源覆盖、频道和人工纠错；Hot 设置仍在设置页。未配置时显示真实状态，页面读取不启动服务或模型。Native 模型工厂支持已有预算下的受控装配与原回执复用；模型默认关闭，配置不能创建付费授权。预算授权、尝试查询及未知尝试终止通过独立 CLI 明确操作，终止不退款。当前实现与配置命令见 [Hot 组件说明](services/hot/README.md)；冻结简报支持固定版本 Markdown/DOCX，继续研究的会话及快照准备已有本地证据。已有真实报告、安装及恢复证据见权威记录；关注、周期简报和最终整镜像仍在验收中，完整 Hot 产品尚未交付。

> 当前产品阶段为 **Web-only**。桌面打包历史仍被保留，但桌面 sidecar、Tauri、安装包和原生桌面 CI 不属于普通 Research Web 的安装或验收前提。

当前主开发与常驻节点为 24GB Mac mini，开发、构建和测试放在 Docker；MacBook Pro 是远程入口。Windows/Linux 原生验收由对应设备负责。固定 DSH 为 0.2.1-alpha.1 的 Fork 提交 `48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0`，安装版本由 `runtimes/research_web.json` 决定。空实例默认 `deepseek-flash`，已有模型 ID 和会话保留，不自动更新已运行的生产实例。

架构阅读从 Settings →「架构文档」或[交互图册](outputs/research-web-architecture/index.html)开始，按产品总览、部署、子系统、关键流程和 API 逐层展开；模块入口关联权威说明、源码与测试。

平台能力及实际证据见[支持矩阵](docs/research-web-platform-support.md)。非 macOS 研究脚本沙箱、Windows Native 架构阅读和 Windows Docker 凭据 ACL 目前存在明确安全边界；Doctor 的实现状态与真机验收分别记录。

## 快速开始

### 前置条件

- Docker 新实例路径（macOS）：宿主 shell、Docker Desktop、Docker CLI/Engine 与 buildx，无需宿主 Python/Node；[开发部署手册](docs/research-web-docker.md)提供 dev/stage/prod 实例入口。Windows cmd 与 legacy Python Docker CLI 保留原合同及未验收边界。
- Native 模式：宿主 Python 3.12、Node.js 22.19+（22 系列）或 24.x、Git；Windows 另需 Visual Studio 2022 Build Tools 的 “Desktop development with C++” 工作负载。

Wind、iFinD、Office 等本机或厂商能力均为可选项；缺少它们不会阻止 Research Web 启动。

### 安装

Mac mini 新实例使用以下入口，默认建立回环端口 18088 的独立 stage 实例：

```bash
./setup-web.sh --runtime docker
./rwb docker stage local doctor
```

当前 Native 入口；`./setup-web.sh` 无参数也默认 Native：

```bash
./setup-web.sh --runtime native
```

Windows Docker 对应入口（真实 Windows Docker 生命周期尚未验收）：

```bat
setup-web.cmd --runtime docker
rwb.cmd web doctor
```

Windows Native 替代入口：

```bat
setup-web.cmd --runtime native
```

跨平台底层入口：

```bash
python scripts/setup_web.py --runtime native
```

Native 安装器创建 checkout 专属 `.venv`；Docker 安装器构建受管镜像，使用单容器内的 DSH 与 Web。两者消费同一带哈希 Web 锁、随包 CJPY 和固定 DSH 合同，不安装数据库、桌面 sidecar 或 Tauri。Docker 的临时认证与运行状态使用容器私有 tmpfs，重启时重建；产品数据和私有凭据分别使用持久 bind。Docker 构建需要网络拉取固定基础镜像和 DSH 依赖；macOS Docker Desktop 已有独立镜像、安装、健康、重启与重建数据保留证据，适用的镜像/宿主提交及限制见支持矩阵；这些结果不认证 Windows/Linux 或厂商授权。

Docker 开发资源的命名、镜像保留、测试收尾与可恢复清理见[资源治理指南](docs/research-web-installation.md#docker-资源命名与收尾)。清理入口默认只预览；正式数据不随停止容器删除，废弃卷先备份并验证恢复。

可在安装后检查运行环境：

```bash
./rwb web doctor
./rwb web doctor --json
```

Windows 请将 `./rwb` 替换为 `rwb.cmd`。

## 启动与管理服务

Research Web 对两种模式使用同一 `rwb web` 命令。Native 管理 DSH 和 Web 两个宿主进程，默认分别为 3081 和 8088；Docker 在单容器内运行两者，默认仅向宿主回环发布 Web 8088。

macOS 启动优先复用已成功记录的端口，否则优先 Web 8088／Native DSH 3081；确认本安装已停止后，
未显式指定的占用端口可自动避让。以 `web status --json` 的实际地址为准。安装器和
`web start/restart` 接受 `--web-port 18088`，Native 另接受 `--runtime-port 13081`；
显式端口被占用会失败。Docker 内部仍固定 8088／3081，不发布 DSH，宿主 3081 无关监听不阻塞 Docker。
已有停止 Docker 容器需要更换绑定时仍返回 `docker_stopped_port_conflict`，不会隐式重建；
这项限制与真实 macOS Docker 验收尚未闭合，不能据单元测试宣称完整端口迭代已交付。

已有数据根缺运行账本时，其他 checkout 的 Web/DSH 仍可能共享该根；未知数据根写者会
拒绝启动，显式新端口也不能绕过。正常 Native 安装 auto-start 可在同次真实生命周期锁下
承接实际创建证明；已结束的 `--no-start` 或既有目录不继承 fresh，详见安装指南。

```bash
./rwb runtime status --json
```

仅在需要切换时二选一；若当前受管模式仍在运行，须显式允许先停止：

```bash
./rwb runtime use docker --stop-current
```

```bash
./rwb runtime use native --stop-current
```

从仓库根目录运行：

```bash
./rwb web start
./rwb web status
./rwb web logs --tail 100
./rwb web stop
```

Native 可在确认没有活动研究时普通重启；Docker 运行中无法认证证明研究空闲，必须显式 `--force`，这会中断研究：

```bash
# 仅 Native
./rwb web restart
```

```bash
# 仅 Docker，显式中断研究
./rwb web restart --force --no-open
```

服务启动后访问 [http://127.0.0.1:8088/#/fingpt](http://127.0.0.1:8088/#/fingpt)。`start` 是幂等的；终端关闭不会停止受管服务。切换、停止和重启都要求可验证的本项目所有权，不接管未知进程或容器。Docker 模式暂不承诺宿主 Office/Wind/Tabbit 等本机集成可用；能力目录出现不等于已配置或可调用。具体升级、修复、凭据与数据目录见[安装指南](docs/research-web-installation.md)。

网页打不开时，先运行 `./rwb web status` 和 `./rwb web doctor --json`。即使 checkout 的 `.venv` 缺失或损坏，这两个只读诊断入口也会报告 Python 环境问题并提示运行公开安装器；该后备入口不会启动或停止服务。正常启动会等 DSH、Web API、首页和主静态模块就绪后再打开浏览器。模型密钥未配置时仍可打开设置页，Doctor 会单独报告模型问题。

## 模型、数据与迁移

受管 Docker 候选支持显式初始化实例专属加密模型凭据和主密钥只读卷；操作与最小恢复材料
见 [Docker 手册](docs/research-web-docker.md)。设置页保存与真实生成分别验收，Native Keychain 保留。

### 模型配置

在产品的 **Settings（设置）→ Model（模型服务）** 中配置固定 Runtime 支持的 DeepSeek 模型。API Key 留空保留、填写替换、独立按钮清除；已有会话保留选模，任务运行时拒绝配置变更。保存、Runtime 可达与真实生成分别展示，生成测试由用户显式发起。

macOS Native 的模型凭据由产品 overlay 挂载的固定用途桥接存入系统 Keychain，按规范化 data home 隔离；不回退环境、旧凭据 YAML 或 `.env`，也不把 Keychain 值复制到文件。不迁移旧模型 Key，需在该实例设置页重新录入。Host 浏览器认证 record 保留固定 DSH 的受控文件实现，和模型 Key 分开。其他平台或 Keychain 不可用时模型失败关闭，设置页与 Host 认证仍可使用；其他平台系统模型存储尚未验证。

管理器明确绑定 `docker-encrypted` 时，使用 AES-GCM 密文和独立只读主密钥卷，与 Fernet 格式不互转。Docker 通用业务凭据与实例加密模型后端分别管理，不把 Native Keychain 保证泛化到容器。
Docker 模型实际生成和重建验收见本轮回执，不从 configured 或健康推断通过。AES 载入认证全部已有模型记录；错误实例、密钥或外来记录明确拒绝，不遮蔽为未配置的新写目标。
常规 staged Docker 的 `docker-encrypted-file`（Fernet）模型凭据使用显式绑定的加密文件后端，保存在独立私有凭据挂载的 `models/` 子目录；API Key 不以明文写入产品索引、旧 YAML 或镜像。主密钥与密文同卷，不防御能读取整个挂载的同 UID 进程或管理员。现有通用业务凭据原样保留，不读取或迁移 Native Keychain；请在当前 Docker 实例的设置页录入模型 Key。保存、重启恢复与真实生成分别验收，不把后端存在当成模型可调用。

DataHub 连接凭据按规范化 data home 隔离系统凭据服务；不同实例互不读取、覆盖或清除。旧全局记录不自动迁移或回退，已有非秘密配置保留，升级后请在所属实例设置页重新录入数据源凭据；旧记录不会被删除。

### 旧 Research Web 数据迁移

从旧研究目录迁移前，先查看不写入的摘要：

```bash
./rwb migrate-research-data --dry-run
```

确认后执行迁移：

```bash
./rwb migrate-research-data
```

该操作复制研究会话、附件、能力版本、数据集和产物，但不会复制凭据。迁移完成并完成恢复验证后，如需将来源目录保留为只读备份，可显式使用 `--archive-source`。

### 运行时目录与日志

Research Web 使用用户私有目录保存运行状态与数据：

- `~/.research-workbench/research-web/`：两种模式顺序使用的同一研究会话、附件、数据集、产物和其他产品数据；切换前必须停止当前运行时。
- `~/.research-workbench/run/`：Native 受管进程的 PID 与命令归属状态；Docker 认证状态位于容器私有 tmpfs `/state/runtime`，每次启动/重启正常重建，不复用 Native 认证/PID 文件。
- `~/.research-workbench/logs/`：受管运行时与 Web 服务日志。
- `~/.research-workbench/install/runtime.json`：当前选择与安装身份；Docker 宿主 `run/docker/<installation-id>/logs` 单独持久绑定，旧 `run/docker/<installation-id>/runtime` 内容保留、不迁移；凭据仍位于 `secrets/docker/<installation-id>/`，均不等同于产品数据目录。
- `~/.research-workbench/runtime/dsh/<commit>/`：固定提交的项目私有 DSH 源码与构建来源。
- `~/.research-workbench/install/manifest.json`：安装摘要与诊断状态。
- `logs/setup-web.log`：仓库内的一键安装日志。

这些目录均服务于当前用户和当前项目管理器；不要将其中的状态文件、日志或安装清单作为跨机器配置复制手段。

## 产品导航

研究台的 **ETF 模拟** 提供固定规则与显式约束的工程回放、模拟账本和复盘。
真实数据与计算准入未闭合，真实链路保持 `BLOCKED`；上传不授予准入，示例结果不证明投资收益。
完整边界见[数据与文件合同](docs/architecture/research-web/03-data-files.md#etf-工程模拟与真实准入边界)。

当前主导航由以下页面组成：

- **FinGPT**：研究对话入口与会话管理。
- **Claw**：可使用 Workflow、资料和产物的研究空间。
- **Asset Observation（资产观察）**：按需查看资产相关数据。
- **Research Workbench（研究台）**：市场、资产、基金、行业与文档的工作台入口。
- **Capability Center（能力中心）**：Skill、Method、Tool、Workflow 与数据能力目录。
- **研究情报**：事件、研报、赛道资讯、快讯与社交内容的原生只读页面；使用 Golddata 现成接口，支持原文阅读与 A 股代码查询。
- **Research Frameworks（研究框架）**：独立的研究框架与快照驱动分析。
- **Operations and Usage（运行与用量）**：只读聚合模型用量、Agent、工具、DataHub、服务健康与存储情况。
- **Settings（设置）**：通用、模型服务、数据源、本机集成与架构文档。

DataHub 是 Research Web 进程内的数据目录、白名单路由、Provider 适配和会话快照层；它不是第二个研究引擎或全局行情数据库。页面展示的来源状态会区分“已登记”“已配置”“依赖就绪”和“当前可调用”，避免把可发现能力误当作已验证的数据连接。

## 开发与平台验收

MacBook Pro 负责项目功能开发、macOS 本地验收与 GitHub macOS CI。Windows 和 Linux 真机分别负责已有功能的本平台适配、本地验收与对应 GitHub CI，不承担功能开发。其他平台待验收不阻塞当前宿主任务，已验证支持范围仍以各平台实际证据为准。详见 [Agent 任务路由指南](docs/AGENT_WORKFLOW.md)。

## 文档

- [文档门户](docs/README.md)：按入门、架构、开发、运维、参考和历史组织的唯一索引。
- [Research Web 当前架构](docs/architecture/research-web/README.md)：当前产品的唯一架构入口、运行边界与阅读路径。
- [Research Web 一键本地安装](docs/research-web-installation.md)：完整安装前提、固定制品与跨平台安装门禁。

## 历史功能

旧 `app.api.main:app` FastAPI 工作台、量化业务、数据库迁移与 PostgreSQL/pgvector 架构仍保留在仓库中，供历史兼容和维护参考；它们不是当前 Research Web 的启动、使用或开发前提。请以本 README 和 [Research Web 当前架构](docs/architecture/research-web/README.md) 为准。

## 许可证

MIT License

能力详情的数据准入范围独立于模型健康：硬条件缺失阻断，可选条件缺失按声明省略章节；旧快照与资源全集不代表当前执行授权。当前Mac验证不扩展成其他平台或所有供应商品牌支持。


## 单一兼容模型连接

设置页支持固定 DeepSeek 官方目录及一种 OpenAI Chat Completions 兼容文本/流式连接。兼容连接显式配置非秘密 base URL 和模型 ID，专用 Key 与官方 Key 隔离；本机无Key模式不读取凭据。模型工具能力未经实测时保持未验证；保存、Runtime应用、真实生成与真实账户验收各自留证，不承诺全品牌支持。

### 框架核心看板

Gold／Dollar 使用同源嵌入页面，共用本站原生数据快照和 Bot 版本绑定；其余九套框架明确为静态导入快照。回测、策略和模型拟合未接入，不能由页面可见推断实时数据或模型验证已完成。

研究情报包含本地热点与事件（`#/intel/hot`，需配置Hot/PostgreSQL）及外部只读资讯；状态、版本和覆盖范围分别展示，已取得材料的完整存储版本/原始响应冻结与DOCX内核已有本地证据；完整Hot研究会话、恢复和安装闭环仍在验收中。

Hot研究交接已具备固定PG运行映射、原生会话恢复与DataHub原件副本的准备接口；当前返回草稿，正式付费研究及其验收仍在实施。

Hot冻结FinGPT研究现使用轻量DSH组合并有界核验原件；真实Markdown报告已生成且通过文件交付核验。累计scope限额保持100k tokens／20次／USD1；收尾请求被预留上限拒绝的原生failed状态保留，不能据文件存在认证完整运行或安装交付。

研究情报新增“研究与报告”，可读取真实报告、核对原运行状态及下载MD/Word。运行失败但报告已生成的状态并列保留；页面刷新与导出不发送模型请求。

Host元数据专项升级在用户单独授权后走显式、精确候选的兼容复核入口；原自动升级清单不变，活动研究延后，失败回滚且保留数据。命令与边界见[安装指南](docs/research-web-installation.md#macos-登录后常驻与自动部署)。
