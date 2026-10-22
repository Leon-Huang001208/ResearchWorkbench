# Research Workbench 架构总览

2026-10-22资产v5大业务索引修复仅让原verify_primary的v5分支复用既有64 MiB安全业务读取器，元数据仍为1 MB；修复8.67 MB业务index在停机前被误拒绝的绑定错误。既有Host、账号数据根、部署节点、锁、version4事务、全账号保全与恢复不变，旧profile／controller／evidence／固定产品均不修改。无新HTTP、数据流、格式或依赖，现有图准确；PR187原Constraints失败及修补后的候选验收分别留证，不以本机通过冒充CI或部署成功。

2026-10-22资产交互v5固定部署只在原操作员增加封闭`reviewed-asset-observation-v5`／`apply-assets-v5`身份：PREVIOUS固定当前常驻`51f09fa783694aae5234905933948394ca167dcc`，PAYLOAD固定PR185真实merge `9bc4e4cab91130647a5bc0dfa519e97f4773416a`。沿原version4事务、维护锁、BirthFence、全账号索引保全及内容寻址恢复；旧资产v1–v4、两个market profile和模型恢复保持。没有新增节点、HTTP、持久格式或数据流，现有图源准确，不重画图；阅读源码链接指向已审产品，v5操作员最终候选仍需独立评审、原三CI／同候选Mac安装及实际部署证据。

行情缺口部署使用封闭 `reviewed-market-gaps-v1` / `apply-market-gaps`：旧版固定 `99d3ee34977c47189a5638207c109a555f52a687`，产品源码检查点固定 `9faeeca3003a912ca75799fb27b635ba1bb87a1a`。检查点为本轮产品修复的不可变祖先，最终操作员/产品组合目标仍必须最新已合并 master、独立评审和原三项 exact-tree CI（含 Mac 干净安装）合格；不把检查点冒充合并版本。复用原 version4 保全/恢复，并在原维护锁内额外核对 MarketService 的 inflight 明确为空；未知或正在采集时不切换。旧 profile、controller/evidence/网关模块字节及模型/账号权限保持，无新部署节点、HTTP或依赖，原图准确。

全市场缺口修复（2026-10-22）：股票列表增加东财官网 f292 交易状态；同身份、同日单股接口有界补取空成交额与停牌参考价。停牌、未上市单列，不计平盘；已上市股票成交额全部覆盖后才合计。沪深大盘日线资金改用已实测访客端点，使用自己的来源、日期、采集时间与返回行数，不沿用板块元数据。无新依赖、来源权限或研究会话；原 Host/MarketService/DataHub/东财拓扑不变，现有图及 API Atlas 不重画。

2026-10-22 全市场常驻部署使用封闭 `reviewed-market-overview-v1` / `apply-market`：旧版固定 `4d2e3c408663b64be9e58b03213f4ca8f1152733`，产品固定已合并 PR179 `5de7e5f2db95b8b501905af9cfdc30e8fe84db0b`。复用原 version4 事务、空闲准入、BirthFence、全部账号索引冻结和内容寻址恢复；旧 profile、控制器、证据读取器及自动兼容白名单保持。操作员候选须独立评审及原三项 CI／同候选 Mac 安装通过，再按用户授权切换并在真实认证页面验收。 该封闭部署事务本身不新增服务、HTTP、持久格式或依赖；它沿用当时已审的图与 API Atlas，不要求重画 HTML/PNG。Windows/Linux 原生与 Docker 产品层保持各自未执行状态。

2026-10-22 资产交互与数据迭代增加两条现有 Host 内的数据路径：单搜索框 → 账号 `AssetDirectory` → 显式授权的 DataHub 天软目录读取 → 24小时账号缓存；专题页 → `AssetWorkspace.load_block` → Broker → 数据集感知的 Provider → 原会话不可变快照。目录读取不创建研究会话或启动模型；新证券的概览与近期前复权历史仍沿原观察／历史任务链路。DSH继续是唯一研究引擎，没有新服务、数据库、依赖或部署节点。新增HTTP与缓存分支分别见[接口](architecture/research-web/04-api.md#资产目录搜索与区块按需加载)和[文件](architecture/research-web/03-data-files.md#资产目录与按需区块缓存)，不沿用此前纯静态迭代的“无新HTTP／持久化”结论。

天软结构化资产适配使用固定表字段和预定义因子，提供估值、财务、股东明细／汇总、行业分类、两融及公告事件；财务按报告期／公布日读取，不套用行情60天区间，缺字段、单位和币种不补造。日线蜡烛实体与所选日期／视区独立保持，专题内容局部更新；真实来源预检、完整浏览器链路、同候选Mac安装CI与常驻切换分别取证。宏观、ETF和指数不因本次A股接入而获得支持声明，详见[DataHub合同](research-web-datahub.md#资产目录与结构化区块)。

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
