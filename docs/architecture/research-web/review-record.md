# 架构迭代核对记录

## 2026-09-16 — 现有 DataHub Provider 真实闭环补强

- AKShare 探针改为固定域名、禁用环境代理/重定向、限制 16 KiB 且受 10 秒总墙钟约束的可取消异步交易日历请求，并与查询共享容量门闩。
- 天软 CJPY 增加精确版本与离线 wheel 哈希锁、安全错误映射、Token 反射拒绝和最近 14 天实时快照窗口；MySQL 增加缺驱动及常见认证、权限、网络、TLS 等稳定错误分类。日志、API 与快照均不携带 SDK/数据库原始错误正文。
- 本批仅收紧既有 Provider 内部探针、日期契约和错误归因，不新增来源、业务 Tool、接口、持久化类别、服务或跨模块数据流，因此现有 DataHub、Runtime 与文件流图无需重生成。公共来源真实验证与天软/MySQL 外部账号验收继续分开记录。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"仅补强既有AKShare、天软CJPY和MySQL Provider的探针时限、日期契约、可选依赖与安全错误映射；目录、Broker、15个业务Tool和快照数据流不变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"Runtime仍通过既有品牌无关DataHub Tool和Broker调用Provider，本批没有新增注册工具、进程、接口或授权边界。","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"查询结果仍写入既有JSON、CSV和Manifest快照；只收紧错误正文不落盘的约束，没有新增持久化类别。","diagrams":[]} -->
## 2026-09-14 — 六个 CPU 有界资讯/事件 Skill

- 能力目录增加每日市场简报、政策哨兵、事件复盘、ETF 资金流、业绩报告监控和业绩预告监控六个
  独立内置包；均复用既有检查、不可变版本、原生发现、会话资源快照与 `research_run_script` 沙箱。
- 种子把阶段 1 CPU 预算、结果和 provenance 资源复制进每个版本并生成 reviewed script 哈希；各包
  仅消费相对路径 JSON，不新增网络、Excel、GPU、子进程、线程池、服务、页面、API 或 Workflow。
- DataHub/Wind 字段映射只描述现有可调用业务工具和明确 fallback gate；ETF 分类及可选暴露由输入
  提供，事件回归样本不足返回 unavailable。现有十张架构图已覆盖能力发布、Runtime 脚本调用和
  DataHub 会话快照关系，因此无需改变拓扑或重生成图源。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"六个CPU计算包复用既有research_run_script沙箱、FIFO、预算和会话相对路径输入，不新增执行节点或权限。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"能力目录增加六个声明式内置Skill及版本资源，仍复用现有检查、发布、原生发现、选择和快照链。","diagrams":[]} -->

## 2026-09-11 — MCP 安装、授权与 Research Web Host

- Registry 仍是只读发现边界；新增 `mcp_runtime` 负责固定制品解析、完整二次确认、不可变安装清单、官方 SDK 连接与 OAuth，秘密只进入独立系统凭据库。
- 工具 schema、风险等级、无人值守许可、会话 grant 和一次性审批由 Host 保存；DSH 只加载命名空间化快照并通过私有 loopback 请求 Host，每次调用重新核对版本、schema 和授权。
- 启停等待活动研究归零并仅重启专属 DSH，候选健康失败时恢复旧激活清单。Tool 市场恢复持久安装并分别呈现探测、启停、移除、OAuth、风险策略、会话授权和高风险审批。Automation/外发仍未进入本阶段。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"MCP市场新增完整安装确认、持久安装管理、工具策略、会话授权和一次性审批队列。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"新增MCP安装、探测、启停、OAuth、能力、授权、资源、提示和审批接口。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"Research Web Host持有官方MCP SDK连接，DSH只经私有控制通道调用命名空间化工具并支持激活回滚。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"capabilities","structure":"changed","reason":"工具发现加入不可变安装版本、schema哈希、风险分级、会话快照和无人值守拦截。","diagrams":["02-module-dependencies"]} -->

## 2026-09-10 — Tabbit CLI 实时页面上下文

- Research Runtime 增加固定 `dsh-tabbit@0.3.4` 供应包、私有 Profile 加载和单一 `ctx.tabbit` 适配层；安装器禁用，不运行时下载或升级。
- Research API 增加安全状态/配置、会话授权和标签候选端点；消息提交增加最多 8 个标签引用、实时确认、发送前再次校验和一次性折叠上下文。
- 输入框增加按需 `@` 标签检索、可移除 chip 和二次确认；设置本机集成页增加两个独立开关、实例选择与诊断。真实 macOS/Windows 浏览器冒烟仍是独立完成门禁，模拟 Runtime CI 不替代该证据。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"输入框新增按需Tabbit标签选择、chip、授权和实时接管确认，设置页新增本机集成状态与配置。","diagrams":["01-deployment","02-module-dependencies","03-research-sequence"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"新增Tabbit状态配置、会话授权、候选标签端点，并在消息提交前完成实时引用校验和提取。","diagrams":["01-deployment","03-research-sequence"]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"Runtime私有Profile加入固定供应的dsh-tabbit和单一ctx.tabbit适配层，新增实时claim、内存token和审批边界。","diagrams":["01-deployment","02-module-dependencies","03-research-sequence"]} -->

## 2026-09-10 — Tabbit macOS 真实验收收口

- 真实 macOS 使用官方签名、公证的 Tabbit 1.13.24.0 与 CLI，完成首次授权、按需检索、1/8 页实时 DOM、动态表单、二次确认、标签保留、占用失败保留草稿、只读自动执行、写操作拒绝/批准和 `web_fetch` 开关旅程。
- Runtime 的 `DSH_HOME` 保持私有，宿主用户路径只用于定位 Tabbit launcher/实例；实时 claim 结果按可信清单恢复用户选择顺序，相同标题与 URL 无法唯一映射时失败关闭。
- 原生审批响应被接受后立即移除 BFF 的待审批投影，迟到的 resolved 事件保持幂等。Windows 继续以原生 CI 交付，真实 Tabbit 浏览器明确未验证；既有部署节点、端口、API 和桌面发布门禁不变，十张图无需重生成。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"审批受理后只收敛既有待审批投影，Tabbit状态、授权、消息和审批API契约不变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"宿主用户路径仅供既有Tabbit插件定位launcher和实例，DSH_HOME、Profile、执行器与部署节点保持不变。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"真实macOS验证覆盖现有授权、标签选择、确认和失败保留交互，没有新增页面或组件边界。","diagrams":[]} -->

## 2026-09-08 — DSH 最新版 Gateway 兼容迁移

- Research Runtime 固定到基于官方最新 `master` 重建的 Fork 运行分支；Workbench 兼容桥把原有白名单调用映射到 Typert Gateway 的斜杠端点、`payload.args`、Cookie 鉴权和 Remote 复用流，对外 HTTP、会话、消息、DataHub、文件与删除接口不变。
- 服务管理器增加一次性启动令牌换 Cookie、`0600` 控制文件核验和可配置备用端口；生产 3081/8088 在隔离验收完成前保持旧运行版本。
- 新版 DSH 已移除独立 `report` 工具；Claw 子 Agent 结果通过原生 continuable 链路回传，能力目录和最终工具 guard 不再声明不存在的工具。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"兼容桥只把既有白名单RPC、历史恢复、审批和事件投影映射到新版Typert Gateway与Remote协议；Workbench对外API、会话语义和SSE边界不变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"固定DSH版本、Cookie鉴权和备用端口属于既有专属Runtime与Service Manager节点内部升级，不新增生产服务、端口或执行引擎。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"移除新版DSH已不存在的独立report工具并同步真实参数名；Skill、DataHub和子Agent能力仍经相同原生工具注册与guard边界。","diagrams":[]} -->

## 2026-09-08 — 用户本地 MySQL DataHub

- DataHub 增加本机连接配置与系统凭据库边界、逐级 schema 和参数化单表工具；目录更新为 15 项能力、22 个来源。真实 MySQL 与原生 Windows 验证尚未执行，不能由离线模拟推导可达性或平台兼容。

<!-- architecture-review {"group":"datahub","structure":"changed","reason":"新增用户本地 MySQL 配置与系统凭据库边界、两个受控业务工具及单线程 Provider。","diagrams":["02-module-dependencies","03-research-sequence","04-data-file-flow"]} -->

## 2026-09-07 — FinGPT 对话、DataHub 自动查询与异常统计

- 对话展示仍位于现有 UI 模块，不新增服务、接口或状态存储；用户右侧气泡、无可见署名、模式化 ARIA 与分类异常横幅属于既有会话投影的呈现修正。图 02 更新 UI 到现有 BFF/DSH 的关系说明。
- DataHub 原生桥删除逐次审批，改为 Runtime 启动时从离线能力目录生成 `enabledTools`；严格参数、来源、会话、loopback、控制令牌、取消和响应上限不变。图 02、03、04 同步自动查询与 fail-closed 边界。
- AKShare 与天软 Provider 截止时间为 15 秒；超时发布 `failed/deadline` 快照，单线程门闩在底层同步调用结束前返回 `provider_busy`，不新增后台队列或执行服务。
- 既有会话的失败历史不迁移；只更正 `subagents` 统计字段和横幅措辞。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"对话消息去除可见身份行，用户气泡右对齐，并将失败活动与异常 subagents 分类汇总；仍复用既有消息、Markdown、SSE 和会话接口。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"DataHub Tool 从逐次审批改为 enabledTools 启动过滤与自动只读查询，并增加严格参数校验、15 秒 Provider 终态和 provider_busy 隔离。","diagrams":["02-module-dependencies","03-research-sequence","04-data-file-flow"]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"Research Runtime 启动时按离线可调用来源生成 enabledTools；未满足来源条件的工具不注册，配置变化重启生效。","diagrams":["02-module-dependencies","03-research-sequence","04-data-file-flow"]} -->
<!-- architecture-review {"group":"capabilities","structure":"changed","reason":"DataHub 工具审批元数据改为 automatic，能力目录继续展示全量登记项但不扩大 Runtime 注册边界。","diagrams":["02-module-dependencies"]} -->

## 2026-09-03 — 研究 UI 与能力中心（进行中）

