# Research Web 能力包与版本

能力中心属于 `app/research_web/capabilities/`。产品保存草稿、不可变版本、来源和校验结果；
DSH 仍是唯一执行引擎，Workflow 编译为原生 SKILL.md 步骤模板，没有第二个运行器。
目录读取不依赖会话、在线 DSH 或模型调用。工具目录为当前研究 composition 的只读声明，
不表示运行实例在线、凭据已配置或某个 DataHub Tool 已进入当前 Runtime 的 `enabledTools`。

`#/skills` 的 v0 能力工作区以 `kind=skill|tool|workflow|data` 作为四个互斥主标签，默认进入
`kind=skill`，不再提供“全部类型”混合流。类型内继续使用 `view=library|mine|plans|connections|market`：
Skill 提供能力库/我的 Skill，Tool 提供工具目录/MCP 市场/连接状态，Workflow 提供能力库/我的 Workflow/
运行计划，数据提供数据能力/数据源与连接。无 kind 的旧 `view=plans` 映射到 Workflow，
`view=connections` 映射到 Tool；既有 kind 深链继续有效，不适用的 view 会回落到该类型目录。
`ui/capability-workspace.mjs` 只聚合本节已有的能力、Tool、数据目录、报告 Workflow 和连接安全摘要，
不建立线上 Skill 商店，也不把缺少可信字段的记录标为 NEW、热门或排名。快览弹窗只展示目录事实；
“立即使用”仍调用既有选用逻辑并返回 FinGPT/Claw 草稿，不自动发送。编辑、版本、回滚和报告
Workflow 管理继续进入原专用管理视图。

DataHub Tool 的可选状态读取统一连接中心的安全摘要，而不是直接读取来源环境变量。配置已保存、单次检测成功、Provider 已适配和当前 Runtime 可调用是四个独立事实；只有 `integration_completed && callable` 的来源才会让对应工具进入 Runtime 注册集合。配置变更后页面可以立即重新检测，但原生工具集合仍以研究服务重启时的快照为准。

当前目录包含 11 个内置 Skill 和 4 个内置 Workflow，其中并行接入的“因子库研究”继续使用
统一连接中心提供的受控数据工具。2026-09-08 新增的五个专用研究 Skill 通过现有原生发现
机制路由，没有新增路由卡片、能力类型或执行器；原有能力与四个 Workflow 的稳定 ID 和历史
版本不被覆盖。旧内容生产代码仍只按可独立验证的脚本、提示和模板迁移；Evidence、Claim、
Quality Gate 与旧报告编译链没有恢复。

阶段 2A 的只读 MCP 市场在三阶段 CI 通过后默认开启；显式设置 `RESEARCH_MCP_REGISTRY_ENABLED=0`
仍会关闭该入口。目录聚合随仓库
配置的官方 Registry 与用户显式配置的私有 Registry，并以
`(registry_id, server_name, version)` 保持身份独立；同名服务器不会合并或覆盖。官方适配器固定
调用 `/v0.1` 搜索、版本与不透明游标接口，ETag、同步时间和游标随最后成功结果原子保存；同步
失败返回带 `stale` 标记的最后成功缓存，不用错误或空结果覆盖缓存。Bearer/OAuth 凭据仅保存到
Keyring 服务 `ResearchWorkbench.MCPRegistry`，产品索引只保留引用。Registry 默认必须使用 HTTPS；
只有 `auth=none` 且主机精确为 `127.0.0.1`、`localhost` 或 `::1` 时允许 HTTP，OAuth 授权与 token
端点始终要求 HTTPS。规范化、缓存和 API 保存有长度限制的 Unicode plain text，拒绝控制字符与
surrogate，不做 HTML entity escape；UI 只在最终 HTML sink 转义一次且不加载远程图标。

包记录将客户端识别能力与不可变制品引用拆为 `package_type_supported` 和 `immutable_reference`。
这两项只说明包类型是否被当前客户端识别、Registry 是否登记了固定版本或所需摘要；未知包类型仍
可浏览。Phase 2B 只对 npm、PyPI、MCPB 固定目标或 Streamable HTTP 生成安装预览，且预览、确认、
安装、健康探测、启用和研究授权始终是独立步骤。

