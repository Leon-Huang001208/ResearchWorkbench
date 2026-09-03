# Research Web 前端

## 范围与入口

`app/research_web/ui/` 是独立的 Research Web 正式应用源码，由 Research Web FastAPI 服务提供 `/` 和 `/static/`。不加载原 `app/web` 管线或原型脚本，不依赖前端构建工具，不新增第三方包。2026-09-02 真实模型与浏览器旅程见 [验收记录](research-web-acceptance.md)。

页面使用 hash 路由：`#/fingpt`、`#/claw`、`#/history`、`#/skills`、`#/settings`。会话地址形如 `#/fingpt?session=<encoded-id>`，刷新页面会重新读取该会话。

视觉延续已批准原型的深蓝顶栏、浅色研究画布、蓝色操作按钮、左侧导航和右侧研究空间；品牌图标复用现有本地资产。原型中的示例消息、进度、市场模块、Claim/Evidence/Quality Gate 与旧管线没有迁入。

## 模块

| 文件 | 职责 |
| --- | --- |
| `index.html` | 自托管资源入口、中文语言标识和键盘跳转入口 |
| `styles.css` | 桌面三栏、平板研究抽屉、手机导航、焦点/禁用/错误/减少动态效果状态 |
| `core.mjs` | `/api/research` API、SSE 生命周期、路由、草稿、幂等请求和会话竞态防护 |
| `markdown.mjs` | 安全文本转义、URL 白名单、有限 Markdown 子集 |
| `views.mjs` | 会话、审批、问题、活动、Agent、文件、历史与模型选项的渲染 |
| `app.mjs` | 页面组合和真实用户交互；配置秘密不进入持久浏览器存储 |
| `shell.mjs` | 顶栏检索、可收起的产品导航、真实运行/最近会话与会话右侧标签面板 |
| `composer.mjs` | 输入框、真实研究 Skill 快捷入口、slash 搜索及附件拖放/粘贴入口；不直接发起研究 |
| `capabilities.mjs` | 同一能力目录的筛选、卡片、详情、检查结果、只读 Tool、不可变版本与 Workflow 模板渲染 |
| `capability-editor.mjs` | 完整候选表单、输入和文件编辑、脚本审查标识、有序 Workflow 步骤与载荷收集 |
| `capability-controller.mjs` | 显式创建/复制/导入/编辑/检查/发布/停用/启用/版本/回滚操作及失败保稿 |

## 接口与行为

所有请求仅访问同源 `/api/research`；读取运行时、模型目录、工作空间、历史、`/capabilities` 与只读 `/tools` 后展示真实响应。错误可见，不生成本地演示结果。目录部分加载失败会独立报告并保留上次成功结果；DSH 离线时产品后端仍可读取已保存目录。Web 服务也离线时只能保留本页已加载状态，不宣称提供离线 PWA 或跨刷新缓存。

- 新研究先 `POST /sessions`，再对新会话 `POST /messages`；消息带 `Idempotency-Key`。同一个失败草稿重试复用相同键；收到 `accepted: true` 才清空原稿。界面不伪造用户/助手消息或进度。
- 会话详情来自 `GET /sessions/{id}`；SSE `snapshot` 替换真实详情，`runtime_error` 显示运行错误。事件连接恢复只重新读取快照，不重发消息。跨会话旧响应会被忽略；较旧 HTTP 快照不会覆盖后来到达的 SSE 输出。
- 历史打开、重命名、取消、批准/拒绝均调用对应真实接口。运行时提问通过问题响应接口回复；根回合结束但子 Agent 仍活跃时保留运行状态和停止入口。
- Agent 卡片显示实际 tokens、错误、已结束回合累计耗时及历史截断提示；活动使用原生工具时戳显示耗时，并以 Agent 名称关联。无测量值不伪造数字。聊天隐藏本次内部任务后缀，但保留用户引用的旧标记和正文。
- 重命名和原生问题使用应用内表单；不调用 `window.prompt`。SSE 重渲染保留当前表单草稿；问题可选择选项并补充文本，仍提交既有原生 `answers` 契约。
  - `multiSelect` 缺省/false 为单选 radio，true 为多选 checkbox；前端收集与后端均拒绝单选多值。