- 起点：`304930d`；隔离分支 `codex/dsh-web-v1`。
- 已核对：独立入口、DSH 传输、原生状态投影、DataHub 与独立文件交付。
- 正在实现：新研究壳、能力包与版本、能力中心、文档同步检查。
- 新模块未完成前不画成已实现；根文档最终入口在集成批次统一更新。
- 图 01 已做一次可读性修正（放大节点、保持拓扑和字体）；图 03 首次四视口发现纵向溢出，收紧行间距后重验通过。01/03/04/06/07 的 showcase 均为 9/9、零错误零警告，四视口自动包含性检查通过；主控制器已查看最终小屏深色与大屏浅色截图。人工核对记录仍需绑定最终哈希，不将自动 `visualReview: pending` 改为伪造通过。
- 运行图展示主要投影与分支示例，不枚举所有转换：连接中断可能覆盖任何状态，恢复后可能回到运行、完成或其他终态；不是只有断线才产生 interrupted/blocked/incomplete。完整语义以 `projection.py` 和 `service.py` 及 02 文档为准。
- UI 首轮审查发现双侧栏结构和 Claw 工作区切换未完成，已退回修正；浏览器发现单独 `/` 没有列出 Skill，同轮回归修复。
- 后端基线复跑：`python -m pytest tests/research_web --confcutdir=tests/research_web -q` 为 118 passed、1 skipped（13.94s）；这是能力改动前基线，不是本轮最终验收。
- Task 1 完整 JS 为 44/44 通过；原生 schema converter 在设置 DSH_SOURCE_ROOT 后聚焦重验 1 passed。新真实会话 `82f9904a-4c4c-4d35-a1cd-93985437f488` 完成四轮、刷新、重命名、脚本生成 HTML；显式 HTML 要求的独立交付通过，旧文件未混入。只读浏览器 readback 四项通过并保存下载哈希，见 `.ai/reports/2026-09-03-research-ui-live.md`。模型一次聊天数字误述已保留并经读取文件纠正，不将格式检查当内容准确性证明。
- Archify `sources` 要求固定公开 GitHub revision，本地未提交代码不具备此条件。因此采用单独受检查的本地 evidence 清单，不伪造公开仓库来源。
- 能力图 05 的 workflow 初稿未通过布局：固定列网格与中文节点发生距离不足，失败分支穿线；两轮几何修正未降低最佳错误数，按 Archify 停止继续微调该候选，保留 JSON 草稿与未完成状态。该图没有可信 HTML 或回执，不列入已交付图册。后续需重新选择适合实际模块关系的表达方式，不能把生成数量当验收。
- 05 失败 workflow 稿已归档 `.ai/reports/archify-drafts/05-capability-workflow.failed.json`。改用 architecture 类型表达「包管理 / 发布边界 / 研究调用」实际关系，9/9 零错误警告通过；四视口第一次 Chrome load 超时，未改 HTML 原样重试通过。最终 1440 深色与 2048 浅色截图已人工查看并绑定哈希。此成功属于替代模块图，不把原 workflow 草稿改称通过。
- 全部必需浏览器/真实模型/安全/文档负向测试完成前，不记为最终通过。
- Task 2 修复后完整 210 项测试通过；限定复审四项均关闭且无新增重要问题。专属实例空闲更新后，旧会话冷恢复发现六项能力，并完成第五轮真实问答、保留两份旧文件；能力创建发布与 Workflow 真实旅程仍待 UI 接线。
- 02 模块依赖图按已出现的三个能力 UI 模块与实际后端路由/服务编写；首轮五个竖向关系标签遮挡源节点，采用诊断建议 labelDy=24 后 showcase 9/9 零错误警告通过。四视口及两张人工查看记录绑定最终哈希。新模块的浏览器功能验收仍单列。
- 只读历史浏览器回归再次打开三份旧真实会话：PDF 页码与附件保留、四资料卡243条13页、两名原生子Agent、最终Excel下载哈希、取消后无审批按钮通过；不将历史读取说成重新执行工具或模型。
- Task3 已提交 c73c5ff 并审查通过；工作流不可变版本读取失败后不重试的 Minor 经 b7a99a3 修正，限定复审 Approved。`DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs` 实际68/68、零跳过。该修复不改变模块依赖或状态定义，因此不改图的原因是仅清理失败缓存占位、保留重试语义；已更新模块说明和回归。
- Task2 真实创建暴露旧文件ledger作为伴随文件来源的问题，d997759 修正当前安全文件清单选择、实际unsafe路径/读取消失拒绝、创建kind冲突及制作schema提示。233 Python passed，限定复审 Approved。07:38 UTC 仅所属Web8088空闲重启；实际根SKILL.md导入由原invalid_resource恢复到正确name_conflict（同名ZIP能力已发布），历史ledger未删。该修复未改变能力包管理/运行层边界，不改05图拓扑的原因是更正既有文件选择及验证实现，补充07模块说明及测试。
- 对话创建模型产物经人工审查，Skill1ba298cc v1实际发布并在新会话7ee7b736使用；真实Python生成统计HTML并读回，浏览器版本刷新、隔离预览和下载哈希通过。手动导入528c5a3d完成元数据编辑/检查/v1/v2/停用/回滚v1/刷新/导出；未调用额外模型或扫描全局Skill目录。详细证据见真实验收报告，不把导入检查替代实际研究质量判断。
- Workflow会话43170801已从旧资料准备会话升级，复制四份当前会话只读快照；使用原生Workflow v1提交双子Agent研究。正在验收文件，未提前勾选预设步骤或宣称交付完成。

## 本轮结构核对与最终证据收口

<!-- architecture-review {"group":"ui","structure":"changed","reason":"拆分产品壳、输入框与能力目录详情编辑控制器，实际研究与能力API仍由同一轻量服务提供。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"消息增加不可变能力版本与创建会话用途验证，仍用原生DSH执行和双通道SSE恢复。","diagrams":["03-research-sequence"]} -->
<!-- architecture-review {"group":"files","structure":"changed","reason":"新增明确停止后的终态缺失复核，只有任务绑定和新鲜空闲证据完整才持久化verification_failed，不解析文件或伪造结束；图07同步异常分支与说明。","diagrams":["07-delivery-state"]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"原生发现仅注册产品专属能力目录，研究会话挂载不可变版本资源，不新增运行引擎或权限。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"capabilities","structure":"changed","reason":"新增包管理、静态检查、版本发布与原生指令编译，统一Skill和步骤模板而不另建调度器。","diagrams":["05-capability-flow"]} -->
<!-- architecture-review {"group":"documentation","structure":"changed","reason":"仓库内新增图文一致性检查并接入原有CI，设置通过固定HTML白名单与隔离CSP访问图册。","diagrams":["08-iteration-docs"]} -->

- 08图对应已提交3e0209e的检查器、路由与CI；showcase9/9零错误警告，四视口通过，1440深色及2048浅色已人工查看。八图均绑定真实JSON/HTML哈希，未改写自动回执的人工待检查字段。
- Workflow 43170801真实两名子Agent共用四份快照；本次没有再取数。初版Excel统计格残留代码文本，保留原件并让模型生成v2。DOCX/HTML/XLSX已下载及重开，净值243条、收益34.869240%、最大回撤−12.478032%、原始单位净值年化波动率21.695831%经独立复算；不是含分红总回报。文件结构通过不等于研究观点正确。
- 新PDF会话63d128e4实际上传、选择资料解读、单次脚本读取18页PDF的物理14/15页；运行中刷新未重复提交，回答给出可核对页码。最终只读脚本重验通过，没有再次调用模型。
- 新审批拒绝会话839ec20a：工具记录明确 `Public data approval rejected; HTTP not sent`，最终无数据、无文件、无子Agent。模型回合完成与被拒工具失败分别显示。
- 本轮新数据/模型旅程、历史只读回归和自动测试分开记录于 `.ai/reports/2026-09-03-research-ui-live.md`。远端CI、公网部署、Windows与桌面未验证且不在范围。

## 2026-09-03 — 本机实施与验收收口

- Task1/2/3与Task4独立复审已完成；Task4五项重要问题修复于abecaf66，设置→隔离图册→图页→主题/节点详情真实浏览器通过。
- 额外停止异常修复经28项正反向与并发回归、独立复审Approved；整套287 Python和123 JS通过，无skip。原610ba6cb异常任务保留verification_failed，新一轮真实模型已恢复，旧失败不被覆盖。
- 图07按实际新路径重新生成，showcase9/9、零错误警告，四视口与1440深色/2048浅色人工查看绑定新哈希。八图其余拓扑未因文本状态核对制造无意义改动。
- 最终15组布局、文档交互及模型旅程的只读回归通过；手动导入/发布/回滚与真实Workflow、自建Skill报告都保留实际版本和文件。详见 [最终报告](../../../.ai/reports/2026-09-03-research-ui-final.md)。

## 2026-09-03 — Codex 风格与双色主题合入

- 用户在侧对话批准视觉稿，并明确要求继续合入正式 Web；以已提交的 30748f7 为合入基线，保留完整能力中心和原生研究控制器。
- 新增 theme.js / appearance.css，仅属现有 Web 展示组件内部：主题枚举保存在浏览器，不进入会话、Skill、DSH 或 DataHub。图 02 的“独立交互模块”仍涵盖产品壳；图 01 部署与图 03 请求序列无新增服务/接口/研究依赖，不制造无意义图源和回执变更。
- 真实布局变化和源码对应写入 docs/research-web-ui.md、docs/research-web-appearance.md；清单补充主题和浏览器回归测试。原八图与绑定哈希视觉证据保持原样，未宣称本次重新生成或重新视觉验收架构图。
- 本轮只读正式页面验证、前端回归及未覆盖边界见 .ai/reports/2026-09-03-research-web-appearance.md。
- v2 保真修正：shell/composer/capabilities 仅调整呈现，新增静态 icons.mjs；800px 编辑区与四列首页卡片有测量基线，搜索改为按需弹层，模型并入输入栏。数据/接口与八图拓扑未改变。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"新增 Light/Dark 浏览器外观属于现有 Web 展示组件内部；单列导航和折叠面板不改变研究 API、能力调用、文件归属或 DSH 部署依赖，图02已以独立交互模块概括此层。","diagrams":[]} -->

## 2026-09-04 — 全源数据目录与品牌无关 Tool

- 能力中心新增“数据”页，以同一静态目录提供按业务能力、按数据来源两种视图。目录读取不联网；手动探测一次只针对一个来源。
- 登记 13 项数据能力和 21 个来源，并拆分代码存在、完成适配、配置、依赖、允许调用、可调用和最近健康状态。当前仅东方财富基金与财联社进入真实 Provider 路由。
- 新研究 Tool 改用稳定子系统前缀 `datahub_*`，与 Research Workbench 品牌解耦；`datahub_get_fund_data` 是正式基金能力工具，不要求未来产品改名时迁移协议。
- 图 02、03、04 按实际目录、路由、原生审批、Provider 和会话快照重新建模；图 01、05–08 的部署、能力包生命周期、运行状态、交付状态和文档门禁拓扑未改变。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"能力中心新增数据目录模块、双视图、来源矩阵、详情与单源探测交互。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"新增静态能力/来源目录、业务查询路由、Provider 就绪状态与探测，并把选源和快照纳入真实研究序列。","diagrams":["02-module-dependencies","03-research-sequence","04-data-file-flow"]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"原生桥新增十三个品牌无关 datahub_* Tool，审批后调用业务查询入口；旧工具只保留兼容。","diagrams":["02-module-dependencies","03-research-sequence","04-data-file-flow"]} -->
<!-- architecture-review {"group":"capabilities","structure":"changed","reason":"只读 Tool 目录加入十三个 DataHub 业务能力，并按实际可调用 Provider 控制可选择状态。","diagrams":["02-module-dependencies"]} -->

- 最终浏览器验收发现手动探测完成后，当前来源详情仍保留旧的 `health=untested`；已先加入失败回归，再让 UI 在目录刷新后只重读同一来源详情。复验财联社显示“已接入 / 健康”，网络记录没有探测其他来源。该修复属于既有单源探测交互内部状态同步，不增加模块、接口或拓扑，因此不再次制造图源改动；02/03/04 已覆盖来源详情、单源探测和目录刷新关系。
- 命名收口后运行时只注册 `research_run_script` 与 `datahub_*` 子系统工具；旧产品前缀脚本和数据工具不再保留。`datahub_get_fund_data` 继续作为正式基金能力工具参与新草稿与消息受理。

## 2026-09-04 — Research Workbench 全仓身份与持久化启动

- 对外名称、Python distribution、CLI、桌面 sidecar、bundle、数据库默认名、数据目录、主题键、环境变量和运行时工具完成硬切换；当前产品不再发布旧 CLI 或旧产品前缀工具。
- 新增 `service_manager.py` 与 `rwb web start|status|stop|restart`。管理器固定项目 3081/8088，持久化 PID、命令指纹、项目路径和数据根；启动健康检查失败只回滚本次进程，停止不操作用户原有 3080。
- 新增 `data_migration.py` 与 `rwb migrate-research-data`。迁移通过文件数、大小与 SHA-256 核对会话、附件、能力、数据集、产物和原生历史；不复制模型凭据、DataHub 控制令牌、overlay、临时文件或日志。
- DataHub 只保留 `business-query` 与 13 个业务工具；删除旧平行目录和查询接口。Tool 目录当前为 8 个研究/控制工具加 13 个数据工具。
- 部署图、模块依赖图和研究序列图因后台服务管理、迁移和硬切接口变化重新生成；DataHub 文件流、能力生命周期、运行/交付状态及文档更新拓扑没有语义变化，不制造无意义图源改动。

<!-- architecture-review {"group":"runtime","structure":"changed","reason":"新增项目级3081/8088持久进程管理、归属指纹、健康等待和失败回滚；删除旧产品工具注册。","diagrams":["01-deployment","02-module-dependencies"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"DataHub只保留品牌无关business-query；研究提交继续通过DSH原生审批和SSE恢复。","diagrams":["03-research-sequence"]} -->
<!-- architecture-review {"group":"files","structure":"changed","reason":"新增旧研究数据的白名单复制、哈希核验和只读归档，明确排除凭据与运行时生成文件。","diagrams":["01-deployment","02-module-dependencies"]} -->
- 本轮完整 Research Web 回归为 308 项 Python 通过、133 项 JavaScript 通过，零失败零跳过。新增服务管理与迁移模块通过 Ruff、Black、isort 及隔离依赖的 mypy；全仓 Ruff 仍有 123 个旧 CLI 历史规则问题，未把旧基线误报为本轮通过。macOS Tauri debug app bundle 已构建；Windows 原生 CI 与真实安装冒烟另行记录。真实公开最小探测仅验证东方财富基金和财联社当时健康，不把其余登记来源称为已接入。

### 改名与持久服务最终结构判定

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"品牌资源、标题、ARIA 与主题存储键完成硬切换，仍由既有产品壳模块提供，不新增前端运行边界。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"新增项目级持久服务管理并保持既有研究 RPC、SSE 与恢复协议，部署边界已反映到图01。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"移除旧平行查询入口，运行时只经品牌无关 business-query 和 datahub_* 工具进入现有路由，更新图02与图03。","diagrams":["02-module-dependencies","03-research-sequence"]} -->
<!-- architecture-review {"group":"files","structure":"changed","reason":"新增白名单研究数据复制、逐文件哈希核验与只读归档边界，更新部署和模块依赖图。","diagrams":["01-deployment","02-module-dependencies"]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"专属3081与8088由持久进程管理器统一启动、核验和安全停止，3080明确排除在项目所有权外。","diagrams":["01-deployment","02-module-dependencies"]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"能力技术标识和依赖改为品牌无关命名，但包管理、版本发布和DSH调用边界保持不变。","diagrams":[]} -->

## 2026-09-04 — 项目私有 DSH 构建路径收口

- `rwb web` 的默认源码从用户开发目录切换到 `~/.research-workbench/dsh-source/`。该目录是固定提交 `b150a551b8d465e31e418e1b2eaf5e79bbb7d28e` 的项目私有副本，并在副本中完成构建；用户原有 3080 进程及其源码工作树未被修改。
- 启动前由固定源码内的 DSH 原生 helper 重建 profile 模块链接，并逐项拒绝失效或越出项目私有源码树的目标，防止迁移状态把 3081 静默接回其他实例的开发目录。
- 首次真实启动发现 Python launcher `exec` 为 Node 后命令行会自然变化；归属校验改为最终 Node CLI、专属 overlay 与端口三项签名，既保留 PID/启动命令审计，也避免把同一受管进程误判为外部进程。
- 这次调整只把既有“专属 DSH 3081”部署边界落实为独立源码路径，不增加服务、端口、接口、状态或数据流，因此部署图 01 的拓扑和其余图源无需重生成。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"服务管理器改用项目私有固定提交DSH源码作为默认路径，仍管理同一3081/8088及相同健康检查和恢复协议。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"固定构建的profile模块链接增加私有源码边界校验，仍由同一launch_runtime组装同一3081运行时，没有新增节点或依赖关系。","diagrams":[]} -->

## 2026-09-05 — 远端门禁暴露的历史分层修复

- GitHub 首轮 Project Constraints 对全仓硬改名变更集执行检查，发现历史市场首页 fact writer 从 data layer 反向导入 service helper。helper 已下沉到 `data_layer/repositories/market_home_invalidation.py`，调度服务仍保留原有 scheduler/materializer 职责。
- 历史 Agent Team、LangGraph、Session/Run 和模板注册表增加异常日志并原样抛出。这些模块不是当前 Research Web 的执行链；当前 Web → FastAPI → DSH、DataHub、文件和能力包拓扑均未变化，因此八张图不重生成。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"本次仅修复历史研究服务的日志门禁；当前Research Web仍由DSH执行，不调用旧Supervisor、LangGraph或Session/Run链。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"历史市场首页事务失效helper在data/service分层内下沉，不改变Research Web DataHub目录、Provider、Tool或快照数据流。","diagrams":[]} -->

## 2026-09-05 — 桌面数据库必需扩展预检

- 原生桌面 CI 在全新 PostgreSQL 上验证出 `asset_identifier` 的文本 GiST 排他约束依赖 `btree_gist`。数据库预检、初始迁移、静态 schema、两端 CI 初始化和安装文档现统一要求 `vector` 与 `btree_gist`。
- 该修复只补齐既有 PostgreSQL 节点的启动前置条件和错误分类，不改变当前 Research Web 的 Web／FastAPI／DSH 部署、DataHub 取数、能力包、运行状态或文件交付拓扑，因此八张 Archify 图不重生成。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"既有PostgreSQL节点增加btree_gist必需扩展预检与脱敏修复状态，不新增服务、接口调用路径或数据流。","diagrams":[]} -->

