# RWB 成熟工具复用：清单、实证与迁移方案

**保留 FinGPT“金融 ChatGPT”和 Claw“金融 Codex”，逐步复用成熟问答、执行、检索、分发与流程组件；RWB 主责收敛到金融语义、授权、证据与质量。目前直接删除 0 项，后续按等价验收退出重复实现。**

宿主：Mac mini/macOS；功能研究及有限验证。本文为 2026-11-22 任务快照，不提供 Windows/Linux 原生证据。Codex 接手后，Native LEO-51 仍是 `BLOCKED`、16/20、两轮 QA 上限、0 行业务源码、无 PR，不改历史。

Product-Progress: not-required — 本仓改动记录选型与来源证据；独立 WeKnora 实例的运行模式切换另留操作回执，未替换 RWB 产品界面或内核。

区分源码、版本、替身、真实协议、真实模型、业务质量、生产启用七层。[完整模块、源码路径和退出责任清单](2026-11-22-rwb-module-reuse-inventory.md)覆盖 13 主导航、其他系统入口与七项支撑底座；原盘点基线 `466f2d1`，本树已正常前移 `92ae4ae`，knowledge/runtime/tools/store/tenant 增量保留。

本批采用顺序：先使用已开放的 **WeKnora 完整 App** 验证 FinGPT 通用问答与 Claw 研究执行，现有 AlphaDesk／DSH 路径维持兼容，不再预设完整 DSH 挂载已经可用。腾讯 SkillHub 先接发现与可审来源；讯飞 Registry、LoopForge 与 OpenBB 保留候选，未证明能退出重复代码前不新增长期服务。DSH 全 Host 实测失败及上游包身份缺口会影响采用决定，不能以“成熟工具”名称代替验收。

## 13 个主导航与保留责任

| 导航 | 可复用层 | RWB 继续负责 |
|---|---|---|
| FinGPT | 已有 AlphaDesk；比较 DSH、WeKnora 完整 Agent | 金融问答、来源权限、引用、旧会话、报告质量 |
| Claw | 对照 WeKnora 完整 App 与 DSH 原生工作台；DSH 当前启动阻断须先解决 | 金融工具、项目/文件、审批、预算、恢复 |
| 报告生产 | DSH、WeKnora、窄 SOP | 模板、Wind/Excel 底稿、确定性装配/交付 |
| Research Bot | 已有 Automation/DSH | 冻结定义、Radar 时效、唯一调度/Run/投递 |
| 全市场概览 | 已覆盖的 OpenBB Provider | 证券/交易日、单位、缺项、评分 |
| 资产观察 | Provider、检索、原生执行组件 | 复权、量额、快照、档案版本与撤权 |
| 研究情报 | 检索、成熟研究执行 | 许可、发布/取得时间、事件版本/去重 |
| AI 资讯 | 检索、摘要、窄采编 SOP | 采编原件、故事版本、版权与批准发布 |
| 研究框架 | Skill 发现/分发、成熟执行 | 金融方法、评分版本、输入快照与 Renderer |
| 策略模拟 | 来源适配、通用步骤 | 确定性计算、PIT/无前视、组合裁决/交易禁门 |
| 能力中心 | SkillHub 来源/分发、DSH 加载 | 唯一目录、pin、依赖审核、审批与会话固定版 |
| 定时任务 | 经对拍的流程编辑/步骤执行 | 同意、幂等、重叠策略、预算、UNKNOWN 恢复 |
| 运行与用量 | 原生事件、日志、执行详情 | 账号/Run/报告绑定、真实计费、终态与质量 |

专业协作、设置、账号、历史、进展等系统入口，保留复核、配置、租户、引用和交付状态。

七项底座：DataHub 语义/快照；`knowledge_backend/` 用户/current-hit；`mcp_facade/` 宿主授权；Store/产物 ID/hash/冻结/质量；Hot 原事实库/唯一队列；runtime/安装准入/恢复/部署；凭据/租户/本机隔离与 Office/Wind。通用组件可复用。

## WeKnora 应按完整产品评估

