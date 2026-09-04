# 架构迭代核对记录

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
- 新研究 Tool 改用稳定子系统前缀 `datahub_*`，与 AlphaFoundry 品牌解耦；旧 `af_public_data` 仅保留兼容，不要求未来产品改名时迁移新协议。
- 图 02、03、04 按实际目录、路由、原生审批、Provider 和会话快照重新建模；图 01、05–08 的部署、能力包生命周期、运行状态、交付状态和文档门禁拓扑未改变。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"能力中心新增数据目录模块、双视图、来源矩阵、详情与单源探测交互。","diagrams":["02-module-dependencies"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"新增静态能力/来源目录、业务查询路由、Provider 就绪状态与探测，并把选源和快照纳入真实研究序列。","diagrams":["02-module-dependencies","03-research-sequence","04-data-file-flow"]} -->
<!-- architecture-review {"group":"runtime","structure":"changed","reason":"原生桥新增十三个品牌无关 datahub_* Tool，审批后调用业务查询入口；旧工具只保留兼容。","diagrams":["02-module-dependencies","03-research-sequence","04-data-file-flow"]} -->
<!-- architecture-review {"group":"capabilities","structure":"changed","reason":"只读 Tool 目录加入十三个 DataHub 业务能力，并按实际可调用 Provider 控制可选择状态。","diagrams":["02-module-dependencies"]} -->

- 最终浏览器验收发现手动探测完成后，当前来源详情仍保留旧的 `health=untested`；已先加入失败回归，再让 UI 在目录刷新后只重读同一来源详情。复验财联社显示“已接入 / 健康”，网络记录没有探测其他来源。该修复属于既有单源探测交互内部状态同步，不增加模块、接口或拓扑，因此不再次制造图源改动；02/03/04 已覆盖来源详情、单源探测和目录刷新关系。
- 命名收口时发现旧 `af_public_data` 仍可被新草稿选择；已保留其原生注册以读取历史活动，但从能力中心可选项和新消息受理白名单移除。新增契约验证 `datahub_get_fund_data` 可受理、旧别名返回 `tool_unavailable`，不改变既有 Runtime/DataHub 拓扑。
- 本轮完整证据为 290 项 Python 通过（3 项按既有条件跳过）、134 项 JavaScript 通过（零跳过）、Ruff/Black/isort/mypy 通过；五个产品视口无水平溢出。真实公开最小探测仅验证东方财富基金和财联社当时健康，不把其余登记来源称为已接入。