## 2026-09-05 — Web 功能合并、页面交接与只读运行监控

- 新增研究台六个页面。页面查询通过 `POST /api/research/data/queries` 进入现有 DataHub；交接只复制用户选中的会话数据集，并把筛选、来源和截止时间写入目标会话的上下文文件。FinGPT、Claw 后续仍由 DSH 执行。
- 新增“运行与用量”只读投影。模型 usage、Agent/Tool 活动、DataHub Audit、服务归属/健康和 Research Workbench 数据根占用均来自已有记录；未知 usage 和未配置价格分别显示，接口不返回问题正文、附件内容、审批参数或凭据。
- CJPY 仅迁移受支持的证券目录、交易日历、行情和快照 Provider；无依赖或配置时保持 blocked，不把登记的数据集冒充已实现。新增市场解读 Skill/Workflow 仅消费已物化文件，不引入第二研究引擎。
- 图 02、03、04 分别更新模块依赖、研究台查询/交接序列和共享资料流；其余图的部署进程、能力发布生命周期、运行状态、文件交付状态及文档门禁没有结构变化。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"产品壳新增研究台和运行与用量路由，并加入页面查询、快照交接和只读监控交互。","diagrams":["02-module-dependencies","03-research-sequence"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"研究台在创建目标DSH会话前新增受控查询和页面交接，原研究提交、SSE与审批协议保持不变。","diagrams":["03-research-sequence"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"新增页面异步查询、CJPY条件Provider、所选数据集复制和真实调用审计，仍使用同一DataHub与快照存储。","diagrams":["02-module-dependencies","03-research-sequence","04-data-file-flow"]} -->
<!-- architecture-review {"group":"files","structure":"changed","reason":"会话快照增加按dataset_id复制和Hash核验，用于研究台向目标会话交接。","diagrams":["04-data-file-flow"]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"新增市场解读原生Skill包但DSH、Guard、脚本沙箱和父子Agent运行边界未改变。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"能力目录增加市场解读Skill和Workflow种子，仍复用既有检查、版本、发布和原生发现流程。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"changed","reason":"新增六页研究台后端查询、页面上下文固化、快照交接和实际产物索引。","diagrams":["02-module-dependencies","03-research-sequence","04-data-file-flow"]} -->
<!-- architecture-review {"group":"operations","structure":"changed","reason":"新增不参与执行的只读聚合模块，读取DSH历史、DataHub审计、服务管理状态和受限数据目录。","diagrams":["02-module-dependencies"]} -->

## 2026-09-05 — 运行监控进程归属校验收紧

- 运行页面的受管进程判定从单独检查 PID 存活，收紧为状态文件版本、角色、端口、数据根、项目根、命令指纹和实际 PID 命令签名全部一致；实时 HTTP 健康仍独立显示。
- 这是既有“运行聚合读取 Service Manager 状态”节点内部的真实性校验，不增加模块、服务、接口或数据流；图 02 已覆盖 Operations → Service Manager 关系，因此不制造无意义图源和回执变更。

<!-- architecture-review {"group":"operations","structure":"unchanged","reason":"仅收紧既有Service Manager状态读取的进程归属校验，Operations模块、API和依赖关系不变。","diagrams":[]} -->

## 2026-09-05 — 能力硬改名历史版本迁移

- 真实 FinGPT 受理暴露出持久能力目录仍含旧 `af_run_script` / `af_public_data`，且内置 Skill 升级后 Workflow 仍绑定旧版本；发送前的全目录安全门因此按设计拒绝研究。
- `CapabilityCatalog` 现在按 Skill → Workflow 顺序创建新的不可变版本：内置包使用当前种子，安全用户包只替换旧脚本名，歧义数据工具保留人工审查；过期 Workflow 重新绑定当前已启用 Skill 版本。历史版本不覆盖，迁移可重复启动且不会继续增版。
- 修复后真实数据根的 10 个已启用 Skill／Workflow 全部通过 selection 校验，FinGPT 会话 `3504a20b-13ad-453f-b837-7e25f21892a2` 成功读取既有财联社快照并完成回答。
- 该修复属于既有能力版本/依赖检查节点内部的持久数据兼容，不新增服务、接口、状态或数据流；图 05 已描述检查、发布与版本关系，因此八张 Archify 图无需重生成。

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"为硬改名后的持久能力目录补充不可变版本迁移和Workflow重新绑定；仍复用既有检查、发布、原生投影与会话快照边界。","diagrams":[]} -->

## 2026-09-06 — 具体报告 Workflow 与资产观察可见性纠正

- 修复报告资源只迁入存储但未进入产品目录的问题：Claw 首页和能力中心现在读取真实 `/report-workflows`，显示创业板50周报、华安ETF周报、华安ETF投资风向标和待补全 AI 周报。卡片与详情来自锁定版本，不再由通用 Workflow 冒充。
- 迁移默认优先读取产品数据根中已经管理的 `report-projects/`，逐文件校验路径、类型和 SHA-256；重复执行 4 个项目均为 `already_present`，没有新增版本或重复历史。
- 资产观察从研究台内隐藏入口提升为主导航独立页面；保留真实行情/财务/事件/公告/新闻/研报区块、自选、笔记、提醒、来源口径和 FinGPT/Claw 快照交接。缺失的同类比较与主题暴露明确显示 unavailable，不恢复旧 Agent 委员会或演示数据。
- 图 02 重绘为当前模块关系，加入具体报告 Workflow、模板/底稿、Excel 刷新、独立资产观察和会话快照边界；showcase 9/9、零错误零警告，四视口无溢出，并人工查看 1440 浅色与 2048 深色截图。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"主导航新增资产观察，Claw首页与能力中心新增真实具体报告Workflow目录和详情。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"report-workflows","structure":"changed","reason":"具体报告资源、不可变版本、迁移、Excel刷新与Claw运行进入当前产品模块依赖。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"资产后端查询、快照交接和个人观察存储边界未变；本轮补充独立导航、真实指标回退和来源状态展示。","diagrams":[]} -->

## 2026-09-06 — 断电后的持久服务恢复

- 真实断电场景复现为 8088/3081 均停止、状态文件仍在；代码提交、报告 Workflow、会话和数据目录没有丢失。
- `WebServiceManager` 现在可清理来自先前 checkout 的死 PID 状态；只有 `_pid_exists` 明确返回 false 才移除，存活 PID 或无法确认的状态仍拒绝操作。
- macOS 将虚拟环境及 `.pth` 标为 hidden 导致 Python 跳过 editable 项目路径；清除该项目虚拟环境的 hidden 文件标志后，标准 `rwb web status` 从任意目录恢复可用，没有安装或升级依赖。
- 使用同一项目入口重新启动专属 DSH 3081 和 Web 8088，两个健康检查通过；浏览器重新核对 Claw 报告 Workflow 与资产观察，console 零错误。
- 本次不新增服务、端口、模块或接口，但 stale 状态恢复是启动时的重要安全分支；图 03 增补 CLI、Service Manager、死 PID 判定与 3081/8088 健康检查序列，并重新生成 HTML 与视觉证据。

<!-- architecture-review {"group":"runtime","structure":"changed","reason":"断电恢复增加可验证的dead PID清理分支，并在启动序列中明确3081 host.describe与8088 runtime健康检查；未知或存活进程仍失败关闭。","diagrams":["03-research-sequence"]} -->

## 2026-09-07 — Report Workflow 真实 Excel、Claw 与文件交付

