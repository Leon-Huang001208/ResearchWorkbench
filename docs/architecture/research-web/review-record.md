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
