# Research Web 前端

## 范围与入口

`app/research_web/ui/` 是独立的 Research Web 正式应用源码，由 Research Web FastAPI 服务提供 `/` 和 `/static/`。不加载原 `app/web` 管线或原型脚本，不依赖前端构建工具，不新增第三方包。2026-09-02 真实模型与浏览器旅程见 [验收记录](research-web-acceptance.md)。

页面使用 hash 路由：`#/fingpt`、`#/claw`、`#/workbench`、`#/workbench/assets`、`#/history`、`#/skills`、`#/operations` 与设置子路由。能力中心的规范入口使用 `#/skills?kind=skill|tool|workflow|data`，并以 `view=library|mine|plans|connections` 表示类型内二级视图；无 kind 的旧 plans/connections 链接分别归一到 Workflow/Tool。设置的规范地址是 `#/settings/general`、`#/settings/model`、`#/settings/data`、`#/settings/local`、`#/settings/docs`；`#/settings` 和非法子页回退至通用，旧 `#/settings?connection=<id>` 链接继续按来源进入数据源或本机集成。资产观察是主导航中的独立入口；研究台其余页面支持 `#/workbench/<section>` 与 `#/workbench?section=<section>`。会话地址形如 `#/fingpt?session=<encoded-id>`，刷新页面会重新读取该会话。

当前采用用户批准的 Codex 风格：中性画布、单列导航、按需展开的研究面板；支持 Light/Dark/跟随系统，Logo 仅图案，浅蓝深白。实现与品牌资产见 [外观与主题](research-web-appearance.md)。真实能力中心、Workflow、DataHub 以外的原生审批、DSH 和文件链路保持不变，没有迁入设计原型的模拟数据。

当前产品身份统一为 **Research Workbench**。浏览器标题、favicon 与品牌图片从现行中性品牌资产读取；消息不显示可见署名，其辅助名称按当前会话模式生成。主题偏好使用 `research-web.appearance.v1`。产品壳不再发布旧名称或旧命令，但 `/api/research/*` 与现有 hash 路由保持稳定。

## 模块

| 文件 | 职责 |
| --- | --- |
| `theme.js` / `appearance.css` | 独立浏览器主题偏好、Light/Dark 色彩、导航和品牌符号；不调用研究 API |
| `index.html` | 自托管资源入口、中文语言标识和键盘跳转入口 |
| `styles.css` | 基础组件、数据与表单状态；当前布局和双色外观由后加载的 appearance.css 覆盖 |
| `icons.mjs` | 复用经批准 v2 样品中的静态线性 UI 图标；Logo 不经过此模块 |
| `core.mjs` | `/api/research` API、SSE 生命周期、路由、草稿、幂等请求和会话竞态防护 |
| `markdown.mjs` | 安全文本转义、URL 白名单、有限 Markdown 子集 |
| `views.mjs` | 会话、审批、问题、活动、Agent、文件、历史与模型选项的渲染 |
| `app.mjs` | 页面组合和真实用户交互；配置秘密不进入持久浏览器存储 |
| `settings.mjs` | 设置分类路由解析和纯渲染；每次只组合当前子页，数据加载、提交与错误仍由 `app.mjs` 控制 |
| `shell.mjs` | 页面标题、导航搜索弹层、可收起的产品导航、真实运行/最近会话与会话右侧标签面板 |
| `composer.mjs` | 输入框、真实研究 Skill 快捷入口、slash 搜索及附件拖放/粘贴入口；不直接发起研究 |
| `capabilities.mjs` | 同一能力目录的筛选、卡片、详情、检查结果、只读 Tool、不可变版本与 Workflow 模板渲染 |
| `capability-workspace.mjs` | Skill、Tool、Workflow、数据四个互斥主标签、类型内二级视图、严格类型过滤、运行计划/连接摘要与共用快览 dialog |
| `data-catalog.mjs` | DataHub 的 15 项能力 / 22 个来源双视图、诚实就绪状态、来源矩阵和单源探测渲染 |
| `connections.mjs` | 设置页统一连接中心、来源分组/同页详情、配置状态矩阵、秘密型表单和旧环境变量迁移确认；不自行读取或持久化凭据 |
| `capability-editor.mjs` | 完整候选表单、输入和文件编辑、脚本审查标识、有序 Workflow 步骤与载荷收集 |
| `capability-controller.mjs` | 显式创建/复制/导入/编辑/检查/发布/停用/启用/版本/回滚操作及失败保稿 |
| `workbench.mjs` | 市场、基金、产业链、资料等研究台入口，按需查询并把真实快照交接给研究会话 |
| `asset-workspace.mjs` | 独立资产观察：概览、OHLC K 线、MA/BOLL、成交量、成交额、换手率、MACD、KDJ、RSI、财务/事件/资料分块、自选、笔记、提醒和来源口径；指标只从 DataHub 行情行计算，缺失数据不填演示值 |
| `report-workflows.mjs` | Claw 与能力中心中的真实报告 Workflow 卡片和详情；显示锁定版本、模板、Excel 底稿、数据插件、步骤、日程和历史产物 |
| `operations.mjs` | 只读展示模型 usage、Agent/Tool、DataHub、服务健康和项目数据根占用 |