- `rwb` 改为仓库自举启动器，不再依赖 hidden worktree 的 editable `.pth`；3080 不在项目进程所有权内。
- Excel 公式检测补齐 Wind 短公式、`EDB`、`S_INFO_*`、`S_WQ_*` 以及 iFinD `THS_*` / `thsiFinD`。迁移只新增不可变版本：创业板 50 误标 Wind 资源保留为 `legacy_mislabeled`，华安静态底稿不执行无意义刷新。
- 华安 ETF 周报真实运行 `d3c6b827e2f2442980335ae2cbfc170e` 完成两份 Wind 底稿刷新、共享快照 `9e15975b2460d92d2ce024cd2fedc4e08ed7b0a3e1401bf346d6322d91548b60` 和两个真实子 Agent。DOCX、HTML、XLSX 均已生成、非空且可重开；模型 Payload 缺少必需区块，所以保持 `delivery_incomplete`，不伪报完成，不启用日程。
- iFinD 探测已真实打开、刷新并保存工作簿，但公式仍返回错误；本机未找到 iFinD Excel 插件安装证据。创业板 50 因此未完成真实报告验收。
- Report Workflow 的实际拓扑、运行序列、Excel 数据流、运行状态和独立交付状态同步到图 02、06、07、09、10。文档门禁同步扩展为固定十图并更新图 08。所有最终图均 showcase 9/9、零错误零警告和四视口无溢出；已人工查看 1440 与 2048 最终截图，未把结构图验收替代研究内容验收。

<!-- architecture-review {"group":"report-workflows","structure":"changed","reason":"新增真实Excel Provider刷新、运行副本、共享快照、Claw多Agent、迟到Payload恢复、确定性组装与独立交付检查。","diagrams":["02-module-dependencies","06-run-state","07-delivery-state","09-report-workflow-sequence","10-excel-report-dataflow"]} -->
<!-- architecture-review {"group":"files","structure":"changed","reason":"报告运行只认可本次新建或更新文件，并增加Office重开、区块缺失、迟到Payload和Hash证据。","diagrams":["07-delivery-state","09-report-workflow-sequence","10-excel-report-dataflow"]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"报告运行在刷新和快照后创建独立Claw会话并要求真实子Agent；启动器改为仓库自举路径。","diagrams":["02-module-dependencies","06-run-state","09-report-workflow-sequence"]} -->
<!-- architecture-review {"group":"ui","structure":"changed","reason":"Claw与能力中心的具体报告Workflow详情新增资源、Provider、版本、运行证据、取消重试、日程和产物入口。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"operations","structure":"changed","reason":"只读运行聚合加入报告运行、Excel刷新、共享快照、子Agent和本次产物体积。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"documentation","structure":"changed","reason":"当前架构清单从八图扩展为十图，并把报告运行序列与Excel数据流纳入固定白名单、哈希、四视口和人工审阅门禁。","diagrams":["08-iteration-docs"]} -->

## 2026-09-07 — 报告缺失语义与 API Atlas 对账

- 报告 Payload 的所有 `*_blocks` 家族统一投影；显式 `missing` 高于区块内的解释文字。解释缺失原因仍会进入报告，但不能把未交付内容变成完整交付。
- API Atlas 现在分别显示 113 个唯一 HTTP 操作与 115 项源码声明。报告运行详情和取消各有一条兼容声明，文档不再把重复声明当作两个不同接口。
- 顶栏搜索入口在桌面、平板和手机均可见；首页折叠式分类与能力选择器按真实用户路径完成 15 组只读浏览器验收。
- 以上变更收紧既有交付判断、文档计数和控件可达性，不新增服务、接口、状态或跨模块关系，因此十张架构图无需再次生成。

<!-- architecture-review {"group":"files","structure":"unchanged","reason":"显式missing改为交付判定最高优先级，仍由既有Payload投影与独立交付检查节点完成。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"API Atlas区分唯一操作和源码声明，仍由同一架构清单生成并通过既有只读文档端点交付。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"恢复既有全局搜索控件在桌面视口的可达性，并按真实折叠控件路径修正验收；页面和模块关系不变。","diagrams":[]} -->

## 2026-09-07 — PPTX 跨片段投影与投资风向标真实验收

- 真实投资风向标产物暴露出 PowerPoint 会把一个 `{{占位符}}` 拆到多个 `<a:t>` 文本片段。渲染器现在按段落跨片段替换，交付验证按相同语义拒绝残留；可打开且含文字不再等同于占位符已完成。
- Report Workflow 的完成判定收紧为“结构化 Payload → 受审查确定性投影 → 独立交付验证”。Claw 提前创建的同名 Office 文件不能跳过投影；投影缺失或失败明确进入 `delivery_incomplete`。
- 迁移报告新版本最低子 Agent 数统一为 2。华安 ETF 投资风向标 v3 运行 `d7e47d9d680647dc878fd42f243dc74b` 完成两个真实子 Agent、确定性 PPTX 投影、ZIP 重开和零残留占位符检查。
- 这次修正落实图 07、09 已表达的投影与交付先后关系，没有增加节点、接口、状态或跨模块依赖，因此十张 Archify 图源无需再次生成。

<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"强制执行既有Payload到确定性投影再到独立交付检查的顺序，并把迁移报告最低子Agent数固定为2；图09已完整表达该关系。","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"PPTX占位符检查扩展为跨a:t文本片段，仍属于既有确定性组装和交付验证节点内部语义。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"补齐既有会话软删除与恢复接口清单；研究提交、DSH事件、恢复和归属边界均未改变。","diagrams":[]} -->

## 2026-09-07 — 会话永久删除与有限保留期

- 会话管理继续使用模式二级侧栏的行级菜单；软删除进入“已删除”并保留 30 天，可恢复或立即永久删除。
- 永久删除新增明确 API：Workbench 先要求 DSH `session.delete(cascade=true)` 返回根会话确认，再清理本产品会话目录与索引；失败保留墓碑和文件以便重试。
- 服务启动时立即清理到期墓碑，长期运行期间每 6 小时重试一次，消除只有重启或打开已删除页才会触发清理的缺口。
- 这是既有 UI、Research API 与文件所有权边界内的生命周期补全；DSH 全局内容寻址附件可能共享，不做单会话误删，十张架构图无需增加新节点。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"会话重命名、软删除、恢复与永久删除收归既有模式二级侧栏和历史视图，路由与页面模块关系不变。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"新增永久删除操作并补充启动及六小时保留期调度，仍由既有BFF校验归属后调用DSH会话API。","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"DSH确认后才清理既有会话目录、数据集、产物与索引；软删除和失败重试期间保持原文件边界。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"API清单和会话生命周期文档同步新增永久删除操作，没有改变文档门禁或图册拓扑。","diagrams":[]} -->

## 2026-09-07 — DSH 会话删除固定版本

- Research Runtime 与能力目录固定到 Fork 的 DSH 运行提交 `c919b2a460753859665db3f60143d525fb9140cf`，启动时继续要求源码提交和已审核构建闭包同时匹配。
- 该升级只替换既有 3081 Runtime 的固定实现版本；服务、端口、模块依赖和能力目录结构保持不变，因此无需重绘架构图。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"仅更新既有3081 Research Runtime的固定DSH源码提交和构建闭包，不改变服务、端口或启动数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"能力目录只读元数据改用与Runtime一致的DSH固定提交，工具集合、权限和模块关系保持不变。","diagrams":[]} -->

## 2026-09-07 — 资产观察终端图表保留

- 新 Research 壳层不再把历史行情降级为单条收盘价折线；恢复 OHLC K 线、MA/BOLL、成交量、MACD、KDJ、RSI、换手率与细行情栏。
- 图表保持无新增依赖的原生 SVG 实现，所有价格与技术指标只由当前 DataHub 历史行情快照计算；数据不足时显示明确空态，不注入旧页面的演示行情。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"资产观察仍沿用既有前端、DataHub快照和路由边界，仅恢复已承诺的行情图表层。","diagrams":[]} -->

## 2026-09-08 — 永久删除只读快照清理修复

- 永久删除兼容会话内按 `0555/0444` 封装的能力快照，并同步移除产品私有 DataHub 调用与快照目录。
- 清理只恢复当前产品根目录内真实目录的所有者写权限，不跟随符号链接；失败继续保留原生已删除墓碑供幂等重试。
- 该修复没有新增存储节点、API 或数据流，现有文件所有权图无需重绘。

<!-- architecture-review {"group":"files","structure":"unchanged","reason":"永久删除补齐只读能力快照及私有DataHub目录的安全清理，仍处于既有会话文件所有权边界内。","diagrams":[]} -->

## 2026-09-08 — 顶栏运行状态降噪

- 健康且已授权的运行时不再在顶栏常驻显示；缺凭据、事件通道连接中或健康失败时仍提供通往设置的可操作提示。
- 顶栏移除全局刷新按钮，页面级刷新、设置中的完整 DSH 状态、`/api/research/runtime` 响应及事件恢复逻辑均保持不变。
- 该变更只调整既有 `shell.mjs` 产品壳内部的条件渲染与状态样式，不新增模块、接口、状态或跨模块依赖，因此十张架构图无需重生成。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"顶栏仅隐藏健康运行时状态并移除全局刷新入口；异常提示、设置诊断、页面级刷新和现有运行时契约保持不变。","diagrams":[]} -->

## 2026-09-08 — 五项专用研究 Skill 与证据协议

- 在并行加入“因子库研究”的当前主分支上，能力目录为十一个 Skill；四个 Workflow 保持不变。新增研报增量、单一金融事件、产业链与主题、业绩与一致预期、宏观与跨资产五项窄边界能力，不登记独立路由 Skill。
- 品牌中立证据协议以一份共享源码维护，种子构建时复制进各专用包并随不可变版本哈希封存。研报校验与 SVG 重绘脚本使用既有研究沙箱和 PDF helper，不增加工具、依赖或宿主权限。
- 能力检查新增 `runtime_incompatible_script`，拒绝受审脚本中的子进程及宿主进程入口。本轮没有新增 API、能力类型、执行器、服务或跨模块关系，既有能力发布与会话快照图已覆盖，因此十张架构图无需重生成。

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"能力目录增加五个专用Skill、版本化证据协议和进程入口检查，仍复用既有种子、检查、发布、原生发现与会话快照边界。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"新增Skill资源继续使用既有原生发现目录、研究脚本沙箱和PDF helper，未增加进程、网络、文件或依赖权限。","diagrams":[]} -->

## 2026-09-08 — 资产成交额与换手率口径纠正

- 资产观察把 DataHub 标准字段 `turnover` 显示为成交额，把 `turnover_rate_pct` 显示为换手率；缺失值保持未知。
- 该修复不改变 DataHub 快照、资产观察 API、图表节点或数据流，只纠正既有 UI 字段映射，十张架构图无需更新。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅纠正既有资产指标卡的成交额与换手率字段映射，不改变模块、API或数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"资产观察继续读取同一DataHub标准行；只区分既有turnover与turnover_rate_pct口径。","diagrams":[]} -->

## 2026-09-08 — 统一数据源连接中心

- 设置页将 22 个来源统一为分组列表与同页详情，并分别展示配置、检测、适配和可调用状态；移动端改为上下布局。该变化仍位于现有产品壳和 DataHub 页面边界内。
- DataHub 增加通用来源配置、系统凭据引用、平台诊断和旧环境迁移；没有新增外部服务、数据快照类型或绕过 Provider 的查询路径。
- Runtime 与能力目录改为读取统一连接状态，但仍只在启动时按 `integration_completed && callable` 生成 `enabledTools`，既有 DSH 与 DataHub 拓扑不变。
- Wind、iFinD 和 Excel 的本机检测只形成诊断证据；未完成 Provider 适配时不进入 Runtime。真实厂商组件与账号环境尚未验收。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"连接中心复用现有设置页、产品壳和同源API，仅把来源列表与真实配置诊断组合为响应式主从视图。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"通用配置、凭据引用、探测和迁移均封装在现有DataHub节点内，Provider路由与会话快照数据流保持不变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"Runtime改读统一来源状态但仍在启动时生成enabledTools，没有新增执行服务、注册阶段或查询通道。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"能力工具目录复用统一连接摘要计算可选性，能力包、版本、原生注册和权限边界保持不变。","diagrams":[]} -->

## 2026-09-09 — 设置分页

- 设置在现有产品壳内增加五个 Hash 子页和响应式分类导航，每次只渲染当前分类。
- 远程数据源与本机集成只在前端投影中分组；仍读取同一 `/data/connections` 安全响应，提交、探测、迁移、凭据库和 Runtime 契约不变。
- 该变化只新增 UI 模块并调整现有前端组合，不新增 API、服务节点、跨层依赖或数据流，十张架构图无需重生成。

## 2026-09-09 — 数据源分类工作台