- 编辑器提供显式 `expected_formats` 与按 Skill 默认格式；选择随草稿/幂等请求保存。父/子任务和交付检查未结束时不排队新消息，允许先准备草稿。右侧单独展示 `delivery` 的要求、实际文件、缺失/损坏原因；“执行已结束”不等于“文件交付已检查”。详见 [交付契约](research-web-delivery.md)。
- 右侧“研究资料”仅渲染会话详情/SSE 快照中的 `detail.datasets`，不另起轮询；它位于交付检查与活动之间，独立于生成文件和交付状态。旧会话的空数组不显示占位卡片。每张真实资料卡展示来源安全链接、状态、请求/实际范围、记录数、分页结束语义/页数/供应商总量、取数时间、`as_of`、缺失、限制和快照复用信息。`partial` 即使分页结束仍以警示呈现，`snapshot` 明确不代表完整历史，未知状态不按成功显示。
- 资料下载由当前会话 ID 和资料 ID 在浏览器本地严格构造，仅允许 `rows.csv`、`rows.json`、`manifest.json` 三个无查询串/片段的专用路径；不信任资料返回中的 URL。会话或资料 ID 含编码分隔符、路径分隔符或其他不合规字符时不提供下载。每个下载操作具有“资料名称 + 文件格式”的独立辅助技术名称；来源 URL 仍通过 `safeURL` 过滤。
- 升级调用 `POST /sessions/{id}/upgrade`，使用返回的新会话和 `draft`；草稿放入新编辑器，不自动提交。
- 附件使用 multipart `files` 字段上传；返回 ID 作为 `attachment_ids` 提交。上传成功仅代表后端收到了文件，不代表模型已读取或工具沙箱已执行。
- 文件下载只使用真实返回且经过检查的同源会话文件 URL。HTML 预览 iframe 使用空 `sandbox` 和 `no-referrer`，前端拒绝外部或任意路径的预览地址；后端仍负责授权、路径隔离和响应 CSP。
- 模型切换和配置调用 `PUT /runtime/model`。API Key 为密码输入，不回填，不写 localStorage/sessionStorage，不进入日志；提交时清空输入框。失败后如需更新 Key，用户需重新输入。
- 前端安全 console 事件只包含固定事件名、请求 method 和 HTTP status；不记录 URL、会话 ID、输入、文件名、响应正文或凭据。服务端持久日志由 Research Web 后端负责写入项目日志设施。

## Markdown 与安全边界

支持标题、段落、粗体/斜体、行内代码、围栏代码块、列表、引用、简单表格与 HTTP(S) 来源链接。原始 HTML 始终转义；不执行模型输出的脚本或 HTML，不远程加载 Markdown 图片。来源链接拒绝活动协议、凭据 URL、控制字符与协议相对 URL。不是完整 CommonMark 实现。

生成文件链接限定 `/api/research/sessions/{sid}/files/{fid}/download` 或 `/preview` 路径；资料链接另限 `/api/research/sessions/{sid}/datasets/{did}/files/{rows.csv|rows.json|manifest.json}`。两者都拒绝路径穿越及编码分隔符。前端校验不替代服务器授权。

## 验证与限制

```bash
node --test tests/javascript/research_web_ui.test.mjs
node --check app/research_web/ui/app.mjs
git diff --check
```

独立 JS 测试涵盖真实解析/渲染、恶意 HTML/URL、API 结构化错误、multipart 上传、日志秘密隔离、幂等重试、跨会话竞态、SSE 重连/清理、Claw 升级草稿、生成文件 sandbox，以及资料卡状态/范围/不完整警示和固定下载路由。

