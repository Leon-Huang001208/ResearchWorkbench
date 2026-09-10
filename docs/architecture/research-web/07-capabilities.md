# 能力包、版本与原生调用

本节对应 `app/research_web/capabilities/` 与能力 UI 模块。后端及界面已通过限定复审；对话创建与手动导入生命周期已有真实浏览器证据，完整 Workflow 交付与全轮门禁独立记录，不能仅凭 API 实现宣称全部验收通过。

## 职责划分

| 模块 | 职责 | 不负责 |
|---|---|---|
| `models.py` | 元数据、输入字段、步骤与产品错误契约 | 执行研究 |
| `packages.py` | 有界 MD/ZIP 读取、路径/类型/编码检查、保留问题 | 安装依赖、解压到任意路径或运行脚本 |
| `catalog.py` | 草稿、检查、不可变版本、原生目录投影、会话资源快照 | Agent 编排 |
| `seeds.py` | 十一个研究 Skill、四个步骤式 Workflow 的声明式内置元数据与共享协议装包 | 虚构在线市场或新增路由器 |
| `tools.py` | 固定 DSH 注册与最终 guard 白名单对应的只读工具目录 | 新增工具权限 |
| `routes.py` | `/api/research/capabilities` 等产品操作 | 绕过研究服务锁直接修改活动运行 |
| `ui/capability-workspace.mjs` | 将 Skill、Tool、Workflow、数据组织为四个互斥主标签，并组合各自目录、管理入口、现有报告日程和连接安全摘要；渲染快览 dialog | 创建第二份目录、混排类型、推断热门排序或执行能力 |
| `ui/mcp-marketplace.mjs` | 在 Tool 的 `view=market` 浏览官方与私有 Registry 的 Unicode 纯文本元数据、包类型/不可变引用事实、真实缓存状态和版本详情；最终 HTML sink 单次转义 | 安装/启用/调用服务器、执行 Publisher、渲染 Registry HTML 或热链图标 |
| `mcp_registry/` | 按 `(registry_id, server_name, version)` 聚合目录，管理安全传输、不透明游标、ETag、原子最后成功缓存和 Keyring 引用 | 合并同名服务器、把秘密写入 JSON、向 DSH 注册工具 |

Skill 和 Workflow 使用同一能力包与版本机制；Workflow 编译成 DSH 读取的原生 Skill 指令，步骤列表是研究模板，不是已执行节点。

能力工作区路由以 `kind=skill|tool|workflow|data` 切换四个主分区，以
`view=library|mine|plans|connections` 切换类型内二级视图；无参数默认 `kind=skill`。
Skill 与 Workflow 各自拥有能力库和“我的”视图，只有 Workflow 提供运行计划；Tool 的连接状态
只展示本机集成，数据源由数据分区单独展示。无 kind 的旧 `view=plans` 映射到 Workflow，
`view=connections` 映射到 Tool；不适用于当前 kind 的 view 回落到该类型目录。任一目录只渲染一种类型。
快览使用有焦点锁定、Escape／遮罩关闭和焦点恢复的居中 dialog，手机改为全屏；复杂管理仍沿用原详情页。

## 数据模型与文件归属

能力条目区分产品稳定 ID、用户名称/slug、类型、来源、状态、当前启用版本和可编辑草稿。元数据包括说明、分类、适用场景、输入字段、默认输出格式、工具需求和 Python 依赖声明。

```text
产品数据根 / capabilities/
  catalog.json                草稿、元数据、版本清单与发布意图
  originals/                  导入原包及哈希，导入时不执行
  versions/<id>/<version>/    不可变 SKILL.md、审核脚本及模板
  native-skills/<native>/     仅当前已启用版本的 DSH 发现目录
  retired/                    原生投影切换保留的旧目录
会话目录 / resources/capabilities/<id>/<version>/
                              研究脚本只读快照，不覆盖旧版本
```

包版本树与文件分别只读；原生投影顶层目录允许服务切换，不授予研究脚本宿主权限。内置原生名称保留现有 ID，自定义名称包含产品 ID 与版本。历史版本可查看、导出；使用非当前版本必须先明确回滚，不能假设 DSH 有版本锁定 RPC。

能力目录、内置 Skill、Report Workflow 和 Research Web 运行配置统一显式使用 UTF-8 读取与原子写入，不依赖操作系统默认代码页；Windows 原生 CI 会实际启动服务并读取中文内置能力，以验证这条启动链路。