`app/research_web/mcp_runtime/` 使用官方 `mcp>=2,<3` SDK 提供 Streamable HTTP / stdio、工具、
资源、提示及 OAuth 客户端。npm 拒绝生命周期钩子并使用固定 lock/integrity 和 `--ignore-scripts`；
PyPI 只从本地 wheelhouse 按完整哈希安装；MCPB 校验 Registry 摘要并拒绝越界链接。远程端点只允许
HTTPS 或字面 loopback，关闭自动重定向；OAuth 使用 PKCE、state、元数据发现、受众校验和系统
凭据库。安装清单不可变，更新必须从 Registry 新版本重新预览，不能原地替换。
staging、安装 payload、清单和确认令牌重放目录在所有平台拒绝非目录、符号链接与 Windows
重解析点；POSIX 继续校验 group/other mode 及所有者，Windows 不使用没有 ACL 语义的 mode 投影
阻断服务启动或安装预览。

健康探测为每个工具保存版本、schema SHA-256 与风险等级；默认风险为
`external_write_high_risk`，第三方声明不能降低。会话只获得用户明确选择的快照；私有数据需要会话
授权，外部写入和高风险调用每次产生人工审批。无人值守必须同时满足 `read_only`、
`allow_unattended=true` 和任务锁定快照。DSH 只加载 `mcp__{installation}__{tool}`，Host 每次调用
复核安装版本、schema、会话授权和审批。Publisher 仍只生成 `executed:false` 的外部 CLI 交接。

Workflow 的“运行计划”由 `app/research_web/automation/` 提供通用 Automation。每个任务锁定目标
种类、ID、版本和内容 SHA，并保存输入模板、工作空间、输出格式、允许的 MCP 工具快照、日程与
投递引用。服务重启只补最近一次遗漏；重叠触发记录 `skipped_overlap`，版本漂移记录
`blocked_version`，研究失败只能手动创建带 `retry_of` 的新 Run。投递有独立状态和三次重试，
不会修改已经完成或失败的研究结果。

无人值守 MCP 只能调用任务明确锁定且同时为 `read_only`、`allow_unattended=true` 的工具；
私有数据须有任务级授权，外部写入与高风险工具不会被 Automation 调用。SMTP、通用 HMAC Webhook、
飞书、企业微信和钉钉的 URL、密码及签名秘密只进入 `ResearchWorkbench.Delivery` 系统凭据库。

## API（全部位于 `/api/research`）