## 接口与行为

所有请求仅访问同源 `/api/research`；读取运行时、模型目录、工作空间、历史、`/capabilities` 与只读 `/tools` 后展示真实响应。错误可见，不生成本地演示结果。目录部分加载失败会独立报告并保留上次成功结果；DSH 离线时产品后端仍可读取已保存目录。Web 服务也离线时只能保留本页已加载状态，不宣称提供离线 PWA 或跨刷新缓存。

- 新研究先 `POST /sessions`，再对新会话 `POST /messages`；消息带 `Idempotency-Key`。同一个失败草稿重试复用相同键；收到 `accepted: true` 才清空原稿。界面不伪造用户/助手消息或进度。
- 研究台和资产观察页面打开不会联网；提交查询后轮询真实查询状态，完成后才能把当前 dataset 和页面上下文显式交给 FinGPT/Claw。交接只复制并核验所选会话快照，不重复取数。资产各区块独立显示 `loading/complete/partial/empty/unavailable/error`；历史行情存在时在同一页渲染 OHLC K 线、MA/BOLL、成交量、MACD、KDJ、RSI 和换手率，所有派生指标都由返回的真实行情行计算。DataHub 标准字段 `turnover` 表示成交额，`turnover_rate_pct` 表示换手率；两者不得混用，缺少换手率时显示未知。没有真实值时不补价格、估值、主题或同类比较。
- Claw 首页先读取 `/report-workflows`，单独展示已迁移的报告 Workflow；通用 Workflow 卡不会冒充具体报告。点击详情只查看资源与版本，点击运行才创建独立 Claw 会话。AI 周报处于 `needs_attention` 时禁止运行。
- 运行与用量页使用单个 `/operations/summary` 汇总请求，避免并发遍历同一 DSH 历史造成瞬时健康误判；页面无停止、重启或删除按钮。缺失 usage 与模型价格分别显示“未知”和“费用未配置”。
- 会话详情来自 `GET /sessions/{id}`；SSE `snapshot` 替换真实详情，`runtime_error` 显示运行错误。事件连接恢复只重新读取快照，不重发消息。跨会话旧响应会被忽略；较旧 HTTP 快照不会覆盖后来到达的 SSE 输出。
- FinGPT/Claw 二级侧栏中的每条会话使用“会话链接 + 同级更多按钮”，菜单提供重命名和删除，正文页不再放独立重命名按钮。菜单在外部点击、Escape、路由切换、滚动或窗口变化时关闭并恢复触发按钮焦点；移动端保留至少 44px 触控区。重命名、取消、批准/拒绝均调用对应真实接口。运行时提问通过问题响应接口回复；根回合结束但子 Agent 仍活跃时保留运行状态和停止入口。
- 删除先把会话移入“已删除”并保留 30 天；模式历史页可在“研究 / 已删除”间切换，已删除项可恢复或经二次确认立即永久删除。到期清理在服务启动时执行，并由在线任务每 6 小时重试；永久删除必须先获得 DSH 原生删除确认，再清理 Workbench 附件、数据集、产物与索引。删除中或已完成原生删除的墓碑不能恢复；运行、排队、等待输入／授权或取消中的会话不能删除。
- 当前会话的用户消息右对齐，Assistant 消息左对齐；两者都不显示可见头像或署名。每条消息容器的 `aria-label` 同时作为 accessible name：用户为“用户消息”；Assistant 按当前会话 mode 分别为“FinGPT 回复”或“Claw 回复”，其他或未知 mode 使用中性的“助手回复”。该视觉变更只作用于当前渲染，不改写历史消息正文或角色。
- Agent 卡片显示实际 tokens、错误、已结束回合累计耗时及历史截断提示；活动使用原生工具时戳显示耗时，并以 Agent 名称关联。无测量值不伪造数字。聊天隐藏本次内部任务后缀，但保留用户引用的旧标记和正文。异常横幅分别统计并表述失败活动与异常子 Agent，不把两者合并为含混总数，也不改写历史记录。
- 重命名和原生问题使用应用内表单；不调用 `window.prompt`。SSE 重渲染保留当前表单草稿；问题可选择选项并补充文本，仍提交既有原生 `answers` 契约。
  - `multiSelect` 缺省/false 为单选 radio，true 为多选 checkbox；前端收集与后端均拒绝单选多值。