## 创建、导入与检查

表单创建和导入先保存草稿。对话创建另建专用会话并返回待发送草稿，不自动消费模型；从该会话实际 `outputs` 中的 SKILL.md 或 ZIP 导入，不能把其他会话资料或聊天文本冒充生成包。

制作提示包含真实 Metadata/Step schema；Skill 只要求 SKILL.md 与 capability.json，Workflow 才要求 workflow.json。模型仍可能输出不兼容草稿，因此后端按实际字节检查，而非相信生成回复。当前安全 inventory 决定根 SKILL.md 的固定伴随文件；已改名的历史 ledger 不再引用。仍存在但不安全的伴随路径、读取过程中消失或创建类型不符均拒绝；显式 ZIP 不混入会话参考文件。名称冲突要求明确改名，不覆盖已发布能力。

安全读取限制：压缩 10 MiB、展开 30 MiB、最多 128 条目、单文件 10 MiB。禁止绝对路径、穿越、链接、特殊文件、嵌套压缩、安装钩子和二进制可执行文件。研究 Python 只允许 `scripts/` 下受检资源；脚本须按实际 SHA-256 审查确认。导入和检查不执行脚本，也不安装缺失依赖。

检查分别报告元数据、原生 frontmatter、调用方式、工具白名单、关联 Skill 状态/版本、依赖版本、脚本语法、安装行为和进程启动入口。即使脚本哈希已经审查，导入 `subprocess` 或引用受检的 `os`/`pty`/`asyncio` 进程入口仍以 `runtime_incompatible_script` 拒绝发布。只有依赖问题时为 `blocked_dependencies`，其他不兼容为 `invalid`；检查通过仍只是 `draft`，需要发布才启用。前端必须展示问题，不能只删除不兼容文件后宣称成功。

这不是任意 Python 的静态安全证明。运行时文件、网络与进程边界仍由现有沙箱及各工具策略强制执行；仅 DataHub 的已配置只读查询取消逐次审批，其他高风险操作的审批策略不变。

## 发布、停用与回滚

通过 `ResearchService` 与提交共享互斥锁。活动父回合、子 Agent、未确定恢复或未完成交付会阻止变更原生发现目录；草稿仍能保留，待任务结束后重试。

发布重新检查，生成新的不可变版本，再记录持久发布意图、切换原生投影并保存索引。切换或恢复失败不能宣称成功；持久 `pending`/目录不一致时禁止提交，需停用专属实例后审查恢复。此机制只支持单 Web worker。

硬改名后的持久目录由 `catalog.py` 做一次性、幂等的版本迁移，而不是原地改写：先迁移 Skill 的旧脚本 Tool ID，再迁移仍绑定旧 Skill 版本的 Workflow。内置包使用当前受审种子，安全的用户脚本包只替换 `af_run_script`；歧义 `af_public_data` 用户包要求人工审查。每次成功迁移均形成新的不可变版本，旧版本仍可审计；失败恢复原条目并留下结构化日志。

原生 FileSystemSkillProvider 仅观察产品专属目录，关闭默认宿主 roots 与链接跟随。使用原生发现/加载，不虚构安装 RPC。首版不删除历史版本或用户源包。

固定 DSH 源码提交 `c919b2a460753859665db3f60143d525fb9140cf` 的会话记录保存 preset ID，而非整份 Skill root 配置快照；能力目录与 Runtime 启动校验使用同一提交标识。冷恢复按 preset ID 重新组合当前配置，已挂载 Agent 则保留现有 generation。因此更新需先确认无活动任务，不能在研究中替换 preset 后假定已生效。Web 提交前实际核对 `skills/list` 中的原生名称；未发现时明确拒绝，不伪装调用成功。2026-09-03 已验证专属服务空闲后更新、旧会话冷恢复发现六个原生能力、恢复八条历史并成功继续第五轮；这不替代自建能力发布调用验收。

## 研究请求与版本证据

`capability_id` / `capability_version` 可选，保留旧 `skill_id`；可选 `tool_ids` 只表达使用意图，不扩大运行时已注册工具。发送前验证所选启用版本、依赖及 Workflow 关联版本，将当前已启用包的资源复制为会话只读快照，并记录当时能力目录。这样即使 DSH 自主选用其他已启用 Skill，也有本轮资源与版本证据。