- 数据源设置页将 21 个远程来源从全量长列表改为状态概览、三类标签、搜索/筛选、卡片网格与同页详情面板；本机集成页保持原投影。
- 搜索、筛选和详情开关均为浏览器内展示状态；来源 ID、Hash 深链、配置字段、凭据库、探测 API、DataHub 路由和 Runtime 物化规则不变。
- 该变化只调整 `ui/connections.mjs`、事件委托和外观样式，不新增服务、端点或数据流，十张架构图无需重生成。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"数据源分类、搜索、状态筛选和详情面板均复用既有设置页与同源连接API，只改变浏览器内信息架构。","diagrams":[]} -->

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"设置分页只调整现有产品壳内的Hash路由、纯渲染和子页加载范围，同源API、凭据库、DataHub和Runtime拓扑保持不变。","diagrams":[]} -->

## 2026-09-09 — 本机集成诊断型重设计

- `#/settings/local` 改为“总体结论 → 环境检查 → 接入详情 → 可用数据能力”的单列诊断结构；单来源隐藏选择侧栏，多来源才显示紧凑选择器。
- 总体结论与组件环境证据分层，组件已就绪不会覆盖 `callable=false`；探测继续使用既有连接目录、启动探测和读取探测状态接口。
- 检测期间补齐持续忙碌态，终态刷新连接目录；失败、超时和格式异常进入既有错误提示与安全日志。本次未新增 API、服务、存储、跨层依赖或数据流，十张架构图无需重生成。
- 使用当前服务返回的本机状态组合完成只读可视核对：未适配状态显示“尚未接入可调用链路”，四项组件证据后置为比较列表，接入阶段默认折叠；未把该核对表述为桌面或 Windows 验收。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"本机集成诊断仅重排既有设置页的信息层级、状态文案和探测忙碌态，仍复用相同Hash路由、连接API、DataHub与Runtime边界。","diagrams":[]} -->

## 2026-09-10 — 本机能力诊断 v0

- `#/settings/local` 改用专用本机诊断投影，五类检查逐项保留发现、授权、验证和可调用事实；顶部不再形成跨组件 callable 结论，报告 Workflow 移出检查表。
- FastAPI 进程内新增无副作用探测管理器和三条同源接口。最新安全投影原子写入产品私有目录；探测不启动软件，不返回本机路径、注册表值、命令、环境变量或秘密。
- DataHub 的连接、探测、`local_cache` 与研究查询接口保持不变；WindPy 和 iFinD 数据接口仍由数据源页判断。本轮没有新增外部服务或改变研究执行、SSE 和数据查询拓扑，因此架构图无需重绘。
- v0 尚未实现文件夹同步、扩展配对、MCP 授权和 Office/Wind 真实操作验证；这些项目保持待配置或待验证，Windows 仅有可测试的无副作用投影。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"本机诊断控制台继续位于既有设置Hash子页，只改用专用同源投影并重排浏览器内信息层级。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"新增进程内本机诊断管理器与同源接口，不增加外部服务、研究执行通道或跨进程数据流。","diagrams":[]} -->

## 2026-09-10 — Windows 本机集成原生验证

- 新增 `windows-2022` 专项作业，真实启动既有回环服务并验证本机集成快照、幂等探测和设置页契约。
- 首轮原生执行发现 Windows 默认 CP1252 无法读取中文能力种子；启动所需产品索引、能力包及 Report Workflow 文本现统一显式 UTF-8。
- 这只修正既有磁盘格式的跨平台读取方式并增加验证通道，不新增服务、接口、存储位置或数据流，十张架构图无需重生成。

<!-- architecture-review {"group":"files","structure":"unchanged","reason":"产品索引文本改为显式UTF-8，目录归属、原子替换和文件数据流保持不变。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"能力种子、工具白名单和目录索引显式使用UTF-8，能力包版本与原生发现拓扑保持不变。","diagrams":[]} -->
<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"报告目录与迁移元数据显式使用UTF-8，Workflow版本、运行与交付数据流保持不变。","diagrams":[]} -->

## 2026-09-10 — Windows 回环控制文件启动兼容

- Windows 原生 CI 在中文能力完成装载后暴露 POSIX 专属 `O_DIRECTORY/O_NOFOLLOW/dir_fd` 阻塞 DataHub 初始化。
- 仅为启动所需固定控制文件增加 Windows 路径回退，保留链接、重解析点、越界、文件类型、硬链接、大小和身份核对；POSIX 路径不变。
- 服务、API、DataHub 节点和快照数据流均未变化，十张架构图无需重生成。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"Windows仅增加固定私有控制文件的安全路径回退，DataHub服务、Provider、API和快照数据流保持不变。","diagrams":[]} -->

## 2026-09-10 — Tabbit Windows 模拟 Runtime 阻塞修复

- 吸收已发布的 Windows DataHub reparse-point 防护，并修复 Tabbit 配置临时句柄、UTF-8 Runtime 配置、npm tar POSIX 路径比较和 adapter 正斜杠序列化。
- 连接配置在 Windows 明确跳过目录 `fsync`；POSIX 权限、描述符和父目录刷新保持不变。API、消息 schema、默认开关、供应版本与授权语义均未改变。
- macOS/Windows CI 仍只验证模拟 Runtime。真实双平台 Tabbit 状态、授权、动态 DOM、1/8 页 claim、写审批与标签保持打开仍是独立验收门禁。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Tabbit配置仅补齐跨平台原子写入和UTF-8异常路径，API与消息契约不变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"供应清单改用POSIX路径比较且adapter路径统一正斜杠，Profile节点和加载顺序不变。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"Windows连接配置仅明确跳过不支持的目录fsync，Provider和数据流不变。","diagrams":[]} -->

## 2026-09-10 — Tabbit Windows CI 第一轮直接根因修复

- 第一轮 PR 原生 CI 中 macOS Web Runtime 合约通过；Windows 进一步暴露 DSH 认证文件误用 POSIX mode、DataHub 快照仍调用 `dir_fd`、下载仍调用 POSIX flags，以及只读快照无法永久清理。
- Windows 认证、DataHub 控制/收据/快照和下载现统一使用规范路径、重解析点拒绝、普通文件/硬链接/大小及打开前后身份核验；快照仍以临时目录和同目录原子改名发布。POSIX 安全 I/O 保持不变。
- 永久删除只为产品所有树中的真实目录和普通文件恢复所有者写权限，不跟随链接或重解析点。服务、API、快照 schema、Tabbit 消息与授权语义均未变化，十张架构图无需重生成。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Windows DSH认证文件改用文件身份与重解析点校验，Runtime地址、认证格式和API不变。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"Windows私有收据与快照补齐安全路径IO，Provider、快照schema和数据流不变。","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"unchanged","reason":"Windows下载和只读文件清理补齐平台兼容，文件归属与删除边界不变。","diagrams":[]} -->

## 2026-09-10 — Windows DSH 认证控制文件读取兼容

- Windows 原生回环冒烟证明 `st_mode` 的 POSIX group/other 位不能代表 Windows ACL；旧判断会把正常控制文件误判为权限不安全。
- Web 客户端与服务管理器改为复用同一有界读取器，所有平台继续拒绝非普通文件、硬链接、符号链接、重解析点、超限内容和读取期间的身份替换；仅 POSIX 执行 mode 位检查。
- 认证格式、回环 RPC、服务节点和数据流均未变化，十张架构图无需重生成。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"共享认证控制文件读取器统一既有客户端与服务管理器的文件校验，不改变回环RPC、认证格式、服务节点或数据流。","diagrams":[]} -->

## 2026-09-10 — 能力工作区 v0 四类分区

- `#/skills` 固定为 Skill、Tool、Workflow、数据四个互斥主标签，并在类型内提供能力库、我的、运行计划或连接入口；旧 kind/view 深链继续归一到对应分区。
- 卡片与居中快览复用现有 capabilities、tools、DataHub 和 report-workflows 接口，只展示真实来源、版本、启用、输出、调用及不可用原因；“立即使用”只带入草稿。
- 本轮新增浏览器内的工作区组合与响应式布局，没有新增后端 API、持久模型、执行服务或跨模块数据流，因此现有架构图无需重生成。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"能力中心在既有Research Web UI内重组为四类互斥主标签、类型内二级视图和共用快览弹窗；同源API、能力执行、DataHub与报告Workflow边界保持不变。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"Skill、Workflow与Tool继续读取既有目录、版本、状态和选择契约，仅在前端严格分区呈现。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"数据能力与数据源仍由既有DataHub目录、连接状态和单源探测提供，只在能力中心与Tool卡片隔离展示。","diagrams":[]} -->

## 2026-09-10 — Windows 私有运行目录校验兼容

- 原生 CI 证明 DSH 认证文件读取已通过后，服务管理器仍在数据、运行状态和日志目录上误用 Windows `st_mode` 的 POSIX 权限投影。
- 目录校验现继续拒绝非目录、符号链接与 Windows 重解析点，仅在 POSIX 检查 group/other mode 位；服务、接口、存储位置和数据流均未变化。
- 新增 Windows/POSIX 目录 mode 回归，十张架构图无需重生成。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"服务管理器仅修正私有运行目录的跨平台安全判断，不改变服务节点、接口、存储位置或数据流。","diagrams":[]} -->

## 2026-09-10 — Phase 2A 只读 MCP Registry

- Tool 分区新增 `view=market`，浏览官方与私有 Registry；同名服务器以 `(registry_id, server_name, version)` 隔离，第三方字段只作纯文本，不渲染 HTML 或加载远程图标。
- FastAPI 新增功能开关保护的 `/api/research/mcp/*` 路由、固定官方 `/v0.1` 与不透明游标同步、ETag 和原子最后成功缓存；失败只返回 `stale` 缓存。Bearer/OAuth 秘密只进入 Keyring `ResearchWorkbench.MCPRegistry`。
- Publisher 仅生成受审 `server.json`、摘要与完整外部 CLI argv，始终 `executed:false`。本阶段不安装、启用或调用 MCP，不改 DSH Runtime；Phase 2B/2C 尚未实施。
- 图 02 增加 Browser MCP Market → FastAPI → Registry service → atomic cache / OS Keyring → official/private Registry 路径，同时保留报告、DSH、DataHub 与快照主链。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"Tool二级导航增加只读MCP市场、目录筛选、stale状态与可访问详情dialog。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"FastAPI装配功能开关保护的MCP Registry路由与服务生命周期，同时保持研究执行链不变。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"mcp-registry","structure":"changed","reason":"新增官方与私有Registry聚合、身份三元组、ETag/游标、原子最后成功缓存及系统凭据库边界。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"API Atlas新增MCP Registry分类，仍从同一架构清单离线生成并经既有只读文档端点交付。","diagrams":[]} -->

## 2026-09-11 — Phase 2A 最终安全与请求归属修复

- 后端修复提交 `c6c3697b`、`f87d8f2c` 将认证 Registry 和 OAuth 端点收紧为 HTTPS，仅保留无认证
  精确 loopback HTTP；规范化、缓存和 API 统一保存有界 Unicode plain text，并把包类型支持与不可变
  引用拆为两项事实，不承诺 Stage 2A 可安装。
- UI 修复提交 `50d7b067` 只在最终 HTML sink 转义一次；搜索和 Registry 替换结果集会作废 pending
  detail，迟到响应不再打开旧弹窗，并保留当前搜索框或选择器焦点。
- 上述修复没有新增路由、服务、持久目录或跨模块依赖，图 02 与 API Atlas 的拓扑/操作清单不变。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"MCP市场修正最终HTML sink转义、包事实文案及搜索/Registry结果集替换时的详情请求归属；仍在既有UI模块和API边界内。","diagrams":[]} -->
<!-- architecture-review {"group":"mcp-registry","structure":"unchanged","reason":"收紧Registry传输、纯文本规范化与包事实字段，不新增服务、存储目录、API路由或Runtime依赖。","diagrams":[]} -->

## 2026-09-11 — Mac 本机集成真实验证

- 设置页新增独立的本机集成验证任务 API；发现仍无副作用，只有用户显式操作才启动 Office 或 Wind。
- Excel、Word 与 PowerPoint 使用各自 Office 容器内的确定性验证文件；Wind 仅刷新已发布报告工作簿的运行副本，源版本保持只读。
- 图 03 同时保留 Tabbit 实时标签序列，并增加 Web → 验证管理器 → Office/Wind 的显式任务序列；DataHub、能力包、MCP Registry 与报告 Workflow 仍使用各自既有模块和存储边界。

