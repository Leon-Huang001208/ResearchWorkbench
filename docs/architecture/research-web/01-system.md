# 部署与模块职责

## 今日发现与账号后端（2026-10-23）

新增能力落在现有Host、DataHub快照、唯一DSH与Automation内；01图的本机准入/RuntimePool分组分别对应ServiceManager与账号Pool，私网网关恢复已同意计划时仍经容量门。每用户后端独立资料/模型/日程，泛用Automation关闭而窄跟踪由宿主flag允许；owner后端关闭或容量延期不保证执行，不启动全局第二worker。详细[合同](../../research-web-discovery.md)。


2026-10-23：终端Native部署沿同一个主实例／私有网关／受管操作员拓扑，仅新增固定`reviewed-market-terminal-v1`身份。原维护锁、BirthFence、完整版本4事务和恢复仍承担切换，不新建服务或运行节点；01／12图保持准确。PR201合入后才由主任务固定最终PAYLOAD，操作员候选CI与实际常驻切换分别认证，见[部署合同](../../research-web-gateway-upgrade.md#全市场终端固定部署2026-10-23)。

终端v2在原Host市场上下文增加分析和个人组合文件；公开行情来源细化为东财报价和新浪历史价格指数日线。用户仅能访问自己根下market-cache，旧core-v1研究仓仍仅固定12，terminal-v2不借旧profile声称入仓。系统部署节点和DSH保持，13图同步实际来源及文件／读取边。
管理员构建器对账只扩展原Docker构建工具节点内部的显式修复路径，继续使用当前本地Docker Desktop endpoint及原操作锁；无新Host／DSH节点或网络公开面，原部署图仍准确。

2026-10-23：市场补齐仍位于原Host MarketService、DataHub公开东财和当前用户缓存内；只增加限价状态、昨日逐股基线及最多30日真实资金留存，无新增部署节点或后台采集服务。 具体来源、缺口与缓存合同见[DataHub](../../research-web-datahub.md#无会话全市场数据)。

公开indices桥由现有ResearchService注入`MarketReader`，仅为MarketService的固定指数分区接入原ResearchWarehouse/StorageRunner。其余分区直取和用户缓存、GET零上游、唯一DSH及部署节点不变；13市场数据流增加可选个人仓库条件边，未配置不会创建数据库或后台采集。

资产v5大索引修复只调整既有Native操作员预检读取绑定：v5业务index沿64 MiB安全读取器，部署元数据仍1 MB。主实例／网关、账号根、锁、BirthFence和version4事务没有新增节点或拓扑；旧profile与固定产品不变，01部署图仍准确。此前8.67 MB索引在停机前被拒绝，不能把随后本机修复或文档补齐当作实际切换成功。

资产交互v5（2026-10-22）只新增原Native操作员的固定profile：旧51f09、产品PR185真实merge9bc4，入口apply-assets-v5。主实例／网关、维护锁、BirthFence、账号数据根和唯一DSH节点保持；没有新守护进程、容器、HTTP或部署拓扑，01部署图仍准确。旧资产／market／模型profile保留，v5最终资格及未部署状态见[操作合同](../../research-web-gateway-upgrade.md#资产交互与数据-v5-2026-10-22)。

行情缺口部署使用封闭 `reviewed-market-gaps-v1` / `apply-market-gaps`：旧版固定 `99d3ee34977c47189a5638207c109a555f52a687`，产品源码检查点固定 `9faeeca3003a912ca75799fb27b635ba1bb87a1a`。检查点为本轮产品修复的不可变祖先，最终操作员/产品组合目标仍必须最新已合并 master、独立评审和原三项 exact-tree CI（含 Mac 干净安装）合格；不把检查点冒充合并版本。复用原 version4 保全/恢复，并在原维护锁内额外核对 MarketService 的 inflight 明确为空；未知或正在采集时不切换。旧 profile、controller/evidence/网关模块字节及模型/账号权限保持，无新部署节点、HTTP或依赖，原图准确。

全市场缺口修复（2026-10-22）：股票列表增加东财官网 f292 交易状态；同身份、同日单股接口有界补取空成交额与停牌参考价。停牌、未上市单列，不计平盘；已上市股票成交额全部覆盖后才合计。沪深大盘日线资金改用已实测访客端点，使用自己的来源、日期、采集时间与返回行数，不沿用板块元数据。无新依赖、来源权限或研究会话；原 Host/MarketService/DataHub/东财拓扑不变，现有图及 API Atlas 不重画。

2026-10-22 全市场常驻部署使用封闭 `reviewed-market-overview-v1` / `apply-market`：旧版固定 `4d2e3c408663b64be9e58b03213f4ca8f1152733`，产品固定已合并 PR179 `5de7e5f2db95b8b501905af9cfdc30e8fe84db0b`。复用原 version4 事务、空闲准入、BirthFence、全部账号索引冻结和内容寻址恢复；旧 profile、控制器、证据读取器及自动兼容白名单保持。操作员候选须独立评审及原三项 CI／同候选 Mac 安装通过，再按用户授权切换并在真实认证页面验收。 该封闭部署事务本身不新增服务、HTTP、持久格式或依赖；它沿用当时已审的图与 API Atlas，不要求重画 HTML/PNG。Windows/Linux 原生与 Docker 产品层保持各自未执行状态。

2026-10-22 Host资产工作区新增账号AssetDirectory和按需load，仍部署在原FastAPI进程，不创建第二研究引擎、守护进程或数据库。目录search GET可以合并后台天软读取，结果落账号24小时缓存；普通专题区块沿原会话DataHub快照，15分钟同条件缓存，规范历史继续history-job。02模块图补目录缓存分支，04区分资产／DSH取数和会话快照，API Atlas登记两新HTTP；这些真实变化不能沿用旧纯静态或封闭部署profile的“无新接口”描述。账号、凭据namespace及唯一DSH边界保持，实际安装与部署仍须独立证据。

Host ResearchService默认挂入可选ResearchWarehouse，也保留受信market_store_bridge注入，仍由现有DataHub和唯一DSH执行。MarketStore是独立业务库接口，不默认连接现有5432或更改服务；resident空闲证明同时纳入所有SDK真实Future、DataHub未终态任务和存储线程占用。


2026-10-22 插件增加现有 Host 内版本/审批适配，现有 gateway → 每用户 Host → 唯一 DSH 的部署节点保持。共享与个人审批从真实 AccountStore 角色进入固定 HMAC 通道；Pool 双阶段冻结/重启只处理自有 DSH，未知不停止。无第二引擎或新的服务进程，详细流见[插件合同](../../research-web-plugins.md)。

2026-10-22 v4沿既有Native主实例/私网网关和version4事务，只增加固定旧5495与PR180产品`9b436613aad9136f4959c992c89dd72fc7354ed5`身份。旧v1/v2/v3、controller/evidence及严格保全保持，无新运行节点/接口/引擎/依赖，原图及Atlas准确，不改HTML/PNG。产品候选654fa6、preview2e069与真实merge同tree；产品三CI和旧v3正式恢复5495不替代v4工具最终验收/部署。

华安ETF周报新合同复用现有Native Host、附接主管理员网关、DataHub和唯一DSH；没有新增守护进程、
数据库或研究循环。`report_workflows`锁定资源/截止期，私有API适配取得同源证据，DSH写规范正文，
Host以原质量门核验并将中文presentation投影到原版式、本期图表和正式归档。普通tenant不获得该
主账号例外。09/10报告图分别展示旧版兼容与新合同；通用部署节点保持。详见[周报生产](../../research-web-etf-weekly-production.md)。

2026-10-22 v3仅为已合并Wind产品增加封闭部署身份：旧主实例/网关5495、产品a0ff3ae2，沿同一model_provider_upgrade协调原Native/网关v4事务。controller、evidence和旧v1/v2恢复保持字节及语义，无新运行节点、HTTP、产品模块或依赖；部署/模块图与Atlas不变，也不重新生成HTML/PNG。最终候选验收通过且root持锁证明全部任务/Future空闲并冻结全账号索引后，才执行本轮已授权切换；[部署合同](../../research-web-gateway-upgrade.md#资产观察固定版本联合部署)是本轮真源。

2026-10-22 Wind工作区在现有Host的AssetWorkspace旁增加`HistoryJobs`与纯历史规范模块，沿Broker串行取得日线/因子并原子发布规范快照，账号Store保存任务和副图偏好。模块及数据流图02/04已同步真实变化，API Atlas补6端点；部署仍是原浏览器/Host/DSH/网关节点，无新守护进程或数据库。Host关闭等待任务排空，resident及操作员空闲证明同时检查真实CJPY Future和持久任务。Automation调度与每用户运行根保持；详细[存储](03-data-files.md#资产历史与图表偏好存储)、[接口](04-api.md#资产历史任务与图表偏好)与[批准计划](../../plans/2026-10-22-wind-asset-workspace.md)分别维护。

Host 新增无会话 `MarketService`，由 ResearchService 初始化和关闭；市场 HTTP 只在 POST 启动有界公共行情采集，GET 读取用户缓存。它不是独立守护进程或研究引擎，不改变 Web/DSH 部署节点；新模块内数据流见[市场概览](../../../outputs/research-web-architecture/13-market-overview.html)。实际常驻升级仍须独立授权和检查新模块任务的排空，不沿用旧固定产品 profile 冒充兼容。

resident 空闲证明同步读取 `MarketService` 的有界活动见证；真实 collector、取消后的排空与 Provider 关闭期间均保持活动。缺失或无效见证、关闭失败保持未知，不能认证可安全停止；请求显示已取消不等于底层采集已经结束。

资产观察 v2 仍由原 `model_provider_upgrade` 协调既有 Native 主实例和网关；固定旧版 `9bc12355` 与产品 `93d62be6`，旧 v1／模型 profile 保留。v4 journal、不可变控制器、生产解释器、冻结恢复包和锁的职责不变，没有新增服务节点或扩大自动升级权限，现有部署图继续准确。

资产观察迁入原 AF 连续指标区仍是既有浏览器 → Host AssetWorkspace → DataHub Broker → Provider／会话快照链路。`asset-indicators.mjs`、`asset-projection.mjs` 与本地固定 ECharts 5.5.0／Chart.js 4.4.7 属于前端内部模块及安装资源，不新增服务节点、数据库、协调器或研究执行引擎；账号权限与唯一DSH不变。原部署图拓扑仍准确，具体页面见[UI合同](../../research-web-ui.md#资产观察工作台)。

资产联合操作员固定证据读取器完整SHA256，CI大日志下载上限120秒，其他命令30秒；节点、不可变controller、全请求冻结及恢复拓扑不变，复核失败仍在停机前拒绝，详见[专项部署](../../research-web-gateway-upgrade.md)。

资产观察部署只为既有联合事务增加封闭固定产品profile，复用同一主实例、网关、不可变控制器及恢复包，不新增部署节点或自动升级权限。

受审源码与既有 Native 发布角色可分别属于不同 Git common directory，但均须是同一 GitHub 仓库。联合事务逐角色固定原目录/inode，不搬迁部署节点或引入新服务。

PR168 导航随原模型服务商联合事务交付，五个 UI 文件使用独立冻结产品身份；后端仍是原受审基线。节点、端口、旧控制器与恢复职责不变，原会话及模型配置由同一保全链核对。

模型服务商联合升级为显式管理平面事务，协调既有主实例 wheel、网关源码及绑定，不新增研究引擎或服务节点。先全局冻结与空闲证明，再优雅停止；原不可变控制器和独立冻结恢复任务共同保留回退通道。

恢复LaunchAgent仅补齐自身工具环境，仍是原管理平面；主实例和DSH不重启，不增加研究节点。新内容身份不覆盖旧artifact/job。

显式v3 static-gateway仅切网关静态版本，主实例保持实际旧SHA和原进程；升级器模块必须等于冻结受审工具，后端差异拒绝，部署节点及恢复职责不变。

显式 stage-primary-ui 仅构建原 resident 的候选记录和新旧 wheel；实际部署/恢复仍由既有不可变控制器执行。网关工具自身随静态产品更新时必须与冻结恢复工具为同一 Git blob，不新增运行服务或自动兼容范围。

网关界面升级只切换已验收UI产品源码；独立审核工具构建version 2恢复artifact并使用原事务。主研究实例继续原进程，依赖、模型和会话根不变；内容寻址helper不是第二研究执行服务。

供应商参数必须为根级object；code/report_plan互斥由原执行入口继续强制，固定DSH和研究拓扑不变。SDK转换与供应商请求序列化分别离线检查，不增加模型调用或权限。

自由分析绑定、中文正文和版本审计附件复用原DSH、固定SDK、Host与会话outputs。新轮次receipt冻结绑定策略，旧记录不迁移；实际渲染核对在原Host验收内，无新增研究循环、进程或持久服务。

系统报告仍运行于原DSH工具和原Native沙箱；新增固定只读计算SDK不启动服务或循环。Host独立重建计算/来源日期/交付格式，归档与数据根保持，自动化和多用户拓扑不变。固定SDK现在为四个Python文件与一个字体。

更新器的退休等待和大保全journal读取仍在原管理平面内，不新增节点。PID未消失时延后，恢复读写预算在停机前闭合；原primary和研究执行拓扑保持。

网关更新器通过Mac内核实际可执行映像绑定受管Python；Homebrew framework的exec不增加部署节点或可停止对象，原primary及私有pair拓扑保持。

显式网关更新器属于既有 Mac 管理平面，使用 primary 的 supervisor/admission 锁，但不重启 primary。旧网关空池出生栅栏与优雅排空之后，目标通过同源全请求冻结启动；联合健康及保全通过才解冻，失败恢复匹配的网关代码与绑定。见[操作合同](../../research-web-gateway-upgrade.md)。

网页数值投影和报告 URL 规范化属于原 Host/SDK/UI 路径。Native/Docker、Automation、多用户和 DSH 执行节点均不改变；静态证据不是外部真实性或模型验收结果。

本轮只调整已有任务提示的报告生成路线：有数值业务观测时不再同时指示手写payload；一般资料保持原功能。原认证网关、用户数据根、DSH及常驻部署事务均未替换。

DSH仍是唯一研究执行端。Host额外对报告字面算式复算，并把最终下载指向本轮已检查不可变归档；不增加模型循环、后台任务或持久表。原自动化和多用户部署节点保持。

原 Native 沙箱可从当前已审 Host 包只读导入固定报告 SDK，兼容资源目录较旧的会话；不替换旧会话文件，不增加执行引擎或进程。仅给四个 SDK Python 文件和一个字体文件精确读取，原账号、模型、资料和写入边界保持。

report_plan 为原 DSH script 工具的数据参数，Host 只提供当前冻结绑定，不新增研究引擎、服务或账号存储。脚本内独立计算和报告组装仍交原 Host 评分；常驻更新须绑定精确版本并保全全部用户根及原模型配置。

有限三组实验在独立case运行精确源码快照和既有Node/DSH；隔离控制器不是常驻部署节点，不修改生产主实例或多用户网关。实验数据、过程、模型就绪及实际验收分别记录。

新增正文读取属于既有研究工具：Host 为已登记来源启动有限只读 HTTP 工作进程，取消/超时 kill 并等待退出，不持有研究执行循环。它沿原研究准入与私有回调，活动请求也阻止常驻切换；不增加依赖、账户设置或持久聊天正文库。

本轮脚本修复仅调整原报告资源、Host受限业务投影与DSH指导；既有常驻网关、账号库和用户数据根不变。部署和真实模型验收分别记录，离线通过不代表业务分析通过。

冻结研究要求时，在既有会话resources内写入可再生业务证据投影；DSH沙箱只读，原Host质量工作线程仍从实际输入重算。无新服务、数据库、端点或凭据流向。

实际业务报告新增的纯Python来源/算术/引用helper仍由原DSH沙箱调用，不增加进程、数据层或研究执行节点。Host门与常驻数据/模型保全边界保持；更新使用审过精确版本的原受控事务。

业务摘录规范化由Host原观测工作线程内的research_business_evidence.py完成，只从当前允许输入实际完整字节派生观测。它扩展原CSV/文件证据适配，不增加存储或执行循环；SDK格式helper没有观测签发权，旧会话和模型配置不迁移。

数值证据格式helper仍位于会话resources，由DSH显式调用后交给既有Host核验；不增加服务、存储或执行节点，常驻更新仍须独立受控事务。

报告来源身份由Host提供规范ID/标题与全文SHA；全量CSV派生数值在Host有界工作线程独立复算，仍走原research_check_quality及严格交付链。无新服务、数据库或模型执行循环。

网关在既有逐用户代理路径透传研究必需的 Idempotency-Key；部署节点、实例归属与认证边界不变。

管理员 release-reservation 沿原 operation.lock 退休已停止 stage 的容量预留；业务容器、卷、网络和生产生命周期不变。

独立私有pool支持显式1至4个pair，默认2；附接常驻按私有max_additional_instances计额外用户（默认1，primary另算1）。本机容量配置选择3额外、4总实例，不增加组件或部署节点；旧“两槽”部署保持默认兼容，显式配置后才提高上限。

逐用户pair在正常停止/网关重启后保留可信回调Web端口；先预留socket，未知占用失败关闭，不回收其他用户进程。部署节点及不驱逐的准入规则保持。

primary 继续配对原后端与原 UI/静态资源，原 AIHOT 阅读路径仍走原实例；新用户沿现有共享资讯入口。认证网关部署不改变原账号资讯执行与数据边界。

显式常驻绑定复用部署图中网关→Native Web 路由：唯一 primary 管理员指向仍由原监督器持有的旧 pair，新用户使用独立 pair。两个总槽中旧实例占一个；只新增网关 LaunchAgent，不增加执行引擎，原服务、数据与模型命名空间保持。绑定与 Tailscale 切换须单独部署授权；参见安装指南的保留既有常驻实例合同。

AI资讯自主化本轮在隔离实例接入原版API/worker与独立库，保持DSH研究执行及当前常驻内容。零调用和后续切换边界见[自主资讯合同](../../research-web-ai-news.md)。

## 可选私网用户网关

`rwb server serve` 独立启动回环 8089 登录网关，外层仅接受操作员指定的一个 Tailscale HTTPS origin（本地开发可用明确回环 HTTP origin）。管理员账号来自交互式 `server init`，无公开注册。每个用户首次研究请求惰性启动独立、单 worker 的 Web/DSH pair，端口、数据和内部令牌均由服务端选择；仅登录或管理账号不启动研究。

全局AI资讯是网关直接提供的独立共享能力：home为 `server_root/shared`，已登录成员阅读，status/control仅admin；未知AI路径不转入逐用户pair。tenant后端封禁全局AI路径，不构造共享资讯服务；既有单用户Host保留自身资讯桥。网关构造不创建目录、数据库或进程，见[图12](../../../outputs/research-web-architecture/12-ai-news.html)。

默认最多两个驻留实例，可选一或二；容量满返回 `runtime_capacity_exceeded`，不驱逐现有用户或停止研究。管理员“停止实例”释放容量；停用账号同时撤销登录态并停止其受管实例，重置密码只撤销登录态。浏览器断开不停止研究，网关正常退出才关闭本进程持有的 pair。进程归属不明或崩溃遗留 `owner.json` 时失败关闭，不能按端口认领或清理未知进程。此入口不接入 resident，也不迁移原个人数据。

该模式仅启用 macOS Native：固定受信工具实现、Seatbelt 研究脚本和用户私有 HOME/TMP 共同收窄访问；同 UID 的 Web/DSH 本身仍受信任，不能宣称 OS 安全租户隔离。首版禁用 Hot、MCP、自动化/日程、报告 Workflow、Office/Wind、宿主浏览器及服务器运维能力，模型连接限定官方 DeepSeek。原 Native/Docker 单用户路径保持独立。

AI资讯全文、事件和主题在既有Host/浏览器内阅读，HTML转换为惰性树。新增固定原版API与采编worker、独立PostgreSQL及持久队列，见[图12](../../../outputs/research-web-architecture/12-ai-news.html)。没有独立SSR网站；研究仍由唯一DSH执行。未配置时诚实503，且没有外站内容后备。

FinGPT 三策略继续由唯一 DSH 执行。Host 质量工具复用现有私有桥、receipt 和会话输出，Native/Docker 部署节点与端口不增加；不合入候选分支的独立 Node 问答引擎。

Host元数据专项升级通过显式 `resident upgrade-host-metadata` 入口执行；自动兼容清单与固定登录控制器artifact保持。专项只接受预期旧版02c086b16、PR122四个已审Host Git blob及同一受管Git源中的精确最新master。控制源必须干净且通过merged PR/独立评审/三CI实际tree核验；未知模块、依赖、Store或Host内容变化仍拒绝。既有bridge完成空闲栅栏、lifecycle lease、journal-before-stop、健康和回滚；成功后才记录baseline审核并刷新安装基线，不搬迁数据或凭据。

会话导航与逐题问答仍在原浏览器原生UI和Host之间工作。导航只保存本实例模式隔离的项目/置顶/顺序元数据，不引入执行器、正文数据库或部署节点；研究与提问终态仍来自唯一DSH。

正文搜索沿唯一 DSH 和现有 session-controller；Host 传产品/模式会话范围，原生层求可见范围交集，返回显式不完整计数。不新增正文库、执行服务或调度器。

macOS可选登录项每60秒以短时管理进程监督既有Native Web/DSH，不新增产品常驻引擎。
同一生产checkout/venv和8088/3081保留；控制器artifact固定，候选通过GitHub精确树与本机交付准入。
FileVault解锁并登录后才启动，Tailscale Serve仍由原配置提供私网入口。

Claw 执行流改造和明确长句试跑识别沿既有浏览器→Host→唯一DSH及Automation链路。候选运行与正式进程隔离；原生工具错误仅补充有限稳定码，不新增服务、端口暴露或外发配置。

迭代收尾属于现有Mac管理员控制平面：`iteration_resources`复用Docker资源退休/归档和Git安全入口，`iteration_cache`负责明确受管构建器合计20GiB的GC。不新增容器常驻服务、产品API或调度器；服务容器没有获得Docker socket，当前/上一接受镜像和运行数据仍受保护。

Native 可显式将单个 Tailscale Serve HTTPS origin 加入 Host/Origin 精确准入。
Web/DSH 仍监听原回环端口，无新增产品进程；Serve 由操作员独立配置且仅限 tailnet。
Doctor 的 web_access 是 Host 已应用配置的投影，不认证隧道或远端设备连通。
Host 的入口导航例外仅返回原静态首页，不增加运行节点、代理权限或 API 跨站访问。

Hot周期任务在原唯一worker中调用既有报告投影的短时Python子进程，固定模块/解释器、
有界stdin/输出/取消，无新常驻节点或调度器。产物原件与子执行回执属于Hot PG；Host只读
下载，同一逻辑数据库的Native/Docker切换复用回执，不重复发起研究。

外部来源适配器、模型预设和独立停止 UI 均留在既有 Web Host/DSH 边界内；
不新增进程、端口或调度器。安装包继续包含固定目录资产，秘密只进入本实例凭据库。

事件日期继续由Hot现有controller纠错事务及event_versions负责；Host核对签名回执，原文/版本/队列和研究引擎归属保持。没有新增服务、迁移或日期抽取模型。

来源状态投影在现有Hot Node中读取目录绑定与controller config列权限；前端不读取数据库或凭据。Source表单沿已有Host API与source.configure，未新增Provider、服务或调度器。

来源激活继续由现有source.configure/controller和Hot PG负责。DataHub固定目录决定endpoint/operator，CLI和Host仅传source ID、期望版本、明确catalog标志及理由；不新增来源服务、研究会话或模型调用。

Automation命名空间内Hot周期管理aliases直接委派Hot，旧Automation feature flag只控制旧Automation。该适配不访问其Store或启动其scheduler；PG/Hot worker仍独占周期事实。

管理平面显式stage镜像替换可退休身份完全匹配的停止pre-AES容器，保留其已有五卷；模型就绪账本不证明旧容器具有密钥挂载。例外仅为已授权升级，普通运行身份门和业务容器无Docker socket边界保持。Native/Docker产品节点及唯一DSH归属不变。

Hot Node现有heartbeat向同一pg-boss hot.brief队列登记周期运行；controller负责计划授权和冻结简报发布，普通worker只处理已有领取/确认。Automation提供管理适配，不在旧Store写第二套计划或周期调度。关注、计划、运行和选材在指定PG schema持久化；ResearchService/DSH仍只承担用户明确提交的正式研究。

Hot 的 Docker 镜像已包含锁定生产依赖和迁移。HotManager 在 Supervisor Web 内识别
Docker 模式，子进程沿 Web 角色归属，写日志到数据目录；不引入新队列或 Docker socket。
实际容器运行与同逻辑 PG 顺序切换仍须独立证据，不从镜像构建推定通过。

Hot/model明确启用的同项目实例在Web Runtime准备时把官方provider重试设为零；该设置
作用于本Runtime的官方模型，未配置实例保留原策略。正式执行API沿ResearchService.send及
原PG运行映射，不创建第二执行器；实际产物完成与UI动作接入仍待验。

Hot流预算插件随现有Runtime overlay装配，借既有私有Host通道连接同一PG模型账本。
当前验证为源码与离线SDK；正常Runtime零重试策略、真实研究及产品安装尚未验收。

## Hot 阶段一组件

`services/hot/` 已有独立 Node/PostgreSQL 控制与读取进程，使用私有 stdin 接收宿主解析后的
凭据，内部接口仅绑定回环并验证签名、实例、模式与代次。它不启动 ResearchService、完整 DSH 研究 Runtime 或旧
Store。`rwb hot` 已接入独立 Native 启停与受管 PG；Web 生命周期与 Docker 产品装配仍待完成。
因此下述基础 Web 部署图仍描述现有 Web/DSH；Hot 的最终部署图将在实际产品装配后同步。
Native 归档入口复用这个独立组件及 PG 工具；恢复只进入不同目标库的不存在 schema。
独立服务现已运行持久 feed scheduler 与受限 worker；它只读 DataHub 的共享公开目录，
不为采集启动 Web、DSH 或旧 Store。Web 生命周期和 Docker 产品装配仍待集成。
来源控制复用当前 Host 签名桥接；只有控制 key 可以在同一运行代次内提交条件配置与审计。
Hot 的共享事件、版本化频道和人工修正现已作为同一 PG schema 的内部业务持久层实现，
不是新的研究引擎或第二套队列。事件/评分历史按截止时间读取；人工评分升版继承保留原出处。
第三频道已验证配置与真实事件规则判断；界面已挂载。Native 模型 factory 在已有预算和受控凭据下
由同一 worker 装配最小 DSH 文本上下文；新授权/价格刷新 CLI、安装级 worker 与领域模型判断仍待验收。
正常 Hot worker 现有可选归组能力端口，parse 事务登记处理项，模型就绪才向同一
`hot.process` 队列调度。未装配时状态为 `blocked_model`，采集与读取继续，待处理项保留。
DSH 模型适配仍无研究会话/工具；事件发布和队列确认共用原 claim 事务，已知拒绝保留回执。
公开 Native bootstrap/Settings 模型激活、模型频道判断和产品界面仍待装配。
领域规则现已接入同一 Hot worker 的 heartbeat，以持久游标有界评价已存在的事件/频道，
不新建调度器或研究会话。评分与不可变依据在原 owner 事务中保存，未知/旧发布时间不增热。
三个频道由非秘密 JSON 配置；公开配置入口与产品页面仍待集成。
内部签名桥现提供有界事件/频道历史读取、频道配置和既有人工纠错，分别使用read/control权限。
读取截止时间与原文/配置/判断版本固定，分页需保留cutoff；入口不采集、不调度、不调用模型。
频道变更保存UUID条件重放审计。Web Host及浏览器页面的挂载仍待完成。
Native `rwb hot` 现已挂载事件/频道读与条件控制，复用同一签名进程身份、系统凭据机制与审计。
输入和操作回执在Python边界验证；不明结果保留UUID且非零退出。Web Host和浏览器挂载仍待完成。
Web Host已新增惰性有界Hot桥与页面入口；其lifespan不启动Hot/PG/model。条件修改显式提交，
读取/超时不会接管基础设置。部署图与Hot专项图记录Node/PG当前实现，Docker产品切换、
真实事件浏览/研究和同SHA干净安装仍须各自验收。

持久验收预算仍在现有Web/DSH部署内，通过受管AES身份和私有Python管道消费；没有新进程或自动激活。默认运行不读账本，过期控制拒绝。

原生研究计划沿用 DSH 唯一执行与日志源：研究 preset 注册已有 Todo，Web projection
读取同会话日志并向既有详情/SSE snapshot 添加计划字段，研究空间只读显示。
新增快照字段不创建调度器、正文库或持久 schema；Native/Docker 部署和生命周期不变。
固定插件无模型进程内集成不代替完整服务启动、干净安装或同平台 GitHub CI。

G2A 在现有单容器部署内增加实例专属 model_key 只读卷，credentials 卷存模型密文；
受管初始化 helper 有 128MiB 硬限额并核对 VM 准入，不改变 Web＋固定 DSH 双进程与唯一引擎。

ETF工程模拟位于现有Host `portfolio_decisions/`，有界SQLite仅保存产品根内模拟账。
无独立服务、调度器、凭据中心或券商连接；见[数据与文件](03-data-files.md#etf-工程模拟与真实准入边界)。

Claw侧栏工作区与文件预览继续由同一Web Host提供。Markdown预览仅调整为浏览器可显示的纯文本MIME，下载仍返回原文件；没有增加服务、转换进程、依赖或执行引擎。

Claw 回答过程复用现有 DSH 事件投影和 Host 的 Run 快照。会话级模型工具目录在既有 guard 的原生 pre-step 接口收窄，执行期校验继续生效；没有新增进程、端口、调度器或研究引擎。详情新增只读字段，旧能力任务继续兼容。

本轮 Claw 日程采用直接 `research_task`（schema_version=1），锁定研究描述、模型、输出要求、资料与工具白名单。用户确认创建并启用后才生效，创建不立即运行；旧 Skill/Workflow/报告任务保持兼容。修改以同一 ID、expected_version 和变更确认卡生成新定义版本，Run 保留不可变 definition_snapshot；手动试跑与 schedule 触发分别记录，不改下一次计划时间。能力与连接管理统一在能力中心，Claw 仅选择能力，Agent 日程使用独立表格。DSH 仍是唯一研究引擎，Automation 仍是唯一调度层。


模型设置的空闲保护仍由 Host 读取 DSH 原生事实；内部活动查询区分运行状态与历史执行模式，不增加进程、公开参数或凭据写者。未知模式不获得执行权限。

Claw 项目和日程草稿由现有 FastAPI Host 管理产品索引；原生提出工具沿现有私有控制通道，不增加进程、端口或调度器。用户确认保存后继续使用 Automation 与同一 DSH。

24GB Mac mini 是 Docker 主开发与常驻节点，MacBook Pro 是远程入口。
dev 挂载对应 worktree；stage/prod 按不可变 image ID 独立运行同一 Web＋DSH，
每实例隔离 data/logs/credentials/cache卷、bridge网络、端口和管理身份。
管理员 `rwb-docker` 与独立限额 BuildKit 管理生命周期；业务及开发容器无 Docker socket。
配置与命令见 [Docker 手册](../../research-web-docker.md)，legacy 单实例入口仍独立保留。

Docker 的 host 管理工具增加资源预览与精确处置职责，仍通过现有 Docker Engine CLI 执行。
此工具不增加产品服务、端口或后台调度；Web/DSH 单容器部署与 Native 顺序切换保持原拓扑。
测试辅助容器只在显式验收或卷恢复校验期间存在，任务结束验证释放。

## 资讯雷达 · 2026-10-09

Host 新增固定 Golddata 公开服务的只读资讯适配器：浏览器同源 GET → Host → `http://47.92.168.126/vibe-research/api`。没有新服务、数据库、调度器或第二研究引擎；DSH 会话与执行循环不参与读取。

Automation 原生关联检查点复用同一 Host 的 Store.save 原子索引，普通会话创建后先落盘再提交；报告已知的主关联及随后出现的 Claw 会话关联也在监控前落盘。恢复重用已证明原生任务，报告须保持自身校验链；组件、部署、唯一 DSH 与调度拓扑未变。

Native→Docker 顺序切换在公开 Native stop 成功后，沿原 stdlib bootstrap 有界等待
原 Native 端口释放，再取得既有 switch_select lease；不新增组件或停止权限。

模式切换 finalize 拒绝仅增加现有 stdlib logger 的 stderr 固定诊断字段；部署节点与控制器职责不变。
Native bridge 的既有 status 拒绝处补固定 precheck/child/postcheck 阶段，不增加 bridge 调用或部署组件。

macOS 异根 Native 私有 pair 的 bounded reader 仍位于 `web_bootstrap.py`；stdlib bridge、
Docker controller 与 Native manager 共享它。候选仅 OS 当前用户标准产品根，调用内身份观察
和 FD 绑定目标真实 lifecycle lease；不增加服务、网络探针、安装依赖或部署节点。

Python 格式、导入和内部类型整理保持本页部署职责；轻量 stdlib 模块、延迟导入及
同一 Web/DSH 启动链不变，没有新增运行时组件。

Docker stdlib controller 的外层 `_locked_guard` 拥有真实 lease 下的调用内 ExitStack；缺失根观察只支持 no-start 选择，真实 mkdir 后的根/父 FD 才支持首次分配。嵌套候选沿同一 controller/lease/home/安装身份执行；up 前分配权限失效，外层发布失败仅保留受严格复核的恢复观察，finally 清除。没有新部署节点、常驻组件或持久 authority。

Native私有认证bootstrap使用规范化的RWB_RUNTIME_STATE，并要求RESEARCH_RUNTIME_AUTH精确等于该目录内auth.json；拒绝目录别名或另一个认证文件。该绑定只保护所属Host/DSH交接，模型Keychain仍走独立provider。

Docker Doctor 的只读 volumes 类型投影与既有挂载一致：data/独立 logs/credentials 为 bind，state 为 tmpfs；schema 1 增加固定 logs 类型字段，verified 仍消费实际 inspect，不增加部署节点。

既有 `runtime_state.py` 仅增加私有拒绝证据日志，由同一 logger 输出固定原因、阶段和
ancestor/leaf；不增加部署节点、probe或公开启动字段，详见安全边界文档。
身份变化取证补充相对叶的 parent/other_ancestor/leaf 与精确所有权对变化分类，不识别Docker业务路径。

DSH staging 的遍历剪枝与最终过滤共用已发布载荷规则，保留运行子树内的 `doc/docs`
代码及资源。Workspace 按 files/negative 声明选择，第三方安装包不重复套用 workspace
声明；包顶层开发目录/文档与任意层级 Git/cache 元数据排除，不创建 yaml 专用白名单。

`docker/stage_dsh.py` 在生产依赖图选定后，保留根 `node_modules` 和私有 pnpm hoist 中既有的
普通／scope 别名，仅指向已选且位于固定源码内的包，并转为镜像内相对链接。这补齐固定 DSH
虚拟 Profile 锚点的 optional peer 搜索，不复制整个 store、不引入开发依赖，也不放宽启动模块校验。

仅固定完整 Compose build research-web argv 使用每路2MiB输出预算与既有脱敏stream；其他命令和默认run_bounded仍64KiB，不增加部署节点。

Docker dsh-builder 的 Node binary 与完整 /usr/local/include/node 来自同一固定 node-runtime
24.19.0 stage；仅 builder 设置 npm_config_nodedir=/usr/local，让原生扩展使用该版本本地 headers。
最终 runtime 不复制开发 headers 或继承该 ENV，原非 root/staged-image 边界保持。

同一 DSH builder 的 pnpm install 命令局部限制并发为 8、单请求期限为 120 秒，
不增加部署节点或 runtime 环境；参数及真实构建验收边界见[安装指南](../../research-web-installation.md)。

research-tools 保持 tools/sessions 注入；生产执行器来自已导入的 child_process.spawn，ctx 自有
data descriptor 只保留原测试替身，避免读取未声明 Cordis 服务 getter，不新增插件或部署节点。

Docker host CLI 只继承经校验的 credentials-free loopback HTTP(S)代理和有界NO_PROXY；共享
Native minimal环境不变。CLI传输、Docker Desktop Engine和build代理是不同层，源码保留env
不证明真实registry/APT/镜像构建可用，也不把宿主127代理注入镜像/Compose/provider运行环境。

Native installer auto-start 在 Web 依赖就绪后由同一 manager 持真实 lease 创建根，覆盖
DSH/build-lock/manifest 与就绪门，再借原 lease 启动。公开入口先进入精确 owned venv
（同脚本/原参数 -I），不跨进程传或持久化 fresh 证明，不新增常驻部署节点。

Native 管理器和模式切换桥在运行账本缺失时仍核验监听者，阻止未知或同数据根的活动写者
通过新端口启动。Docker 失败恢复分别处理本次新建与本次启动的既有容器。

无 Native 环境的只读桥使用同一标准库监听与进程事实。稳定 argv/启动身份只证明进程，
其他 checkout 的 Web/DSH 也可通过环境/配置共享当前数据根；没有不同数据根证据时拒绝。
Docker-only 的既有服务复用仍由 Docker controller 的 inspect/mapping/健康核验负责。
Native 首启只有本次生命周期锁内成功 mkdir 且身份仍匹配的根可作 fresh 证明，子进程启动前失效。

失败恢复另保留本次事务的内存证明：同一已验证 lease/根身份、原监听集合与 PID/argv/启动
身份必须持续匹配，本次所有子进程必须已退出；该证明只恢复元数据，不授权新分配或重试。

私有端点与内部 origin 事务已接入 macOS 安装器、Native 管理器和 Docker controller。
它们不创建常驻部署节点、不迁移控制 token 或数据。Docker 单缺失控制文件的准备使用临时
无网络/无发布端口 guest：固定接受或候选 image、仅受管 data bind，其余镜像 VOLUME 用
私有 tmpfs 覆盖，不挂载真实凭据。准备结束并确认精确临时容器退出后，host 才建立 origin
事务的原文件身份基线；正式消费者仍由既有单容器 supervisor 运行。

公开 Web 安装器的 Native 路径在运行前创建 checkout 专属 `.venv`，并把固定 DSH 构建发布到用户私有的
`runtime/dsh/<commit>/` 版本目录；运行时仍是既有 3081 DSH 与 8088 FastAPI 两个受管进程。
`rwb web doctor` 读取安装摘要与健康事实，不增加守护进程、端口或数据库。
checkout Python 环境缺失或损坏时，`rwb`/`rwb.cmd` 将顶层 `--help`、`web status` 和
`web doctor` 转入标准库后备入口；帮助输出不探测服务，诊断不管理服务或声称 DSH/Web ready。正常环境由
`service_diagnostics.py` 表达 state、进程、归属、端口、协议与 ready，
`lifecycle_lock.py` 串行化 `start/stop/restart`，`service_manager.py` 只对已证明归属的进程执行恢复。
Web ready 同时要求 DSH 已认证协议、`/api/research/runtime`、首页和 `/static/app.mjs` 通过；
浏览器仅在最终产品 ready 后打开。模型凭据与目录失败单独报告，不阻止设置页访问。
`rwb web status` 只加载轻量服务管理合同并核对进程、端口与真实健康；DSH 构建闭包、Capability
目录和 MCP Runtime 功能图仅在 Doctor、安装诊断或实际 Runtime 启动需要时加载。
`rwb web start` 在创建任何子进程前复用同一份 Doctor 安装事实；checkout 专属环境、Web 锁、
CJPY、Node 或固定 DSH 未就绪时直接返回稳定 issue code 和安装器指引，不再先启动 3081 后等待超时。
安装器与 `rwb` 使用同一 Node 选择顺序：显式参数、`RESEARCH_NODE_BINARY`、可执行的 Codex bundled
Node、最后才是 PATH；Node 构建子进程也把选中版本置于 PATH 首位。Python 与 Node 安装子进程只继承
HTTP(S) 代理，Git 仍可继承 SOCKS；过滤不修改宿主环境，也不记录代理值。安装事务只用已经通过固定
提交与闭包校验的 DSH state 原子刷新 Runtime build lock，Doctor 同时核对该锁。POSIX 锁读写逐级
使用 no-follow 目录描述符；Windows 逐级拒绝 reparse point，目录 alias 不会越出产品数据根。
干净用户目录会先从固定 DSH 模板初始化 `web` Profile，再加入 Tabbit 层；Windows Profile 的 pnpm
目录 junction 与 POSIX symlink 一样必须解析回固定源码树。Windows 服务归属使用 CIM 命令行核对、
无 shell PowerShell PID 探针和 `taskkill /T`，POSIX 继续使用进程组并把僵尸状态视为已退出。
显式 `--repair` 复用安装器自有 `.venv` 前先做 15 秒 pip 探测；不可响应时保留 `.venv.failed-*`
并原子重建。安装清单只在 checkout 的 `app.research_web.main:app` 于 300 秒内真实导入后写为
`installed`，因此依赖文件存在但 Web 源码仍不可读取时不会误报安装完成。
安装器在首次修改自有环境前先把旧成功清单原子改为 `installing`；任何失败都会保持非完成状态，
不能让 Doctor 或下一次 start 继续消费上一次事务的陈旧成功证据。

## Native 与 Docker 部署分支

统一 stdlib 入口先选择模式，再检查 Native 环境；损坏的 Native 安装不能阻断 Docker 路由。
共享进程规范保留 Native 的规范化 overlay 路径；生命周期仍由 Native 排他锁或容器 supervisor
分别拥有。容器复用完整 Web 页面就绪协议，但所有 HTTP 请求共用容器探测的总时限，不读取
Native PID 账本来推断容器进程归属。
Web 启动探测的单轮总预算为 3 秒，并受剩余启动期限裁剪；DSH 单轮保持 0.25 秒。
这一预算调整复用现有探测器，不增加部署节点或健康接口。

Host controller 为一次新建启动临时叠加 launch label，Compose up失败后也凭该标记、
候选image与既有归属合同识别精确回滚对象；不新增常驻配置或改变部署节点与挂载。

Docker `/state` 是 UID/GID 10001、0700、1 MiB 的私有 tmpfs，显式启用
`rw,nosuid,nodev,noexec`；`/state/runtime` 由未修改的严格目录 guard 正常创建。
状态认证随容器停止丢弃，每次启动/重启通过原认证链重新创建，不预写文件或 marker。
宿主 `run/docker/<installation-id>/logs` 单独 bind 到 `/state/logs`，保留导入期日志；
supervisor 的产品日志继续使用 `/data/research-web/logs`。数据和凭据绑定位置不变。
仅凭据 `private` 与产品 `logs` 两个固定缺失叶保留原两阶段首建例外，状态无映射豁免。
controller 对实际 Mounts 的类型/来源/目标/RW 和 HostConfig.Tmpfs 完整选项执行严格核验；
HostConfig 必需 `/state`、`/tmp`、`/home/rwb`，缺失、重复、替代类型或未知选项均拒绝。
Engine 可省略 Mounts 中 tmpfs 的重复条目；若提供则同样严格核验，不接受 bind/volume 遮盖。
旧 host state/runtime 保留，不迁移、不自动删除旧停止容器；其挂载合同不符时失败关闭。
Docker VM 的 tmpfs 可能进入 swap，不能据此宣称认证从不落盘；见
[Docker tmpfs 文档](https://docs.docker.com/engine/storage/tmpfs/)。

Docker controller 的接受状态来自私有安装摘要中的不可变镜像身份及当前构建合同；单容器
启动只在双服务真实健康后成功。每次候选构建拥有独立 tag，发布失败不会通过共享 tag 改变
选定镜像。此修复保留 Native/Docker 部署拓扑、DSH 唯一引擎及已有端口/挂载边界。

`research_workbench_entrypoint/bootstrap.py` 在导入 Native Click/.venv 前，以 stdlib 读取 `install/runtime.json`；无参数安装和缺省模式仍是 Native。`rwb runtime use native|docker` 只在新旧模式的服务/端口归属可验证时切换；有运行中旧模式需显式 `--stop-current`。`runtimes/research_web.json` 是 Python/Node/CJPY/固定 DSH/pnpm 的单一版本事实。`app/research_web/process_spec.py` 定义 DSH/Web 命令，Native 服务管理器和 Docker supervisor 共用；`runtime_state.py` 将认证与 build lock 等状态从产品数据分离。

Docker 路径由 `Dockerfile` 构建固定资产，以 `docker/stage_dsh.py` 派生经 `app/research_web/staged_runtime.py` 验证的运行目录，不把完整 Git/dev/test 树留在最终镜像。`compose.yaml` 以非 root、只读根文件系统、能力剥离的单容器运行 `docker/supervisor.py`，后者顺序启动 DSH 和 FastAPI，保持唯一研究引擎、双服务健康和有界停止。只有 `127.0.0.1:8088` 发布到宿主；DSH 3081 留在容器回环。`docker/healthcheck.py` 同时检查认证 DSH 与 Web。Docker 容器、镜像、挂载、端口和安装身份均由 host controller 校验；未知归属失败关闭。

产品数据仍是 `~/.research-workbench/research-web/`，Native 与 Docker 顺序共享，不并发访问。Native PID/认证状态、Docker tmpfs 状态与宿主 `run/docker/<installation-id>/logs` 持久日志以及 Docker `secrets/docker/<installation-id>/` 凭据分别管理；`app/research_web/credential_backend.py` 只在 Docker 显式配置时使用私有文件后端，Native 继续走宿主 keyring。Docker 的宿主 Office/Wind/Tabbit 等本机集成不因 Web 可启动而自动可调用；Windows Docker ACL 未验证时 `docker_credentials_acl_unverified` 关闭失败。部署图 `01-deployment` 表示拓扑，不替代真实镜像构建、运行或平台验收。

研究框架由同一 Research Web 服务内的薄注册表暴露 Gold 与 Dollar；目录、调度生命周期、快照存储和新鲜度协议共享，定义、契约、采集、评分、上下文与前端 renderer 保持领域专属。它不增加独立进程、数据库或资产详情服务，浏览器 GET 只读取已保存快照，不触发外网采集。

## 当前启动链

模型设置继续通过同一 `ResearchService` 与专属 DSH 处理，不增加模型执行器。固定 Provider 与 Runtime 标识分离，配置只改变新会话默认模型；用户显式生成测试复用原生会话及最终事件。研究工具插件只读取已声明注入的 Cordis 服务，子进程测试替身由独立函数参数提供，不进入运行时服务依赖。

`ui/index.html` → 原生 ES 模块 → 同源 FastAPI `app.research_web.main:app` → `ResearchService` → `DSHClient` → 产品专属 DSH。原生下行双 WebSocket 归一为 Web SSE 快照。模型调用、执行循环、原生日志、工具、Skill 与子 Agent 均由 DSH 完成。

独立入口不导入旧 FastAPI 生命周期、后台爬虫、知识处理或数据库迁移。轻量模块只复用项目日志设施等实用基础组件。

| 模块 | 实际源码 | 所负责的边界 |
|---|---|---|
| Web API | `app/research_web/main.py` | 同源/回环访问约束、产品路由、上传下载、SSE |
| 研究适配 | `app/research_web/service.py` | 会话归属、幂等受理、运行投影、审批与子任务状态 |
| 研究台 API | `app/research_web/workbench.py` | 页面按需查询、查询状态、快照交接与实际产物索引 |
| 运行聚合 | `app/research_web/operations.py` | 从 DSH 历史、DataHub manifest、服务状态和项目数据根生成只读指标 |
| 原生传输 | `app/research_web/client.py` | 有限 RPC 名称、关联 ID、历史分页、双 WS |
| 运行时认证文件 | `app/research_web/runtime_auth.py` | Web 客户端与服务管理器共用的有界读取、别名拒绝和打开前后身份核对 |
| 事件投影 | `app/research_web/projection.py` | 从真实日志重建消息、活动、状态、用量，不执行研究 |
| 本地索引 | `app/research_web/store.py` | 原子索引、会话目录、文件 ID、安全打开 |
| 文件交付 | `app/research_web/delivery.py` | 本任务基线、有效输出集合、缺失格式和原因 |
| DataHub | `app/research_web/datahub/` | 15 项能力/22 个来源静态目录、统一连接状态、白名单选源、Provider、单源探测、不可变资料和共享分析；MySQL 仅开放逐级 schema 与受控单表查询 |
| MCP Registry | `app/research_web/mcp_registry/` | 在功能开关内聚合官方与私有 Registry，保存原子最后成功缓存并输出只读市场/API；不安装、启用或调用 MCP |
| MCP Runtime Host | `app/research_web/mcp_runtime/` | 不可变安装、官方 SDK 连接、OAuth、schema/风险/授权快照、人工审批及激活回滚；不执行 Registry 发布 |
| Automation | `app/research_web/automation/` | 锁定版本任务、IANA 日程、独立 Claw 会话、运行恢复与研究/投递双状态；不自动升级或重试研究 |
| 连接中心 | `app/research_web/datahub/connection_center.py`、`connections.py`、`probes.py` | 本地非秘密配置、系统凭据引用、平台诊断、旧环境迁移和四维状态；不向浏览器或模型返回秘密 |
| 集成协调器 | `app/research_web/integrations/` | 聚合 DataHub、本机诊断与 Tabbit 的五阶段状态，编排启动/手动探测批次、逐来源授权和安全快照；不替代 Provider 或验证器 |
| 本机集成诊断 | `app/research_web/local_integrations/` | 标准应用位置、已知注册信息和 Python 模块的无副作用发现；用户显式触发后，在受管临时目录与可终止子进程中验证 Office/Wind，Workbook 阶段 timeout 明确不超过 180 秒总预算减 10 秒协调余量，安全投影不返回路径或秘密 |
| 受限脚本 | `app/research_web/sandbox.py` | 文件访问、环境和进程终止边界 |
| 运行时组装 | `app/research_web/launch_runtime.py`、`runtime/` | 固定源码闭包、专属目录、私有模块链接校验；常驻注册 15 个 DataHub 业务工具，由 Broker 在调用时按最新状态选源 |
| Tabbit 适配 | `app/research_web/tabbit.py`、`runtime/tabbit-adapter.mjs`、`vendor/dsh-tabbit/0.3.4/` | 固定供应包校验、会话级页面授权、实时标签 claim、一次性内存上下文与写操作审批；只复用唯一 `ctx.tabbit` 执行器 |
| 服务管理 | `app/research_web/service_manager.py` | `rwb web` 的安装前置诊断、进程归属、健康检查、跨平台私有目录校验、项目私有 DSH 源码选择、持久后台启动、停止和失败回滚 |
| 服务事实与生命周期锁 | `app/research_web/service_diagnostics.py`、`lifecycle_lock.py` | 无副作用的进程/监听/协议事实投影与受管服务操作排他；不授权未知 PID |
| 后备诊断合同 | `research_workbench_entrypoint/web_contract.py`、`web_bootstrap.py` | 共享 Node/环境/安全读取合同，以及 `.venv` 不可用时的静态帮助与只读 status/Doctor |
| 数据迁移 | `app/research_web/data_migration.py` | 会话/附件/能力/数据集/产物的哈希复制；排除凭据并支持只读归档 |
| 能力管理 | `app/research_web/capabilities/`、`app/research_web/skills/` | 草稿、声明式内置种子、受检资源、版本、原生目录投影、版本化证据协议与只读 Tool 声明 |
| 报告 Workflow | `app/research_web/report_workflows/`、`report_workflow_routes.py` | 具体报告的模板/底稿资源、不可变版本、迁移、Claw 运行、Excel 刷新、日程与独立交付 |
| 产品壳、连接中心与输入框 | `ui/shell.mjs`、`ui/connections.mjs`、`ui/composer.mjs` | 双侧栏、会话与能力检索、统一来源配置/诊断、草稿输入；不执行研究或保留密码 |
| 能力前端 | `ui/capabilities.mjs`、`ui/data-catalog.mjs`、`ui/capability-editor.mjs`、`ui/capability-controller.mjs` | Skill/Tool/Workflow/数据卡片与详情、候选表单、步骤编辑、来源矩阵与显式版本/探测操作 |
| 研究台、资产与监控前端 | `ui/workbench.mjs`、`ui/asset-workspace.mjs`、`ui/report-workflows.mjs`、`ui/operations.mjs` | 研究台按需数据入口、独立资产观察、报告 Workflow 目录/详情、显式交接和只读运行指标；不直接执行研究或删除数据 |

数据目录和能力中心 UI 已接入当前源码；上表指源码职责，不表示登记的 22 个来源都已适配、配置或完成真实连接验收。当前东方财富基金与财联社可直接调用；MySQL 与天软仅在本机配置、依赖和权限满足条件时进入各自能力路由。

三十个内置 Skill 和四个 Workflow 继续进入同一能力目录。五个专用研究 Skill 的共享证据协议在种子构建时复制为版本资源，不是独立可调用能力；`framework-research` 只服务用户显式触发的框架深度验证，并受只读 Runtime 预设约束。六个 CPU 有界资讯/事件 Skill 通过相同版本机制封存计算脚本、严格输入输出 schema、运行时 provider/mapping/version/单位/日期/复权契约、来源哈希、synthetic golden 及 `cpu_bounded_v1` 共享资源。共享契约只接受 `YYYY-MM-DD`，验证来源哈希的规范非空 key 与 SHA-256 value，并固定 daily/ETF 的 CNY 口径；显式 null、首尾空白或含 CR/LF/Unicode 行段分隔符的 key 被拒绝，字段缺失时结果明确降级。它们在真实 Wind/Excel 对照未执行时可在能力中心发现但保持 disabled，不进入原生 provider candidates；catalog 只从严格 macOS Wind/Excel evidence artifact 路径派生 receipt，分别重算当前版本 golden 与 comparison run actual 摘要，再以数值容差和非数值严格一致做业务 JSON 比较，并在启用或回滚时复核文件未变。已知初版升级先撤下投影并禁用，异常失败关闭。六 CLI 在 POSIX 从 cwd fd 逐组件 openat/no-follow，Windows 校验最终句柄；dataset refs/source hashes 各限 32 项，完整 JSON envelope 按 UTF-8 不超过 64 KiB，成功 stdout 不附换行且恰好 65,536 字节仍允许，`row_delivery` 不复制顶层 refs。Stage 3 另增加七个基金/组合/行业 CPU Skill；它们复用同一严格 schema/运行时契约、安全 loader、受检算术、预算、envelope 和 comparison receipt verifier，全部可发现但默认 disabled，真实对照缺失时不能进入原生投影。基金穿透对完整输入子图 cycle fail-closed，行业计算器只吃预聚合数据。Stage 4 再增加利率均线、股权风险溢价、风格轮动、平台突破和缠论确认分型与笔五项 CPU 研究 Skill；同样复用严格 loader、预算、不可变版本和 receipt 门禁，并在真实对照证据缺失时保持 disabled。前三项以必填 provider-aware series identity 在输入和输出中绑定 descriptor role、identity、version 和 tenor：synthetic 精确绑定 fixture，`user_input` 可携带并原样回传符合格式的真实业务 identity；角色、期限、版本或风格双序列唯一性错配均失败关闭。Wind/DataHub 未命中 field mapping 精确生产身份白名单时同样失败关闭。平台突破只处理显式有限观察列表，缠论只实现非递归严格分型与交替笔的受限子集，歧义结构失败关闭。研报校验、SVG 重绘、PDF 读取及 CPU JSON 计算均受现有 `research_run_script` 沙箱限制。静态进程入口检查只拒绝不兼容包，不授予脚本新的进程、网络、文件或依赖安装权限。

comparison receipt 当前采用 artifact v2：宿主登记器以 HMAC-SHA256 绑定当前脚本、提交 synthetic
input、独立 Wind/Excel actual input、固定宿主执行器和两侧结果；`research_run_script` sandbox 的显式
最小环境不继承登记密钥，普通 JSON 与被审计算器不能自证。Stage 3 七包提交实际 synthetic source
artifact，未核验 DataHub 映射标为 `callable=false` 并强制 contract/ref provider 一致；基金/组合只接
受单一快照和非杠杆权重，基准偏离逐条匹配顶层报告期/因子日/行业版，行业计算增加全局 128 条嵌套投影、
统一日历/成交总额约束和拥挤度至少两个滚动观测。真实宿主签名对照仍缺失，所以七项继续 disabled。
catalog 初始化时会重新审计全部已启用的 receipt-gated 能力；非 v2、HMAC/绑定证据不可复核或登记器
密钥缺失时，立即撤下原生投影并持久化 disabled。能力选择前再次执行同一门禁，避免重启后的陈旧
enabled 状态绕过证据校验；该收紧不新增服务、接口、执行器或持久节点。

comparison evidence 的 synthetic/actual input 必须同时满足相对路径不同和读取后 SHA-256 不同；仅复制
synthetic 内容到另一文件再由登记器签名仍按 `invalid_comparison_evidence` 失败关闭。缠论计算器继续
要求所有记录属于同一 `asset_id`，并在结果顶层必填回传该唯一身份；改变整组记录身份会改变结果身份，
混合身份仍返回 `data_not_equivalent`。两项均只收紧既有目录与计算器契约。

Stage 2 六包输出 schema 的 parameters、dataset refs 与 provenance 现与 Stage 3/4 采用相同失败关闭
公共契约；event-review 回归在同一计算节点先对齐共同交易日，再计算相邻共同日的配对收益。该修正
不新增 API、状态、执行器或数据源，也不改变能力默认 disabled 与 receipt 门禁。

Research Runtime 固定注册 15 个品牌无关 `datahub_*` 工具。DataHub Broker 在每次调用时读取最新的
配置、授权、探测与 Provider 状态，因此来源可用性变化无需重启 Runtime；没有可调用来源时明确失败，
显式指定来源且禁止回退时不会静默换源。AKShare、天软等同步 Provider 的单次截止时间为 15 秒，
低于桥接层 22 秒；超时保存 `failed` 数据集，并以单线程门闩把仍未返回的第三方调用隔离为
`provider_busy`。

Wind 只以五项具备封闭适配路径的 capability binding 参与 callable 计算；市场活动内部只开放
资金流、融资融券和股东数据，现有龙虎榜方法不作为大宗交易暴露。指数限定实时 `quotes`，没有等价
方法的宏观/利率与基金持仓不登记为 Wind binding。Provider 返回值必须先经过 capability/dataset
固定 schema，并逐行匹配证券身份和请求日期，未知列或越界响应不会进入会话数据集。该 DataHub
Provider 仅实例化 xlwings/Excel `WindAdapter`，故只有 WindPy 或选择 `client_api` 不计为 callable；
所有 Wind binding 的市场范围固定为 `.SH`、`.SZ`、`.BJ` A 股。`market_bars` 与 `market_snapshot`
binding 只声明股票，请求必须显式携带 `asset_type=stock`；指数和 ETF 不由六位代码推断，指数仅走 points 口径的
`index_data`。日线行情、资金流和融资融券在构造或探测 adapter 前完成起止日期类型、正序和最多
60 个日历日跨度检查，避免先执行潜在大查询再依赖返回行数门禁；返回终点不足只标记 partial。

启用研究脚本时，Host 使用当前受管启动解释器执行 readiness 探测：必须是 Python 3.12 且能导入
numpy、pandas、matplotlib、openpyxl；失败投影为稳定的 `runtime_not_ready`，不搜索或回退系统
Python；非对象 JSON 等无效探针响应同样失败关闭。`research_run_script` 在可信 Host Runtime 中共享一条 FIFO 队列，全局只运行一个脚本，
排队最多 60 秒；取消项在获准执行前移除，超时返回 `runtime_busy`。脚本仍受默认 15 秒和 60 秒
hard cap。FIFO 槽只在子进程发出 `close` 后释放；SIGKILL 后仍无法确认关闭时 Host 进入 poisoned
busy 状态，拒绝启动后续脚本。通用 child `error` 只说明执行异常，不证明进程已关闭，因此不能释放
槽或清 poison；恢复只依赖实际 close 或 Runtime 重启。
队列不会把权限或宿主状态授予子进程。

Tabbit 由 Profile 私有依赖链按 `base → web-app → dsh-tabbit → research-tabbit-adapter` 顺序加载。供应归档、许可证和文件清单在复制前逐项校验，运行时禁用 `tabbit_browser_install`，不执行下载或自动升级。浏览器自动化默认开启，Tabbit `web_fetch` 接管默认关闭；配置写入 Research Web 数据目录并在下次安全重启生效。页面正文只停留在 DSH 内存的一次性 token 中，不进入产品索引或日志。

跨平台 staging 把 npm tar 成员固定解释为 POSIX 路径，完成越界与链接检查后才映射到宿主文件系统；Windows 原子配置替换先关闭临时文件句柄，adapter overlay 路径固定使用正斜杠。这些兼容修正不增加执行器、下载器或存储节点。

Windows 读取 DSH 认证文件、DataHub 私有控制/收据/快照和会话下载时使用产品根内的规范路径回退，拒绝链接与重解析点并核对普通文件、硬链接数、大小及打开前后身份。快照仍以同目录临时目录和原子改名发布；永久删除只为产品所有树中的真实目录和普通文件恢复所有者写权限。POSIX 继续使用目录描述符、`NOFOLLOW`、私有 mode 与目录 `fsync`。

## 存储归属

- DSH 原生日志是研究正文和执行事件的持久来源。BFF 不另建聊天事实库。
- 产品 `index.json` 保存会话归属、文件标识、默认模型元数据、幂等和交付收据，不保存 API Key。
- 同一索引保存研究台查询、交接收据和安全化操作审计；它们是指向 DSH/manifest 的产品索引，不是第二套研究或指标事实库。
- `sessions/<sid>/inputs/` 是上传资料；`resources/` 是研究脚本可读的审核资源；`outputs/` 是研究可写产物。
- DataHub 私有原始响应与会话可读数据集分开。所有共享资料仍绑定目标会话及原始哈希，不提供任意路径读取接口。
- DataHub 非秘密连接配置位于 `connections/`；密码、Token 和账号池秘密只存运行 8088 的操作系统用户凭据库。API 仅返回 `secret_configured`，浏览器提交后立即清空秘密字段。
- MCP Registry 非秘密配置、ETag、游标与最后成功缓存位于数据根的 `mcp-registry/`；目录元数据是有界 Unicode plain text，API 原样投影，UI 仅在最终 HTML sink 转义。Bearer/OAuth 秘密只进入 Keyring 服务 `ResearchWorkbench.MCPRegistry`。认证 Registry 仅使用 HTTPS，无认证 HTTP 仅限精确 loopback，OAuth 端点始终使用 HTTPS。官方与私有 Registry 的同名服务器按身份三元组隔离。
- MCP 安装清单、隔离 payload、Runtime 状态和激活列表位于数据根的 `mcp-installations/` 与 `mcp-runtime/`；本地环境值和远程 OAuth token 只进入系统凭据库。DSH 只读取 Host 生成的安全工具绑定和私有控制文件，不读取安装秘密。
- Automation 与 Run 事实位于数据根的原子索引；任务锁定目标版本、内容 SHA 与 MCP 工具 schema 快照。投递渠道 JSON 只保存非敏感投影，URL、密码和签名秘密只进入 `ResearchWorkbench.Delivery`。
- 最新本机诊断安全投影原子写入 `local-integrations/local-integrations.json`，权限限制为当前用户；Excel、Word、PowerPoint 的真实验证副本位于各自 Office 容器内。Wind 复用当前 Excel 厂商会话但只持有独占空白工作簿；监督器仅清理本轮真正拥有的进程，用户已有 Excel 不进入清理集合。不持久化探测到的绝对路径、命令参数、环境变量或秘密。
- 本机显式验证结果按 TTL 和上下文指纹读取；TTL 截止时刻即失效，`0` 表示不产生可复用的可调用证据。
- macOS Native 模型 ref 仅进入按 data home 隔离的系统 Keychain；staged Docker 显式绑定独立私有凭据挂载中的加密模型记录，均经 product overlay/私有 stdio 挂载于固定 DSH CredentialProvider。Host 认证 record 独立保留；模型秘密不提供给研究脚本环境。Docker 后端不作为 Native 失败后的回退，其它 Native 平台的模型系统存储仍未实施。
- Tabbit 页面访问授权只存在于当前 Research Runtime 生命周期；实时正文 token 绑定当前会话、单次消费并在 10 分钟后过期。
- 迁移只复制研究状态和 DSH 会话索引；凭据、运行时 overlay、临时文件、旧控制令牌与日志不复制。新实例需要在设置页重新授权模型。

## 并发与部署限制

当前索引和锁按**单 Web worker**实现，不能启动多个 Uvicorn worker 共写一个数据根。`rwb web start` 默认从 `~/.research-workbench/dsh-source/` 启动经过固定提交构建的项目私有 DSH，只管理 3081/8088；`RESEARCH_DSH_SOURCE` 仅用于显式覆盖。状态文件保存 PID、命令指纹、项目路径和数据根；运行监控和停止命令都要求状态内容与实际 PID 命令签名一致，绝不把任意存活 PID 当成受管进程，也绝不操作用户原有 3080。原单用户服务仅回环；可选服务器模式另用本页账号网关，不能将原单用户入口直接暴露为多人服务或公网入口。

只验证当前 macOS 脚本隔离；不把 Web 本地成功当作 Linux/Windows/桌面支持证据。DSH 固定源码提交为 `48504f07f217f9fd45a4f6d8fca4b1ed35c2d4b0`，基于官方最新版并包含会话原生永久删除协议与持久层实现。

研究脚本是本机 CPU-only 能力，无 GPU 依赖；数值库子进程线程上限固定为 4。当前沙箱仍只在
macOS 支持，Windows 只执行不加载 Wind 的 Provider 契约测试，不能作为 Windows 沙箱或真实
Wind 会话的支持证据。

Phase 2A/2B/2C 的 Registry、Runtime 与 Automation 在远端门禁通过后默认初始化；三个保留环境开关仍可显式设为 `0` 独立关闭。数据根、系统凭据库、单 worker 和专属 DSH 边界不变。

2026-09-11 的格式基线维护仅整理本机集成包导入、常量和时间解析表达式，不改变进程、存储或部署拓扑。

仓库 `rwb` 启动器进入自身解析出的项目根后再导入 Python 入口，并在 Codex Desktop 可用时固定其 bundled Node；其他环境可通过 `RESEARCH_NODE_BINARY` 固定已审核 Node，避免调用目录遮蔽和原生模块 ABI 漂移。

2026-09-14 增加的 Method 层仍位于现有 FastAPI 能力目录与同一 DSH Runtime：Research Workbench
拥有结构化 Method 契约和策略，DSH 只读取编译后的原生 Skill 包装。没有新增服务、端口、worker、
数据库或第二研究引擎；Codex／Claude 工程框架不属于本部署拓扑。

## 2026-09-23 重启与刷新稳定性回执

服务管理器的非强制重启改为先查询已认证 DSH `session/list`，任一运行会话都会阻止重启。会话目录
仍由同一 ResearchService/DSHClient 链读取，一次 `session.list` 后以并发不超过 8 的父作用域
`subagent.list` 补齐子状态（50 个父会话的扇出同样受此上限约束）。仅同时满足“已创建、存储状态为
`running`、原生父会话空闲、全部子会话空闲”的陈旧行进入 `detail()` 状态恢复；恢复也以不超过 8 的
并发、原目录顺序执行。任一异常或调用方取消都会取消并等待所有未完成的恢复任务后再传播原异常；未创建、
原生仍运行或子会话仍运行的行不恢复。前端每个目录独立维护 pending count 与 generation，按资源 settled，且
latest request wins；仅 runtime pending 向 UI/Composer/submit 投影可见 `connecting`，仅 settled
runtime failure 投影 `offline`。现有 3081/8088、单 worker、Automation、DataHub、文件与信息架构
关系均未改变，架构图清单不变。

## 2026-09-28 Windows 服务停止回执

Windows 对已核对命令签名的受管 PID 先执行非强制 `taskkill /T`；该尝试返回非零但 PID 仍存活时，
服务管理器不再提前中止，而是进入既有等待和 `/F` 强制升级。强制终止仍失败时继续 fail closed。
该修复不改变 3081/8088、进程归属、启动顺序、服务拓扑或外部 API。

固定Runtime升级只在空闲的所属独立实例验收，生产数据不自动迁移。启动模块使用原生createRuntimeResolution解析表，逐项校验仍归属于固定源码或两项受管Profile供应包。

## 设置闭环阶段3：当前能力范围

owned overlay将所属researchRoot绑定到原有全局guard；工具和模型步骤通过同一受鉴权DataHub回环通道检查数据范围。非AI工作台查询仍使用原DataHub授权，设置页不要求模型可用。


## 单一兼容模型适配（1B实施中）

owned overlay额外挂载产品侧文本/流式LlmAdapter，Native LlmAdapter和attributionHeaders仅从固定DSH构建路径取得，研究执行仍只有既有原生loop。非秘密连接事实沿既有实例私有Host通道读取，秘密只在所属系统凭据ref通过原私有进程桥接解析。正常CLI/正式preset的无Key合成生成已验证，尚无真实新增服务/完整设置保存验收，不宣称全品牌、工具或其他平台可用。

Doctor 以安全固定字段投影平台能力；available 只描述实现，不认证真机结果。Windows 文档与 Docker ACL、非 Mac 沙箱的边界见 [支持矩阵](../../research-web-platform-support.md)，不改变 Web/DSH 两服务结构。

镜像内 DSH 发布资产保留生产依赖的运行时目录（包括 YAML dist/doc）；筛选只剔除包根开发资料和明确元数据，不新增服务或改变单容器结构。

Docker `/state` 使用 UID/GID 10001、0700 的 Linux 私有 tmpfs；临时认证、build lock 和内部日志随重启重建。持久研究数据与凭据继续独立 bind，不通过放宽身份检查处理 Desktop 属性映射。单容器、两服务、端口与产品数据拓扑保持。

独立 rwb hot 模型管理 CLI 通过同包 Node 脚本直接进入指定 PG；只有迁移身份和控制实例可在停机/过期归属下授权或终止。只读尝试使用普通角色，不启动服务/数据库/模型。11 专项图分别表达此管理路径和 Web 签名 worker 路径，不增加第二队列或研究引擎。

定价配置沿现有模型管理 CLI 的私有校验进程保存，不连接 PG 或模型；正常 worker 从实例/项目绑定的数据目录读取，仍不增加调度器或研究引擎。

Hot Native数据边界现在包含不可变简报版本/审计，Web Host经controller显式发布、reader签名分块读取。简报预览和Markdown沿同一数据库冻结证据，不创建新研究引擎；正式ResearchService/DSH交接、DOCX和完整恢复仍待完成。部署/模块图同步此边界，不用于认证未执行平台。

## 本机状态投影

Office自动验证只复用Host内既有集成批次和受管验证器，不增加进程或守护服务。实例同意、同快照汇总及真实证据/清理的条件见[集成协调器](09-integration-coordinator.md)。Doctor仅投影所属实例开关，不调用Office，也不改变安装或服务就绪。


## 研究情报统一入口 · 2026-10-12

主导航统一为“研究情报”，本地热点与事件在 `#/intel/hot`，现有外部8栏目仍在 `#/intel/*`。旧 `#/workbench/hot` 链接保留视图/事件参数后转入本地页。两类页面共用栏目导航、主题与Host；本地版本证据和Golddata外部只读数据保持身份与覆盖来源区分，外部读取不写Hot、领取任务或调用模型。Hot未启用时，外部栏目与设置继续可用。

恢复的DOCX切片通过 `GET /api/research/hot/briefs/{brief_id}/docx?version=<固定版本>` 从签名/哈希核对的冻结输入生成并保留私有产物，复用报告DOCX生成器；导出不创建会话、不调用模型、不外发。该路径尚需完整产品/恢复验收，局部测试不代表研究闭环完成。


Hot完整原件读取继续复用独立Node/PostgreSQL与Host reader通道，没有新服务、队列或研究引擎。逻辑数据库实例与材料版本绑定在冻结清单中，切换运行代次不更改历史证据；真实Native/Docker切换仍待验收。


研究准备源码链为Hot PG运行映射→Host ResearchService原生会话→DataHub会话原件快照。Hot worker仍不写旧Store，不启动第二研究引擎；既有DSH继续负责研究执行。原生会话故障注入及签名Node/PG→Host→快照组合已验证，真实DSH创建/付费研究与安装仍需实际验收。


2026-10-13续跑：Hot预算管理追加token-only停机修订；现有Host脚本准入可验证并读取当前Hot研究的冻结快照。服务、队列与研究引擎拓扑保持；研究实际调用不等于报告已完成。

## FinGPT 研究融合 · 2026-10-13

FinGPT 深入研究沿用 ResearchService→固定 DSH 执行链。Web 投影原生 todo/write，保存创建时锁定的 research_depth/source_scope；证据、笔记与报告使用会话资源和原 DeliveryManager，不增加研究执行器。HTML/DOCX/PDF 共用底稿，PDF 使用项目锁定 ReportLab 与随包许可字体。

## 历史子会话模式兼容 · 2026-10-13

历史读取与执行能力分开：列表及父详情复用原生已认证活动目录，旧子会话模式无法恢复不会阻断全部父会话。仍只有DSH持有历史和执行状态。

AES 现有记录的全树认证只收紧同一凭据边界，不增加部署节点、写者、卷或迁移步骤。

## 框架嵌入核心闭环 · 2026-10-14

嵌入核心看板仍位于原 Browser→同源 Host→唯一 DSH 节点内；静态资源是 Host 的仓库资产，不新增服务器、进程、外部数据服务或部署模式。Gold／Dollar 原生采集和 Bot 保留，其他九项仅导入快照。

模型服务在原Host设置路由内管理多个命名连接，Store只保存公开profile身份，原凭据桥将两个固定DSH ref路由到独立物理账号。唯一DSH引擎、Native/Docker拓扑及原用户隔离不变；具体身份和失败关闭合同见02/04/05章。

2026-10-23 资产v6封闭部署配置绑定常驻c1a260fa与已合并PR197产品eac68068；仅此配置使用固定ZIP日志读取器，旧恢复合同和严格全账号保全不变。详见[部署合同](../../research-web-gateway-upgrade.md#资产筹码与精炼布局固定部署v6)。

## 2026-10-23：长期研究档案与机会预警

档案服务及 dossier_scan 位于原 Host／Automation 内，个人 SQLite 与 pin 跟随已有用户 Store.root，保全扩展不新增网关、容器、运行节点或 PostgreSQL。Native／Docker 单一写入与 RuntimePool 账户隔离保持；维护准入、源会话永久删除和元数据备份／恢复均核对档案引用。01／12 图仍描述部署拓扑，新增模块依赖归入 02 图；实际部署、真实凭据与他平台验收另留证，详见[档案保全](../../research-web-dossiers.md#备份恢复与部署边界)。


2026-10-23：固定v7只绑定当前主实例/网关共同c4e前版和组合产品3a62；原部署节点、唯一DSH、私网入口与version4事务拓扑不变。