用户允许全部功能。现役 standard-r2 五服务：`v0.9.0`/`f17ee8a`，固定镜像 `0fae…`；本地补丁二进制未完整重算，不冒称上游逐字相同。已在原操作锁内将 `WEKNORA_RETRIEVAL_ONLY` 从 `1` 改为 `0`，只重建 app，健康通过；其他四服务身份及镜像、原数据挂载保持。`/mcp/endpoint` 从专用 profile 403 变为正常 Bearer 401，证明全局限制已解除、认证仍在。保留 KB、账号、原文、embedding、摘要/图谱配置与恢复材料，不批量回填；功能配置与业务验收另列。

后续认证检查发现原 RWB 正式绑定 JWT 已过期；一次沿现有登录引用的正常登录虽然成功，返回身份却与该绑定不同，因此在读取资源之前停止，未改绑定、未写入新 token 或使用其他账号替代。模型、Agent、Skills、MCP 和沙箱的已配置状态仍未取得正式用户验收，不能将模式解除写成全部已配置可用。

| v0.9 能力 | RWB 当前边界/验收 |
|---|---|
| 解析、索引、检索 | 已有薄适配；保留用户/文档授权、原文/current-hit |
| Agent、Skills、MCP | 上游具备；金融工具、依赖/权限/恢复待验 |
| 子 Agent/协作 | 上游具备；两真实子任务、预算/独立复核待验 |
| 终端、文件、产物 | 上游具备；隔离、编辑/diff、取消/质量待验 |
| 引用、工具过程可视化 | 已有上游能力；不等于金融口径/PIT/报告合格 |
| Embed Widget | 问答而非完整 IDE；无完整 Toolbox，访客无 RWB 身份/来源权限、引用不读原件 |
| RWB 金融接入 | 已有 JWT/资料映射；完整 Agent 未等价 |