<!-- architecture-review {"group":"research-api","structure":"changed","reason":"新增本机验证创建与轮询接口，并将显式用户动作、异步任务和安全结果投影纳入现有Research Web API。","diagrams":["03-research-sequence"]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"新增可终止的Office/Wind验证子进程、受管Office容器临时文件和本轮Excel实例清理，不进入DSH研究执行链。","diagrams":["03-research-sequence"]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"iFinD HTTP探测补齐登录、健康、只读查询和登出，继续复用既有连接配置与系统凭据库，不新增DataHub服务或存储。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"本机页只链接并消费既有报告Workflow元数据进行受管副本验证，不改变Skill、Tool或Workflow的发布与调用拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"本机设置页在既有诊断列表增加逐项验证按钮、进度和最近验证时间，不新增产品壳或页面模块。","diagrams":[]} -->

## 2026-09-11 — Mac Office/Wind 沙箱验证修正

- Excel 验证复用报告刷新器已有的 macOS `aeosa` 兼容入口，避免隐藏虚拟环境跳过 `appscript` 路径后把已安装自动化桥误判为失败。
- PowerPoint 改由 AppleScript 直接创建演示文稿，并在另存为后按随机文件名重新绑定本轮对象；不新增或隐式依赖 `python-pptx`。
- Wind 的烟测和完整刷新继续使用已发布工作簿的只读源，但所有运行副本迁入 Excel 应用容器内的有界验证目录，避免逐文件授权窗口占用验证预算。HTTP 路由、状态 schema、DSH 和报告 Workflow 边界不变。
- 图 03 更新本机验证消息，明确受管子进程在对应 Office 容器内操作副本；参与者与其他业务序列不变。

<!-- architecture-review {"group":"research-api","structure":"changed","reason":"本机验证运行副本从通用状态目录收敛到对应Office容器，并修正PowerPoint对象生命周期；API与状态schema不变。","diagrams":["03-research-sequence"]} -->

<!-- architecture-review {"group":"runtime","structure":"changed","reason":"Office与Wind验证子进程改用对应Office容器的受管运行目录，进程身份、超时和清理协议保持不变。","diagrams":["03-research-sequence"]} -->

## 2026-09-11 — Phase 2B MCP 安装、授权与运行时

- MCP 市场从只读目录扩展为显式的预览、二次确认、不可变安装、健康探测、Runtime 启停、OAuth、风险分级、会话授权和一次性高风险审批；安装、启用和授权保持分离。
- Research Web Host 使用官方 Python SDK 管理 Streamable HTTP/stdio 连接并代理 tools/resources/prompts；DSH 只加载经过版本、schema 哈希和策略校验的 `mcp__{installation}__{tool}` 声明，通过私有 loopback 控制通道调用 Host。
- 本地制品解析、逐项哈希、最小环境、系统凭据库、目录授权、Runtime 候选探测和失败回滚都位于当前本地数据根；不新增桌面进程、PostgreSQL 或第二研究引擎。
- 图 02 的既有 MCP 节点升级为 Registry + Host 和不可变清单/授权职责；API Atlas 与文件边界同步加入 Phase 2B 契约。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"MCP市场增加完整预览、二次确认、安装生命周期、风险分级、会话授权和高风险审批交互。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"FastAPI装配Research Web MCP Host、Runtime生命周期、OAuth回调和私有DSH控制通道。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"mcp-runtime","structure":"changed","reason":"新增固定版本制品解析与哈希校验、不可变安装清单、SDK连接、schema快照、分级授权、人工审批和Runtime原子回滚。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"专属DSH只加载Host验证后的命名空间工具声明，并通过私有loopback控制通道调用Research Web Host。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"mcp-registry","structure":"unchanged","reason":"Registry继续提供隔离身份和受审固定目标；安装状态、授权和调用由独立mcp-runtime模块持有。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"API Atlas扩展MCP Runtime分类，仍由同一架构清单离线生成并通过只读文档端点交付。","diagrams":[]} -->

## 2026-09-11 — Phase 2C 通用 Automation 与外发

- Workflow“运行计划”升级为通用 Automation：锁定 Skill、普通 Workflow 或报告 Workflow 的版本与内容 SHA，按一次、每日、每周或每月 IANA 时区日程创建独立 Claw 会话。
- 本地原子索引保存 Automation 与 Run 事实；服务恢复只合并最近一次遗漏，拒绝重叠，版本漂移、运行中断和手动重试均保留独立状态与关联。
- SMTP、通用 HMAC Webhook、飞书、企业微信和钉钉投递与研究状态分离，渠道秘密只进入 `ResearchWorkbench.Delivery`；无人值守 MCP 工具必须是任务锁定、只读且明确允许。
- 旧报告日程仍可读取，只有用户逐项确认且新 Automation 原子保存成功后才停用。图 02 增加 Automation service、原子事实/Keyring 与外部投递边界。
- 图 02 最终 HTML SHA-256 为 `01aed4e526e3876396e5b3575f4836623f5c57a74e005c3974e52b734ccff803`，规范 SHA-256 为 `fd63c80fc915d319f60b6804ec81048eb01e87af9005ac40862c6a51df4a9534`。showcase 9/9、零错误零警告，四视口自动包含性通过；控制器已人工查看 1440 浅色与 2048 深色最终截图，未见遮挡、裁剪或节点穿线。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"Workflow运行计划增加通用任务、最近Run、投递渠道、显式旧日程迁移和响应式表单。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"FastAPI装配功能开关保护的Automation、Run、迁移和投递渠道接口及服务生命周期。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"automations","structure":"changed","reason":"新增锁定版本任务、IANA日程、独立Claw会话、遗漏合并、重叠拒绝、恢复与研究投递双状态。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"mcp-runtime","structure":"changed","reason":"MCP Host增加Automation锁定工具快照的无人值守复核，不放宽风险分级或人工审批边界。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"report-workflows","structure":"changed","reason":"旧报告日程增加逐项预览和原子迁移入口，既有日程API继续兼容。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"API Atlas扩展Automation分类，仍由同一架构清单离线生成并通过只读文档端点交付。","diagrams":[]} -->

## 2026-09-11 — Phase 2C Windows CI 边界修复

- 显式验证记录在 `verification_ttl_seconds=0` 时立即失效，截止时刻采用包含边界，避免 Windows
  时钟分辨率下同一时间刻度仍被判为可调用。
- POSIX 进程组清理测试只在提供 `getpgid`/`killpg` 的 POSIX 平台执行；Windows 继续由独立
  `taskkill /T /F` 契约覆盖。实现拓扑、API、状态 schema 与产品页面均不变。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"修正本机验证TTL截止比较并限定POSIX进程组测试平台，不改变验证进程、API、持久化或UI拓扑。","diagrams":[]} -->

## 2026-09-11 — Wind 插件验证与用户 Excel 所有权修正

- 本机 Wind 诊断改为复用生产公式客户端，在已登录 Excel 应用中创建独占空白工作簿执行最小心跳；具体报告工作簿重新归属各自 Workflow 的刷新与校验。
- macOS 冷启动时通过 LaunchServices 正常打开 Excel；检测到 Wind 的二维码“安全验证”窗口后返回待授权，不再误报终端未登录或通用异常。
- 监督器只清理验证器真正拥有的 Excel 进程；复用现有 Excel 时仅关闭独占验证工作簿，用户应用与工作簿不进入清理集合。
- API、状态 schema、持久目录和研究执行拓扑不变，图 03 的现有“显式验证 → Office/Wind”序列仍准确，无需重绘。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"Wind验证在既有可终止任务内改用独占空白工作簿并收紧Excel进程所有权，参与者、进程边界和API拓扑不变。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"Wind插件心跳与报告Workflow刷新分离，既有能力和报告服务边界不变。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Wind验证在既有API白名单与状态投影内改用独占空白工作簿，路由、schema与可调用判定不变。","diagrams":[]} -->
<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"Wind最小公式心跳与报告工作簿刷新分离，Workflow既有发布、运行与刷新契约不变。","diagrams":[]} -->

## 2026-09-11 — Phase 2 功能默认启用

- MCP Registry、MCP Runtime 与 Automation 在各阶段远端门禁通过后默认装配，Host 与 DSH 启动层使用一致的 Runtime 默认值。
- 三个环境变量显式设为 `0` 时仍独立关闭；安装、启用、授权、版本锁、审批、调度与投递安全契约不变。
- 本次只修改功能门控回退值和对应测试/文档，不新增服务、路由、存储、页面或跨模块依赖，图 02 拓扑不变。

<!-- architecture-review {"group":"mcp-registry","structure":"unchanged","reason":"Registry通过门禁后默认装配，显式关闭和只读缓存安全契约不变。","diagrams":[]} -->
<!-- architecture-review {"group":"mcp-runtime","structure":"unchanged","reason":"Host与DSH启动层默认启用Runtime，但安装授权审批和回滚拓扑不变。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"Automation默认装配但不自动创建任务迁移日程或外发，既有服务和存储拓扑不变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"DSH启动层与Host共享Runtime默认值，不改变专属Runtime进程或控制通道。","diagrams":[]} -->

## 2026-09-11 — Phase 2 默认启用 Windows 私有目录修复

- MCP staging、安装 payload、清单与确认令牌重放目录采用统一跨平台私有目录边界：Windows 不以
  POSIX mode 投影代替 ACL，但继续拒绝非目录、符号链接和重解析点；POSIX 继续检查 group/other
  mode 与所有者。
- 修复只影响平台校验分支，不改变安装清单、确认令牌、API、存储位置、Runtime 拓扑或页面。

<!-- architecture-review {"group":"mcp-runtime","structure":"unchanged","reason":"MCP私有目录校验改用既有跨平台证据边界，安装清单、令牌、API和Runtime拓扑不变。","diagrams":[]} -->

## 2026-09-11 — Goldar 研究框架 V0 视觉检查点

- 产品壳新增 Framework Hub 与 Goldar 专属 hash 路由，七个章节由固定 fixture 和专属 Lieflat SVG renderer 呈现。
- 本阶段没有 API、服务、存储、采集器或 Runtime 变更；固定样例显著标注，不形成实时市场结论。
- 新文件仍位于架构图既有的 Research Web UI 边界内，`app.mjs` 仅组合无副作用的展示叶模块，因此现有部署、模块依赖和研究序列图不变。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"Goldar V0是既有Research Web UI边界内的无副作用展示叶模块，只增加hash路由和固定fixture，不增加服务、API、存储、Runtime或跨边界数据流。","diagrams":[]} -->

## 2026-09-11 — 本机集成格式基线维护

- 仅整理本机集成包导入、敏感键正则和 ISO 时间解析表达式，使相关文件同时符合 Ruff、Black 与 isort。
- API、状态 schema、验证流程、持久化和页面拓扑均未改变，现有架构图继续准确。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"本机集成格式基线维护不改变API、状态模型、验证流程、持久化或UI拓扑。","diagrams":[]} -->

## 2026-09-12 — Goldar V1 连续研究画布与框架 Bot

- 七个独立章节页收敛为一张连续研究画布，页内锚点保留旧 `?tab=` 深链兼容；Lieflat 图表从六张缩减为四张承担明确比较任务的 Basics 图。
- `frameworks/goldar/` 新增版本化黄金方法、严格快照、内容 revision、原子存储和旧结构保留迁移；当前 seed 明确为确定性离线证据，不宣称实时行情。
- 页面 Bot 复用唯一 DSH：默认解释会话无工具，用户显式深度验证时另建只读会话；两种模式都绑定精确快照 revision，不能写快照或改评分。
- 新模块仍封装在既有 Browser → Research Web API → DSH 与本地数据文件边界内，不增加部署进程、执行引擎或事实数据库，因此现有架构图的节点与连线仍准确。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"Goldar连续画布、四张Lieflat图和响应式Bot仍位于既有Research Web浏览器节点内，不增加跨边界关系。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"框架目录、严格快照和页面会话接口封装在既有Research Web API与本地文件及DSH关系内。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"新增解释与验证预设仍由同一专属DSH进程加载，不增加Runtime、工具宿主或跨进程通道。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"framework-research通过既有不可变Skill目录和原生发现链交付，没有新增能力类型或执行器。","diagrams":[]} -->

## 2026-09-13 — Research Web 本地依赖与测试基线