- 编辑器提供显式 `expected_formats` 与按 Skill 默认格式；选择随草稿/幂等请求保存。父/子任务和交付检查未结束时不排队新消息，允许先准备草稿。右侧单独展示 `delivery` 的要求、实际文件、缺失/损坏原因；“执行已结束”不等于“文件交付已检查”。详见 [交付契约](research-web-delivery.md)。
- 右侧“研究资料”仅渲染会话详情/SSE 快照中的 `detail.datasets`，不另起轮询；它位于交付检查与活动之间，独立于生成文件和交付状态。旧会话的空数组不显示占位卡片。每张真实资料卡展示来源安全链接、状态、请求/实际范围、记录数、分页结束语义/页数/供应商总量、取数时间、`as_of`、缺失、限制和快照复用信息。`partial` 即使分页结束仍以警示呈现，`snapshot` 明确不代表完整历史，未知状态不按成功显示。
- 资料下载由当前会话 ID 和资料 ID 在浏览器本地严格构造，仅允许 `rows.csv`、`rows.json`、`manifest.json` 三个无查询串/片段的专用路径；不信任资料返回中的 URL。会话或资料 ID 含编码分隔符、路径分隔符或其他不合规字符时不提供下载。每个下载操作具有“资料名称 + 文件格式”的独立辅助技术名称；来源 URL 仍通过 `safeURL` 过滤。
- 升级调用 `POST /sessions/{id}/upgrade`，使用返回的新会话和 `draft`；草稿放入新编辑器，不自动提交。
- 附件使用 multipart `files` 字段上传；返回 ID 作为 `attachment_ids` 提交。上传成功仅代表后端收到了文件，不代表模型已读取或工具沙箱已执行。
- 文件下载只使用真实返回且经过检查的同源会话文件 URL。HTML 预览 iframe 使用空 `sandbox` 和 `no-referrer`，前端拒绝外部或任意路径的预览地址；后端仍负责授权、路径隔离和响应 CSP。
- 模型切换和配置调用 `PUT /runtime/model`。API Key 为密码输入，不回填，不写 localStorage/sessionStorage，不进入日志；提交时清空输入框。失败后如需更新 Key，用户需重新输入。
- 设置在产品主导航内增加独立分类导航，拆为通用、模型服务、数据源、本机集成和架构文档；每次只渲染当前子页。DSH 模型配置不再折叠，DataHub 远程来源和本机能力互不混入。数据源页以真实连接状态概览、专业/API/公开分类、跨分类搜索和状态筛选组织 21 个远程来源，只展开当前分类；选择来源后在右侧详情面板复用原配置与探测表单。本机集成页读取专用诊断 API，按本机服务、文件夹、Office 与金融插件、浏览器、本地 MCP 五类逐行展示发现、授权、验证和可调用事实；顶部只汇总服务在线、可用项和需处理项，不输出跨组件 callable 结论。分类导航使用不修改 Hash 路由的按钮，窄屏诊断行纵向排列且交互目标不低于 44px。报告自动化位于检查表之外并链接 Workflow 目录。
- MySQL 详情仅显示本地非秘密字段；密码通过统一配置 API 交给系统凭据库，输入提交后立即清空，GET 永不回填。Wind 只保存 `auto/client_api/excel` 偏好，不收集账号密码；Client API 探测读取当前会话状态但不代为登录，Excel 未提供真实工作簿心跳时保持未验证。iFinD 和知丘使用账号池，天软、Tushare、Tavily、Bing 使用单一秘密；所有秘密都只进入系统凭据库。尚未完成 DataHub 适配或无需鉴权的来源只展示真实状态与诊断，不渲染无效配置表单。
- Excel 应用与自动化桥、Wind 终端与 Excel 插件都在本机页分别展示，发现事实不能覆盖授权、真实验证或可调用结论。Wind 登录未验证时不显示“无需授权”；iFinD 专业终端在 macOS 标记不适用，普通同花顺客户端不作为其证据，SDK 与 HTTP API 继续由数据源页管理。报告自动化位于环境检查之外。重新检测使用专用异步探测 API，任务有服务端时限、单通道执行门和安全字段白名单；终态后只采用完整且一致的状态快照。旧 `.env` 迁移仍只属于数据源页：先显示不含值的预览，用户选择目标并二次确认后才调用迁移接口。
- 前端安全 console 事件只包含固定事件名、请求 method 和 HTTP status；不记录 URL、会话 ID、输入、文件名、响应正文或凭据。服务端持久日志由 Research Web 后端负责写入项目日志设施。