| 方法与路径 | 输入 / 返回 |
| --- | --- |
| GET `/capabilities?kind=skill\|workflow` | `{items, publication_uncertain}`；不传 kind 返回全部 |
| GET `/capabilities/{id}` | 概览、`draft`、`checks`、当前版本 `steps` |
| POST `/capabilities` | `DraftInput`；201，创建手动草稿 |
| PATCH `/capabilities/{id}/draft` | 完整替换草稿的 `DraftInput`，不改变已启用版本 |
| POST `/capabilities/{id}/copy` | `{name,slug}`；201，内置/自建能力均可复制，脚本需重新审查 |
| POST `/capabilities/import` | multipart 单个 `file`：精确名 `SKILL.md` 或 `.zip`；201，返回草稿及检查 |
| POST `/capabilities/{id}/check` | `{valid,status,issues:[{code,message,path}],bindings,checked_at,executes_code:false}` |
| POST `/capabilities/{id}/publish` | 检查通过后新建整数版本并启用；不修改原版本 |
| POST `/capabilities/{id}/disable`、`/enable` | 停用/重新启用当前版本 |
| POST `/capabilities/{id}/rollback` | `{version:整数}`，显式切回已有版本，不创建或重写旧版本 |
| GET `/capabilities/{id}/versions` | `{items:[{version,native_name,metadata,published_at,sha256,current}]}` |
| GET `/capabilities/{id}/versions/{version}` | 原始指令、元数据、文件及步骤，`read_only:true` |
| GET `/capabilities/{id}/versions/{version}/export` | ZIP：原始 SKILL.md、capability.json、可选 workflow.json、资源 |
| GET `/tools` | 23 项真实 guard/注册声明：8 项研究/控制工具和 15 项 `datahub_*` 业务数据工具；当前只有具备已适配 Provider 的数据 Tool 可选 |
| GET `/workflows` | 同一能力目录中四项种子及用户 Workflow；没有平行目录 |
| GET / POST `/mcp/registries` | 列出或保存官方/私有 Registry 的非敏感配置；关闭功能开关时为 404 |
| GET / PATCH / DELETE `/mcp/registries/{registry_id}` | 读取、修改或删除单个 Registry；秘密只通过凭据引用管理 |
| POST `/mcp/registries/{registry_id}/sync` | 执行一次目录同步；失败时返回最后成功缓存并标记 `stale` |
| GET `/mcp/servers` | 按 Registry、搜索词、包类型与不透明游标浏览服务器；身份不跨 Registry 合并 |
| GET `/mcp/servers/{registry_id}/{server_name:path}/versions/{version}` | 返回指定身份三元组的 Unicode 纯文本详情，以及 `package_type_supported` / `immutable_reference` 两项包事实；不承诺可安装 |
| POST `/mcp/publisher/preview` | 生成规范 `server.json`、SHA-256 与完整外部 Publisher CLI argv；不执行 |
| POST `/mcp/publisher/validate` | 校验不可变发布描述并返回 `executed:false` 的外部交接结果 |
| POST `/mcp/installations/preview` | 解析固定版本，返回未截断 argv、来源、全部制品哈希、环境变量名称与短期确认令牌 |
| GET / POST `/mcp/installations` | 列出不可变安装及真实 Runtime 状态；确认摘要完全一致后执行隔离安装 |
| GET / PATCH / DELETE `/mcp/installations/{id}` | 读取安装、逐工具保存风险等级；仅停用后可移除 |
| GET `/mcp/installations/{id}/status`、`/capabilities` | 返回激活/健康状态与 Host 拥有的 schema、风险策略投影 |
| POST `/mcp/installations/{id}/probe`、`/enable`、`/disable`、`/update` | 探测与 DSH 原子激活/回滚；update 返回必须重新预览的新版本约束 |
| POST `/mcp/installations/{id}/oauth/start`、GET `/mcp/oauth/callback` | 启动并完成 PKCE OAuth；token 只进系统凭据库 |
| POST `/sessions/{id}/mcp-authorizations` | 锁定安装版本、工具名和 schema 哈希的会话授权 |
| POST `/sessions/{id}/mcp/resources/read`、`/mcp/prompts/get` | 对已激活且已授权安装代理资源和提示请求 |
| GET `/mcp/approvals`、POST `/mcp/approvals/{id}/approve`、`/deny` | 不暴露参数正文的一次性人工审批 |
| GET / POST `/automations` | 列出或创建锁定版本和内容 SHA 的通用任务；功能关闭时返回 404 |
| GET / PATCH / DELETE `/automations/{id}` | 读取、完整校验更新或删除单个任务；运行中不可删除 |
| POST `/automations/{id}/enable`、`/disable`、`/run` | 启停或手动触发；版本漂移与重叠均保留可审计 Run |
| GET `/automation-runs`、POST `/automation-runs/{id}/retry` | 查询研究/投递双状态；手动重试创建关联的新 Run |
| GET / PUT `/delivery-channels` | 管理非敏感渠道投影；秘密写入系统凭据库且不回显 |
| POST `/automations/migrations/report-schedules/preview`、`/apply` | 逐项预览和原子迁移旧报告日程；失败不修改两边 |
| POST `/capabilities/creation-sessions` | `{kind:"skill"\|"workflow",goal}`，201，真实创建会话并返回未发送的 `draft` |
| POST `/capabilities/from-artifact` | `{session_id,file_id}`，201，仅专用创建会话实际 outputs 产物导入为草稿 |

普通失败为 `{error:{code,message}}`；名称/slug 冲突、内置覆盖、活动回合和历史版本选择冲突
为 409；草稿不兼容为 422；压缩上传超过上限为 413；存储/发布异常为 503。
内置只能复制修改；允许停用/启用，不能编辑或再次覆盖发布。草稿编辑无需运行实例在线。
`status` 为 `draft/invalid/blocked_dependencies/enabled/disabled`；已发布能力编辑后仍保留
原 `enabled/disabled` 状态，`has_draft:true` 与 `checks.status` 表达未发布候选状态。

### 草稿契约

