# 研究框架

全市场终端v2属于Host内市场概览，不新增研究框架、对话引擎或报告生成；个人组合是显式输入的静态快照及缓存估值。状态分、风格方向与研究有效性分别展示，既有框架和策略模拟准入不变。

2026-10-23：市场限价/昨日金额/资金历史均为无会话行情展示，不改变Gold/Dollar、ETF报告、研究质量门、框架执行或DSH工具授权。 具体来源、缺口与缓存合同见[DataHub](../../research-web-datahub.md#无会话全市场数据)。
华安 Excel 仍沿原 Workflow → DSH → Host 研究链，模型只取证写 canonical 正文。Host 冻结原始输入及真实采集时间；历史在线重查不认证当时快照。本轮 Excel 日程关闭，原一次有界修订及正式质量门保持。

资产行情的工具条、筹码统计和数据说明改为连续布局，主体仍通过原观察快照向唯一DSH交接。关闭的来源/公式说明与历史查看行为不创建框架运行、不自动分析或升级为研究证据；本次样式不改框架选择、发布版本或研究质量状态。

全市场缺口修复（2026-10-22）：股票列表增加东财官网 f292 交易状态；同身份、同日单股接口有界补取空成交额与停牌参考价。停牌、未上市单列，不计平盘；已上市股票成交额全部覆盖后才合计。沪深大盘日线资金改用已实测访客端点，使用自己的来源、日期、采集时间与返回行数，不沿用板块元数据。无新依赖、来源权限或研究会话；原 Host/MarketService/DataHub/东财拓扑不变，现有图及 API Atlas 不重画。

华安ETF周报新生产合同复用私有DataHub、原DSH和Host质量链，不调用或修改Gold/Dollar框架的
采集、评分与生命周期。周报日程和正式稿状态不能成为框架有效性证据；冻结材料只有按原有归属
和哈希边界显式交接后才能使用。产品合同见[周报生产](../../research-web-etf-weekly-production.md)。

可选研究仓面板仅在数据设置和能力中心数据目录挂载。原生财务/宏观快照不自动作为Gold/Dollar框架输入或改变评分/采集生命周期；框架沿用原交接，正式回测必须另行满足历史可得性合同，不能因为数据已保存就视为验收通过。

2026-10-22 资产单搜索／真实专题及目录／load接口仍属于AssetWorkspace，不创建Gold／Dollar快照、Bot调用或新研究循环。目录缓存无会话，资产区块及历史交接保留原会话不可变证据；财务、股东名单和公告事件不自动成为框架评分或已核验研究结论。相关Host依赖与区块资料流同步02／04图，框架部署、授权和生命周期节点保持。


2026-10-22 MCP隔离：仅macOS固定离线Python在新增权限、policy/runtime/安装树/schema复审后条件开放；逐次重验并在受管Seatbelt内执行。Node/npm、其他平台、凭据环境、网络和子进程需求保持受限或失败关闭。解析前字节/连接时限与真实进程回收分别核验，回收未知保留准入栅栏；固定远程及非受管Native维持各自合同。具体包就绪不由Doctor入口存在推断。

2026-10-22 插件页面属于能力中心；导入/审批/受限 Hook 不触发 Gold/Dollar 采集或框架研究。隔离验收显式关闭框架、Registry 和报告自动调度，仅真实 Host/native 适配与自有无害夹具；不会以能力支持表声明框架已完成真实研究。见[插件合同](../../research-web-plugins.md)。

2026-10-22 Wind历史工作区只扩展资产Host/DataHub任务、账号副图偏好和快照证据，不调用Gold/Dollar框架采集或Bot、不改变其评分与生命周期。固定锚点复权与筹码估算不自动成为框架事实或通过DSH质量门；交接仍读取有归属与hash的原会话材料，既有框架图无需新节点。真实资产数据流已在02/04图更新，不能沿用旧“无API/持久化变化”概括本轮资产工作。

全市场概览为独立 `#/market` 入口，位于资产观察之前；三个市场页签不属于 Gold／Dollar 等研究框架，也不创建框架快照或调用框架 Bot。板块和指数的行情点击复用资产观察身份，研究执行仍由既有 DSH 负责；新增无会话数据流见[市场概览](../../../outputs/research-web-architecture/13-market-overview.html)。

资产观察 v2 固定版本部署仅复用现有主实例／网关控制面，Gold／Dollar 的领域快照、评分、Bot 准入和唯一 DSH 执行路径保持；部署空闲与保全不触发框架、模型或供应商查询。原研究框架及数据流图拓扑无需更新。

资产摘要分组、来源默认折叠及图表透明主题仅属于资产观察页面；Gold／Dollar 的画布、来源快照、评分与 Bot 仍按原合同运行。资产来源动态状态只说明当前快照载入，不推导框架来源已核验；原数据／执行拓扑无需新增节点或改图。

业务导航取消研究台一级入口：资产观察承载行情与基本面和独立 `fund_data` 基金查询，研究情报承载主题新闻/研报/公告检索，ETF 工程模拟进入 `#/simulation/etf` 的“策略模拟”。研究框架仍按分析体系组织，现有 `#/frameworks` 与详情路由、嵌入画布、采集器、快照、评分及 Bot 准入均保持原合同；策略模拟不注册为新框架。此次只重分组前端路由，Host/DataHub/DSH 与既有执行/存储图不变。完整归属与旧链接映射见[业务模块与导航](../../research-web-ui.md#业务模块与导航-2026-10-21)。

资产观察承接原AF连续指标工作区：基本行情、五图、估算筹码、资金流和五张基本面卡片；新闻／公告等补充区域位于指标之后，旧专题地址定位对应区域。本地ECharts／Chart.js、确定性指标与分区来源日期仅属于资产页。Gold／Dollar继续使用自己的连续画布、领域快照与Bot准入，不从资产图表、估算筹码或Golddata文章推导框架已核验；显式刷新仍只取得原观察的一个DataHub区块，不调度框架或新增研究循环。

登录页统一外观仅复用产品壳主题、Logo及原登录控制器；框架嵌入、能力准入、会话、执行与数据权限均保持原合同。

旧壳菜单升级仅规范账号入口及设置分类顺序，研究框架和研究任务控件不参与升级事务。

会话栏折叠修复仅调整共用壳的桌面展开按钮、搜索文字及可见焦点；框架页面仍使用原主导航，Gold/Dollar 画布、Bot、快照和框架准入不变，不新增 API 或执行节点。

框架页复用共用账号菜单：点击顶部身份进入应用内账号资料，设置仅增加管理员用户管理分类。Gold/Dollar嵌入画布、快照与Bot准入保持原合同；浏览账号不停止研究或改变框架快照。

自由分析数值绑定只扩展现有报告配方与Host复核；Gold/Dollar框架、策略、快照及调度保持。系统计算不能替代框架来源和口径验收，中文呈现与审计底稿的分离不授予研究通过。

Claw composer-menu 仅组织产品壳已有附件、能力、方法、格式和模型入口，不添加框架、API或研究执行器；能力继续绑定原发布版本和可用性，日程执行追问保持已批准范围。FinGPT保留原控件。

Claw 首页示例区的移除仅删除产品壳的案例/分类渲染与专用样式，保留日程新建草稿入口；不改变研究框架、执行、会话、文件或模型接口。

网页 GDP 数值和日期投影不改变框架来源授权、覆盖要求或策略执行。报告只允许当前已核对归档的回环误拼 URL 转为同源，历史无绑定检查仍显示原缺口，不能冒充框架核验通过。

Claw 欢迎页与整行问答修复仅调整既有产品壳的空态条件、选项点击和焦点；没有新增执行引擎、后端消息或框架接口。Gold/Dollar画布、Bot与快照准入保持原合同，问题卡不能补造原生消息。

本轮消息渲染只核对研究报告版本，不变更框架数据、指标或任务拆解。外部来源链接与用户上传附件保持原导航；显式算式匹配仍不能替代框架数据的来源/期间核验。

框架研究使用正文读取时仍限本轮允许的 web 来源与受信身份，不能用模型改写标题或搜索摘要替代原文。框架采集器、快照和调度保持；报告版本与质量回执按同一规范字节绑定，缺口仍独立保留。

primary 界面与原 backend 版本配对，框架嵌入仍经该账号代理；新用户沿当前界面和独立数据根，原组件拓扑不变。

常驻 primary 保护仅影响账号页停用/停止按钮，不改变框架嵌入、研究画布、导航或领域组件合同。

AI资讯自主化本轮在隔离实例接入原版API/worker与独立库，保持DSH研究执行及当前常驻内容。零调用和后续切换边界见[自主资讯合同](../../research-web-ai-news.md)。

邀请制服务器通过已认证网关访问既有框架页和嵌入资产，绑定当前用户的独立 Host/DSH 与数据根；框架定义、快照、评分、Bot 准入和数据证据合同不改变。登录/账号页属于产品壳，不能以登录成功提升框架可调用状态，也不授权原本被服务器 profile 禁用的宿主、MCP、日程或报告 Workflow 能力。

AI资讯文章全文、事件/主题专题及报刊均为独立只读模块，不改变Gold/Dollar框架快照、Bot准入、评分或研究上下文。

FinGPT 质量提示与报告面板复用产品壳，Gold/Dollar 快照、评分与 Bot 绑定不变；报告质量检查不能代替框架数据的来源与截止时点校验。

会话侧栏与逐题问题的统一仅调整原产品壳；Gold/Dollar嵌入画布、框架快照、评分与Bot准入保持。项目置顶/排序不会改变框架绑定或跨会话引用数据。

框架与 Bot 的既有流程不变；Claw 搜索覆盖信息仅属会话检索，不改变框架快照、研究上下文、模型或工具权限。

框架页沿用共用产品壳：顶部页面/框架面包屑与独立搜索图标已移除，一级导航搜索、
窄屏导航与服务异常提示保留；框架正文、Gold/Dollar嵌入画布及Bot入口继续按原合同渲染。

Claw 的轻量执行流及发送/上传竞态修复仅作用于既有会话界面：不改变Gold/Dollar快照、框架Bot、运行模型或批准范围。上传仍经Host校验；步骤展示与文件交付分别认证，不从折叠或工具成功推断领域研究完整。

周期简报的站内Word报告复用既有报告投影，不激活Gold/Dollar框架或DSH研究preset，
不将报告生成当作新增领域数据可调用。用户继续研究仍走原框架准入与冻结证据合同。

当前内置 framework-research 缺少可验证的 DataHub data_requirements 时，显式验证保持
capability_data_unavailable（readiness 中 data_contract_missing），不提交原生 prompt。
解释 preset 不替代验证准入。两条成功链的离线回归使用正规发布的合成 web-only v2，
不代表默认内置 Skill 已获真实数据准入，也不通过测试绕过资源或凭据门。

共用聊天 renderer 的停止、超时和重试资格检查不改变 Gold/Dollar 的版本、快照或准入。
外部资料工具仍经会话 DataHub admission；框架不能凭目录或兼容传输支持绕过数据/工具验证。

离线真实材料评价复用scoreChannel和canonical输入函数，只验证冻结领域规则和既有三次归组回执，不创建研究/框架或给Claw评分。工程核对不能替代独立人工标注，零规则分尤其可能源于空摘要。

日期核验沿人工纠错改变Hot事件版本，不创建FinGPT/Claw会话；新简报/研究冻结可携带新版本，旧会话不回填日期。字段记录人工来源核验，不能冒充独立评价标注或付费抽取已通过。

有界来源next补抓只写Hot原件/待处理材料，不创建FinGPT/Claw会话或付费调用；历史补录仍沿取得时间及冻结版本合同，不因补录制造新鲜热度。

来源配置页面仅管理Hot既有公开源的绑定、频率与启停，不注册框架、Bot、商业Provider或新研究。明确目录操作仍沿Hot控制权限，数据进入同一PG材料版本；FinGPT/Claw必须另由用户冻结资料并提交问题，来源保存不授权模型或外发。

关注和周期简报按Hot频道与固定原件选材；没有注册Gold/Dollar框架或改变Bot/评分合同。周期冻结不启动FinGPT/Claw；需要正式研究时仍由用户从冻结简报准备资料并明确提交问题。

Hot 的两步研究入口选择 FinGPT 或 Claw，沿已有 ResearchService 与 DSH 执行；不注册新 Gold/Dollar 框架，也不复制其规则或调度。冻结简报资料先准备会话，明确提交问题才进入研究。

2026-10-13 的 AIHOT 阅读界面适配仅作用于研究情报的 `.hot-reader` 区域，复用原 Hot/外部
资讯控制器及GET投影；Gold/Dollar画布、框架快照、Bot和采集边界保持。版式与现有研究
入口共存，不为前端展示创建研究回合或复制框架数据。

原生 Todo 仅进入研究 preset 与现有研究空间；Gold/Dollar 的采集、评分、Bot 快照和
framework-explain/framework-verify preset 不增加 Todo 或改变契约。研究空间的原生计划
来自会话日志，与框架步骤及 Workflow 版本说明分别呈现，不推断阶段归属。

Docker 模型存储来源展示复用模型设置，框架定义、快照、评分和 Bot 的数据合同保持；
文本凭据调用成功不能替代框架研究或 Linux 代码沙箱验收。

ETF工程模拟作为策略模拟中的独立确定性领域入口，不注册新框架、不扩大framework-explain/verify权限，
Gold/Dollar快照及Bot绑定仍沿原合同。真实链路BLOCKED；见[数据与文件](03-data-files.md#etf-工程模拟与真实准入边界)。

Claw 工作区侧栏切换保留当前聊天和输入草稿，文件按钮只打开当前会话的既有预览；项目管理仍有独立入口。此导航修复不改变 Gold/Dollar 路由、快照、Bot 或权限，也不将文件自动注入框架上下文。

Claw 的工具卡、运行报告和执行快照只投影原生研究事实，不改变 Gold/Dollar 的计划、来源、模板和校验。新工具目录限制仅应用研究型 Automation 会话；框架 preset 保持原有准入。

本轮 Claw 日程采用直接 `research_task`（schema_version=1），锁定研究描述、模型、输出要求、资料与工具白名单。用户确认创建并启用后才生效，创建不立即运行；旧 Skill/Workflow/报告任务保持兼容。修改以同一 ID、expected_version 和变更确认卡生成新定义版本，Run 保留不可变 definition_snapshot；手动试跑与 schedule 触发分别记录，不改下一次计划时间。能力与连接管理统一在能力中心，Claw 仅选择能力，Agent 日程使用独立表格。DSH 仍是唯一研究引擎，Automation 仍是唯一调度层。


Claw 项目归属只组织会话，不重绑 Gold/Dollar 快照或改变 Bot 执行。项目聚合不把其他会话数据自动注入框架，日程提出工具也不改变 framework-explain/verify 的权限。

## 资讯雷达 · 2026-10-09

资讯雷达作为独立只读页面读取外部现有资讯。它不调用 Gold/Dollar 框架分析、创建框架会话或更改快照；事件与研报详情使用独立前端状态。

异根 Native pair 的私有记录认证在框架消费者启动前复核单写者边界；不同根的完整已认证
日常实例可继续运行，同根或未知 writer 仍拒绝。框架定义、快照/评分/Bot 合同不变；该源码
fixture 不替代安装后实际框架生命周期或 Native/Docker 同根数据往返验收。

双运行时 Python 质量整理不改变框架目录、采集、评分或 Bot 协议；其格式/类型检查结果
仅为源码证据，不能替代框架消费者的实际运行验收。

研究框架为 Gold / Dollar 提供领域定义、真实采集、版本快照、确定性评分和绑定快照的 Bot。它是解释层，执行仍复用唯一 DSH，不创建独立研究引擎。

从[分层阅读入口](../../../outputs/research-web-architecture/index.html#module-frameworks)进入总图、流程、API、源码和测试。

Native / Docker 复用同一框架合同；模型配置影响新建 Bot 的默认模型，已有会话保留选模。采集失败保留最后成功值和缺口，集成状态或服务健康不替代框架快照证据。

DSH 0.2.1 下 framework-explain、framework-verify 由 owned overlay 显式注册到同一原生 preset registry；既有 ID、Gold/Dollar 定义、评分和快照绑定保持不变。空实例采用 `deepseek-flash`，不改写已有 Bot 会话或保存的模型值。模型生成成功与框架数据完整性分别验收，不由新版模型目录推导框架可用。

模型设置更新只影响新建Bot会话的默认模型，已有Gold/Dollar会话保留选模；活动父/子任务阻止共享凭据变化。模型生成测试复用无研究工具的框架解释preset，但不绑定业务快照、不改变确定性评分或框架采集。测试通过只证明指定模型生成，不证明框架数据能力。

模型设置更新只影响新建Bot会话的默认模型，已有Gold/Dollar会话保留选模；活动父/子任务阻止共享凭据变化。模型生成测试复用无研究工具的框架解释preset，但不绑定业务快照、不改变确定性评分或框架采集。测试通过只证明指定模型生成，不证明框架数据能力。

Native 正常安装 auto-start 连接真实创建证明与就绪后才启动框架消费者；no-start/已有根
不能借 marker 取得 fresh。新 HOME 的真实框架/Runtime 生命周期仍须对应平台验收留证。

启动失败恢复和缺失账本监听检查在研究框架启动前保护同数据根的单写者边界；恢复完成后
才可再次启动既有框架消费者，不能以换端口绕过活动研究归属。

其他 checkout 的 Web/DSH 数据根未经证明时，缺账本启动不会另起框架消费者；已创建的
安装数据根不因测试用途而成为 fresh，框架真实生命周期与 canonical 同根往返仍需各自验收。

fresh 启动失败后，回滚须先证明本次消费者全部退出及原外来监听身份未变；恢复证明不
授权另起框架消费者。无法证明时保留原错误与事务标记，供所属安装明确恢复。

macOS生命周期现在可记录非默认端口并重绑内部控制origin；框架仍使用同一已配置Runtime连接，
不硬编码由本次CLI选定的宿主端口，不修改框架定义、快照、评分或研究语义。

Native 和 Docker 复用 Gold/Dollar 的定义、快照 revision、评分、renderer 和 Bot 请求合同。
模式只改变同一 3081/8088 服务的部署位置；Docker 单容器健康检查同时要求两项服务 ready，
但框架采集是否取得真实外部数据仍由各自来源与缺口规则判断。Docker 健康通过不证明宿主
Office/Wind 等可选集成可用，也不构成 Windows Docker 验收。

2026-09-29 启动稳定性变更只调整 Research Web/DSH 的进程归属、恢复与页面 ready 判定。
Gold/Dollar 仍由同一 3081 Runtime 和 8088 Host 执行；定义、采集器、调度、快照 schema/revision、
评分、renderer、Bot 会话绑定和框架图源均未改变。模型未配置时 Web 设置页可访问，不代表框架
解释或深度验证已经可调用；该能力继续由真实 Runtime、模型及快照状态决定。
未安装环境的顶层 `rwb --help` 只输出静态诊断指引，不加载 Gold/Dollar 定义、采集器、快照
或 Bot；本轮 CI 修复不改变框架版本和页面合同。

Web 一键安装只统一运行依赖和固定 DSH 构建；Gold/Dollar 的定义、采集、快照 schema、评分、
renderer 与 Bot 会话绑定均未变化。框架仍由同一 3081 Runtime 和 8088 Host 执行。
启动前 Doctor 门只阻止未完成安装的 checkout 创建共享 Runtime；通过后仍沿用同一框架注册表、
调度器和快照协议，不增加框架进程或改变评分、renderer 与 Bot 会话绑定。
Runtime build lock 只绑定同一已验证 DSH 闭包；锁修复不修改 Gold/Dollar 定义、快照 revision 或调度频率。
全新 DSH `web` Profile 初始化、Windows junction containment 和 PowerShell PID 探针只保证这条唯一 Runtime 可启动/停止，不改变
Gold、Dollar 的注册、采集、评分、快照或页面协议。
Office/Wind 验证 timeout 的跨平台浮点上界修正只作用于本机集成验证器，不进入框架采集、评分、
renderer 或 Bot 会话。
`rwb web status` 不再因服务管理器导入而加载 Runtime Capability/MCP 功能图；这只缩短停止态诊断
路径，不改变 Gold/Dollar 注册、调度、快照、评分、renderer 或 Bot 预设。
安装阶段的 Web import readiness 可以加载框架定义以证明入口完整，但不进入 FastAPI lifespan，
因此不会启动采集调度、读取外部来源、写快照或创建 Bot 会话。

## 产品边界

新增Hot黄金频道属于共享材料/事件的规则视图，不替代Gold框架快照或其Bot。Hot页面与设置
独立路由，不借用框架验收声明；正式冻结交接至FinGPT/Claw仍待实现。

研究框架是 Research Web 的解释层，不是第二个资产行情终端。`#/frameworks` 固定列出黄金与美元流动性，`#/frameworks/gold` 和 `#/frameworks/dollar` 分别提供专用研究画布；资产观察继续负责个股、基金、债券、外汇和商品的行情与资产详情。框架引用的美债、美元、基金和商品只作为因果驱动、传导或组合背景。

两个框架都使用一张连续研究画布，而不是七个相互割裂的页面。Gold 的七个语义锚点保持不变；Dollar 按“总览 → Q 总量水库 → P 资金价格 → g 财政水流 → M 融资管道 → X 跨境美元 → 传导与证据”排列。`?tab=` 深链映射到同页锚点。产品壳持有唯一 `main` 地标，专属 renderer 把连续画布输出为带框架名称的 `section` 区域。桌面 Bot 是画布右侧的吸顶解释面板，移动端为全页底部面板；900px 及以下的关闭入口收为 44px 图标按钮，打开态契约不变。

## 版本化专用包

`app/research_web/frameworks/base.py` 只定义薄的跨框架协议：框架元数据、章节、来源、缺口和区块新鲜度。`registry.py` 固定注册框架，`storage.py` 负责严格有界的原子快照，`scheduler.py` 只创建一个幂等的 `AsyncIOScheduler`。Gold 与 Dollar 分别拥有 definition、contract、collector、score/context 和前端 renderer，不把 Q-P-g-M-X 或黄金字段提升成通用 schema。

黄金的因果链、反证条件、字段、状态门、样例和采集全部留在 `frameworks/goldar/`：

- `definition.py`：不可变方法版本与来源修订 `758ae3848dc32adf2b361fdd070f98cbc75ce496`。
- `contracts.py`：严格、禁止额外字段的黄金专用快照。
- `seed.py`：可复现的离线初始快照及内容 revision。
- `store.py`：使用共享存储协议并把 Gold v1 原件备份为 `snapshot.legacy-v1.json` 后迁移到 v2。
- `collector.py`：WGC/SPDR 黄金价格与持仓、FRED 宏观、Goldhub 供需/ETF、Cboe GLD 期权和 CFTC 年度 ZIP。

`frameworks/dollar/` 使用方法修订 `2c210b45577905c0e8ec5f9c061e7069a6cb3b96` 和 DollarSnapshot v1。核心读取 FRED、纽约联储、FiscalData 与 TreasuryDirect Upcoming Auctions；日度财政失败时保留 WDTGAL 周频代理并标明代理属性。“WALCL − TGA − ON RRP”只称净流动性代理，不描述成会计恒等式。五维平均值大于 `0.15` 为偏松、小于 `-0.15` 为偏紧；任一维度不可计算或存在高严重度缺口时强制待核验，同时保留已知小计和可能区间。

后续调整框架逻辑时，先改框架自己的 definition/contract/collector/context/renderer，新增方法版本并配套迁移和回归，不原地改变历史版本语义。只有至少两个真实框架出现同一生命周期或展示概念后，才把重复内容提升到公共协议或 `ui/frameworks/common.mjs`。

## API 与研究状态

- `GET /api/research/frameworks` 返回框架元数据和可用状态。
- `GET /api/research/frameworks/{slug}/data` 返回 `{framework, snapshot}`。
- `POST .../sessions` 创建只解释当前快照的 DSH 会话。
- `POST .../messages` 在原解释会话继续提问。
- `POST .../verify` 仅在用户显式触发后，新建只读深度验证会话。

所有 Bot 请求都携带并复核 `snapshot_revision`。数据更新后旧会话返回 `framework_snapshot_changed`，不得把新旧证据混在同一结论中。默认 `framework-explain` 预设没有工具，只能解释服务器提供的框架上下文；`framework-verify` 通过 `framework-research` Skill 使用当前 Runtime 实际暴露的只读检索与公共数据工具。两种模式都不能写快照、改评分或输出交易指令。

Gold 研究状态只使用“偏强 / 中性 / 偏弱 / 待核验”，Dollar 使用“偏松 / 中性 / 偏紧 / 待核验”。关键区块缺失、过期或存在高严重度缺口时，严格契约强制降级。seed 只用于离线测试和首次尚无真实快照的服务端状态；生产浏览器在 API 失败时不加载 fixture。采集器按区块保留最后成功值，并记录 `checked_at` 与 `failure_code`；GET 请求只读本地快照，不触发外网。

## Lieflat 图表协议

Gold 使用 F2（价格背景）、F9（四维贡献）、F6（需求同比）、F5（期权压力）和 L4（相关性矩阵）。Dollar 使用 F9（五维贡献）、F3（净流动性代理）、F12（政策路径变化）、F6（TGA/发行）、F2（SOFR−IORB）和 F8（跨境关系）；单页模板不重复且不超过六张。周期、事件和证据继续使用紧凑表格或 disclosure。

每张图只有一个结论、一个标题、一组来源与一条编码说明；数字使用等宽样式，颜色只表达正负、风险和缺口语义。SVG 提供 title/description，不加载外部字体、CDN、iframe 或品牌素材。移动端允许图表容器局部横向滚动，但页面本身不得横向溢出。

## 验证

`tests/research_web/test_frameworks.py` 覆盖两框架目录、严格契约、精确快照绑定、跨框架拒绝、迁移和生命周期；`test_framework_collectors.py` 覆盖转换、门限、CFTC 幂等与最后成功值。`test_workbench_operations.py` 覆盖全局 Artifacts 忽略软删除会话、显式查询仍返回 410、恢复后重新出现。JavaScript 测试覆盖两个连续画布、单一主地标、具名画布区域、图表、无浏览器 fixture、状态与安全用语。浏览器验收覆盖浅/深色、1440/1024/768/390、900px 窄屏标题摘要、44px Bot 入口、键盘锚点、Bot、横向溢出和 reduced-motion。

框架间 hash 路由切换还必须覆盖“目标 slug 已更新、旧快照仍在内存”的同步渲染窗口；`frameworks.mjs` 在调用专属 renderer 前拒绝 slug 不一致的快照，并显示目标框架加载态。

Dollar 的实时 `plumbing_m` 保存 60 期 SOFR−IORB；F2 renderer 只取最近 30 期，以满足图表密度上限。该裁剪不回写快照，也不改变 M 维评分、来源或观测日期。

框架服务随 8088 由同一固定部署根加载；启动器对调用目录和 Node ABI 的确定性处理不改变框架注册、快照或 Bot 上下文协议。

Research Workbench Method 层不改变 Gold／Dollar 的领域定义、版本、采集、评分、快照或 renderer。
框架 Bot 仍走唯一 DSH 链；未来如为框架能力配置 `method_policy`，也必须使用当前框架快照 revision，
且 Method 采用记录不能替代来源、因子或结论证据。首版框架能力未配置默认推荐方法。

统一集成协调器只改变设置页的来源/本机状态聚合和 DataHub 业务工具的动态选源，不改变 Gold、Dollar
的专用采集器、快照 revision、评分或 Bot 会话绑定。框架来源失败仍按各自 collector 的最后成功值与
缺口规则处理，不能用集成页的“可用”替代框架快照证据。

资产观察对 AKShare 财务缺失哨兵的规范化不进入 Gold／Dollar 专用 collector、快照 schema、评分或
Bot 上下文；框架数据缺口仍只由各自严格契约判断。

Hot简报继续绑定Hot自身事件/材料/频道版本，来源陈述、规则/模型/人工判断独立展示；不借用或伪造Gold/Dollar框架快照、研究方法revision或Bot会话归属。共享UIcore只增加Hot简报子路由，正式框架handoff仍待接入现有ResearchService。

## 设置闭环阶段3：当前能力范围

Gold/Dollar采集、评分、revision及renderer保持原合同；公共源码的能力准入和脚本读取门也作用于同一Runtime，不能由模型生成成功提升为框架数据完整。无工具解释preset不因此获得专业数据授权。


## 单一兼容模型连接

兼容模型文本/流式连接不会授予专业数据或工具能力。无工具的框架解释preset可用于显式生成验收；Gold/Dollar采集、版本快照、确定性评分及深度验证范围不变，模型成功不提升框架数据完整性。

## 设置页本机证据与框架分离

本机设置页精简和Office自动验证不改变Gold/Dollar框架、评分、采集器或框架快照。Office状态只表示对应本机验证，不能提升任何研究框架或DataHub来源为已验收；状态投影与授权边界统一由[集成协调器](09-integration-coordinator.md)维护。


Hot研究与报告是既有FinGPT/Claw会话结果的读取面，不启动另一研究框架或周期调度。框架工作区和后台Collector不因该列表改变；真实报告依据有限RSS标题，保留推断和覆盖缺口。

## FinGPT 研究融合 · 2026-10-13

FinGPT 的 research_depth/source_scope 属于研究会话，不进入 Gold/Dollar 快照或框架 Bot。新增报告底稿与 PDF 使用会话 outputs 和原文件交付解析；框架数据及生命周期仍由原模块负责。

## 同源嵌入看板与原生数据闭环 · 2026-10-14

Gold／Dollar 的页面由同源 iframe 核心看板呈现，原生 definition、collector、score、store、schema、历史快照和 DSH Bot 保留。旧原生画布 renderer 仅作兼容代码与回归对照；新页面不再使用旧画布布局，也不读取导入 JSON 作为核心数据回退。

宿主只读取既有 data API，领域适配器保留数值、null、单位、来源、日期和 revision。iframe 渲染同一快照后返回来源窗口、slug、revision 和本次 token 一致的 ack；在确认前不能发起 Bot。刷新不改变旧会话绑定；旧 revision 触发原有 409。源失败保留原生最后成功值和缺口。

回测、量化策略和模型拟合入口明确为尚未接入；不向 Bot 注入这些静态结果。其余九个框架是 2026-10-14 导入的静态看板，其日期表示导入日期，不表示各指标观测日期；没有实时采集或 Bot。静态看板 coverage=0，不把资产存在当数据完整。静态看板创建 Bot 返回 framework_bot_unavailable。

静态入口位于 /frameworks-embed/{slug}/，单独使用同源 iframe CSP；主页面 CSP 不放宽。新标签页进入宿主框架详情。原生模型真实生成、供应商实采及其他平台证据分别记录。

## Dollar 托管美债来源纠正 · 2026-10-14

X 维度的外国官方及国际账户托管美债使用 [FRED WMTSECL1](https://fred.stlouisfed.org/series/WMTSECL1)，来源美联储 H.4.1，周频周三水平，原值百万美元除以1000显示为十亿美元。它是限定账户范围的托管可流通美债，不代表全部海外美债持仓或跨境资金流。指标和独立来源条目均保留该序列实际观测日期；取数时间不替代观测期。

TRESEGUSM052N 是 IMF 月频美国不含黄金储备，不能用于上述名称；旧 WMTSECL 已终止，也不使用。此项纠正原方法既有指标实现错误，X 评分仍只沿原广义美元公式，阈值、快照schema、Gold和Bot权限不变，不引入新方法或迁移。历史坏值不认证为正确；正常采集写新revision替换该区块，不回写旧快照或重绑旧会话。正确来源不可用时保留旧值并标stale／待核验，不回退到错误序列。

## Gold 配置模块未接入边界 · 2026-10-14

原生 `allocation_context` 的 diversification_note、drawdown_note、scenarios、correlations 目前仅由 seed 提供；现有 collector 没有该区块的真实采集与计算链，也没有可审计的股票/债券总回报及统一观测窗口。既有真实黄金/美元/利率序列不能替代这套配置研究结果，本轮不引入回测或新采集。

当前嵌入看板保留“情景与配置”入口，对 fixture、missing、无来源、`.invalid` 来源或明确 fixture 计算方法显示“尚未接入”，不绘制相关性、情景表或样例说明。新 Bot 解释与深度验证的上下文同样剔除这些样例值，仅保留未接入原因和缺口。带真实来源的 complete/partial/proxy 以及 stale 最后成功值保留其数值、来源和日期；来源元数据的存在不是实采认证。

原生 schema 2、API 形状、seed 和历史文件不迁移；同一 snapshot revision、确定性评分和覆盖率保持（实采后配置仍缺失时为85%）。API 为合同兼容仍保留明确 fixture 区块，它不能被认作当前事实；当前生产 renderer/Bot 在消费边界拒绝使用。旧离线 canvas renderer 仅由测试直接调用，不是当前宿主生产入口。旧会话历史不回写，新提示上下文按服务器绑定的原 revision 生成。

模型服务页的多连接卡片和完整添加页仅属于设置路由；框架画布、策略快照、研究Bot准入不变。框架后续新研究仍使用当时默认连接，已存在研究按自身profile绑定执行，不凭页面切换改写旧会话。

2026-10-23 资产近期raw来源选择与Broker等价备用只改变既有Host/DataHub/快照链的参数和校验；不触发Gold/Dollar框架、模型或第二研究引擎。新asset-history-raw-2只有声明单位及证券/日期校验通过才能发布，不能据此宣称框架或正式回测已通过。

2026-10-23：资产行情数值采用A股红涨绿跌，开高低收各自对真实前收比较；涨跌额/幅按正负着色，零、无效及缺失基准保持中性。沿原主题红/绿变量，只给数值上色；历史十字线、日周月与局部报价刷新同步，计算和冻结数据不变。