浏览器视觉、键盘/移动端状态和真实 DSH 全链路由集成任务另行验证。DSH 模型凭据、工具沙箱、文件读取与 Agent 执行能力取决于实际后端，不由 UI 模拟。此变更不涉及桌面安装或 Windows 运行验证。

## 产品壳与研究首页（2026-09-03）

研究壳保留 AlphaFoundry 深蓝顶栏、深色窄主导航 rail、浅色二级会话栏及白色研究画布。rail 的 FinGPT、Claw、能力中心、历史和设置使用可见文字；折叠仅作用于二级会话栏。≤1050px 时二级栏改为抽屉，内有明确“关闭会话侧栏”按钮；桌面折叠后在手机打开仍暴露正确 ARIA 状态。顶栏检索匹配已加载的真实会话与同一 Skill/Workflow/Tool 名称和简介；手机提供“打开全局搜索”按钮。运行任务从完整会话目录筛选，最近会话才限制为十项；hash 路由和原有 selector 保持兼容。

FinGPT 与 Claw 分别呈现首页。FinGPT 面向问题研究，其四个快捷入口严格筛选同一 `/capabilities` 目录中的 `document-reading`、`company-research`、`industry-research`、`fund-evaluation`。Claw 明确目标、约束与预期交付；快捷区标题为“研究步骤模板”，只展示同目录 `kind=workflow` 且 `enabled=true` 的真实模板（包括已发布自建模板），不硬编码模板 ID，也不把缺项替换为 Skill 卡片。Claw 仍可通过上方能力选择框/slash 使用真实 Skill，并明确模板不代表已执行。目录缺项显示空态，不补造卡片。

两种首页分类选项仅来自各自快捷区条目的实际 `category`，`#quick-category[data-quick-category]` 只在本页内存筛选；切换路由时复位，目录更新后未知分类按全部显示。筛选不请求后端、不改变草稿或执行能力。卡片可见名称、简介、场景、输入和默认输出。既有 `data-skill-detail` / `data-skill-shortcut` 按钮保持：详情进入能力中心，选择将不可变的 `capability_id` / `capability_version` 放入此前 FinGPT 或 Claw 的当前草稿，不创建会话或启动模型；旧 `skill_id` 仅保留 API 兼容。

输入框继续使用既有附件、模型和格式契约。`/` 搜索已启用 Skill/Workflow，ArrowUp/ArrowDown 选择、Enter 放入草稿、Escape 关闭；slash 草稿不会意外提交模型。显式 `expected_formats`（含空数组）优先，否则根据所选目录元数据显示默认格式并由后端绑定；删除了前端平行的硬编码默认格式表。工具意图使用 `tool_ids`，不改变原生审批。运行时未就绪只禁止真实发送，仍允许浏览和准备草稿。

拖放/粘贴文件复用既有 multipart 流程。空首页不分配右侧空面板；研究详情中桌面也可显式收起/展开。活动/资料/文件标签仍只读取当前会话，Claw 会话/当前工作区切换继续复用安全下载与隔离预览，原生审批、停止、子 Agent 和交付语义不变。

## 能力中心闭环

接口契约和包边界以 [能力包与版本](research-web-capabilities.md) 为准。Skill/Workflow 使用同一目录，支持内置/我的、分类和中文搜索。Tool 仅为只读声明，可选工具才有“放入草稿”；参数、来源、审批与条件均来自后端。

手动新建与编辑提交完整 `DraftInput`，剔除服务器生成的 import/file issues，但保留候选文件内容或 base64 字节。脚本阅读后显式确认当前 SHA256，改写候选文件会清除审查确认；保存后还需检查和发布。内置只有复制入口，不覆盖编辑。导入精确 `SKILL.md` 或 ZIP 使用单个 multipart `file`，检查失败仍展示原问题，不伪造成功。发布、停用、启用、回滚与版本查询均调用真实 API，活动冲突保留草稿和后端错误。SSE 状态会回填会话摘要，进入能力中心也刷新列表；可能过期的其他会话 running 缓存仅作提示，不永久锁住发布按钮，后端全局活动锁最终裁决。发布直接采用已确认的完整变更响应，避免额外回读失败把已成功发布误报为失败。历史版本只读，导出地址按 ID/整数版本构造固定同源路径，不信任任意下载 URL。