## Markdown 与安全边界

支持标题、段落、粗体/斜体、行内代码、围栏代码块、列表、引用、简单表格与 HTTP(S) 来源链接。原始 HTML 始终转义；不执行模型输出的脚本或 HTML，不远程加载 Markdown 图片。来源链接拒绝活动协议、凭据 URL、控制字符与协议相对 URL。不是完整 CommonMark 实现。

生成文件链接限定 `/api/research/sessions/{sid}/files/{fid}/download` 或 `/preview` 路径；资料链接另限 `/api/research/sessions/{sid}/datasets/{did}/files/{rows.csv|rows.json|manifest.json}`。两者都拒绝路径穿越及编码分隔符。前端校验不替代服务器授权。

## 验证与限制

```bash
node --test tests/javascript/research_web*.test.mjs
node --check app/research_web/ui/app.mjs
git diff --check
```

独立 JS 测试涵盖真实解析/渲染、设置五个子路由与旧深链、单页正文和来源分组、本机总体诊断与组件状态映射、探测完成/失败/格式异常/超时、恶意 HTML/URL、API 结构化错误、multipart 上传、日志秘密隔离、幂等重试、跨会话竞态、SSE 重连/清理、Claw 升级草稿、生成文件 sandbox，以及资料卡状态/范围/不完整警示和固定下载路由。

浏览器视觉、键盘/移动端状态和真实 DSH 全链路由集成任务另行验证。DSH 模型凭据、工具沙箱、文件读取与 Agent 执行能力取决于实际后端，不由 UI 模拟。此变更不涉及桌面安装或 Windows 运行验证。

## 产品壳与研究首页（2026-09-03）