```json
{
  "kind": "skill",
  "metadata": {
    "name": "我的研究",
    "slug": "my-research",
    "description": "围绕上传资料开展可追溯研究",
    "category": "资料研究",
    "inputs": [{"name":"question","label":"研究问题","type":"text","required":true}],
    "scenarios": ["解读资料"],
    "default_formats": ["md"],
    "required_tools": ["research_run_script"],
    "dependencies": []
  },
  "instructions": "---\nname: my-research\ndescription: 有来源的研究\n---\n# 研究\n核对来源，列出缺失。",
  "files": [{"path":"templates/report.md","content":"# 报告"}],
  "steps": [],
  "reviewed_scripts": []
}
```

`inputs.type` 为 text/file/date/number。格式为 md/html/docx/xlsx/png。
文本文件用 `{path,content}`；图像等二进制用 `{path,base64}`。返回文件包含 size/sha256，
可读 UTF-8 用 content，其他用 base64。编辑接口不是 JSON Merge Patch，发送完整候选；
不要回传服务器生成的 `file_issues/import_issues`。前一原始上传仍保留在私有 originals。
`instructions` 必须是完整 SKILL.md；name 必须等于 metadata.slug，缺字段不补默认后宣称兼容。
ZIP 必须以包根 SKILL.md、capability.json 开始，不自动移动多层目录。
单独 SKILL.md 因缺产品中文元数据而形成 invalid 草稿，用户编辑后才能发布。

Workflow 的 kind 为 workflow，instructions 可空；steps 为有序
`{title,instruction,skill_id?:已启用Skill的产品ID,tools:[]}` 数组。
发布记录关联 Skill 的具体版本与 native_name；关联版本变化或停用后，该 Workflow
不能再用于发送（包括未选择能力、由模型自主发现的发送），须停用该 Workflow 或编辑重新发布。
步骤是计划模板，不应由前端标记为已经执行。

### 内置研究 Skill 边界

能力中心由 `seeds.py` 的声明式元数据生成 11 个内置 Skill。资料解读、公司研究、行业研究、
基金评价、市场解读和因子库研究保持各自既有入口；本批新增能力只在下列窄场景触发：

| 专用 Skill | 正向触发 | 反向边界 |
| --- | --- | --- |
| 研报增量分析 (`sell-side-report-reader`) | 卖方研报或研究文章的增量、公开时序、可信度与证伪 | 一般通读、提取和格式转换使用资料解读 |
| 金融事件研究 (`finance-news-event-research`) | 单一、有时间戳的公告、政策、新闻或突发事件及其传导链 | 多事件复盘、盘前或市场综述使用市场解读 |
| 产业链与主题研究 (`industry-chain-research`) | 价值流、瓶颈、主题阶段及受益/受损映射 | 完整供需、竞争格局和行业关键指标使用行业研究 |
| 业绩与一致预期 (`earnings-consensus-research`) | 单家公司业绩、指引、预期差与机构分歧 | 完整业务、财务、竞争力、估值与风险使用公司研究 |
| 宏观与跨资产 (`macro-asset-research`) | 宏观制度、政策、流动性及利率、汇率、股票、信用和商品传导 | 不用于单一公司、产业链或日常多事件复盘 |

不登记独立研究路由 Skill；触发与反向条件写入每个包的 frontmatter、产品说明和分类，交给
现有 DSH Skill discovery。五个专用 Skill 的 `default_formats=[]`，默认在聊天中回答；只有用户
明确要求文件且当前 Runtime 实际暴露对应工具时，才生成并核验 Markdown、HTML、DOCX 或 XLSX。
这不更改其他四个既有通用 Skill 的历史默认格式；资料解读原本也以聊天交付为默认。

### 共享证据协议与运行时降级

`app/research_web/skills/_shared/evidence-protocol.md` 是品牌中立的唯一维护源码，不是可调用
Skill。种子构建把相同字节复制到每个专用能力包的 `references/evidence-protocol.md`；发布后
它与该版本其他资源一起计算 SHA-256、封存和导出，因此后续协议修改不会改写历史版本。
协议统一来源层级、事实/来源观点/新增证据/研究推断、日期与口径、比较基线、反向证据、
情景、失效信号和非个性化建议边界。