- 现有 uv 管理环境补齐 Research Web 最小依赖，并将 `httpx2>=2,<3` 纳入开发依赖，消除
  TestClient 的旧 httpx 兼容弃用路径；可选行情、机器学习和回测栈仍不进入最小环境。
- MCP PyPI 安装器在当前解释器缺少 pip 时可使用宿主已有 uv 执行同一份离线安装计划，强制当前
  解释器、staging 私有缓存和禁用用户配置；无 pip/uv 时仍关闭失败。
- worktree 启动器只在自身没有 `.venv` 时解析 Git common directory 并复用主 checkout 的项目环境；
  `PYTHONPATH` 仍指向当前 worktree。测试中的来源可调用性和 Provider readiness 使用显式 fixture，
  不再依赖本机可选 SDK、Keychain 或进程调度时序。
- 本次不新增 API、服务、持久目录或跨模块数据流，现有架构图继续准确。

<!-- architecture-review {"group":"mcp-runtime","structure":"unchanged","reason":"PyPI安装器在缺少pip时使用受限uv执行同一离线计划，Host、清单、确认、目录和授权拓扑不变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"worktree启动器可复用Git common directory中的项目虚拟环境，不新增进程、服务或部署边界。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"能力目录测试显式固定可调用来源，生产来源目录和工具注册逻辑未改变。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"依赖与确定性测试修复不改变Research Web路由、请求响应schema或错误码。","diagrams":[]} -->

## 2026-09-14 — Gold/Dollar 真实框架与 Artifacts 错误隔离

- Gold 升级为 V2 真实数据快照，Dollar 新增 Q-P-g-M-X V1；薄注册表、原子快照协议和单一调度器都位于既有 Research Web API/本地文件边界内。
- 两个详情路由使用连续七章节画布与 11 张用途明确的 Lieflat SVG 图；框架 Bot 绑定 slug、章节、缺口、方法版本和精确快照 revision，继续复用唯一 DSH。
- 全局 Artifacts 目录忽略软删除会话，资产观察不请求或继承 Artifacts 错误；显式访问删除会话仍返回 410。
- Browser、Research Web API、DSH 和本地文件之间的既有节点与连线仍准确，不新增服务或跨进程通道，因此无需重绘架构图。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"Gold与Dollar连续画布、Lieflat图和框架Bot仍封装在既有Research Web浏览器边界，资产页只收紧错误归属。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"多框架注册表、采集调度、严格快照和Artifacts过滤仍位于既有Research Web API、本地文件及DSH关系内。","diagrams":[]} -->

## 2026-09-14 — 全局 rwb 部署入口确定性

- 真实部署预检发现从其他 checkout 调用会让 Python 当前目录遮蔽固定部署入口，Homebrew Node 25 也与按 Node 24 构建的 DSH 原生模块 ABI 不兼容。
- 仓库启动器现在先进入自身部署根，并在 Codex Desktop 可用时固定 bundled Node；其他环境保留 `RESEARCH_NODE_BINARY` 显式选择及 `PATH` 回退。
- 该修复不新增进程、服务、端口、接口或文件拓扑，现有架构图继续准确。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"启动器固定部署根和已审核Node选择，仍由既有Service Manager管理同一3081与8088进程。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"入口确定性修复不改变Research Web路由、schema、数据根或Artifacts契约。","diagrams":[]} -->

## 2026-09-14 — 框架路由快照隔离

- Gold 与 Dollar 之间切换时，路由状态可能先于异步框架读取更新。前端现在在进入专属 renderer 前核对目标 slug 与快照 slug，不一致时只显示目标加载态。
- 该修复位于既有 Browser 节点内部，不改变框架 API、快照 schema、DSH 会话、服务或文件流；现有架构图仍准确。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"框架路由切换增加快照slug一致性守卫，只修复既有浏览器节点内部的异步渲染竞态。","diagrams":[]} -->

## 2026-09-14 — Dollar F2 实时窗口界定

- `plumbing_m` 的 60 期 SOFR−IORB 快照继续完整保留；浏览器只将最近 30 期交给 F2，以符合既有图表密度契约。
- 该修复只改变既有 Dollar renderer 的展示窗口，不改变快照、评分、API、服务或数据流；现有架构图仍准确。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"Dollar F2只界定既有SOFR-IORB序列的展示窗口，不改变浏览器节点、API或数据流。","diagrams":[]} -->

## 2026-09-14 — Research Workbench 推理方法层

- 能力目录增加十个只读 Method，Skill／Workflow 增加 `method_policy`，研究提交可选择最多三个方法。
- Research Workbench 保持 Method 权威来源；DSH 只接收原生 Skill 包装。采用工具只记录当前会话的
  ID、版本和来源，不保存 Prompt、正文或隐藏思维链，不授予外部权限。
- 复用现有 FastAPI、能力版本、会话收据和 DSH 进程；没有新增服务、端口、数据库、网络边或第二
  执行器。Prompt 模板阶段因尚无真实质量晋级证据而未启动。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"能力工作区在既有单页壳与目录投影中增加只读Method标签和输入选择，不增加前端数据源或执行器。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"现有能力与消息接口扩展Method字段，继续使用同一FastAPI服务、会话收据和目录锁。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"DSH只加载Research Workbench编译的Method Skill包装，并通过现有research-tools插件记录有界身份。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"Method层未改变Automation计划、触发、版本锁、授权或外发拓扑。","diagrams":[]} -->

## 2026-09-16 — 统一集成协调器与动态 DataHub 路由

- Research Web Host 内新增统一协调器，恢复安全快照并编排启动/手动探测；数据源、本机发现和 Tabbit
  仍由既有模块执行，不增加进程、端口、数据库或外部通道。
- 设置页合并连接目录与统一状态，展示五类汇总、五阶段详情、真实批次进度、逐来源授权及 Tabbit
  保存/Runtime 双状态；旧单项探测接口继续兼容。
- 15 个 DataHub 业务工具改为常驻注册，Broker 每次调用按最新安全状态选源；查询仍走既有私有回环、
  会话归属、参数白名单和快照链。Automation 未改变任务、Run、授权或外发语义。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"统一状态、批次进度、五阶段详情和Tabbit双状态都位于既有设置页与连接中心模块内，没有新增浏览器边界或跨层数据源。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"协调器和四个统一端点封装在既有Research Web Host内并复用DataHub、本机管理器与Tabbit，不新增服务、进程或外部数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"探测恢复、指纹失效和动态选源都复用既有DataHub Provider、业务查询与会话快照边界，没有新增查询通道。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"共享ResearchService只增加集成协调器生命周期；Automation的计划、Run、版本锁、MCP授权与外发拓扑保持不变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"十五个DataHub工具由既有public-data适配器常驻注册并继续调用同一私有业务查询入口，DSH进程、Guard和数据流拓扑不变。","diagrams":[]} -->

## 2026-09-16 — Web 一键环境、CJPY 0.5.2 与持续安装门禁

- 新增跨平台公开 setup 入口、checkout 专属 Python 3.12 `.venv`、带哈希 Web 锁、随包 CJPY
  0.5.2、固定 DSH 构建和安全化 Doctor；这些是运行前的可复现供应链，不新增生产服务或端口。
- 天软状态现在区分依赖缺失/版本错误与厂商认证、权限、限流、不可达；保存 Key 后由每次调用动态
  读取凭据库，未配置 CI 仍明确不可调用。
- 原生 macOS/Windows CI 对每个 PR 与主分支更新执行干净安装、DSH 构建、3081/8088 启动、Doctor
  和无凭据天软断言；安装文档与项目规则把这项要求固化为后续迭代门禁。
- 干净 runner 验证进一步要求 Windows 子 checkout 自带 Git 长路径设置、全新 DSH Home 先初始化
  `web` Profile；服务管理器按平台核对命令行并停止进程树，不改变同一 3081/8088 生命周期。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅细分既有数据源卡片的安全错误文案，设置页、路由、抽屉和状态数据源保持不变。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Doctor和版本化DSH路径仍由既有Service Manager管理同一3081/8088，不新增HTTP路由、进程或端口。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"CJPY依赖版本检查和动态凭据读取只收紧既有天软Provider就绪状态，Broker、业务查询和快照链不变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"安装器固定来源提交与构建闭包后仍启动同一专属DSH及既有工具适配器，没有新增运行节点。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"全新Profile初始化、Windows长路径checkout与原生进程管理只修复既有专属DSH的跨平台启动停止，不新增进程、端口或工具通道。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"新增跨平台安装CI作为并行交付门禁，既有十图映射、回执、视觉检查和Web文档入口机制保持不变。","diagrams":[]} -->

## 2026-09-14 — CPU 有界研究底座与受限 Wind DataHub Provider

- `research_run_script` Host 增加单槽 FIFO 队列、60 秒排队截止、排队取消移除与无输入内容的
  wait/run outcome 日志；执行超时和既有沙箱权限保持不变。
- Runtime 启用研究脚本前验证受管 Python 3.12 与 numpy、pandas、matplotlib、openpyxl，失败使用
  既有 Runtime 状态投影并返回 `runtime_not_ready`，不新增公开 API 或解释器回退。
- DataHub 增加 Wind 封闭业务映射；只调用现有适配器方法，并以 capability/dataset 固定输出字段、
  类型、单位和日期映射拒绝未知列。指数仅登记可执行的 `quotes` 子集；宏观/利率和基金持仓在没有
  真实等价方法时不登记为 Wind callable。复审进一步移除以龙虎榜方法伪装的大宗交易入口，只将
  xlwings/Excel 视为 DataHub Wind Provider 就绪依赖，并把所有 binding 市场收紧至 A 股。固定 schema
  同时逐行核对证券身份和请求日期；指数点位和融券余量分别标记 points、share。未登录、方法缺失、
  口径不等价和 5,000 行上限均失败关闭。
- 第三轮复审把 Wind `market_bars` binding 明确收紧到股票，并将 `asset_type` 加入稳定 BusinessQuery、
  Runtime bridge 与能力工具 schema；缺失类型、指数或 ETF 请求均在 adapter 前失败关闭。日线行情、
  资金流与融资融券共用前置历史区间验证，拒绝非字符串、反向和超过 60 个日历日的区间，不再
  只依赖取数后的 5,000 行上限。
- 第三轮补充复审将同一显式资产类型契约应用于 Wind `market_snapshot`：binding 只声明股票，缺失、
  指数或 ETF 在 adapter 实例化、可用性检查和方法调用前返回 `data_not_equivalent`；通用能力仍可由
  其他 Provider 声明其真实支持的指数或 ETF 子集。
- 代码质量复审将自动 Wind 查询改为每次独立隐藏 Excel 应用/workbook 并在 finally 中无保存关闭，
  不枚举或选择用户 workbook；容量为 1 的 worker 使用 18 秒 deadline，超时或取消后保持
  `provider_busy` 直到原调用返回并回收。历史跨度前置收紧为 60 日历日，终点未覆盖时标记 partial；
  每个固定 schema 验证最低有效字段和请求字段，关键值全空失败、部分缺失只返回 partial。
- Host FIFO 只在 child close 后释放；强杀仍未 close 时保持 poisoned busy，实际 close 或 Runtime
  重启后才恢复。上述竞态、隔离生命周期和字段质量均用 fake process/xlwings/adapter 验证，未访问
  真实 Wind 或用户 workbook。
- 后续复审明确通用 child `error` 事件不是生命周期终止证据，不能释放 FIFO 或清 poison。Wind
  workbook/app close/quit 异常同样保留 client 所有权并返回 `wind_cleanup_failed`，Provider 保持
  poisoned busy 至进程重启，不创建新 Excel。fake kill-error/no-close 与 quit side effect 回归覆盖该边界。
- 这些变化收紧既有 Host Runtime 和 DataHub Provider 节点内部的调度、readiness 与映射，不新增
  进程、端口、持久目录、浏览器接口或跨模块连线，现有十张图继续准确。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"既有Host研究脚本节点内部增加FIFO单槽调度、readiness、数值线程上限和仅由close释放的poisoned门闩，不新增进程、服务或权限边界。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"既有DataHub Provider节点增加Wind独立Excel生命周期、清理失败poison、单worker、固定schema质量和失败关闭口径，不新增数据服务、接口或持久数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"共享CPU预算与结果资源由后续Skill种子复制使用，不注册新的Skill种类或执行器。","diagrams":[]} -->