当前产品采用 68px 一级导航与 248px 模式二级侧栏。一级导航只承担 FinGPT、Claw、资产观察、研究台、能力中心、运行与用量和设置；“新研究”、运行任务、最近研究属于当前 FinGPT/Claw 二级侧栏。Claw 二级侧栏再以“会话 / 工作空间”标签切换，非 FinGPT/Claw 页面不渲染二级侧栏；≤1050px 时这些导航进入可开关抽屉。导航底部和设置页都能选择外观，手机保留原有全局搜索按钮。顶栏展示当前页面/会话标题；搜索只覆盖已加载的真实会话与 Skill/Workflow/Tool。运行时健康且已授权时顶栏保持静默；只在需要配置模型、事件通道连接中或研究服务不可用时显示通往设置的异常提示；顶栏不提供全局刷新，完整 DSH 诊断与页面级刷新仍位于设置、运行与用量及相关业务页面。研究面板默认收起，展开后仍显示实际活动、资料、文件及固定版本 Workflow；异常和未完成交付在主画布保留提示。原 hash 路由、其他页面的 data selector 和全部能力操作契约不变。

FinGPT 与 Claw 分别呈现首页。FinGPT 面向问题研究，其四个快捷入口严格筛选同一 `/capabilities` 目录中的 `document-reading`、`company-research`、`industry-research`、`fund-evaluation`。Claw 明确目标、约束与预期交付；快捷区标题为“研究步骤模板”，只展示同目录 `kind=workflow` 且 `enabled=true` 的真实模板（包括已发布自建模板），不硬编码模板 ID，也不把缺项替换为 Skill 卡片。Claw 仍可通过上方能力选择框/slash 使用真实 Skill，并明确模板不代表已执行。目录缺项显示空态，不补造卡片。

两种首页分类选项仅来自各自快捷区条目的实际 `category`，`#quick-category[data-quick-category]` 只在本页内存筛选；切换路由时复位，目录更新后未知分类按全部显示。筛选不请求后端、不改变草稿或执行能力。首页卡片使用 v2 四列紧凑布局（手机两列），默认显示名称和简短输入要求；完整说明在能力详情查看，分类放入“浏览研究入口与分类”折叠区。能力中心按视口使用四／三／二／一列卡片，显示简介、来源、输出和实际状态；场景/输入可原位展开，不删除元数据。既有 `data-skill-detail` / `data-skill-shortcut` 按钮保持：详情进入能力中心，选择将不可变的 `capability_id` / `capability_version` 放入此前 FinGPT 或 Claw 的当前草稿，不创建会话或启动模型；旧 `skill_id` 仅保留 API 兼容。

首页采用样品的左对齐标题、800px 编辑区、单行桌面工具栏。模型从顶栏移入编辑器，格式和完整能力下拉按需展开；输入框继续使用既有附件、模型和格式契约。`/` 搜索已启用 Skill/Workflow，ArrowUp/ArrowDown 选择、Enter 放入草稿、Escape 关闭；slash 草稿不会意外提交模型。显式 `expected_formats`（含空数组）优先，否则根据所选目录元数据显示默认格式并由后端绑定；删除了前端平行的硬编码默认格式表。工具意图使用 `tool_ids`；当前 Runtime 已暴露的 DataHub 工具在调用时自动执行、不逐次确认，其他原生审批契约不变。运行时未就绪只禁止真实发送，仍允许浏览和准备草稿。

拖放/粘贴文件复用既有 multipart 流程。空首页不分配右侧空面板；研究详情中桌面也可显式收起/展开。活动/资料/文件标签仍只读取当前会话，Claw 会话/当前工作区切换继续复用安全下载与隔离预览。DataHub 按启动时已物化的可用工具自动查询；其他原生审批、停止、子 Agent 和交付语义不变。

## 能力中心闭环

接口契约和包边界以 [能力包与版本](research-web-capabilities.md) 为准。能力中心固定为 Skill、Tool、Workflow、数据四个主标签，任一页面只渲染当前类型；主标签使用 roving-tab 键盘行为，切换时清除不适用筛选。Skill/Workflow 使用同一目录但分别呈现，并提供能力库与“我的”二级视图；Workflow 另有聚合既有报告日程与运行证据的运行计划。Tool 仅展示真实只读声明、调用状态和授权原因，连接配置深链设置页，可选工具才有“放入草稿”；参数、来源、审批与条件均来自后端。

