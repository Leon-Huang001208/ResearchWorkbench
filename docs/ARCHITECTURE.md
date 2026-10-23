# Research Workbench 架构总览

华安固定升级 v2 仅将组合产品锁定为 PR209 merge `56709a8d`，前版仍为 `5343e18d`；复用原事务及该产品已有 dossier 保全，不新增节点、执行器或部署权限。v1 与既有图保持；v2 最终候选另行验证、评审及授权。

华安周报的封闭 `apply-etf-weekly` 只固定已审产品988046d与当前前版5343e18d，复用原version4维护锁、BirthFence、全账号64MiB业务索引保全及恢复。没有新服务、HTTP、依赖或执行引擎；原图仍准确。代码/CI资格与实际常驻切换、正式报告验收分开，最终执行仍须独立明确授权并锁内复查当前身份与空闲状态。

今日发现新增现有Host内的固定Intel读取→显式选材校验→原DataHub归档→一次DSH提交分支；独立开启跟踪复用原Automation与账号RuntimePool恢复，不增加研究引擎、数据库或后台服务。资料流与研究序列有真实新边，01/02/03/04图同步；受理、规范报告质量和实际部署分开，合同见[今日发现](research-web-discovery.md)。

华安经济日历的时间、前值、预测值和今值沿原 Excel 快照保留，Host 从锁定原件独立重建全部事件字段，类型、顺序、来源不符即阻断。此为原资源重放与底稿投影边界的补齐，不新增引擎、HTTP、依赖或持久格式，原架构图仍准确；Word 经济表维持原三列。

2026-10-23 SPDR 四项快照扩展现有外部 Provider 和原生研究仓白名单；单次原件、四项行/字段及单位通过同一解析器绑定。
仅增加现有 gld 的数据合同版本，Host → DataHub → Provider/可选 MarketStore 的节点与边保持，现有图准确。
无新 HTTP 路由、数据库表、服务或引擎；首次观测快照、每次授权和正式 PIT 限制见[原生快照](research-web-vendor-snapshots.md)。