## 2026-09-15 — CPU Skill 输入等价性与启用门禁复审

- 六个 Stage 2 计算器增加共享严格输入契约，拒绝不等价 provider/mapping/version/单位/日期/复权、
  未来记录与未来 dataset ref；CLI 仅保留安全的工作量超限元数据。
- 六项真实 Wind/Excel 对照尚未执行，因此内置种子可发现但初始 disabled；已有能力目录、不可变版本、
  DataHub 快照、DSH 原生发现和脚本执行拓扑不变。
- 后续复审把日期收紧为 `YYYY-MM-DD`、daily/ETF 币种固定 CNY，并统一验证来源 SHA-256；哈希缺失
  以 partial/limitation 降级。daily 所有集合与非负整数 breadth 与 schema 运行时一致。
- clean catalog 测试证明 disabled 六项不进入原生 provider candidates；压力测试改用已有 psutil
  从父进程采样 RSS，不调用系统 `ps` 或引入新执行权限。
- 最终复审区分缺失与显式 null 来源哈希：仅字段缺失允许降级；显式 null、空白 key 或带首尾空白的
  非规范 key 固定返回 `invalid_source_hashes`，不再静默 trim 或合并碰撞 key。
- schema/运行时允许集合进一步对齐：来源 key 内部出现 CR、LF、U+2028 或 U+2029 同样固定拒绝。
- 六项 enabled/rollback 状态增加持久 macOS Wind/Excel comparison receipt 校验，并将已知初版脚本
  迁移为当前不可变版本且保持 disabled；不新增公开 API、能力类型或执行器。
- 六 CLI 共用防越界/no-follow/身份复核的相对 JSON loader 与有限数算术；全部输入仍在既有 sandbox
  内计算，最多内联 128 条并用 `row_delivery` 披露其余数据，使 stdout 保持 64 KiB 上限。
- 业绩预告记录报告期与参数严格等价，每日简报 provenance 复用规范化 dataset refs；这些是既有
  calculator 内部契约收紧，不改变模块拓扑。
- 最终质量复验把 receipt 登记入口收紧为 evidence artifact 路径：内部重算 artifact、输入来源、
  仓库 golden、实际结果和当前脚本摘要，状态切换再次验证；不把该校验描述为抵抗本机管理员伪造。
- 已知初版迁移在发布/保存/校验前撤下原生投影并禁用，异常保持 uncertain 或初始化失败；POSIX
  loader 改为从 cwd fd 逐组件 openat/no-follow，Windows 校验打开句柄最终路径和 reparse 属性。
- dataset refs/source hashes 各限 32 项、复制文本限 4096 字符，完整 JSON envelope 按 UTF-8 计不超过
  64 KiB；无法表达时返回小型完整 workload 错误，`row_delivery` 不再复制顶层 refs。
- receipt 的 packaged golden 与 comparison run actual 改为分别校验各自声明摘要；解码后数值按
  `rtol=1e-6`/`atol=1e-8`、日期/分类/信号等非数值严格一致做业务比较，不再要求文件字节相同。
- 六 CLI 的成功 stdout 不附加换行，使完整输出恰好 65,536 字节时仍符合 sandbox 输出门。

<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"共享输入契约和预算错误投影只收紧既有research_run_script内部计算器，不新增进程、服务、权限或跨边界数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"六项内置Skill改为receipt门控的disabled初始状态，仍使用既有目录、版本、检查与选择状态机。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"严格日期、CNY和来源哈希验证只收紧既有计算器输入；psutil仅用于测试进程观测，不进入产品Runtime。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"clean目录测试确认disabled六项不进入既有原生provider candidate投影，能力拓扑和状态机不变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"来源哈希仅收紧既有共享输入校验和六份schema，不增加执行节点、权限或数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"来源key换行分隔符拒绝仅对齐既有共享校验与schema允许集合，不改变拓扑、权限或数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"六项专用comparison receipt与已知初版disabled迁移只收紧既有catalog状态机，不增加公开API、能力类型或执行器。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"相对JSON安全读取、有限数算术和64KiB有界结果仍在既有research_run_script沙箱节点内，不新增进程、权限或跨边界数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"evidence artifact验证与失败关闭迁移只收紧既有catalog状态机和持久索引，不新增公开API或能力类型。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"逐组件openat与完整UTF-8 envelope只收紧既有research_run_script文件和输出边界，不新增执行节点或权限。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"golden与actual独立摘要及业务JSON容差比较只收紧既有comparison receipt verifier，不新增API、状态或持久节点。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"六CLI移除成功stdout末尾换行只对齐既有64KiB sandbox输出门，不改变执行拓扑或权限。","diagrams":[]} -->

## 2026-09-15 — CPU Skill 阶段 3 基金、组合与行业计算

- 七个新 Skill 通过既有内置种子、不可变版本和 `research_run_script` 沙箱交付，分别承担基金匹配、
  基金穿透、组合重合度、组合基准偏离、行业景气度、行业象限监控和行业拥挤度监控；未新增能力类型、
  API、Workflow、执行器、进程、端口或持久目录。
- 七项复用 `cpu_bounded_v1`、严格 schema/运行时字段等价、`YYYY-MM-DD` 前视边界、有限数值与受检
  算术、安全相对 JSON loader、完整 64 KiB UTF-8 envelope 和无尾随换行 stdout。
- 七包提交可哈希 synthetic source artifact 并由 fixture/golden/provenance 绑定真实摘要；未核验的
  DataHub 映射标记 `callable=false`，contract provider 必须与全部 dataset refs 一致。
- 基金穿透覆盖 percent/decimal、多层持仓和重复路径，对全部给定基金子图做 cycle fail-closed，并
  以拓扑检环及逐层动态聚合在单一快照内保留重复路径语义；组合拒绝隐式杠杆，基准偏离逐条匹配
  顶层报告期、因子日和行业映射版本，并要求跨组合/基准的 canonical 资产因子事实一致；
  三个行业计算器只消费预聚合行业指标，景气贡献全局最多投影 128 条，拥挤度要求统一交易日、市场
  总额约束以及每行业至少两个同口径滚动观测。
- 七项在 clean catalog 中可发现但全部 disabled，只有绑定当前不可变版本且可重算的 macOS
  Wind/Excel comparison evidence artifact v2 且由宿主登记器 HMAC 认证后才能启用或回滚到 enabled。
  证据绑定 synthetic/actual 输入与固定宿主执行器；sandbox 不继承密钥，普通 JSON 不能自证。当前
  synthetic fixture/golden 只验证计算和门控机制，不代表真实 Wind/Excel 对照。
- catalog 初始化时重新审计全部 enabled receipt-gated 能力，并在非 v2、签名/证据不可复核或缺少
  登记器密钥时撤下原生投影、持久化 disabled；能力选择前再次复核。该失败关闭仍位于既有 catalog
  状态机和本地索引边界内，不新增 API、Runtime 或存储拓扑。
- Stage 3 迁移的精确摘要白名单补入基金穿透与组合基准偏离的已发布直接父脚本，并保留初始摘要；
  合法旧 v2 receipt 仍只绑定旧版本，successor 保持 disabled 且不继承原生投影。

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"七个Stage3内置Skill复用既有目录、不可变版本和comparison receipt状态机；启动审计与选择复核只撤下不可信原生投影，不新增API、能力类型或执行器。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"Stage3已发布直接父脚本的精确摘要兼容只扩展既有一向迁移白名单；版本、receipt和原生投影状态机不变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"七个Stage3计算器继续位于既有research_run_script沙箱；拓扑检环、逐层聚合、严格输入与64KiB输出只收紧内部计算边界。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"Stage3行业计算器只接受预聚合输入，基金与组合计算器也不新增Provider binding或DataHub数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"Stage4五个CPU研究Skill复用既有种子、不可变版本、disabled与v2 HMAC receipt门禁；仅增加包和声明式元数据。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"Stage4计算器继续位于既有research_run_script沙箱，复用cpu_bounded_v1、相对JSON和64KiB输出边界。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"Stage4仅声明现有业务工具意图，未核验联合字段映射保持callable=false，不新增Provider binding或数据流。","diagrams":[]} -->

## 2026-09-16 — CPU Skill 阶段 4 规格复审修正

- 利率均线、股权风险溢价和风格轮动的输入/输出增加必填 `series_identity`，逐条绑定 identity、
  version 与 tenor；运行时严格拒绝期限错配、指数身份/版本变化及风格 A/B 交换或重复。
- 风格均线乖离方法增加独立 input/golden 与数值容差、信号断言；缠论双重枢轴及过近反转均明确
  验证为 `ambiguous_structure`。
- 五包静态扫描扩展到 SKILL、references、fixtures 和 scripts；后两项不可用来源仅保留逻辑描述和
  候选摘要前缀，不记录本机绝对路径。该修正没有增加 API、Provider binding、执行器、持久节点或权限。
- 二次复审将前三项身份契约改为 provider-aware descriptor：role/version/tenor 固定，identity 校验
  非空格式；synthetic 精确绑定 fixture，`user_input` 可原样回传真实业务 identity。Wind/DataHub
  未命中 field mapping 精确生产身份白名单时失败关闭。五包十份 schema 恢复官方 Draft 2020-12
  自描述 URI；静态检查只允许该元数据 URI，不增加远程加载或可执行网络能力。

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"Stage4 series identity/version/tenor、独立golden与来源描述修正只收紧既有不可变能力包契约，不新增能力类型、API或状态。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"Stage4身份等价性和缠论歧义结构检查继续运行在既有research_run_script沙箱内，不新增执行节点、网络或文件权限。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"Stage4 provider-aware身份契约只允许field mapping已核验生产白名单；当前Wind/DataHub白名单为空且继续callable=false。","diagrams":[]} -->

## 2026-09-16 — CPU Skill 阶段 4 质量复审修正

- catalog 在读取 synthetic/actual input 后强制 SHA-256 不同；路径不同但内容完全相同的已签名 evidence
  仍按无效证据失败关闭。Stage 2/3/4 合法 receipt 测试使用内容真实不同但业务可比的 actual input，
  golden/actual 输出继续按既有数值容差和非数值严格等价比较。
- 缠论结果 schema 与 golden 新增顶层必填 `asset_id`，来源固定为所有输入记录共同的已验证身份；
  全量记录改名会改变结果身份，混合标的仍返回 `data_not_equivalent`。

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"comparison input内容独立性只收紧既有artifact v2验证器，不新增API、receipt字段、状态或执行器。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"缠论顶层asset_id由既有单标的校验结果派生，仍在同一research_run_script沙箱与输出envelope内。","diagrams":[]} -->

## 2026-09-16 — Stage 2 输出契约与事件收益配对修正

- 六包输出 schema 的 parameters、dataset refs 与 provenance 对齐 Stage 3/4 公共严格契约；真实
  golden 继续通过，删除必填、错误类型/provider/日期/SHA、33 项 refs 和额外字段 mutation 均失败。
- event-review 先按共同交易日对齐标的与基准价格，再从相邻共同日同时计算事件前配对收益；目标或
  基准任一侧缺日时不再将两日收益与一日收益配对。

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"Stage2输出schema严格化只收紧现有不可变能力包的结果验证，不新增能力类型、状态或API。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"event-review共同交易日配对仍在既有research_run_script计算节点内，不新增数据源、网络、文件或执行权限。","diagrams":[]} -->

## 2026-09-17 — Windows DSH Profile 与进程生命周期修正

- 原生 Windows bootstrap 证明 pnpm Profile 使用目录 junction；Runtime 现在像 POSIX symlink 一样
  解析并限制最终目标仍在固定 DSH 源码树内，不再把合法模块回退误报为空。
- Windows PID 存活探针改为无 shell PowerShell `Get-Process`，终止仍使用 `taskkill /T`；不再调用
  Windows 不支持的 `os.kill(pid, 0)`，探针异常继续按进程存活失败关闭。
- Workbook 验证阶段 timeout 显式钳制为 180 秒总预算减 10 秒协调余量，消除 Windows 单调时钟
  浮点舍入导致的上界漂移；验证进程、输入、输出和支持平台边界不变。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"Windows PID探针只修复既有3081/8088受管进程生命周期，不新增API、进程节点、端口或持久状态。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"pnpm junction containment只收紧既有DSH Profile模块回退校验，Runtime组合、工具、权限和数据流不变。","diagrams":[]} -->