金融事件、产业链、业绩和宏观能力只声明 `web_search`；研报增量分析声明
`research_run_script` 与 `web_search`。DataHub 和文件生成工具只有在 Runtime 实际暴露时才
使用，不是包的必然前提。搜索摘要只用于寻找候选来源；决定性原文、完整正文或附件无法读取
时输出“证据不足”或“无法判断”，不能用摘要或模型记忆补齐。

研报 PDF 文本只通过现有 `research_helpers.read_pdf` 读取。结构化摘要校验与 SVG 知识图谱
脚本作为包内受审 Python 资源在研究沙箱执行，包含显式错误处理和日志；没有宿主路径、安装、
shell、Poppler 或子进程依赖。v1 不裁剪 PDF 原页；可读图片附件可作原图证据，关系均有来源
定位时可重绘 SVG，否则明确“视觉证据受限”。行动含义必须标明研报明示/隐含、适用对象、
时间窗、条件、来源定位和失效信号，不转换为个人仓位或买卖建议。

产品硬改名后的历史目录可能仍保存 `af_run_script` / `af_public_data`。目录启动迁移不会
覆盖历史版本：内置包从当前受审种子创建新的不可变版本；仅包含旧脚本名的用户包安全替换为
`research_run_script` 后创建新版本；含歧义旧数据工具的用户包保留并要求人工审查。Skill 版本
升级后，已启用且仍绑定旧 Skill 版本的 Workflow 也会按依赖顺序创建新版本并重新绑定，防止
一个过期 Workflow 让整个可发现目录阻断研究提交。迁移幂等，失败会恢复原条目并记录错误。

### 会话与提交

已有 `POST /sessions/{sid}/messages` 增加 `capability_id`、`capability_version`（正整数）及
`tool_ids`（仅表达已登记可选工具的使用意图）。推荐客户端始终传选中的版本。新数据能力统一选择 `datahub_*`；工具名使用子系统语义，不依赖产品名称。
版本省略时首次受理绑定当时版本；同一幂等键重试使用原收据，不重新执行、不因后来停用而重发。
非当前版本需要先显式回滚；`skill_id` 保留兼容，原有五个内置 Skill ID 不变。
显式 `expected_formats`（包括空数组）优先，否则用能力默认格式。

发送前在同一锁内验证状态、真实 `skill.list` 的 exact native_name、依赖和包哈希，
将启用目录资源复制为本会话只读快照；因为 DSH 也会自主挑选 Skill，所有已启用包均提供快照。
快照前对整个启用目录调用与显式选择相同的校验：任何包的依赖/工具、关联版本或原生正文失效，
均明确拒绝本次发送、不会提交模型；不静默跳过仍可被原生发现的失效包。
已存在快照不覆盖，跨会话不共享可变路径。收据记录用户选择 `capability` 及可用快照
`capability_catalog`；详情返回 capability/capability_history，不能将可用快照列表说成实际执行列表。
DSH 得到的是原生 slash invocation 与当前会话相对资源指引，不绕过其原生 Skill loader。
旧会话原有 `resources/skills` 不改写。

创建接口只创建真实会话并把候选要求放入 draft；不自动提交模型、不自动发布。
创建提示直接包含当前 Metadata 模型的 JSON Schema（必填、枚举、禁止额外字段）；
inputs.type 明确为 text/file/date/number，default_formats 只选目标需要的格式，
标准库不作为第三方依赖、仅标准库时 dependencies=[]。明确 outputs 已存在且不探测宿主 cwd。
仅 Workflow 创建附带 workflow.json 和 Step 模型约束。提示不保证模型首稿兼容，仍必须执行实际检查。
用户通过普通消息接口开始制作包，结束后选择实际 outputs/SKILL.md 或候选 ZIP。
选择根 SKILL.md 时仅一并读取实际根 capability.json/workflow.json；需要脚本/模板时产出完整 ZIP。
主文件与伴随文件以本次安全文件清单为准，重命名/删除遗留的历史索引不再参与打包，也不删除历史索引。
固定伴随路径仍存在但不安全（链接、目录等），或列举后读取失败时明确拒绝，不静默忽略。
缺少 capability.json 保留 invalid 草稿且不能发布；专用会话的候选解析类型必须符合 creation_kind，
例如 Skill 会话多出 workflow.json 或 Workflow 缺步骤文件会422 creation_kind_conflict，要求修正原文件。
不会自动删除多余文件或悄悄转换类型。显式选择 ZIP 时只检查该 ZIP，不合入会话里其他参考 JSON；
普通手动 ZIP 导入不受创建会话类型限制，仍按包的实际结构识别。
只有专用创建会话的 ZIP 才加入产品文件索引，普通会话不扩展文件格式。
导入仍需检查、审查脚本和显式发布。静态安全检查不是“恶意代码已证明安全”。