“数据”主标签不是第四种运行器。页面从 `/data/catalog` 读取静态能力、来源和绑定，以“数据能力 / 数据源与连接”二级视图隔离展示，不与 Tool 卡片混排；保留分类、市场、状态和鉴权筛选。来源卡同时展示代码、适配、配置、依赖、允许、可调用和最近探测，不能用一个绿色状态掩盖缺口。只有用户点击“检测连接”才 POST 单一来源 probe；打开、切换和刷新目录不联网。把能力放入研究草稿只选择相应的品牌无关 `datahub_*` Tool，不立即取数。

四类共用居中快览 `dialog`，展示简介、适用场景、输入、输出、依赖、所需工具和真实状态原因；支持 Escape、遮罩关闭、焦点锁定和关闭后的焦点恢复，手机降级为全屏弹层。“立即使用”只把锁定能力和默认格式带入此前研究草稿，不创建会话、不发送消息；不可用条目禁用操作并显示具体原因。编辑、包文件、版本和报告 Workflow 的复杂管理继续进入专用视图。

手动新建与编辑提交完整 `DraftInput`，剔除服务器生成的 import/file issues，但保留候选文件内容或 base64 字节。脚本阅读后显式确认当前 SHA256，改写候选文件会清除审查确认；保存后还需检查和发布。内置只有复制入口，不覆盖编辑。导入精确 `SKILL.md` 或 ZIP 使用单个 multipart `file`，检查失败仍展示原问题，不伪造成功。发布、停用、启用、回滚与版本查询均调用真实 API，活动冲突保留草稿和后端错误。SSE 状态会回填会话摘要，进入能力中心也刷新列表；可能过期的其他会话 running 缓存仅作提示，不永久锁住发布按钮，后端全局活动锁最终裁决。发布直接采用已确认的完整变更响应，避免额外回读失败把已成功发布误报为失败。历史版本只读，导出地址按 ID/整数版本构造固定同源路径，不信任任意下载 URL。

对话创建只调用 `/capabilities/creation-sessions` 并将返回的未发送 `draft` 放入新会话。用户明确发送后才制作包。只有 `purpose=capability_creation` 且 `kind=outputs` 的实际 `SKILL.md`/ZIP 可进入 `/capabilities/from-artifact` 审查，普通研究产物和上传附件无此入口。导入不自动发布。

Workflow 表单提供有序步骤、关联 Skill、工具意图和输出格式，不提供拖拽或独立运行器。会话详情使用收据记录的 `id:version` 读取不可变版本，右侧明确分离“预设步骤”和 DSH 实际活动；缺少版本数据时说明未载入，不以当前目录推断历史执行，不自动标记步骤完成。

不可变版本读取期间使用占位防止重复请求；读取失败会移除该占位，后续显式刷新或新会话快照可重新读取。恢复成功只清除对应的版本读取错误，成功版本仍保留缓存，不重发研究消息或工具调用。

已保存候选在后端持久化，刷新可从目录详情恢复。尚未保存的表单/研究草稿仅在本页内存保留，不写浏览器持久存储。选择版本随会话草稿切换与幂等重试保留，目录更新不静默改绑版本。

### 状态矩阵