对话创建只调用 `/capabilities/creation-sessions` 并将返回的未发送 `draft` 放入新会话。用户明确发送后才制作包。只有 `purpose=capability_creation` 且 `kind=outputs` 的实际 `SKILL.md`/ZIP 可进入 `/capabilities/from-artifact` 审查，普通研究产物和上传附件无此入口。导入不自动发布。

Workflow 表单提供有序步骤、关联 Skill、工具意图和输出格式，不提供拖拽或独立运行器。会话详情使用收据记录的 `id:version` 读取不可变版本，右侧明确分离“预设步骤”和 DSH 实际活动；缺少版本数据时说明未载入，不以当前目录推断历史执行，不自动标记步骤完成。

不可变版本读取期间使用占位防止重复请求；读取失败会移除该占位，后续显式刷新或新会话快照可重新读取。恢复成功只清除对应的版本读取错误，成功版本仍保留缓存，不重发研究消息或工具调用。

已保存候选在后端持久化，刷新可从目录详情恢复。尚未保存的表单/研究草稿仅在本页内存保留，不写浏览器持久存储。选择版本随会话草稿切换与幂等重试保留，目录更新不静默改绑版本。

### 状态矩阵

| 状态 | 已实现的 UI 语义 | 验证证据 |
| --- | --- | --- |
| 默认 / hover | 导航、真实 Skill 卡和标签可聚焦；hover 仅轻微强调 | `research_web_ui_layout.test.mjs` 渲染契约 |
| loading / disabled | 原有控制器 busy/loading 状态禁用上传、选择与提交；不清除草稿 | 既有 `research_web_ui.test.mjs` 控制器覆盖 |
| running | 运行任务显示在侧栏；停止仍使用已有取消接口 | 壳层渲染 + 既有 controller/API 测试 |
| error | 目录/API 错误保留可见；失败活动默认展开并显示错误 | `views.mjs` 渲染与 UI 回归 |
| empty | 缺少真实会话、Skill、资料或文件时显示操作性空状态，不填演示数据 | 壳层与既有 views 测试 |
| keyboard | skip link、焦点恢复、Enter 发送、Escape 关闭抽屉沿用；`/` 可搜索真实 Skill | 静态/单元覆盖；未做浏览器键盘验收 |
| 能力禁用/缺依赖/冲突 | 停用能力只可查看；导入检查问题和操作错误可见，不自动发布或安装 | `research_web_capabilities_ui.test.mjs` |
| 编辑/保存/版本 | 失败保留完整候选；保存可由新控制器重新读取；版本与工具意图参与幂等消息 | `research_web_capabilities_ui.test.mjs` |
| 离线/键盘 | 运行时离线禁发送但可编辑；真实 app 事件处理器消费 slash/Escape/移动抽屉和搜索 | 无网络 DOM 边界测试；不替代真实浏览器 |
| Claw 工作区 | 会话恢复聊天；当前工作区主画布只投影当前 `detail` 的资料与文件，复用安全下载/预览 | `research_web_ui_layout.test.mjs` |
| 首页模板/分类 | Claw 仅已启用 Workflow；FinGPT 四 Skill；分类本地筛选，卡片与上方 Skill 选择只准备版本草稿 | 布局渲染测试 + 实际 app 事件无网络 DOM 边界测试；视口/hover 由控制器另验 |

本轮未启动服务、未请求模型，也未做浏览器视觉验收；单元测试不能替代 1440/1600/1920、平板和手机的实际界面验收。