显式 `expected_formats` 优先；未提供时使用所选能力默认格式。详情显示能力/版本和 Workflow 预设步骤，执行活动及最终文件从原生历史与真实产物读取，不由模板推断完成状态。

Tool 目录只读展示 8 个研究/控制工具与 15 个 `datahub_*` 业务数据工具，共 23 项。新增数据库目录与单表查询仅在本机 MySQL 配置、凭据和依赖就绪后由 Research Runtime 写入 `enabledTools`；配置变化在重启后生效。已注册的只读 DataHub 查询自动执行，未注册能力不会出现在模型工具列表中。

Tool 的 MCP 市场是 Phase 2A 的独立只读二级视图。官方 Registry 固定使用 `/v0.1`，私有
Registry 必须由用户显式配置；认证 Registry 只允许 HTTPS，无认证 HTTP 仅限精确 loopback，OAuth
授权/token 端点始终为 HTTPS。列表和详情始终保留 Registry 身份，不按名称去重。离线或上游失败
展示带同步时间的 `stale` 最后成功缓存，不以空目录伪装成功。规范化目录保存有界 Unicode plain
text，UI 只在最终 HTML sink 转义；搜索或 Registry 替换结果集会使旧详情请求失效并保留当前上下文
焦点。包记录分别显示 `package_type_supported` 与 `immutable_reference`，只说明客户端识别与固定引用
事实，不承诺可安装。Publisher 预览/校验只生成规范 `server.json`、SHA-256 与完整外部 CLI argv，且返回
`executed:false`。Phase 2A 没有 MCP 安装、授权、工具调用、Runtime 重启或 Automation；这些分别
保留给 Phase 2B/2C。

工具目录与 Runtime 使用统一连接中心的来源状态：保存配置、探测健康、完成适配、允许调用和当前可调用分别计算，不因 Wind/iFinD/Excel 被本机检测到就虚构 Provider。能力 API 接收当前数据根后读取同一安全摘要；秘密、主机账号明文和探测临时响应不会进入能力包、原生 Skill 或 Tool schema。

本轮从旧市场内容能力中只迁入可独立运行的“市场解读” Skill 和“市场资料筛选与解读交付” Workflow：脚本读取当前会话已有结构化资讯，按时间、来源和关键词执行透明排序并生成文件。它不导入旧 UI、数据库、调度器、事实断言或报告编译链；没有实际数据时不得生成市场结论。

2026-09-08 在不改变上述包、版本和执行拓扑的前提下增加五个品牌中立专用 Skill：研报增量分析、金融事件研究、产业链与主题研究、业绩与一致预期、宏观与跨资产。它们分别避开一般资料提取、多事件市场复盘、通用行业报告和完整公司研究；触发与反向条件直接写入 Skill frontmatter 和产品元数据，不登记独立路由 Skill。五项均以 `default_formats=[]` 默认在聊天中回答，文件和 DataHub 仅在 Runtime 实际暴露且用户明确要求时使用。

共享证据协议以 `skills/_shared/evidence-protocol.md` 为单一维护源码，种子构建时复制到每个专用包的 `references/evidence-protocol.md`，随不可变版本保存自己的 SHA-256 快照。协议统一来源层级、证据分层、日期口径、基线、反向证据、情景和非个性化建议。搜索摘要不能替代原文，决定性来源不可读时必须降级为“证据不足”或“无法判断”。研报 PDF 通过现有 `research_helpers.read_pdf` 读取；结构化摘要校验和 SVG 知识图谱是沙箱内受审脚本，不使用宿主路径、Poppler、shell 或子进程。v1 不裁剪 PDF 原页，没有可靠来源定位时不生成关系图并标记视觉证据受限。

具体报告使用 `Report Workflow`，不是独立报告执行引擎。每个不可变版本持有自己的 Word/PPT 模板、Excel 公式底稿、品牌素材、映射、结构化步骤和交付合同；共享 Skill 负责检索、市场解读、图表分析和段落写作，共享 Tool 负责 Excel 刷新、底稿提取、模板检查、图表渲染、Office 组装和文件验证。运行修改的是 Run 副本，永不覆盖 Workflow 母版。

华安 ETF 周报、创业板 50 周报、华安 ETF 投资风向标和 AI 周报均在 Claw 与能力中心展示。创业板 50 的活动工作簿按公式识别为 iFinD，误标 Wind 文件只保留为 `legacy_mislabeled`；AI 周报继续 `needs_attention`。日程默认关闭，且只有手动运行达到 `completed` 且文件交付为 `complete` 后才能启用。