v0.9 固定官方依据：[Agent](https://github.com/Tencent/WeKnora/blob/v0.9.0/website-docs/03-features/07-agent.md)、[Skills 沙箱](https://github.com/Tencent/WeKnora/blob/v0.9.0/website-docs/03-features/22-skills-sandbox.md)、[Embed](https://github.com/Tencent/WeKnora/blob/v0.9.0/website-docs/03-features/13-embed-channel.md)；同目录 `26-weknora-assistant.md#collaboration`、`18-chat-experience.md` 说明协作/引用/过程/产物。

现有入站 MCP 四工具只列能力/数据集、读冻结数据/材料，不是 live `DataHub.query`。DSH 完整 App 接入须验证账号同源 WebSocket、mutation→ResearchService 与原事件；WeKnora 完整 App 接入须将原生用户／空间与 RWB 授权的数据、文件和报告服务衔接。两者均不能裸反代，也不能用 Widget 成功替代。

## 候选身份与实际状态

| 候选 | 固定身份/用途 | 本次状态 |
|---|---|---|
| DSH | `7ecf564`/`0.2.1-alpha.1`，Leon-Huang001208/deepseek-harness | 已构建；真实 bootstrap 成功，完整 Host 启动被 Keychain 授权阻断 |
| AlphaDesk | 已迁入 FinGPT | 已是复用，本批未重验模型/业务 |
| WeKnora | 上述 v0.9.0 知识/Agent | 已有服务；模式/业务另证 |
| 腾讯 SkillHub | 官方源 `a051f06`，插件声明 `0.2.16`；推荐先选发现层 | 真实公开读取/一次有界下载通过；未安装/执行 |
| 讯飞 SkillHub | App `v0.2.28`；独立 CLI `0.3.1` | 自托管 Registry 候选，分发/RBAC/回滚 `NOT_RUN` |
| OpenBB | `5.0.0`、FRED/BLS Provider `2.0.0` | 包未安装，同源对拍 `NOT_RUN` |
| LoopForge | 平台版工作台/沙箱/SOP/脚本/人工 gate；Local 已标 Legacy | exact 候选未冻结、未安装/运行 |

腾讯还支持私有技能、评测、沙箱/流式会话/付费；只接发现是范围选择。插件 npm/tag 本次404、公开 API200。讯飞 Registry **不执行 Skill**。LoopForge 平台与 SuperAgent 重叠；Local Classic/Portable 无 server 但属旧版，不作新长期底座，只试窄 SOP。

外置 `upstream-data-skill-check-20261122-jiwxxrgy/official-upstream-review.md` 保存版本/许可原件：[腾讯](https://github.com/Tencent/skillhub/blob/a051f06f7944d24ade04bea27735f430b19a8298/docs/README.md)、[讯飞](https://github.com/iflytek/skillhub/blob/b81af32f145c393c03051865031eae7bfbeaafa4/docs/skillhub/en/introduction.md)、[OpenBB V5](https://docs.openbb.co/odp/python/migration-from-v4)。逐包/数据源许可独立。

## 可以退出的八组文件责任

路径默认相对 `app/research_web/`；只退出重复分支，消费者见全量盘点。

| 退出候选 | 接替层 | 必须先通过 |
|---|---|---|
| `client.py` 事件重建、`ui/claw-{flow,workspace}.mjs` | 原生工作台 | 审批/两子任务、断线/取消/幂等、旧历史 |
| `qa_worker/` 循环/IPC、`qa_frontend/` | 完整 Agent | 金融同题、工具/引用、产物/质量、旧会话 |
| `capabilities/{seeds,catalog,methods}.py`、`mcp_registry/{catalog,sync}.py` 来源维护 | SkillHub | 唯一目录、许可/pin/hash、会话版、撤权 |
| `capabilities/packages.py`、`plugins/packages.py` 投递 | Registry | 双宿主同包、安装树/副作用/回滚；保留审核 |
| `ui/capability-editor.mjs`、`automation/{schedule,transport}.py` 通用步骤 | 窄 LoopForge SOP | 原 Run/attempt、单副作用、取消/重启 UNKNOWN；唯一调度 |
| `datahub/providers_external.py` 已覆盖源分支 | OpenBB Provider | 同源同窗的值/口径/原件/错误/PIT、代码减少 |
| 仓库根 `knowledge_layer/retrieval/` 旧向量检索 | 现有 WeKnora | 无活动旧消费者；原文/断言/权限/撤权、历史与恢复 |
| 根 `cognitive_agents/{workflow,committee,blackboard}.py` | 成熟执行/SOP | 消费者/历史、金融方法、预算/复核等价 |

保留问答任务的归属／恢复、Claw、AutomationService、ReportWorkflow、安全门。Architect 划界、模块实施、QA 验收后同步退重复调用/测试/文档。

## DataHub 保留与 OpenBB 的实际边界

保留 `BusinessQuery` purpose/quality/as_of、证券/交易日/单位/币种/频率/复权、授权路由、原响应/hash/分页/缺项、快照/vintage/PIT/报告冻结。Wind、iFinD、天软保留原接入；已核 V5 官方目录无等价 Provider，第三方未核。

V5 是 `obb.fred`/`obb.bls` 命名空间，非 V4 共享 model/router；15 个旧包已移除，V5 Apache-2.0 不覆盖旧 AGPL/数据条款。当前 **RWB 直读，非 OpenBB 对拍**：FRED 7 行 snapshot、非完整历史；BLS HTTP403/failed。vintage/发布时间及 BLS 修订复原未闭合，不能认定 PIT。

## 分阶段 PR 与退出顺序

1. **最小闭环 PR**：固定版本，隔离账号/目录实测 Gateway→Host→DSH→文件；核调用、事件、hash、失败与清理。WeKnora 解除模式另留受管回执。
2. **完整 Agent PR**：不另建向量库；同题比较 DSH/WeKnora 的当前用户、真实资料、金融工具、两子任务、报告，再选 FinGPT/Claw 主内核。
3. **内核替换 PR**：先迁单入口；旧会话/文件/报告只读兼容，新会话固定内核版本。原 ID/attempt 恢复，禁止重放副作用；UNKNOWN 对账。开关回退至可运行旧内核，不伪装记录格式。
4. **来源/数据 PR**：腾讯固定 namespace/versionId/hash；有私有分发需求再验讯飞。OpenBB 仅 FRED/BLS，同源同指标同窗对拍后决定采用。
5. **SOP/退役 PR**：LoopForge 只试 Agent→Script→Human；不能简化唯一调度/恢复则不采用。消费者迁完、历史可读、回滚实测、同候选 CI/本平台业务验收后退旧实现。

合并、生产启用、退役分别签收。WeKnora 已有五个服务，当前内存硬限额合计 6.5 GiB；解除模式复用原镜像，未构建或拉取。此数字是配置限额，不是实测工作负载峰值。新沙箱、模型、讯飞 Registry 和 LoopForge 的增量资源及维护成本仍待测，不编节省比例/工期。

## S0–S4 实际证据与缺口

| 阶段 | 已取得证据 | 尚未取得 |
|---|---|---|
| S0 盘点 | 13 导航、7 底座、8 组条件退出，新旧基线分开 | 业务替换未完成 |
| S1 工作区/知识 | 早期 DSH Web200/RWBClient/浏览器有限链；本次真实 Gateway 登录、固定 DSH bootstrap、Host spawn；WeKnora 全模式已应用 | DSH Host 等待 Keychain 授权而超时，session/events/文件未执行；WeKnora 模型、工具、金融业务待验 |
| S2 Skill／SOP | 腾讯读取/一次下载、15 文件 SHA-256 相符；LoopForge 官方边界已核 | namespace 歧义、包许可未建、未验签/安装/执行；讯飞分发、LoopForge SOP 未运行 |
| S3 数据 | FRED 7 行 snapshot；BLS403 | OpenBB 未安装/对拍；PIT/业务未验 |
| S4 统一验收 | 原 Native 两轮独立 QA 拒绝记录保留；本次报告待精确候选独立评审 | 全部能力端到端尚未通过，不宣称完成产品替换 |

腾讯 ZIP 额外 `_meta.json` 已离线对照；本地过严集合假设的初次失败保留。`signed=true` 非本地验签，slug+semver 非唯一身份。详见外置同目录 `tencent-s2-read-poc/S2-execution-report.private.md`。

原件：`logs/leo51-codex-20261122/{fred,bls}-live.json`、`logs/leo62-c100debf/epoch2/receipt.json`。本机外置证据：`Scratch/RWB/leo51-dsh-host-20261122/conclusion.json`、`Data/RWB/weknora-runtime/operations/leo51-full-mode-20261122/`。前者保留首次 WorkDisk 可写祖先拒绝、私有临时根上的正式启动超时、一次有效 stdout 捕获及进程 sample；采样显示 `SecItemAdd → defaultKeychainUI → AuthorizationCopyRights`，不能据此认证唯一调用条目。DSH 日志另有四个 Tabbit entry 因 `ctx.settings.register is not a function` 未激活。该 DSH PoC 未触系统授权 UI、未读取既有秘密；Keychain 持久化结果未知，模型调用为 0。全部自有 Gateway／pair 已退出，失败最小根保留；不能用 DSH 认证成功替代 Host、文件或浏览器通过。WeKnora 认证检查按既有凭据引用只在进程内取值，不输出或落盘密码／JWT，不改绑定或借用另一身份。

未装新依赖。后续需批准 OpenBB 三包/依赖锁与接口权限；讯飞/LoopForge 需 pin 服务/镜像、存储/恢复；完整 Agent 需可用生成模型、工具/网络与预算准入，embedding 不代表生成模型就绪。保护 KB/账号/原件/会话/凭据，模型/金融质量及生产启用另证。

## 本仓实际检查与交付边界

本次源码改动为两个清单／报告和两份合同文档。完整 changed set 经原 Router 选为 `docs-only / L0`：固定 Node 24.19 执行 `node scripts/check_documentation_governance.mjs --project .`、既有 Python 3.12 环境执行 `python scripts/generate_py_file_index.py --check`，实际均退出 0；`git diff --check` 通过。该文档检查不认证失败的 Host、真实模型、完整工具链或其他平台。

Git 交付继续使用原任务与 worktree，不重新 start 或改写旧 receipt；精确候选评审、PR、CI 与收尾状态由原受管 delivery 记录，未取得的证据不沿用旧候选。WeKnora 模式操作与源码 PR 分开记账，不把 PR 合并当作运行模式切换或金融验收证明。