2026-10-23：市场终端固定部署仅在原Native操作员增加`reviewed-market-terminal-v1`／`apply-market-terminal`身份，复用version4维护锁、BirthFence、主实例与网关升级、全账号保全及恢复；不新增运行节点、协议、依赖或第二研究引擎。产品13图已有终端数据边界，操作员沿原01／12图，无须重复重画。固定候选、尚待PR201合并后冻结的产品身份及分层验收见[部署合同](research-web-gateway-upgrade.md#全市场终端固定部署2026-10-23)；本机回归不代表常驻已切换。

2026-10-23全市场终端v2沿现有浏览器→Host MarketService→公开来源及账号文件增加版本化24指数目录、三周期六维证据、风格矩阵与组合预览确认。东财行情与新浪前日价格指数日线分别保留来源；旧12指数研究仓合同不扩写。持仓与首次观察日线保存在原用户market-cache，GET不采集、不创建目录，不新增守护进程、依赖、研究会话或交易接口。13市场图按Host模块抽象同步这些数据边界。
2026-10-23构建器对账沿现有管理员rwb-docker／Docker Desktop节点增加显式preview→指纹绑定apply／recover工具，复用原operation.lock、固定BuildKit和资源限额。仅恢复当前已核验本地引擎中容器与卷同时缺失的登记；无新Web服务、业务数据流或常驻切换。详见[Docker对账](research-web-docker.md)。

2026-10-23官方与中国宏观接入继续走Host/DataHub/Broker/既有公开worker/ResearchWarehouse。NYFed与Treasury采用已登记端点；AK的四个factor_macro序列复用现有业务查询接口，原始响应与参考期字段进入provider-native捕获。04数据图的normalize节点已包含可选研究仓、修订与冻结，本轮增加其封闭合同及版本检查，没有新服务、HTTP路由、数据库表或第二研究引擎。观察期不等于披露时间；这些捕获不获得正式PIT资格。错误封包修复在原Provider和会话缓存边界，不能通过HTTP200获得数据成功状态。

2026-10-23市场补齐沿既有浏览器→Host MarketService→DataHub公开东财→当前用户缓存拓扑，新增同批限价状态、同池昨日逐股金额重算及最多30日真实资金留存；不增服务、HTTP路径、业务index、依赖、模型调用或跨账号流。原13市场图拓扑不变，缓存可选字段和公开投影分别见[缓存](architecture/research-web/03-data-files.md#全市场概览缓存)、[API](architecture/research-web/04-api.md#全市场概览接口)与[口径](research-web-datahub.md#无会话全市场数据)。
华安周报新增既有 DataHub 私有 wind_excel 来源分支，复用 Report Workflow、唯一 DSH、Host 独立复算与原版式投影。EDB/日历绑定同版本原生导出证据；市场截止15:30与实际冻结分别记录，历史重查不认证当时快照。09/10图同步来源分支，无新服务、HTTP或依赖；本轮定时关闭。
本期 schema4 只为已证实的伦敦金历史单点缺口附加同版本原生 WSD／TDAYS 资源；Host 重读原 EDB
并重算重叠、覆盖及补点，不覆盖原始导出。它仍是09/10图中的来源证据与 Host 核验节点，未新增执行路径；
封包审查、实采预检、正式 Run 与交付认证分别记录。

## 2026-10-23 资产筹码与精炼行情布局

本轮保留 Host → AssetWorkspace → DataHub/Broker → 账号绑定 CJPY 的既有拓扑。`market_activity/chip_turnover` 是现有适配器内的封闭数据集，不新增服务、任意公式或第二研究引擎。历史任务可冻结逐日换手与同复权 VWAP，全部输入验证后原子更新快照；前端 `asset-chips.mjs` 只从该版本计算自有估算。新增布局与数值格式模块不改变原始数值或冻结证据。既有运行时与数据流图仍准确，模块及持久/API合同见 03/04 章和 DataHub 文档。


2026-10-23公开指数研究仓桥沿现有Host/MarketService/DataHub/ResearchWarehouse拓扑：默认Host注入无会话MarketReader，POST indices显式取公开eastmoney后将完整固定12指数响应归档；GET仍只消费market-cache。内部允许缓存请求可读同来源/同个人profile摘要的短时捕获，读写前后重验Host根、关闭状态与profile epoch。没有新增服务、HTTP接口、依赖、研究引擎、共享scope或第二来源；13市场图新增indices-only的可选写仓/内部缓存读取分支，不沿用此前无仓库边的旧图结论，精确边界见[DataHub](research-web-datahub.md)。

PR188合流后的当前v5组合产品固定88ef3817680ac822e2d7c819db845de4b7275173，包含资产9bc4及DataHub研究仓；PREVIOUS仍51f09，8f2cb39a的一行业务读取修复另保留源码身份。用户已批准组合验收后部署锁定baostock0.9.4／psycopg3.3.6，但不启用／迁移数据库、不改外盘。PR188已审新04数据流保持，以下“v5本身无新结构／依赖”只描述原封闭profile及一行修复，不覆盖组合产品的研究仓变化；旧a114三CI全PASS不认证新组合，最终仍须重验。

2026-10-22资产v5大业务索引修复仅让原verify_primary的v5分支复用既有64 MiB安全业务读取器，元数据仍为1 MB；修复8.67 MB业务index在停机前被误拒绝的绑定错误。既有Host、账号数据根、部署节点、锁、version4事务、全账号保全与恢复不变，旧profile／controller／evidence／固定产品均不修改。无新HTTP、数据流、格式或依赖，现有图准确；PR187原Constraints失败及修补后的候选验收分别留证，不以本机通过冒充CI或部署成功。

2026-10-22资产交互v5固定部署只在原操作员增加封闭`reviewed-asset-observation-v5`／`apply-assets-v5`身份：PREVIOUS固定当前常驻`51f09fa783694aae5234905933948394ca167dcc`，PAYLOAD固定PR185真实merge `9bc4e4cab91130647a5bc0dfa519e97f4773416a`。沿原version4事务、维护锁、BirthFence、全账号索引保全及内容寻址恢复；旧资产v1–v4、两个market profile和模型恢复保持。没有新增节点、HTTP、持久格式或数据流，现有图源准确，不重画图；阅读源码链接指向已审产品，v5操作员最终候选仍需独立评审、原三CI／同候选Mac安装及实际部署证据。

行情缺口部署使用封闭 `reviewed-market-gaps-v1` / `apply-market-gaps`：旧版固定 `99d3ee34977c47189a5638207c109a555f52a687`，产品源码检查点固定 `9faeeca3003a912ca75799fb27b635ba1bb87a1a`。检查点为本轮产品修复的不可变祖先，最终操作员/产品组合目标仍必须最新已合并 master、独立评审和原三项 exact-tree CI（含 Mac 干净安装）合格；不把检查点冒充合并版本。复用原 version4 保全/恢复，并在原维护锁内额外核对 MarketService 的 inflight 明确为空；未知或正在采集时不切换。旧 profile、controller/evidence/网关模块字节及模型/账号权限保持，无新部署节点、HTTP或依赖，原图准确。

全市场缺口修复（2026-10-22）：股票列表增加东财官网 f292 交易状态；同身份、同日单股接口有界补取空成交额与停牌参考价。停牌、未上市单列，不计平盘；已上市股票成交额全部覆盖后才合计。沪深大盘日线资金改用已实测访客端点，使用自己的来源、日期、采集时间与返回行数，不沿用板块元数据。无新依赖、来源权限或研究会话；原 Host/MarketService/DataHub/东财拓扑不变，现有图及 API Atlas 不重画。

2026-10-22 全市场常驻部署使用封闭 `reviewed-market-overview-v1` / `apply-market`：旧版固定 `4d2e3c408663b64be9e58b03213f4ca8f1152733`，产品固定已合并 PR179 `5de7e5f2db95b8b501905af9cfdc30e8fe84db0b`。复用原 version4 事务、空闲准入、BirthFence、全部账号索引冻结和内容寻址恢复；旧 profile、控制器、证据读取器及自动兼容白名单保持。操作员候选须独立评审及原三项 CI／同候选 Mac 安装通过，再按用户授权切换并在真实认证页面验收。 该封闭部署事务本身不新增服务、HTTP、持久格式或依赖；它沿用当时已审的图与 API Atlas，不要求重画 HTML/PNG。Windows/Linux 原生与 Docker 产品层保持各自未执行状态。

2026-10-22 资产交互与数据迭代增加两条现有 Host 内的数据路径：单搜索框 → 账号 `AssetDirectory` → 显式授权的 DataHub 天软目录读取 → 24小时账号缓存；专题页 → `AssetWorkspace.load_block` → Broker → 数据集感知的 Provider → 原会话不可变快照。目录读取不创建研究会话或启动模型；新证券的概览与近期前复权历史仍沿原观察／历史任务链路。DSH继续是唯一研究引擎，没有新服务、数据库、依赖或部署节点。新增HTTP与缓存分支分别见[接口](architecture/research-web/04-api.md#资产目录搜索与区块按需加载)和[文件](architecture/research-web/03-data-files.md#资产目录与按需区块缓存)，不沿用此前纯静态迭代的“无新HTTP／持久化”结论。

天软结构化资产适配使用固定表字段和预定义因子，提供估值、财务、股东明细／汇总、行业分类、两融及公告事件；财务按报告期／公布日读取，不套用行情60天区间，缺字段、单位和币种不补造。日线蜡烛实体与所选日期／视区独立保持，专题内容局部更新；真实来源预检、完整浏览器链路、同候选Mac安装CI与常驻切换分别取证。宏观、ETF和指数不因本次A股接入而获得支持声明，详见[DataHub合同](research-web-datahub.md#资产目录与结构化区块)。

研究仓作为现有 Host/DataHub 的可选存储边界，MarketStoreService 逐次检查来源与租户授权，WarehouseBridge 只接受可信宿主数据合同与交易日历。原件/事实修订/PIT/冻结位于独立 PostgreSQL 适配，不引入第二执行引擎；正式连接与迁移尚未启用。资料流图04同步可选仓、真实工作占用和冻结边界。


2026-10-22 受管本地 MCP 沿原 Host → 官方 SDK → stdio 链增加 `mcp_runtime/managed_sandbox.py`：仅 macOS 固定 Python 的离线 Seatbelt，安装包/runtime只读、每连接scratch可写，禁网络/子进程/凭据环境。新权限与实际政策/runtime/包/schema审核逐次重验；远程HTTP与非受管Native保留，无新引擎/服务/依赖。节点拓扑不变，详细边界与验收分层见[插件合同](research-web-plugins.md)。

2026-10-22 插件包由 Host `plugins/` 管理不可变版本、审核与投影，`plugin_routes.py` 和 `multiuser/plugin_routes.py` 连接原能力中心、真实网关角色与原 MCP 生命周期；`runtime/plugins.mjs`/guard 接唯一 DSH，不增加研究引擎。双阶段受控重启复用请求出生冻结，仅停止 Pool 自有空闲 DSH，未知保持冻结。文件、权限、接口和支持差异见[插件合同](research-web-plugins.md)。

2026-10-22 部署profile v4复用原Native/网关version4事务，旧版固定5495、产品固定PR180真实merge `9b436613aad9136f4959c992c89dd72fc7354ed5`。旧v1/v2/v3、controller/evidence及严格保全门不变，无新服务、API、持久格式或产品数据流，不改图/架构HTML/PNG或CI。旧v3失败已正式恢复5495/preserved=true/fenced=false；产品三CI与v4工具最终验收/部署分开，详见[固定部署合同](research-web-gateway-upgrade.md#资产观察固定版本联合部署)。

华安 ETF 周报新生产合同沿既有 Report Workflow、私有 DataHub、唯一 DSH 和 Host 质量门运行。
主管理员周五15:30冻结本期数据，DSH写规范正文，Host将同版本中文presentation投影到原模板并核验
本期图表及文件后才能定稿；旧版payload合同不补认证。SDK、日历、同源等价及真实周周期未核实时保持阻断，
不新增部署节点或研究引擎。详见[周报生产合同](research-web-etf-weekly-production.md)。

2026-10-22 启动保全热修复只调整Store序列化：旧磁盘缺失且仍为精确默认值的`asset_history_jobs`、`asset_history_keys`及`chart_preferences`仅在内存兼容提供，启动/无关服务save不把它们写入旧索引；首次真实变化后才持久化，原来已存在的键（包括空值）和已持久化后恢复默认的键均保留。严格索引保全门、不可变控制器、部署事务与产品API/数据流不变，因此不改图或CI结构。真实v3切换因增加默认键被保全门拒绝、回滚/恢复状态由本次报告如实记录，不把门禁阻断说成部署成功。

2026-10-22 Wind工作区独立部署profile v3复用既有Native主实例/私网网关的v4事务，仅增加封闭旧版5495与产品a0ff3ae2身份及apply-assets-v3入口；不修改已合并产品、HTTP、数据流、控制器或证据读取器。旧v1/v2恢复保持。新增部署节点、研究引擎或持久格式均不存在，因此本轮不重画现有图、不改架构HTML/PNG；准确身份、授权/空闲与保全条件见[部署合同](research-web-gateway-upgrade.md#资产观察固定版本联合部署)。

2026-10-22 Wind资产工作区沿现有Host增加持久历史任务和账号指标偏好：浏览器 → `asset_routes.py` → `AssetWorkspace/HistoryJobs` → DataHub Broker → CJPY → 不可变原始块/因子 → 同版本规范快照 → 研究交接。近期2年、续取4年和全部扫描共享固定复权锚点；取消仍等待真实Future，常驻空闲证明覆盖历史非终态与CJPY调用。`index.json`新增键，无新数据库、依赖或第二研究引擎。新增6项API及真实数据流已同步[接口](architecture/research-web/04-api.md#资产历史任务与图表偏好)、[文件](architecture/research-web/03-data-files.md#资产历史与图表偏好存储)和既有模块/数据流图，不沿用此前“无新HTTP/持久化”的旧迭代结论。批准计划、有限预检与未完成验收见[Wind计划](plans/2026-10-22-wind-asset-workspace.md)。

全市场概览新增 Host 内无会话 `MarketService`：市场页面 → 固定参数刷新入口 → DataHub 目录中的公开行情适配 → 覆盖核验与用户有界缓存 → GET 筛选／导出。它不经过会话物化或研究循环，DSH仍为唯一研究引擎；新数据流见[市场概览图](../outputs/research-web-architecture/13-market-overview.html)，界面和接口分别见[前端](research-web-ui.md#全市场概览)与[API](architecture/research-web/04-api.md#全市场概览接口)。

该适配的报价访客路径、官网沪深北范围及待上市处理属于现有固定来源合同，见[全市场数据](research-web-datahub.md#无会话全市场数据)。真实验收使用隔离账号的正式 AccountStore／Gateway／RuntimePool 启动候选 Web 与固定 DSH，再经 `/auth` 页面读取上游；浏览器假数据回归不替代这层证明。

资产观察 v2 部署 profile 只为既有显式联合升级器增加固定的旧版 `9bc12355`／PR175 产品 `93d62be6` 身份，复用原 v4 主实例与网关事务、不可变控制器、锁及冻结恢复包；旧 v1 与模型 profile 保留。没有新增部署节点、研究引擎、HTTP 或持久化格式，现有部署与数据流图仍准确；资产／DataHub 空闲与全索引保全适用于两种资产 profile，详细固定合同见[部署说明](research-web-gateway-upgrade.md#资产观察固定版本联合部署)。

资产摘要与主题迭代仍沿浏览器 AssetWorkspace → Host → DataHub Broker → Provider／会话快照链路：估值与八区来源表只投影当前载入行和既有元数据；原生折叠状态由当前资产身份管理。透明图表及主题同步继续由既有 ECharts／Chart.js 实例负责，不增加服务、数据库、Provider、HTTP字段或第二研究引擎，现有部署与数据流图拓扑仍准确。缺失口径不派生，Wind 未核验股本不用于市值；详细契约见[资产页面](research-web-ui.md#资产观察工作台)与[DataHub](research-web-datahub.md)。常驻应用需产品版本冻结后独立正式 profile，不由静态改动或原封闭部署 profile 自动覆盖。

显式资产部署对 CI 大日志采用120秒有界读取，原API命令30秒与完整资格检查保留；证据读取器由操作员固定完整SHA256并进入同一恢复包，无新增节点、引擎或自动兼容范围，详见[部署合同](research-web-gateway-upgrade.md)。

资产观察的显式联合部署沿既有 v4 主实例/网关事务，以封闭 profile 固定 c688 旧版与 PR171 产品；原不可变控制器、DSH、节点及恢复拓扑不变。部署空闲证明同时覆盖未完成的资产观察/DataHub 查询，部署合同见[固定版本部署](research-web-gateway-upgrade.md#资产观察固定版本联合部署)。

资产观察沿用 Host 内的 AssetWorkspace → DataHub Broker → 会话快照链路，A 股指标区迁入原 AlphaFoundry 连续工作区：基本行情、五图终端、估算筹码、资金流及五张基本面卡片。浏览器内 `asset-indicators.mjs` 确定性计算，`asset-projection.mjs` 保留真实字段和缺口；ECharts 5.5.0 / Chart.js 4.4.7 以已批准的固定本地资源随包交付。请求只增加分区来源、日期与 valuation 区块，HTTP路径、单区块刷新和会话快照边界保持；不迁 Agent 委员会、数据库或协调器，DSH仍为唯一研究执行引擎。合同见[资产页面](research-web-ui.md#资产观察工作台)与[API](architecture/research-web/04-api.md#资产观察区块刷新)。

联合升级分别锁定源码权威仓库及两个发布角色的 Git common directory/inode；发布主实例可为同 GitHub 仓库的独立 clone，不能强制搬入开发 worktree。构建源码继续来自受审 source，恢复逐角色复验身份。

显式联合升级的导航范围固定为 PR168 的五个 UI blob；其他产品仍绑定原模型服务商基线，旧控制器、v4 journal、研究执行与会话/模型数据根不变。此范围由已审操作员源码和冻结恢复包共同校验，不新增部署机制。

模型服务商后端的显式联合部署通过 `resident/model_provider_upgrade.py` 同步主实例 wheel、源码和网关绑定；version 4 全局意图先于出生占槽及主实例 journal，保留原控制器和自动兼容清单。活动/未知等待，失败恢复两端且保全原数据；详见[联合升级合同](research-web-gateway-upgrade.md#模型服务商联合升级)。

冻结恢复任务显式保留系统与既有Homebrew工具PATH，部署前验证Git LFS可用，保持原Git钩子和身份检查；不安装依赖或改变研究服务拓扑。

保留主实例版本的显式静态网关更新使用 version 3 `static-gateway`，同时核对主实例/旧网关到目标的受限差异与冻结工具身份；不改变原研究进程、自动兼容清单或恢复保护。旧主实例菜单适配保持唯一控制器，详见[网关升级](research-web-gateway-upgrade.md)。

账号资料与管理复用现有网关：菜单顶部身份进入应用内 `#/account`，管理员用户管理归入设置；登录入口保持独立。只改变浏览器路由和共用账号控制器，不新增执行服务、权限接口、数据格式或依赖。

模型服务在既有 Host/Store/凭据桥内增加命名 profile 索引与独立账号映射；旧逻辑 ref、Keychain 命名空间和 DSH 协议保持。会话与 research_task 日程保存 profile 身份，换连接不静默改旧绑定；细则见[模型服务](research-web-ui.md#模型服务商与连接)。

网关界面更新允许已审工具版本与已验收产品版本分离，复用原空池/排空/保全事务。新version 2恢复包从工具Git对象冻结，离线核对两段受限差异和实际primary；旧恢复合同、主研究进程与自动兼容白名单不变，详见[网关升级](research-web-gateway-upgrade.md)。

研究工具向供应商发送根级object参数；code/report_plan互斥仍在执行边界强制。固定DSH的SDK转换成功不等于供应商接受schema，离线检查同时经过实际pi-ai上下文和HTTP请求序列化，不调用真实模型。

系统报告进一步绑定自由分析：数值事实与公式用受控引用插入，Host从实际正文独立重建plan、声明、中文呈现及附件。新网页研究在原receipt冻结bound-analysis-v1，不能回退手工payload；旧receipt/旧报告不迁移。重复英文底稿保存于同版本审计JSON，正文与HTML/Word/PDF实际内容另核对，DSH及原research_quality判据不变。

附接网关的显式安全升级复用既有管理平面：空私有池出生栅栏、优雅 HTTP 排空和持久全请求冻结共同保护切换。主实例持续运行；恢复只处理网关源码和匹配绑定，不写业务数据，不扩大自动兼容白名单。合同见[网关升级](research-web-gateway-upgrade.md)。

Host 复用已有来源读取和证据快照，从完整网页字节提取闭合年度 GDP 布局，并保存全文 SHA、原文 span、期间和初步/最终版本。它只扩展确定性证据，不新增模型循环；不支持的布局、日期冲突和未绑定版本继续保留未核验。

允许网页取证的研究从空索引起统一使用原 research_run_script(report_plan)；后取得数值不切回手写 payload。系统从原始观测执行有界 calculations 配方，生成声明、父来源及同节笔记；Host 从实际输入重建观测并独立重算，原 research_quality 判据不变。自由分析与跨版本可比性不因此通过。仅上传的一般研究和旧 SDK 调用保持兼容，无第二执行循环。

数字与链接修复不新增执行循环：research_arithmetic 只复算有限字面算式，不能替代来源核验；report_delivery 由 Host 将当前规范内容哈希、检查回执和不可变归档绑定。UI 禁用不匹配别名并展示该检查版本，原生历史不改写。

三组FinGPT对照是默认关闭的本机验收控制器，源码快照、Host、凭据namespace及研究数据均隔离；仅测试侧适配模型接入和预算，不合并或部署原Node引擎。详见[实验合同](research-web-fingpt-comparison.md)。

正文读取复用原生研究工具与私有 Host 回调：仅接受本会话登记来源 ID，固定公共 DNS 地址并验证 TLS，有限读取进程在取消或总时限到达时回收。它不执行研究计划；DSH 仍是唯一研究引擎。Host 对规范报告实际字节建立版本与检查结果的精确关联，不能把另一版本的 passed 沿用给当前或历史报告。

AI资讯采用固定原版AIHOT API与worker、独立PostgreSQL和Host私有桥；默认关闭采集、推理和付费源，从自主库重新起刊。隔离验收不导入线上历史，不更新常驻内容；DSH继续是唯一研究执行引擎，Hot宏观及研究证据保留，重叠AI信源在未来真实闭环验收后的显式切换事务中交接。详见[自主资讯合同](research-web-ai-news.md)。

可选私网多用户模式由独立认证网关和 SQLite 账号库组成，管理员邀请用户通过固定 Tailscale HTTPS origin 登录。网关按已认证 UUID 惰性启动独立 Web/DSH pair，各自持有数据根、状态、端口、内部密钥及凭据命名空间；DSH 仍是唯一研究引擎。首版仅 macOS Native，默认最多两个驻留实例且不自动驱逐；同 UID 的受信后端不是 OS 租户安全边界。账号与部署合同见[安装指南](research-web-installation.md#私网邀请制多用户macos-native)及[安全边界](architecture/research-web/05-security-validation.md#私网邀请制账号与执行边界)。

FinGPT 三策略复用唯一 DSH loop、原生历史及现有模型凭据。Host 仅冻结每轮要求、检查实际证据与文件并保存质量回执；补查沿当前原生回合，报告版本保留在会话 outputs，不增加研究引擎或正文库。

Host元数据专项升级通过显式 `resident upgrade-host-metadata` 入口执行；自动兼容清单与固定登录控制器artifact保持。专项只接受预期旧版02c086b16、PR122四个已审Host Git blob及同一受管Git源中的精确最新master。控制源必须干净且通过merged PR/独立评审/三CI实际tree核验；未知模块、依赖、Store或Host内容变化仍拒绝。既有bridge完成空闲栅栏、lifecycle lease、journal-before-stop、健康和回滚；成功后才记录baseline审核并刷新安装基线，不搬迁数据或凭据。

macOS 可选 resident 管理平面在用户登录后监督既有 Native Web/DSH，不增加研究引擎。
控制器使用固定 artifact、GitHub exact-tree 验证、同根 wheel 切换和原生命周期 lease；
研究准入共享锁先于生命周期锁，事务 journal 保证恢复优先。依赖/持久化/未知路径不自动升级。
配置与操作见[安装指南](research-web-installation.md#macos-登录后常驻与自动部署)。


本页只维护系统级边界。Research Web 的模块、协议、数据文件、安全和接口细节统一从 [Research Web 当前架构](architecture/research-web/README.md) 进入；旧平台的完整历史说明已归档。

## 当前产品边界

Mac mini 的 Docker 基座使用管理员 `rwb-docker`，dev/stage/prod 各自有身份账本、
数据/凭据/日志/cache卷和网络。dev挂载worktree，stage/prod固定不可变image ID；
唯一研究引擎与容器内 Web/DSH 回环不变。独立限额 BuildKit 和瞬时管理容器属于管理员平面，
业务与开发容器无 Docker socket。旧 Native/Docker 单实例管理合同保留，不能混用数据和账本。
资源、最短命令及 G2-G6 缺口见 [Docker 手册](research-web-docker.md)。

macOS 已存在的目标产品根可复用标准 OS 用户根中完整且已认证的不同根 Native 私有 pair。
共享 reader 的观察在真实目标 lifecycle lease 内保留目录/记录 FD 并复查，scope 退出失效；
未知与同根 writer 保留拒绝。部署节点、研究引擎、认证交换与持久 schema 不因此改变。

Docker 首装的无启动接受与首次启动分别使用同一现有生命周期入口内的 RAM 证明：前者只确认产品根缺失，后者必须实际私有 mkdir 并 pin 父目录/根 FD。证明不持久化或跨调用转移；已有根、已知容器、Native 记录或未知变化不获得 fresh 权限，部署节点与认证实现不变。

Research Workbench 当前交付的是本地优先的 Research Web，Native 与 Docker 只是同一产品的两种互斥部署：

```text
浏览器原生 UI
    ↓ 同源 HTTP / SSE
Research Web FastAPI Host（8088）
    ├─ 会话、文件、能力、DataHub、框架、集成与运维投影
    ├─ 按需签名桥 → 可选 Hot Node / PostgreSQL（原文、事件、唯一队列）
    └─ 私有 RPC / WebSocket
         ↓
项目专属 DSH Runtime（3081）
    └─ 唯一研究执行循环、历史、Skill、Tool 与子 Agent
```

- 入口：`app.research_web.main:app`。
- DSH 是唯一研究引擎；Research Web 不创建第二套 Agent 编排、聊天正文库或研究事实库。
- Native 以两个宿主进程运行 Web 与 DSH；Docker 以一个非 root 容器运行两者，仅向宿主回环发布 Web 8088，DSH 3081 留在容器内。`rwb runtime` 先按私有模式记录选择，再由 `rwb web` 按进程或容器归属管理；同一数据目录只允许顺序使用。
- Host 与 Runtime 保持回环访问边界；两种模式都不接管未知进程、容器或端口。
- macOS 启动链用私有 `install/endpoints.json` 记录健康后接受的实际回环端口。
  Native/Docker/最终模式选择共用 `run/lifecycle.lock`；元数据写锁在生命周期锁内短时获取。
  Docker 内部端口固定，只有宿主 Web 端口参与分配；可信控制 origin 的成对变更保留原 token。
- Docker 安装摘要绑定不可变 image ID、依赖锁、DSH/CJPY 与 Compose；公开启动和 Doctor 必须验证该已接受构建。构建候选使用独立 tag，启动等待真实健康后才发布选择；失败只回滚本次创建且再次确认归属的容器。
- Docker `/state` 使用私有 tmpfs，`/state/runtime` 在每次启动/重启由原认证链重建；日志单独持久绑定到 `/state/logs`，凭据仍为 `/run/rwb-secrets/private`。旧宿主状态保留，不迁移或自动清理；共享数据与 Native 路径不变。
- 基础研究不要求 PostgreSQL；启用 Hot 时，独立 PostgreSQL schema 承载原文、事件、预算和唯一持久队列。Host 桥是惰性、有界的，Hot 故障不接管基础设置或研究启动。pgvector、Tauri、桌面 sidecar 和旧 `app/api` 生命周期不进入本次 Web 交付。
- 当前阶段为 Web-only；只有修改桌面专属路径或用户重新开启桌面工作时，才应用桌面原生 CI 和安装级烟测。

## 主要子系统

ETF工程模拟由Host内 `portfolio_decisions/` 完成确定性信号、组合裁决和事务账本，真实准入保持BLOCKED。
合同见[数据与文件](architecture/research-web/03-data-files.md#etf-工程模拟与真实准入边界)。


[产品总图与分层图册](../outputs/research-web-architecture/index.html)先展示使用者、Web / DSH 及外部系统边界；各模块卡片继续连接说明、API、源码和测试。

| 子系统 | 源码 | 职责 | 权威文档 |
| --- | --- | --- | --- |
| Web Host 与协议 | `app/research_web/*.py` | API、SSE、会话投影、文件和安全边界 | [系统与运行时](architecture/research-web/README.md) |
| 双运行时入口 | `research_workbench_entrypoint/`、`runtimes/research_web.json`、`scripts/setup_web.py` | stdlib 模式选择、统一依赖合同和两条安装链 | [安装指南](research-web-installation.md) |
| Docker 部署 | `Dockerfile`、`compose.yaml`、`docker/` | 固定镜像、单容器监督、健康和隔离挂载 | [部署与职责](architecture/research-web/01-system.md) |
| 原生 UI | `app/research_web/ui/` | 产品壳、研究、能力、设置和运维页面 | [UI 合同](research-web-ui.md) |
| DataHub | `app/research_web/datahub/`、`integrations/` | 静态目录、Provider、动态选源、探测和会话快照 | [DataHub](research-web-datahub.md) |
| 研究框架 | `app/research_web/frameworks/` | Gold／Dollar 专用定义、采集、快照、评分与 Bot 绑定 | [研究框架](architecture/research-web/08-research-frameworks.md) |
| 能力与方法 | `app/research_web/capabilities/`、`skills/` | Skill、Method、Tool、Workflow 的版本与发现 | [能力管理](architecture/research-web/07-capabilities.md) |
| MCP 与自动化 | `mcp_registry/`、`mcp_runtime/`、`automation/` | 目录、受控安装/调用和定时执行 | [Research Web 架构](architecture/research-web/README.md) |
| 报告 Workflow | `report_workflows/` | 模板、底稿、运行、Excel 刷新和独立交付 | [文件与交付](architecture/research-web/03-data-files.md) |

## 数据与信任边界

- DSH 原生日志持有研究正文和执行事件；产品索引只保存归属、状态、版本、文件和审计指针。
- 用户上传、DataHub 快照、能力资源和产物使用产品数据根内的受控相对路径；普通 API 不接受任意本机路径。
- Native 密钥只进入产品设置和宿主凭据库；Docker 使用独立私有容器凭据目录，不自动跨模式迁移。迁移、日志、快照和浏览器响应均不得回填秘密。
- DataHub 的登记、配置、授权、探测、适配和当前可调用是不同事实；目录存在不等于真实连接已验证。
- 框架快照绑定方法版本和 revision；旧会话不得混用新快照。

## 兼容平台

仓库仍保留 `app/api/`、`app/web/`、`core/`、`services/`、`data_layer/`、`storage/`、`signal_lab/` 等旧模块化单体代码，用于历史兼容、桌面维护和既有数据流程。它们是实际代码，但不是当前 Research Web 的启动链或新增能力默认依赖。

兼容平台的文件级历史说明位于 [归档](archive/README.md)；仍需维护的模块合同位于 `docs/modules/`、`DATA_STORAGE.md` 和各专项文档。任何把兼容代码重新接入当前产品的工作都必须先更新本边界和 Research Web 架构清单。

## 文档与验证

- 双运行时 Python 质量整理只涉及现有文件的格式、导入顺序、显式默认值与内部类型说明。
  进程、目录、认证、控制事务和回滚的原有边界不因此改变；类型检查债务与实际生命周期证据分开记录。
- [Development Map](DEVELOPMENT_MAP.md) 映射源码区域、权威文档和测试。
- [文档门禁](research-web-documentation.md) 校验文档分类、权威唯一性、链接、退役命令、生成索引和 Research Web 架构清单。
- `.ai/reports/` 保存每次任务的真实命令、结果和架构影响；`CHANGELOG.md` 只保留用户可见变化。

2026-10-23 资产历史来源修复：HistoryJobRequest/source、HistoryJobs冻结来源配置映射及真实输入授权，recent/none经现Broker等价候选降级；Wind纯参数校验前移候选准入。asset_history.normalize_raw_rows核验CNY/share/amount声明与证券/日期后生成asset-history-raw-2；旧版与Tinysoft固定复权门不变。UI历史来源选择、初次auto/none及冻结重试沿既有Host/DataHub/快照图，无新引擎、数据库、依赖或HTTP端点。离线HTTP/执行器/快照与JS证据分别保留；真实供应商、认证浏览器及同候选Mac安装CI另验。

2026-10-23 CJPY字段字典元数据补齐仍沿原单Future/快照链，仅为已证明股票日线成交量提供share和金额原生元声明，OHLC/CNY仍未知。证据版本/hash随新Provider Result保留，旧快照、Host/DSH、规范仓bridge和部署拓扑不变，不增加请求或服务节点。

2026-10-23 规范raw单位策略落在datahub/contracts.py的typed required_semantics与broker候选准入，HistoryJobs冻结到查询/任务/块缓存/canonical；默认null沿旧合同。当前CJPY缺OHLC单位而在该策略下跳过，通用native不变。providers_cjpy逐行身份限定局部vol证据，research_snapshot_store保留静态field_dictionary_evidence及其冻结/恢复、拒绝native满足新规范合同；无新引擎、HTTP、依赖或SQLschema，原结构图仍准确。

2026-10-23 资产v6封闭部署配置绑定常驻c1a260fa与已合并PR197产品eac68068；仅此配置使用固定ZIP日志读取器，旧恢复合同和严格全账号保全不变。详见[部署合同](research-web-gateway-upgrade.md#资产筹码与精炼布局固定部署v6)。

2026-10-23：资产行情数值采用A股红涨绿跌，开高低收各自对真实前收比较；涨跌额/幅按正负着色，零、无效及缺失基准保持中性。沿原主题红/绿变量，只给数值上色；历史十字线、日周月与局部报价刷新同步，计算和冻结数据不变。


2026-10-23：资产副图扩展沿现有浏览器→Host偏好→账号Store链路：封闭15类OHLCV计算与有限数值参数，无厂商公式、模型、新服务或依赖。持久化仅显式用户保存，旧偏好不物化新默认键；原系统拓扑/数据流图准确。

## 2026-10-23：发布版本研究仓

BEA 2024Q2官方档案的有限PIT绑定与新浪利润表日期字段沿用原Host→DataHub→MarketStore，复用既有available_at/ingested_at修订、原件与冻结表；只新增Provider内部解析与受信WarehouseBinding，未新增服务、HTTP、数据根或数据库schema。通用native仍是首次观测；东财SDK/游客资金流同源且单位未知，不授予跨源等价。模块与时点范围见[研究仓](research-web-market-store.md)。


2026-10-23资产副图固定v7部署：封闭apply-assets-v7 / reviewed-asset-observation-v7，PREVIOUS=c4e953c4386c615cde89ad2d014d60c6e2959303，PAYLOAD=3a62ca1a3bff0927db681322a1ff028f08cf03cd（含PR204资产及PR203财务补齐的组合产品）。沿原version4事务、维护锁、BirthFence、64MiB严格业务索引/全账号保全及恢复；额外复用现有市场inflight空闲检查。旧v1–v6、market、模型身份和controller/evidence字节保持。锁文件7c631d4f、严格reader5c3077固定，无新依赖、HTTP、schema或权限；仍须新操作员同候选独评/完整Router/三CI/Mac安装及实际部署证明。

## 2026-10-23：BaoStock盈利能力来源

BaoStock单报告期盈利能力沿Host/DataHub/Broker/既有公开worker进入现有SnapshotSeries和可选MarketStore；不增加服务、HTTP、表或引擎。该来源原生财务数据不是新浪利润表的自动替代，公布日为日期精度，历史修订和报告期间累计口径未核验。原02/04图包含这些节点和可选仓路径，无新增拓扑。

## 2026-10-23：长期研究档案与机会预警

长期研究档案新增 Host 内的 DossierService 与个人 `dossiers/metadata.sqlite3`，仅保存不可变修订、原件引用、成果关联和保全 pin；原文仍在现有会话／DataHub Snapshots。手动扫描确定性读取冻结材料，A股持续跟踪复用 Automation 且默认关闭，当前不自动采集。研究交接为 Prompt-only，只有用户发送时绑定 receipt，继续由唯一 DSH 执行并保留原报告质量门。小创候选缺少已核验 Registry 身份，保持 unsupported；54 子弹仅为估算，真实报价、凭据、付费与部署未执行。模块及资料边界由主任务更新 02／04 图，详见[档案合同](research-web-dossiers.md)、[扫描合同](research-web-dossier-scans.md)与[小创候选](research-web-seek-alpha.md)。


## WGC 月度吨数与研究时点（2026-10-23）

现有 ext_wgc/etf-holdings 与 etf-flows 只开放固定 Monthly/tonnes 四地区投影，分别保存持仓存量和吨数流量；不推导二者差分，不混入价格、美元或其他频率。完整切片与原件、字段、地区身份、月份连续性和单位绑定后才入既有可选研究仓；截断、错列、错日期、全无数值或合同不符拒绝入仓。来源 asOfDate 与参考月不当作公布日期，首次观察与历史 vintage 分开；旧合同缓存跳过，旧回执保留。WGC 聚合区域不同于单只 SPDR GLD，更不同于 A 股个股资金流；未经证明不归并，也不按包装库重复计独立上游。

AKShare 个股资金流 SDK/guest 同一上游，在执行 SDK 前统一拒绝 as_of 与正式 backtest，不以随后元数据的非 PIT 声明替代守卫。宏观、财务、资金流及 WGC 的首次观测修订可按捕获时点重现，不能据今天下载制造过去可得版本。实际验收使用隔离 Host/PG 与独立 Python 子进程重启读回、空库恢复；当前任务报告区分已执行和待执行，不启用正式库、服务、外盘或周报日程。


2026-10-24：资产v8只在原Native操作员增加固定身份，不新增服务、HTTP、数据流、权限或引擎；原version4、主实例/网关与DSH拓扑准确，旧profile与不可变控制器保留。 详见[固定部署合同](research-web-gateway-upgrade.md)。
