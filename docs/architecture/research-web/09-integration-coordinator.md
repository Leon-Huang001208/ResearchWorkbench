# 统一集成协调器

2026-10-23宏观与来源修复由既有连接协调、DataHub准入和运行健康反馈管理。AK只开放四个明确宏观series；错误签名、空序列和业务拒绝封包不因HTTP成功而提升为可用来源。单股资金流SDK失败后的guest仍是同一Eastmoney上游，不能计为独立来源；真实失败保留为未完成。个人仓的配置、授权复核与原worker占用边界不因新增序列而放宽，不启动正式服务或替用户配置凭据。

2026-10-23：本轮市场限价与历史补齐只使用现有固定公开接口及用户缓存，不扩展连接管理、配置秘密或供应商授权；其他资金分类无可靠等价时不混入沪深日线。 具体来源、缺口与缓存合同见[DataHub](../../research-web-datahub.md#无会话全市场数据)。

筹码逐日换手输入由原AssetWorkspace历史任务经Broker/Provider串行取得，复用同账号授权、范围和真实Future排空。协调器不新增全局CJPY凭据、任意因子入口、数据库启用或研究触发；缺失/取消仍保留旧规范快照，不把可读行情升级为报告验收。

公开indices仓库桥在现有Host内复用ResearchWarehouse/StorageRunner；连接协调器的来源管理、探测、秘密接收和能力启停逻辑不变，不给未登记eastmoney来源伪造Broker绑定。仓库配置仍由原显式个人设置管理，未配置/停用只明确未入仓，不启动后台采集或共享服务。

全市场缺口修复（2026-10-22）：股票列表增加东财官网 f292 交易状态；同身份、同日单股接口有界补取空成交额与停牌参考价。停牌、未上市单列，不计平盘；已上市股票成交额全部覆盖后才合计。沪深大盘日线资金改用已实测访客端点，使用自己的来源、日期、采集时间与返回行数，不沿用板块元数据。无新依赖、来源权限或研究会话；原 Host/MarketService/DataHub/东财拓扑不变，现有图及 API Atlas 不重画。

华安ETF周报的私有Wind Client API适配读取既有连接配置/允许状态并经Broker准入，不由集成协调器
自动安装SDK、登录或探测真实厂商。通用Wind Provider仍保留原Excel合同；私有周报的依赖可导入、
精确指标覆盖、跨市场日历、经济日历和同源对照分别取证，不从既有callable或Office诊断推导成功。
来源配置身份变化使等价证据失效，未知输入保持数据阻断，见[周报数据合同](../../research-web-etf-weekly-data.md)。

本轮复用现有来源授权与目录：BaoStock支持沪深股票原始日线、股票目录、交易日历及明确的单季度盈利能力财务数据集，新闻仍未适配。财务不增加账号或自动探测授权；真实健康按实际列明能力记录。运行时fallback仅允许审核过的原始日线口径，qfq/hfq与财务/资金流定义不静默互换。查仓和分段补数仍逐次核验授权，真实健康与接线存在分别记录。

2026-10-22 资产目录及结构化Provider复用原账号连接namespace和天软SDK；目录在读取秘密前后及返回后复核显式来源的配置／授权指纹。结构化适配只开放固定表／字段／预定义因子，metadata不符合时拒绝，不接收任意repo或公式；不增加厂商登录、探测、凭据设置入口或自动权限授予。AssetDirectory与区块task持续进入resident活动／关闭等待，真实SDK Future未结束不释放容量。缓存及原始行／报告期／单位边界见[DataHub](../../research-web-datahub.md#资产目录与结构化区块)。

2026-10-22 天软在既有factor_macro目录内增加封闭adjustment_metadata/listing_date/adjustment_factors绑定，仍经原依赖/配置/授权/健康/适配检查；≤500日期、单沪深股票及精确定义hash不等于开放通用因子库或宏观服务。历史任务复用Broker、真实单Future容量与取消排空，账号缓存复用也重新核验配置授权；已有预检只证明两股票范围。协调器不增加厂商登录、探测、秘密入口或第二研究引擎，详见[固定复权合同](../../research-web-datahub.md#资产历史任务与固定复权)。

全市场概览通过固定公共行情端点读取，运行状态由本区实际请求、时间和覆盖元数据确认；不启动 Excel／Wind、本机探测或供应商登录，也不使用另一条 AKShare 探测的成功替代全市场采集证明。协调器及宿主权限不变，日常刷新由 MarketService 独立管理。

市场公开报价和指数分时走固定 `/webguest/api/qt/` 路径，沪深大盘日线资金独立保留来源不可用缺口；沪深北股票池采用东财当前官网范围，保留上市日期和缺报价语义。连接中断修复只改变既有固定来源的请求路径与范围，不增加凭据、备用源自动切换或宿主网络配置。新浪、腾讯等独立候选的可达性与正式接入分别记录，不能混源填补后认证东财完整性。

资产观察按原观察身份显式刷新一个区块，仍经现有 DataHub Broker 和来源准入；页面、SVG 图表、202 受理或旧快照都不提升来源的配置/依赖/授权/健康状态。Wind 财务只转换等价 `indicators` / `metrics` 名称，保留最新一期或明确单期，非等价报表/多期失败关闭。该路径不新增探测、连接、供应商登录或宿主集成操作；新闻/公告只读 Golddata 阅读与 DataHub 快照分别标明来源。

公开正文读取与报告检查继续受原生会话和能力来源范围控制；协调器不增加研究引擎或重复发送。常驻空闲判断计入尚未回收的正文读取任务，取消须到达受管请求并回收进程；报告归档与质量回执各自绑定具体版本，不以文件存在代替研究通过。

新增质量检查沿现有可信插件内部桥，仅检查当前会话已取得证据；不注册新厂商连接、不探测宿主配置、不改变集成协调与权限。

Claw日程桥接仅增加既有Automation稳定拒绝码的脱敏透传；不改变本机集成协调、探测、供应商鉴权或来源准入。4KiB错误边界、JSON/正则与重定向拒绝保持，错误正文和秘密不传播到模型。

外部来源加入连接目录，但自动探测只返回配置/适配状态，不读取秘密或调用上游。
认证 HTTP 入口显示 credential_transport_blocked；已配置不提升为厂商真实健康。
连接中心可配置四类外部凭据，实际取数仍由已有 DataHub 入口验证和审计。

DataHub Broker的未适配与当前不可用来源分别投影为`data_capability_not_integrated`/`data_capability_unavailable`，不因改写查询而提升就绪状态。当前搜索绑定缺少适配仍须显示缺口；已有原生web_search与Tabbit继续各自核验，不把另一条通道的成功移作DataHub成功。

Claw 原生工具目录存在只证明注册，实际来源配置、授权、适配和可调用状态继续由既有协调器与 DataHub 核验。回答工具卡、报告文件与执行完成不提升集成状态；参考浏览器无法连接也不自动改变模型或浏览器集成设置。

Claw 日程研究在独立 DSH 会话锁定 approved_data_sources 与 approved_tools，仍由原 DataHub/原生准入校验。资料未就绪时保留缺口，定时定义不证明金融来源可调用；试跑文件也不能把合成数据作为真实市场数据。

Hot流归属与账本借既有私有数据通道；连接探测和集成五阶段状态保持原合同。
合成SDK回执不能提升DataHub厂商的可调用状态。

Claw 技能/连接入口读取既有目录状态，不产生探测、授权或修复；项目文件聚合和日程草稿不能把配置/安装状态提升为厂商可调用。原集成五阶段投影保持不变。

macOS 异根 lifecycle reader 只认证标准 OS 用户根中的既有私有 Native pair，不读取厂商
凭据或进程环境，不新增来源探测。消费者仍须目标单写者与就绪条件；Docker/Native 服务
生命周期成功不提升 Office/Wind/Tabbit 的授权或可调用状态，五阶段投影保持原合同。

启动器内部类型与格式整理不改变来源登记、授权、探测或可调用性投影；
质量检查与集成的实际能力验收继续分开记录。

统一集成协调器聚合 DataHub 与本机能力的登记、配置/授权、探测、适配和当前可调用事实。它复用已有 Provider、本机验证器、Tabbit 和 MCP Host，不创建新的数据引擎或守护进程。

从[分层阅读入口](../../../outputs/research-web-architecture/index.html#module-integrations)进入总图、说明、API、源码和测试。

公开来源探测有界并发，本机探测串行，结果原子持久化。Native / Docker 凭据不自动迁移；Doctor 或模型生成成功不提升来源为可调用，容器可见文件也不证明宿主 Office/Wind 可用。
Hot 公开 feed 的双轮采集证据仅覆盖其四项后台适配器。共享来源目录位于 DataHub，
尚未接入 IntegrationCoordinator UI/Broker 投影；不能据此修改其他来源的可调用状态。

固定 DSH 升级只迁移原生模块解析、preset 注册及子任务活动投影。协调器继续独立判断数据和本机能力，不将模型冷重启或一次公开基金查询的成功传播为所有来源可调用。空实例新默认模型和已有配置兼容，不新增探测器、来源注册或认证中心。
模型配置页的保存、Runtime应用、凭据与真实生成结果来自既有ResearchService，不加入第二套来源注册或五阶段协调器。模型生成成功不改变任何数据来源/本机能力的授权与可调用投影；模型凭据回执未知时阻断模型请求，来源探测仍按原合同独立报告。

installer 同次 auto-start 的创建 scope 不传集成凭据、不改协调器阶段；owned venv 与
实际 root/lease 就绪后进入原启动链，product_ready 仍不证明厂商能力可调用。

Native 控制文件首建先核验既有 MCP/DataHub origin，一致后才补齐缺失记录；协调器消费者
仅在成对配置与实际端点一致后启动，畸形配置失败保留原记录。

消费者启动前还须证明研究数据根单写者；其他 checkout 的产品监听可能通过环境/配置
共享当前根，稳定进程身份不足以放行。归属未知时先拒绝，不读取厂商凭据来推断隔离。

消费者健康失败的 fresh 事务可在精确退出与持续原监听/根/lease 证明下恢复原内部 origin；
失败恢复不会重新启动协调器或读取凭据，未知时主错误保留并附加受控恢复诊断。

macOS生命周期的实际端口记录和成对控制origin重绑只影响内部回调地址；不改变协调器五阶段，
不迁移厂商凭据，不把Docker服务健康当作宿主Office/Wind/Tabbit可调用证据。

内部控制 JSON/回环 URL 的纯 parser 提取至 stdlib helper；DataHub 原 reader 保留原异常和
额外有效字段语义，不改变协调器五阶段、来源授权、探测或凭据迁移边界。

Native 使用宿主 keyring；Docker 在显式配置的私有凭据目录中保存 DataHub 秘密，协调器只读取
DataHub 的安全状态投影，仍以登记、授权、探测、适配、可调用五阶段判定结果。两模式顺序共享
产品数据，但凭据不自动迁移；Docker 容器无法仅凭可见目录证明宿主 Wind、Office、Tabbit
或系统会话可用。Windows Docker 凭据目录 ACL 未能证明时安装失败关闭，不能把来源提升为
`runtime_callable`。

2026-09-29 的启动恢复只影响受管 3081/8088 的进程与页面可访问状态，不改变协调器五阶段状态、
责任桶、来源授权、批次并发、快照或 DataHub 动态选源。Doctor 的 `product_ready` 证明 Web 壳与
Runtime 协议可访问，不证明 Wind、天软、MySQL 或其他来源当前可调用；各来源仍须按现有配置、
授权与真实探测结果单独投影。
未安装环境的顶层 `rwb --help` 不初始化协调器、不恢复快照或发起来源探测；本轮 CI 修复
不改变五阶段状态和责任归因。

一键安装为协调器提供可复现的 Web 依赖与 CJPY 0.5.2，但不把“已安装”当成探测或可调用成功。
没有 `CJ_KEY` 时天软保持待用户配置；保存后的秘密由凭据库在每次探测/查询时动态读取，协调器仍
按既有五阶段模型和责任归因记录结果。
安装器对 Windows DSH checkout 启用命令级长路径，Runtime 首次启动先初始化固定 `web` Profile；
Profile junction containment 与 PowerShell PID 探针仅保证 Windows 3081 安全启动和回收；
这些修复只保证协调器所在 8088/3081 可复现启动，不把任何来源状态提升为可调用。
服务管理器在 spawn 前校验 Doctor 安装事实；安装未就绪时协调器和启动探测都不会创建。
该前置门不把 CJPY 已安装、数据源已登记或历史探测快照误报为当前可调用。
Node 选择与 Runtime build lock 的一致性只决定 3081 是否可安全启动，不改变协调器五阶段状态、
授权或 Provider 可调用结论。
纯 `rwb web status` 的导入不创建协调器，也不加载 Capability、MCP 或 DataHub Runtime 功能图；
Doctor、start 与 8088 Host 仍在各自既有边界内加载并验证这些组件。
安装阶段的 Web import readiness 不运行 lifespan 或协调器启动探测，不读取凭据，也不把任何来源
从已安装提升为已配置、已验证或当前可调用。

## 目标

`IntegrationCoordinator` 是 Research Web Host 内的数据源与本机能力状态编排层。它不替代
DataHub Provider、本机验证器、Tabbit 或 MCP Host，也不创建新的守护进程。它负责把这些既有
边界的登记、授权、探测、适配和 Runtime 可调用事实聚合成一个可恢复、可审计的状态模型。

```text
设置页 / Runtime 状态
        ↓
IntegrationCoordinator
  ├─ DataHub 单来源 probe（公共来源最多并发 4）
  ├─ 本机发现 probe（串行）
  └─ Tabbit 保存配置 + Runtime 应用配置 + 实时诊断
        ↓
原子状态快照 + 批次进度 + 兼容接口
```

## 状态契约

`IntegrationItemStatus` 使用 `schema_version=1`，每项包含：

- `registered` 与 `implementation_state`：区分目录登记、已实现和未交付。
- `configured` 与 `authorized`：配置存在不代表已授权。
- `stages`：固定为登记、授权、探测、适配、可调用五阶段。
- `last_attempt_at`、`last_success_at`、`stale` 与安全 `error_code`。
- `capabilities`：品牌无关业务能力 ID。
- `runtime_callable` 与 `responsibility`：责任限定为 `user/system/vendor/developer`。
- `bucket`：`available/checking/user_action/system_fault/not_delivered` 五类页面汇总。

认证失败和账号权限不足归入 `user_action/user`，因为下一步是用户更换本机凭据或联系供应商开通账号；
依赖缺失、版本错误和凭据库不可用归入 `system_fault/system`；限流、供应商不可达和供应商响应异常归入
`system_fault/vendor`。页面不再把无效 Key 误显示为本机系统故障。

快照仅保存白名单字段，不保存密码、Token、Cookie、MCP 环境变量、用户文件正文或本机绝对路径。
Provider、配置和环境指纹变化时，旧的成功证据保留为历史时间，但当前探测阶段变为过期，不能继续
证明可调用。

## 探测与授权

- 服务启动先读取最后一次原子快照，再异步创建 `trigger=startup` 的全量批次。
- `trigger=manual` 的全量刷新会对全部公共来源和已经取得逐来源授权的来源真实执行探测；未授权的
  账号、终端或可能计费来源明确显示跳过，不以一次“刷新全部”绕过授权。同 scope 同时只保留一个
  活动批次。
- 无凭据公共来源默认允许自动探测；账号、终端或可能计费来源需要逐来源一次性授权。
- 授权撤销后不再自动探测该来源，旧成功证据立即过期。
- DataHub 继续拥有单来源探测语义；本机管理器继续拥有软件发现和真实 Office 验证语义。
- 协调器关闭时取消未完成任务并把批次标为取消，不静默留下“检测中”。

写操作同时要求精确同源 `Origin` 与页面显式用户动作头，用于阻止普通跨站页面驱动本机探测。
当前产品是单用户 Web-only 回环服务，没有可向普通浏览器安全发放且能抵御同用户本机进程的私有
会话凭据；因此同源 XSS 和能直接伪造 HTTP 请求的同用户本机进程属于本批明确保留的威胁边界，
不能把上述头部描述成此类攻击的认证机制。

## API

- `GET /api/research/integrations/status?scope=all|data|local`
- `POST /api/research/integrations/probe-batches`
- `GET /api/research/integrations/probe-batches/{id}`
- `PUT /api/research/integrations/{id}/auto-probe-consent`

原 `/data/sources/{id}/probes`、`/data/probes/{id}`、`/local-integrations/probes` 和本机验证接口继续
保留；本机验证内部的 Workbook timeout 明确受 180 秒总预算减 10 秒协调余量约束，不改变协调器
状态或来源可调用判定。旧页面数据接口允许增加字段，但不删除既有字段。

## Runtime 工具

十五个 `datahub_*` 品牌无关工具常驻 Runtime。可用来源由 DataHub Broker 在每次调用时根据最新
配置、探测、适配和授权状态选择，因此连接状态变化不要求重启 Runtime。没有可调用来源时查询明确
失败；显式 `source` 且 `allow_fallback=false` 时不得静默换源。

Wind binding 只投影已登记且能由现有 `WindAdapter` 证明等价的业务能力、数据集、字段、日期、
复权和单位；不接收公式、表达式、路径或凭据。股票行情要求显式 `asset_type=stock`，指数继续走
独立 points 口径，无法等价映射的宏观利率、基金持仓和大宗交易保持不可调用。自动 Excel 查询使用
容量为 1 的专用 worker 和独立隐藏工作簿；超时或关闭未确认时保持单飞或 poison，不选择、保存或
关闭用户工作簿。

十八个 CPU 有界 Skill 不是新的协调器来源，也不直接持有 Provider 会话；它们只消费会话内已经
物化并带 dataset refs 的相对 JSON 快照，受统一行数、字节、序列、标的和 64 KiB 完整结果预算约束。
不可变能力快照仍由既有会话生命周期发布，清理只处理产品会话目录、调用收据和快照引用，不跟随
链接、不删除 DataHub 原始来源或用户打开的 Excel 文件；真实 Wind/Excel 对照不足时能力保持
disabled。

## 当前批次边界

协调器底座批次已交付协调、持久化、自动探测、统一 API/UI、Tabbit 双状态和 Runtime 工具常驻。
现有 Provider 闭环批次进一步完成 AKShare 轻量真实网络探针、天软/MySQL 安全错误投影，以及
精确 `cjpy==0.5.2` 的离线哈希锁、`PyMySQL>=1.2.0` 依赖契约。AKShare、财联社和东方财富基金已有真实探测、查询、
快照及 Runtime 调用证据；天软和 MySQL 在用户完成逐来源授权并提供真实外部条件前仍保持
`user_action`，不得以依赖可导入或模拟连接替代成功证据。

AKShare 财务摘要的布尔缺失哨兵规范化只发生在 Provider 结果边界，不改变目录登记、五阶段状态、
探测授权、动态选源或 `runtime_callable` 判定；Provider 查询成功仍与单元格是否缺失分开表达。

专业数据源扩展、其他公共/监管来源、文件同步和本地 MCP 真实调用属于后续批次；未交付项必须显示为
`not_delivered/developer`，不能计入用户“需处理”。

连接凭据改为每实例系统服务后，旧全局记录不参与配置/探测/可调用投影；需要在本实例重新录入。协调器仍按当前凭据状态失效和判定，不以其他 data home 的 Key 存在证明本实例可用。

## 设置闭环阶段3：当前能力范围

能力准入只消费现有DataHub当前配置/依赖/允许/探测事实；探测结果绑定非秘密配置身份，配置替换后旧健康证据失效。它不新建协调器；一次来源探测仍不代表全部dataset权限，真实调用持续检查且不能从失效缓存恢复授权。


## 单一兼容模型连接

兼容模型的配置/系统ref/原生生成仍独立于协调器五阶段数据与本机投影；文本生成不提升任何来源/集成为可调用。私有通道的model-connection只返回已验证非秘密配置，不读商业数据凭据，不新建协调器或Vault。

## macOS Office 显式验证诊断

PowerPoint sandbox根使用厂商实际bundle identifier `com.microsoft.Powerpoint`，与应用显示名Microsoft PowerPoint分开；不得由显示名推导容器标识。路径合同修正并不证明此前保存超时已经解决。

Office 验证在调用前将服务端验证ID绑定到本次32位run UUID与合成文件名；完整位置仍由既有Office sandbox根和固定后缀推导，普通API不接受任意路径。现有私有状态文件保留有界的验证run登记，冷启动将未完成任务标为interrupted，不重新执行Office，也不把工作进程退出解释为功能或文件清理成功。

验证结果分别记录last_completed_step、function_outcome、cleanup_outcome。只接收有限步骤/结果和合成文件名，不回传文档正文、账户秘密或任意本机路径。Word使用原生创建、保存、关闭/重开读回，并在save-as后按登记文件名重新绑定文档引用；Excel记录真实应用计算/保存/读回阶段；PowerPoint记录原生演示文稿/幻灯片阶段。库文件生成或编译成功均不是应用真实可用证据。

超时后父进程仅停止已登记的验证工作进程与所属Excel实例，不再重复Office受保护目录I/O。功能结果和清理结果互不替代；清理未确认时保留任务自己的进度目录和文件身份，不按普通老化规则删除，不通过文件名前缀认定未知对象可清理。文件已存在时拒绝验证且保留该未知文件。Word/PowerPoint只关闭所创建/重新打开的测试对象，不退出共享应用。

Wind Excel验证使用既有独立应用/工作簿模式及任务私有元数据目录；它不创建验证文件到Excel Documents。插件心跳成功只证明此次会话调用，不代替具体字段、日期、单位及数据集权限验证。iFinD目录中的旧用户名/密码HTTP网关协议并不是厂商官方refresh/access token协议，普通终端账户不自动证明HTTP接口权限；未完成的接口仍按事实保留未交付或待配置状态。

Office失败理由仅以明确错误号区分：-1743自动化拒绝、-54/-61文件访问拒绝、-1712命令超时、-600未运行、-128用户取消；unknown permission文字不推断授权拒绝。原始错误号只作为有限非秘密整数进入诊断，不回传stderr文档内容。准备阶段10秒、每个原生阶段30秒，记录整秒开始/完成/耗时；原总监督限额不提高。阶段超时仍不证明具体权限拒绝。

文档业务的Excel/PPT原生路径使用任务私有run目录的输入副本，不借用Office容器目录来绕过授权。Excel准入检查全部定义名称与普通公式，仅允许明确的本地函数；数组/数据表公式、外部链接/宏/连接拒绝，工作表与范围在启动前核对。PPT仅支持简单文字对象修改，按OOXML对象身份映射原生对象名称，固定脚本读取私有JSON；保存、关闭、重开后核对文本。原生失败不会转为文件模式。Word原生业务入口及两款真实应用闭环仍需各自验收，不由离线合同或编译通过提升为可调用。

## 2026-10-09 本机状态与受控 Office

本机汇总从管理器本次发现与有效期核对后的同一快照生成。GET local-integrations 返回该快照及 integration_status（scope=local、local_revision、generated_at）；前端只消费此响应，不拼接另一次旧协调器缓存。GET/status 与发现 probe 不操作 Office。Excel 自动化桥保留独立事实，但作为 Excel 组件不重复计入用户能力。

新增 unverified、stale、not_detected、not_applicable 分类；not_delivered 仍保留三占位项。仅观察到异常/验证未通过才计入 system_fault，缺可选软件、未验证、失效与不适用不是故障。真实探测失败仍关闭旧可调用结论并保留故障。Office 24小时、Wind最多5分钟TTL不变。

同意接口只扩展 local:excel_app、local:word_app、local:powerpoint_app。设置页一次开启三项，也可逐项关闭；同意摘要绑定协调器/本机管理器所属状态根，异实例复制不继承。开启同意或已开启实例的启动发现批次可执行自动验证；普通手动probe和GET刷新仅发现。已有有效结果直接复用，当前任务繁忙跳过。每个目标/条件指纹最多一次，启动前持久化停止标记，失败/取消/冷启动不重放；条件指纹变化或用户关闭后重新开启才允许新尝试。没有第二scheduler，复用原批次与串行受管验证器，Excel/桥共用excel目标。关闭时取消本协调器登记任务并阻止后续目标；清理仍由原验证器负责。厂商、Wind/iFinD与模型不在Office同意范围。

本机scope恢复与Office同意操作不恢复DataHub状态，也不读取来源目录/连接凭据元数据；数据scope按原合同延迟恢复。页面仅在有效证据到期或重新可见时发GET更新，不把状态刷新变为真实验证。

2026-10-09追加授权收口：Office成功且关闭确认后，仅归档登记的合成文稿到既有私有验证run目录，再清理沙箱副本；成功marker移除，仍沿原16项/512MiB/24小时有界保留策略回收，不新增执行器或任意路径接口。Office开启改用页内说明、确认/取消按钮，系统权限弹窗仍由人工处理。


Hot固定原件发布复用DataHub私有会话快照目录与读取授权；它不是新的外部Provider探测，也不会更改既有发现/授权/验证/可调用五阶段。Hot交接需要已原生确认的目标会话，来源保存状态和模型/研究验收状态独立。


2026-10-13续跑：Hot冻结快照是已验证的会话证据副本，script准入不要求它伪装成普通DataHub供应商，也不提升任何来源可调用状态；原capability许可先于只读路径授予。


2026-10-22 基金NAV入仓：基金NAV例外仅限eastmoney_fund、nav/fund_nav及最多31日完整分页；授权撤销、配置epoch和profile失效仍阻止查仓，不扩大跨源等价或令牌权限。

2026-10-22 iFinD凭据复用：官方iFinD授权验证优先已有access，固定HTTPS权限策略检查不触发行情、不提升数据权限；坏access失败关闭，不自动以refresh重试或切账号。

2026-10-23 iFinD历史行情修复：合法flat与reqBody按官方合同二选一，仅历史dataset固定出口改到history_data；未知参数在取密前失败。凭据仍来自当前Host connections，原账号/配置epoch/授权及原生快照白名单不变；不读取全局Skill配置，不新增EDB或正式回测权限。

2026-10-23 历史任务请求显式source并冻结来源配置映射，最终规范发布与缓存复用复查实际输入来源授权；取消/partial复用worker_activity的所有实际涉及来源排空。仍通过现Host、Broker、Provider及会话快照，不增加协调器节点、存储服务或新HTTP入口。