能力中心现在有 Skill、Tool、Workflow、数据四个页签。“数据”不是新的执行类型，而是 DataHub 的只读目录投影：支持按业务能力和按来源双视图，展示字段、参数、市场覆盖、候选来源和六维就绪状态。把数据能力“放入研究草稿”只加入对应 `datahub_*` Tool，不立即联网或产生费用。DSH 原生网页搜索仍留在 Tool 目录，不冒充 DataHub 数据源。

## 验证边界

包安全、生命周期、受理互斥、专用创建产物、资源哈希和原生 provider 测试位于 `tests/research_web/test_capabilities*.py`；研报校验、SVG 及沙箱降级在 `tests/research_web/test_sell_side_report_skill.py`。能力中心卡片、详情、完整编辑表单、版本、脚本审查和专用创建入口分别在 `ui/capabilities.mjs`、`ui/capability-editor.mjs`、`ui/capability-controller.mjs`，全局/首页/输入选择共享同一目录。当前 UI 继续由目录数据动态生成，因此支持 11 个 Skill 无需新增产品 UI 分支；JavaScript 回归通过项目 Python 环境实例化真实 `CapabilityCatalog` 并调用 `list(kind="skill")`，再把结果交给页面函数核对数量、分类、搜索、详情和不存在路由卡片，并触发真实 `data-use-skill` 页面事件核对输入栏的已选选项与能力 chip。相对解释器 override 先按调用者 cwd 固定为绝对路径；找不到项目解释器时测试明确失败，不回退到手写目录。

2026-09-03 实际对话产物经人工审查发布 `1ba298cc4b754aee9496b7d1c5c78bf7` v1，在新会话 `7ee7b736-673a-4aff-8006-73de6c10b600` 生成并下载 HTML，保存原生名称及编译哈希。手动导入 `528c5a3dd15849b0a7f29fbdf5441b01` 从不完整元数据草稿，经表单编辑、检查、v1、v2、停用、回滚v1、刷新、ZIP导出完成闭环。记录在 `.ai/reports/2026-09-03-research-ui-live.md`；失败首稿与原版本保留。

Workflow 历史页面按研究记录的不可变版本读取预设步骤；请求失败显示缺失说明且允许显式刷新重试，不能永久缓存失败空步骤，也不能用当前目录替代旧版。恢复后只清除该版本读取错误，不隐藏其他运行错误。预设步骤不显示自动完成勾选。

Claw 首页直接展示同一目录中的已启用 Workflow（含自建），FinGPT 首页保留四个通用 Skill 快捷入口；完整 11 个 Skill 在能力中心按目录动态展示。分类不发请求，卡片只打开详情或加入草稿。真实Workflow会话 `43170801-cfeb-4c89-914a-a6973dbb8c9a` 使用基金模板v1、两名原生子Agent和四份共享快照，生成DOCX/HTML/XLSX并实际下载、重开；初版Excel内容问题经模型生成v2并独立复算，旧文件未删除。

## 具体报告 Workflow

通用能力目录的 Workflow 规定可复用研究步骤；`app/research_web/report_workflows/` 则管理“每篇报告一个 Workflow”的真实资源包。两者都由 Claw/DSH 执行，但具体报告额外锁定 Word/PPT 模板、Excel 底稿、品牌素材、映射、交付契约和日程，不能由一张通用模板卡替代。

本机 Wind 验证会读取当前已发布报告 Workflow 的工作簿策略，在受管运行副本中执行最小刷新与完整刷新；这个诊断入口不发布新版本、不运行 Claw，也不改变 Workflow 自身的可运行判断。验证成功只证明当前设备上的插件调用链，不能代替报告内容与交付验证。

Claw 首页和能力中心 Workflow 页从 `GET /api/research/report-workflows` 读取该目录，分别显示状态、当前版本、交付格式、Excel Provider 和最近运行。详情读取模板/底稿、刷新策略、报告区块、版本、日程和历史产物；只有 `enabled` 且存在当前发布版本的项目可以创建运行。AI 周报保持 `needs_attention` 时只能查看。

当前真实迁移结果为：创业板50周报 v1、华安ETF周报 v1、华安ETF投资风向标 v1，以及待补全的 AI 周报。迁移后的文件存放在产品数据根 `report-workflows/`；旧 `report-projects/` 在验证和最终清理门禁前保留，不作为运行时的平行执行器。