| 状态 | 已实现的 UI 语义 | 验证证据 |
| --- | --- | --- |
| 默认 / hover | 导航、真实 Skill 卡和标签可聚焦；能力中心顶层页签只以文字与弱细线轻微强调，选中态由 `aria-selected` 和 2px 指示线表达，hover/按下不复用主按钮填充态 | `research_web_ui_layout.test.mjs` 与 `research_web_capabilities_ui.test.mjs` 渲染契约 |
| loading / disabled | 原有控制器 busy/loading 状态禁用上传、选择与提交；不清除草稿 | 既有 `research_web_ui.test.mjs` 控制器覆盖 |
| running | 运行任务显示在侧栏；停止仍使用已有取消接口 | 壳层渲染 + 既有 controller/API 测试 |
| error | 目录/API 错误保留可见；失败活动默认展开并显示错误 | `views.mjs` 渲染与 UI 回归 |
| empty | 缺少真实会话、Skill、资料或文件时显示操作性空状态，不填演示数据 | 壳层与既有 views 测试 |
| keyboard | skip link、焦点恢复、Enter 发送、Escape 关闭抽屉沿用；`/` 可搜索真实 Skill；数据源分类支持左右方向键/Home/End，详情可由 Escape 关闭并把焦点还给来源卡片 | 单元及真实浏览器 slash/Escape/ArrowDown/ArrowRight/Enter、移动抽屉检查 |
| 能力禁用/缺依赖/冲突 | 停用能力只可查看；导入检查问题和操作错误可见，不自动发布或安装 | `research_web_capabilities_ui.test.mjs` |
| 编辑/保存/版本 | 失败保留完整候选；保存可由新控制器重新读取；版本与工具意图参与幂等消息 | `research_web_capabilities_ui.test.mjs` |
| 离线/键盘 | 运行时离线禁发送但可编辑；真实 app 事件处理器消费 slash/Escape/移动抽屉和搜索 | 无网络 DOM 边界测试；不替代真实浏览器 |
| Claw 工作区 | 会话恢复聊天；当前工作区主画布只投影当前 `detail` 的资料与文件，复用安全下载/预览 | `research_web_ui_layout.test.mjs` |
| 会话管理 | 行级菜单重命名/软删除；已删除视图恢复或永久删除；30 天后在线自动清理 | UI 布局测试 + `test_api.py` 生命周期测试 |
| 首页模板/分类 | Claw 仅已启用 Workflow；FinGPT 四 Skill；分类本地筛选，卡片与上方 Skill 选择只准备版本草稿 | 布局渲染测试 + 实际 app 事件无网络 DOM 边界测试；视口/hover 由控制器另验 |
| 数据目录 | 15 项能力、22 个来源双视图；MySQL 展示本地配置状态链，未适配/未配置/不可调用分别可见，显式探测只访问一源 | `research_web_capabilities_ui.test.mjs` + `research_web_ui.test.mjs` + `test_datahub_catalog.py` |
| 数据源工作台 | 21 个远程来源按专业/API/公开分类；搜索跨分类，状态筛选叠加当前视图；详情关闭不修改连接或凭据状态，空结果提供可恢复提示 | `research_web_connections_ui.test.mjs` + `research_web_connections_workbench.mjs` |

实现子任务未启动模型；集成控制器已另行执行真实Web验收。`tests/e2e/research_web_layout.mjs`覆盖1440/1600/1920、820平板与390手机共15页面组合，搜索、分类、slash键盘、抽屉及四Skill双模式草稿通过；`tests/e2e/research_web_connections_workbench.mjs`使用只读本地目录夹具覆盖 1440×1000、768×1024 与 390×844 的数据源分类、跨分类搜索、状态筛选、详情关闭、键盘和水平溢出。屏幕阅读器和桌面平台未验证。新真实模型旅程（自建Skill、PDF、Workflow双Agent文件）和只读历史回归见 [本轮记录](../.ai/reports/2026-09-03-research-ui-live.md)。

设置中的「架构文档」链接只打开 `/api/research/documentation/index.html`，新页以noopener/noreferrer隔离；目录与八图由固定路由、受限文件读取及独立CSP提供，详见 [文档模块](research-web-documentation.md)，不会开放仓库或Runtime目录。

Windows 专项 CI 会在原生 runner 上启动同一 Research Web 服务并调用本机集成状态与探测接口，再执行设置页 DOM 契约；它验证页面消费真实 Windows 投影，不用预制“已安装”数据替代厂商软件证据。

已受理但原生不运行、交付仍等待时显示「重新核对停止」，调用已有取消端点。离线不可操作，复核前发送仍禁用；后端严格核对后只允许以verification_failed说明缺失终止记录，不能用UI按钮将任务伪报成功。普通运行任务仍使用「停止」。