## 存储与安全

```text
<RESEARCH_DATA_HOME>/capabilities/
  catalog.json                  # 原子产品目录、草稿、版本记录、发布 pending 标记
  originals/<id>                # 原始上传字节，只读；不提取、不运行
  versions/<id>/<version>/      # 不可变已审核包（文件 0444，目录 0555）
  native-skills/<native_name>/  # 仅当前启用版本的 DSH 单层 discovery 投影
  retired/<opaque-id>/          # 原生目录切换保留的旧投影，不扫描
<RESEARCH_DATA_HOME>/sessions/<sid>/resources/capabilities/<id>/<version>/
```

导入压缩上限 10 MiB，展开总计 30 MiB，最多 128 ZIP 条目，单文件 10 MiB。
拒绝绝对路径、`..`、反斜线/盘符、点目录、大小写重复名、文件/目录前缀冲突（含空目录与包元数据名）、链接/特殊文件、加密 ZIP、
嵌套压缩、二进制可执行 magic、安装配置/钩子。ZIP 不使用 extractall，候选保存在索引与原始 blob，
恶意路径不会写出目标目录。允许 md/txt/csv/json/yaml/yml/html/css/j2 文档模板、
png/jpg/jpeg/webp/gif/svg/pdf 资料，及 `scripts/*.py` 研究脚本。
图片/PDF 必须与扩展名匹配并有容器证据：PNG 块边界/CRC、JPEG 帧/扫描标记、GIF 子块、
WebP RIFF/图像块、SVG 根元素、PDF 头/交叉引用位置/EOF；拒绝空 ZIP、32/64 位 Mach-O、XZ 等伪装资源。
此检查不解压图像、不渲染、不执行内容，也不保证所有像素/文档对象可解码或证明资源无恶意。
SVG 拒绝 DTD/实体及未知编码。合法格式不因此获得额外执行权限。
研究脚本检查语法、静态缺失 imports、显式依赖、安装行为与宿主进程入口；脚本哈希须加入
reviewed_scripts。即使脚本哈希已经审查、没有安装行为，只要导入 `subprocess`，或引用
`os`/`pty`/`asyncio` 中受检的进程启动入口，也以
`runtime_incompatible_script` 拒绝发布。静态检查不执行脚本。不存在自动依赖安装；
URL/extras/marker 依赖声明不支持，明确报错。
导入检查保留失败问题；用户完整编辑候选是显式处理，不悄悄修复并声称原包兼容。

发布、停用、启用、回滚、发送共用 ResearchService.lock；原生父任务、子 Agent、诊断异常、
断连、未知受理或未确认交付均阻止目录切换，草稿仍保留。
切换前持久化 pending；异常尝试恢复原映射，无法确认时拒绝后续发送/发布。
版本先写入 `versions/<id>/.staging-<version>-<opaque>`，完成后封存并提交正式版本名；
写入、重命名或封存失败会返回 503，保留草稿/旧版本及隐藏暂存证据，正常恢复后可直接重试。
暂存不参与原生发现；不会覆盖历史版本。若无法撤回未完成的正式目录，持久化 pending 并拒绝继续。
回滚/启用在目录变更前重新核对目标版本的 name/slug；已被其他能力或草稿占用时返回 409 name_conflict，
当前版本与原生投影均保持不变。
进程崩溃遗留 pending 或目录与索引不一致时，启动 prepare_native_root 拒绝宣称成功；
须由操作者停止专属实例后核对 catalog、versions 与 retired，恢复一致状态再启动。
不自动覆盖、删除版本或清除未知标记。仅支持一个 Web worker。
macOS 移动目录需更新 `..`：native 投影顶层目录为服务自有 0700，文件仍只读；
不可变 versions 树与会话资源仍只读，不增加脚本沙箱权限。

## 原生接线与工具真实性

DSH 固定提交 `c919b2a460753859665db3f60143d525fb9140cf`。
核对 upstream `packages/skill/skill-filesystem/README.md` 和 FileSystemSkillProvider 源码：
发现仅一层 bundle，watch 触发 invalidate，每次 get 重读正文，无版本 pin 或 install RPC。
产品以不可变包 + 带版本的原生名称实现绑定；自建名称为 `rwb-<产品id>-vN`，内置保留原 ID。

研究 preset 使用 `includeDefaultRoots:false`、唯一 `customSkillDirs:<data>/capabilities/native-skills`、
`watch:true`、`watchFollowSymlinks:false`。不读取宿主默认项目/用户 skills。
启动器 prepare 已接入此目录；本任务没有重启 live 3081/8088，更没有触及旧 3080。
主控制器须确认所有实际任务结束后，通过原授权启动器更新专属实例；旧实例指向仓库 skills，
自建版本在旧实例会明确报 native_discovery_pending，不伪装已经调用。

冷恢复边界（固定源码核对，未做本批跨重启实测）：DSH 会话记录的是 preset ID，
不是完整 Skill root 配置快照。`agent-presets/src/session.ts` 解析该 ID；
`apiproxy/src/api-proxy.ts` 的 agentFor 依此重新 compose；
`agent-presets/src/index.ts` 的 ensureStanding 按当前 preset 文件构建 generation。
仍挂载的旧 Agent 保留原 generation，真正冷恢复则按该 ID 当前可解析的 preset 挂载。
因此同 ID 的授权启动文件更新后，不能断言旧会话必然继续扫描旧 root，也不能把尚未实测说成已经升级成功。
Web 先以 session.models 冷恢复再 skill.list 核对；缺 exact native_name 时409拒绝，不改写会话历史。
界面应提示等待已授权目录接线；仍缺失时新建/显式升级会话并复用资料，不自动重写旧 preset 记录。

tools.py 是已核实原生注册的离线投影，读取现有 guard 取交集，并附参数、来源、审批和条件。DataHub 元数据标记为 `automatic`；Runtime 启动时只注册至少有一个可调用来源的固定工具。能力中心“数据”页另从 DataHub 静态目录投影 15 项业务能力、22 个来源和绑定矩阵；其中“因子库研究”只通过 schema、受控单表和会话脚本工具工作，不能直连数据库或绕过 `enabledTools`。
真实原生注册测试覆盖 skill/subagent/report/send_message/interrupt_agent/list_agents/web_search
及本项目 research_run_script/datahub_get_fund_data；DataHub 的 Query schema 与五个 SOURCES 直接复用。
新版 DSH 已移除独立 `report` 工具；子 Agent 通过原生 continuable 结果链路回传，所有工具权限、模型、执行上限及审批策略均未改变。

## 验证映射

| 源码 | 测试 | 验证边界 |
| --- | --- | --- |
| capabilities/models/packages/catalog/seeds、skills | test_capabilities.py、test_capabilities_safety.py、test_capabilities_review.py、test_sell_side_report_skill.py | 11 Skill/4 Workflow 离线种子、专用边界、证据协议快照、恶意ZIP、媒体容器、脚本/进程入口审查、研报校验与SVG、不可变版本/故障重试、回滚唯一性 |
| capabilities/routes、main/service/store | test_capabilities_admission.py、既有 research_web 回归 | 原生名称核对、格式优先、幂等、跨会话、并发、创建产物 |
| tools、launch_runtime、research.cordis.yml | test_capabilities_native.py | 固定源码真实 provider list/get/watch 与实际注册；不调用模型 |

实际命令、RED/GREEN 和剩余验收见 [后端任务报告](../.ai/reports/2026-09-03-capabilities-backend.md)。
本批不涉及桌面/Windows/发布；不以本地协议测试代替主控制器后续真实界面与模型调用验收。

Windows 原生回环验证会从冷目录装载全部中文内置 Skill。能力种子、工具白名单和能力索引均显式按 UTF-8 读取或原子写入，避免系统默认代码页改变能力内容或阻止服务启动；该验证不代表 Wind/iFinD 厂商登录已经完成。
