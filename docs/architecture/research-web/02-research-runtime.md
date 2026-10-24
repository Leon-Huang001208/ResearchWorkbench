# 研究协议、执行状态与恢复

资产V8不启动研究，后台空闲复核覆盖已上线今日发现跟踪、Automation与Workflow；原Host/Native/私有池、资产Future和市场inflight未知或活动继续拒绝。旧profile恢复身份与唯一DSH保持，不重试任何未知模型调用。

华安 v2 不启动研究或模型，只新增固定升级分派；原Native/Host/私有池、真实Future及市场inflight空闲门保持，沿现有事务恢复。PR209档案运行状态继续纳入保全；周报仍经唯一DSH与Host质量门，不自动重复未知调用。

华安固定Native模式不启动研究，不改DSH协议、历史或模型配置。原Host显式空闲、Native、private-pool与市场inflight检查继续约束升级；未知/忙碌不切换。实际获准更新后，周报仍经原Report Workflow冻结输入→DSH→Host质量门与确定性排版，没有第二执行链或自动模型重试。

## 今日发现显式交接与跟踪（2026-10-23）

GET读取已有Intel第三方事件，无模型；首次新抽屉的GET selection只读核对所选事件完整详情，独立scope feed不污染首页、不写Store/创建会话；prepare再核对精确详情与预览事件版本、冻结正文/快照及上下文，再按预分配ID/cwd创建和配置原DSH。execute独立确认、固定键至多提交一次，未知只查原receipt/历史，FinGPT与Claw均经原规范报告质量门。跟踪保存禁用、单独启用，原Automation在同用户后端存活时读来源、去重、每日最多一次研究；受理/运行/质量独立。03图新增实际顺序，详见[合同](../../research-web-discovery.md)。


2026-10-23：终端部署profile不改变DSH研究协议或原生历史。原居民活动／研究、历史查询、MarketService inflight必须明确为空，未知或活动即拒绝切换；沿version4 journal和逐阶段恢复，不中断未知任务。产品代码、工具组合、原三CI及真实主实例／网关切换分别留证；尚未部署不能转写为运行验证通过，见[部署合同](../../research-web-gateway-upgrade.md#全市场终端固定部署2026-10-23)。

市场分析和持仓浏览不创建DSH研究会话或模型调用。POST指数刷新同时有界获取可核验的前日价格指数日线；可见／暂停／取消和服务关闭沿原MarketService回收。画像读取只消费缓存与真实首次观察；正式择时总分和仓位受服务端证据门限制。
`builder-reconcile`不启动研究或改变DSH pin；只有指纹绑定的管理员apply可临时启动新建且身份验证通过的BuildKit，完成就绪检查后停止。恢复也必须先完成卷、账本、配置、运行任务及预算全门，不能中断常驻或未知构建。

2026-10-23：市场逐股限价、昨日成交额和资金日线留存不创建研究sid、dataset或模型回合；原采集inflight/取消/排空和部署空闲见证保持，不改变研究协议。 具体来源、缺口与缓存合同见[DataHub](../../research-web-datahub.md#无会话全市场数据)。

2026-10-23固定公开indices仓库桥不创建研究sid或DSH回合，不改变任务receipt、自动化和恢复协议。它复用Host生命周期与StorageRunner，取消/关闭等待真实事务结束；公开指数入仓不认证研究报告、正式回测或周报。

资产v5索引读取修复不改变DSH协议、研究回合、任务状态或恢复流程；只在原verify_primary的v5分支复用已有64 MiB业务读取，元数据及旧profile保持。原明确空闲、排空、BirthFence、全账号保全和version4 journal继续生效，真实失败停在停机前；没有新生命周期节点，01／12图仍准确，也不启动研究、周报或模型。

资产交互v5固定部署不改变DSH协议、回合、历史、取消或恢复状态机，也不运行研究／周报／模型。固定旧51f09与产品9bc4沿原操作员锁、明确空闲及version4 journal；目录租约、区块／历史task和真实Future仍按产品既有witness判定，未知状态不据作可切换。原01／12图的部署及生命周期边界保持，profile版本不等于journal版本；正式recover只按验证后的v5 mode回51f09。

行情缺口部署使用封闭 `reviewed-market-gaps-v1` / `apply-market-gaps`：旧版固定 `99d3ee34977c47189a5638207c109a555f52a687`，产品源码检查点固定 `9faeeca3003a912ca75799fb27b635ba1bb87a1a`。检查点为本轮产品修复的不可变祖先，最终操作员/产品组合目标仍必须最新已合并 master、独立评审和原三项 exact-tree CI（含 Mac 干净安装）合格；不把检查点冒充合并版本。复用原 version4 保全/恢复，并在原维护锁内额外核对 MarketService 的 inflight 明确为空；未知或正在采集时不切换。旧 profile、controller/evidence/网关模块字节及模型/账号权限保持，无新部署节点、HTTP或依赖，原图准确。

全市场缺口修复（2026-10-22）：股票列表增加东财官网 f292 交易状态；同身份、同日单股接口有界补取空成交额与停牌参考价。停牌、未上市单列，不计平盘；已上市股票成交额全部覆盖后才合计。沪深大盘日线资金改用已实测访客端点，使用自己的来源、日期、采集时间与返回行数，不沿用板块元数据。无新依赖、来源权限或研究会话；原 Host/MarketService/DataHub/东财拓扑不变，现有图及 API Atlas 不重画。

2026-10-22 全市场常驻部署使用封闭 `reviewed-market-overview-v1` / `apply-market`：旧版固定 `4d2e3c408663b64be9e58b03213f4ca8f1152733`，产品固定已合并 PR179 `5de7e5f2db95b8b501905af9cfdc30e8fe84db0b`。复用原 version4 事务、空闲准入、BirthFence、全部账号索引冻结和内容寻址恢复；旧 profile、控制器、证据读取器及自动兼容白名单保持。操作员候选须独立评审及原三项 CI／同候选 Mac 安装通过，再按用户授权切换并在真实认证页面验收。 该封闭部署事务本身不新增服务、HTTP、持久格式或依赖；它沿用当时已审的图与 API Atlas，不要求重画 HTML/PNG。Windows/Linux 原生与 Docker 产品层保持各自未执行状态。

2026-10-22 账号目录loader与资产区块task属于Host数据工作，不创建DSH回合、子Agent或Automation日程。目录在SDK批次间仍有活动witness，真实Future结束前不认证空闲；初始观察、旧刷新与load共享区块锁，受理保存失败原位撤回本次字段，保持其他活跃block引用。resident与关闭等待覆盖目录、区块、历史及真实Future；未确认witness仍阻止切换。DSH协议、原生历史、模型预算、取消／恢复和研究质量判据不变，目录缓存也不转换为研究事实库；细图见02模块及04快照资料流，原研究执行状态图保持。

DataHub查询前台总预算18秒，独立owned计时器在HTTP断连后仍有效；超时返回504并保留同call_id，任务继续真实排空，完成前不释放SDK/数据库容量。成功提交后取消保留真实warehouse版本，迟到数据不发布。DSH与Automation预算、历史回合及模型授权没有扩大。


2026-10-22 MCP隔离：仅macOS固定离线Python在新增权限、policy/runtime/安装树/schema复审后条件开放；逐次重验并在受管Seatbelt内执行。Node/npm、其他平台、凭据环境、网络和子进程需求保持受限或失败关闭。解析前字节/连接时限与真实进程回收分别核验，回收未知保留准入栅栏；固定远程及非受管Native维持各自合同。具体包就绪不由Doctor入口存在推断。

2026-10-22 插件指令读取当前 session 不可变 pin；仍批准旧版本跨升级继续使用，显式撤权即时拒绝。Skill/Workflow 走既有能力目录、Agent 走既有 DSH subagent 与预算，精确 MCP 工具需 Host/schema/guard 全链确认；Hook 与运行中请求计入空闲证明。原Automation调度保持，双阶段重启未知保留 fence。见[插件合同](../../research-web-plugins.md)。

2026-10-22 v4 profile固定旧5495与PR180产品`9b436613aad9136f4959c992c89dd72fc7354ed5`，不改变version4 journal和前进/回滚/冻结recover状态机。既有DSH/历史任务/真实Future/取消排空/日程/私有池空闲及旧v1/v2/v3恢复身份保持。旧v3已正式恢复5495且网关解除fence；产品三CI属于产品证据，v4最终本机/评审/CI/部署另验，不新增运行状态或重画图。

显式华安周报合同由受信Report Run创建Claw会话并冻结原要求；数据失败不发送模型，不把任意Claw
会话提升为可自动定稿。规范正文及中文presentation经Host确定性投影后，原质量门重新核对实际文件，
最多一次有界补查；执行/交付/质量/定稿独立记录。未知受理不重发研究，已知原研究可显式仅重投影，
重启或新失败保留上一正式归档。原DSH历史、工具准入与其他会话质量合同不变，见[周报生产](../../research-web-etf-weekly-production.md)。

2026-10-22 Wind部署profile v3复用原v4前进/恢复状态机，journal中的封闭mode只选择固定旧版5495，旧v1/v2恢复不变。原DSH、历史任务、取消排空、真实CJPY Future及研究质量协议均不修改；root切换前仍须持锁证明研究/日程/私有池/观察/DataHub/历史全部明确空闲。产品验收不替代profile候选CI与实际版本/保全，未知状态继续阻止；没有新运行状态或执行拓扑，因此不重画当前图。

2026-10-22 历史任务属于Host数据工作，不创建DSH研究回合或Automation日程。queued/running/cancelling/draining为活动，completed/failed/cancelled/interrupted为终态；服务关闭/会话取消联动子DataHub call_id并等真实Future结束，无owner恢复为interrupted且不自动重试。固定复权规范/raw/因子/metadata通过原会话快照交给唯一DSH，旧冻结研究材料继续只读。resident活动同时反映任务与真实Future，异常witness为未知；操作员要求全部明确空闲，不能仅凭HTTP取消或浏览器关闭切换。[历史合同](../../research-web-datahub.md#资产历史任务与固定复权)不放宽DSH执行、质量门、模型及厂商授权。

市场刷新使用独立 request ID 与每个读取者的订阅，同 key 采集合并；最后读取者取消及服务关闭均取消并等待后台 HTTP 回收。行情缓存不进入研究会话、DataHub 会话 receipt 或 DSH 历史，研究协议和质量门保持；市场 pending/running/completed/failed/cancelled 不能解释为研究执行或验收结果。

资产观察 `apply-assets-v2` 复用原 v4 前进／恢复状态机；已验证 journal 的 v2 mode 固定恢复 `9bc12355`，v1 和模型 mode 保留原旧版。两资产 mode 均要求观察和 DataHub 明确终态，活动／未知延后；DSH 协议、研究历史、质量门、取消语义及原恢复拓扑不改变，不调用模型或供应商。

资产观察的图表公式和字段投影仅在浏览器确定性执行，不引入AF Agent委员会或第二执行循环。新增section_sources／section_ranges保存在原观察请求，刷新和恢复复用原任务／取消状态机；失败沿有效显式来源返回，不自动改来源或重试。DSH协议、原生历史、研究质量与用户授权边界保持。

部署资格只对CI日志读取有界等待120秒，普通命令30秒与全部研究空闲条件保持。读取器按完整SHA256冻结进原恢复包，不运行模型、不改变DSH协议或既有回滚状态机。

资产观察的apply-assets仍走原v4前进/恢复状态机；恢复按受审profile绑定的c688旧版执行，不沿用模型专项旧版。加载或未知的资产观察/DataHub查询与Native/Host活动一样阻止停机，不修改DSH或研究执行协议。

联合恢复按记录的各角色 Git 目录身份复验，独立 primary clone 不要求等于源码 source_common；切换前缺目标对象直接拒绝。全部原活动、排空、持久冻结与恢复门保持。

联合升级允许的五个导航 UI blob 不改变运行/恢复状态机；新冻结恢复包包含同一范围检查，活动、未知、排空失败仍沿原 deferred/recovery_required 处理，原研究不会因 UI 交付被强停。

模型服务商专项 v4 事务联合更新主实例与网关，执行前复核 Native、Host、自动化及私有池空闲。preparing 意图先于 BirthFence，占槽中断由原身份校验恢复；主实例 journal 保持旧控制器可读，全局 HTTPS 503 阻止旧控制器提前撤门。

网关SIGTERM优雅等待预算为90秒，让已接纳请求结束；超时保留恢复事务，不升级强杀。恢复任务本身提供已验证的Git钩子工具PATH。

v3静态网关事务沿用Native/Host/自动化空闲探测；任一活动或未知均延后。不会重启主实例、DSH或接管其研究任务。

静态候选准备与实际切换分开：stage-primary-ui 不发停止信号；原 resident 继续执行原生/Host/自动化空闲、准入锁和 journal-before-stop。网关恢复再次核对升级器的同一 Git blob，活动/未知仍延后，研究执行协议和固定 DSH 不变。

新网页轮次冻结bound-analysis-v1，Host提供可选中文字数目标；report_plan用fact/formula完整引用绑定分析中的数字和推导，禁止通过手工payload降级。固定DSH参数schema使用独立互斥object分支；wire不支持的长度/数值关键字不承担授权，原固定脚本和Python入口仍强制全部16/40/8/0..12及字节上限。预算、取消、历史和一次补查通道不变。

允许web的研究在首次空证据时就采用plan；正文回调刷新后选择实际ID，原native admission每次提供最新受信context和冻结formats。calculations仅传原始引用/操作/展示位数；系统生成声明、笔记、底稿与格式，Host从实际字节重算。错误反馈返回有界唯一ID，修正不新增补查许可。原预算、取消、历史、幂等及JSON最后发布/失败恢复协议保持。

SIGTERM后的进程签名变化不能证明已退休；等待同PID从进程表消失，超时继续deferred且不追加信号。退出未回收回归使用真实Mac子进程延迟reap，不影响DSH协议或研究预算。

优雅排空前新增内核映像重验，避免将Python启动器路径误当实际运行映像；完整argv、起始时间、端口归属与无强杀合同保持。研究协议和DSH执行不变。

空私有池网关更新只在primary Native、Host及自动化均空闲时请求旧网关优雅排空；私有owner/未知状态保留延后。DSH协议与原研究循环不变，任何超时不升级强杀。恢复沿持久阶段重入，目标全请求冻结解除前不得出生新研究pair。

research_read_source 在正文落盘后刷新原 research_evidence.json 并返回实际 numeric_observations，模型可用既有 select_business_evidence/report_plan 组装声明。Host 检查时仍独立重读正文重算；补查、取消、原生历史和预算不变。

具备数值业务观测或允许后续网页取证时，首次执行与唯一补查均提示原report_plan；定性引文也可使用无Summary的配方，不编造数字。Python仍支持独立计算、取证及绘图，避免同时下发另一套规范报告payload指令。原生预算、补查计数、模型配置与实际Host质量状态不变。

research_check_quality返回具体算术mismatch与对应expected供原一次补查使用，同时给出Host report_delivery。模型最终消息须引用该版本URL；重写报告后重新检查，不创建友好别名绕过版本。研究预算、取消、耐久历史及原生工具边界不变。

旧会话无需重建：run_script 优先导入当前 Host 包的固定 SDK，而不是覆盖会话资源副本。Host 向 PDF helper 注入已验证 session 绝对根以保持相对输出及 cwd 恢复；字体仍来自已审包。模型没有 SDK 路径参数，代码/输出/时间、取消及网络/fork 禁令不变。

Host 抓取正文即使保存在 inputs，也只沿原 web 身份核验；切换到 uploads 范围后不会再通过附件观测进入业务索引或快照。重新启用 web 仍保留来源日期，不能借文件落盘重置截止日。

research_run_script 增加与 code 互斥的 report_plan 数据参数，仍由原准入、槽位、超时、输出上限及 Native 沙箱执行。可信 task/contract/要求来自 Host；模型只选择当前实际观测、提供有界算术步骤及分析。规范数值、笔记、要求映射和全部父来源确定性组装，模型分析及真实 missing 原样进入同一质量门。没有增加工具、模型循环或补查预算。

三组实验仅对模型接入、工具限额和可观察性加测试包装，保留各自原生研究步骤。配置齐备、独立评审和全部零生成预检通过后，按A/B/C各发一次；900秒内预留退出窗口并核验整个owned进程组，父进程退出不表示后代已退休。

research_read_source 的身份清单来自受信原生快照中的已完成搜索事件，解决持久事件尚未到达 Host 时的登记滞后；只保存有界来源元数据，不复制原生对话。list 返回准确 id/title/url，read 仅凭该 ID 取公开正文。执行标识由原生 call_id 与受信会话生成，取消先到亦阻止后续取证；总时限和取消会回收有限 HTTP 进程，落盘前仍受原任务和来源范围约束。一次补查及质量门不变。

每次research_run_script是独立进程，须重新导入并读取已成功保存的文件。select_business_evidence把实际记录选择和要求映射合并，未知/多期间歧义拒绝；business_仅作观测标识，citations填全部父source_ids。治理提示仅从冻结要求选择，不因共享任务描述把组织实施缺口加给财务研究。不增加工具、重试或补查预算。

DSH实际业务提示要求规范来源ID、原文期间/单位、精确算术和完整同节引用；可用报告helper提前拒绝错误arity、虚构计数或舍入冒充精确claim。不能表达的证据保持未核验，不增加补查/模型循环；Automation授权和恢复不变。

冻结合同后可先load_business_evidence(task_id,sha256)从本回合只读投影直接选取实际观测；模型仍须读输入并生成独立底稿/草稿，原research_check_quality再从实际输入独立评分并返回business_observations及原文位置；原一次补查中可按真实metric/period选择观测，用business_evidence替换对应错误事实/方法，保留全部冻结要求及真实missing。不能把原文外推断伪装成规范句，也不能省掉跨文件父来源。未支持布局仍未核验；没有自动续领补查或新回合。

FinGPT提示可使用calculation_evidence组装同配方四项实际观测的原句、章节、笔记与需求映射；helper没有验收权，不增加补查次数。真实missing继续incomplete，明确的研究范围限制另如实说明；Automation授权、调度与恢复保持原合同。

FinGPT发送与质量返回只提供允许资料范围内的规范来源身份；校验工作线程读取冻结contract/files/sources/delivery副本，返回前重验当前delivery key和完整合同，过期结果409拒绝，不能发布旧passed或续领补查预算。

研究提交的幂等键沿认证网关原值传给用户后端；缺失键继续拒绝，网关不生成键、不重试模型研究。

stage 预留退休不启动、取消或恢复任何研究。原任务句柄终态须先确认，新任务沿独立实例继续 DSH 验收，不复用旧会话或凭据。

容量限制只控制新建逐用户pair；已存在的用户先复用，满槽返回503且不驱逐已有实例。独立池显式上限1至4；附接常驻max_additional_instances默认1，本机选3。槽位随管理员停止实例/停用用户或正常网关退出而释放，退出浏览器不释放。

恢复已存在的用户根时，不再为Web随机改址：读取并验证DataHub/MCP原址，保留同一Web端口；DSH端口与私有gateway key可重新生成。控制token及所有会话字节保持；未知监听、控制事务未完或记录不一致均拒绝启动。

primary UI/静态资源绑定其旧后端版本，原 AIHOT GET 经该实例；新用户仍按最新独立执行与共享资讯合同运行，不启动资讯数据库或 worker。

常驻网关可只读验证并附接唯一 primary 管理员的原 pair；不通过新池启停它。原 resident 继续执行原准入与生命周期合同，启动短暂未就绪时网关有界等待。新用户 pair 正常退出清理；只有不同 kernel boot UUID 的已知 owner 可以归档退休，同 boot 或未知状态保持失败关闭。

AI资讯自主化本轮在隔离实例接入原版API/worker与独立库，保持DSH研究执行及当前常驻内容。零调用和后续切换边界见[自主资讯合同](../../research-web-ai-news.md)。

私网服务器不新增执行引擎：认证网关将用户 UUID 绑定到独立 Web/DSH pair，内部 RPC、历史和会话搜索仍用现有协议。每个 pair 使用用户私有 HOME、TMP、状态目录及凭据命名空间，不继承管理员 HOME。`tenant_policy` 与原生执行 guard 双层拒绝宿主浏览器、MCP、日程/自动化、Hot 和报告 Workflow；native 文档在实际执行入口及私有回调均拒绝，仅允许文件模式。浏览器断开只关闭订阅，研究继续；账号停用和管理员显式停止实例才结束相应受管进程。默认两实例上限不是研究任务队列或强隔离；同 UID 后端与固定工具实现仍受信任。

服务器共享资讯由gateway直接读取 `server_root/shared/ai-news`，不调用用户runtime pool，也不占DSH槽。已登录成员可读，status/control仅admin；tenant_policy拒绝全局AI路径，用户pair不构造资讯bridge。共享采编worker生命周期仍须显式管理，账号登录或资讯请求不会启动它。

AI资讯详情与同新闻来源通过有界Host读取本机原API，前端取消和代次隔离覆盖正文语言、专题合并链、来源延迟与主题分页；不进入研究生命周期。

AI资讯阅读不进入DSH；自主采编由原AIHOT worker独立管理，仅处理资讯，默认零模型与付费调用。它不创建研究会话或触发Hot重复采集。
现有唯一研究引擎、凭据和研究任务生命周期保持；失败只影响该阅读模块。

## FinGPT 三策略与固定质量门

quick/deep/agent 均复用唯一 DSH loop、已保存模型与凭据，旧 instant/deep 深度参数保持兼容。Agent 是动态规划策略，不承诺每次并行或固定步骤。research_check_quality 通过既有私有认证桥核对本轮冻结要求、截止时点、报告与实际证据，不启动另一个引擎或回合。同报告重查复用回执，最多一次补查，仍受原工具/子任务预算约束。

执行状态、质量 passed/incomplete/invalid 和文件状态分别显示。补查仍缺证据时保留可用报告与缺口；补资料在同会话新回合继续并保留新增要求和旧版本。通过范围仅限实际来源摘录与确定性数值检查，无法验证的语义改写保持未核验。只在聊天回答而未提交可验证底稿时不伪造质量通过或文件。

Host元数据专项升级通过显式 `resident upgrade-host-metadata` 入口执行；自动兼容清单与固定登录控制器artifact保持。专项只接受预期旧版02c086b16、PR122四个已审Host Git blob及同一受管Git源中的精确最新master。控制源必须干净且通过merged PR/独立评审/三CI实际tree核验；未知模块、依赖、Store或Host内容变化仍拒绝。既有bridge完成空闲栅栏、lifecycle lease、journal-before-stop、健康和回滚；成功后才记录baseline审核并刷新安装基线，不搬迁数据或凭据。

Codex式提问卡只维护浏览器逐题草稿，最终仍经原生问题事件和既有answer通道提交整组答案。明确跳过使用原custom字段记录用户未提供答案，不改变工具/日程授权；收起不答复、不取消，待答问题仍阻止空闲部署。两模式项目与导航元数据不复制原生会话正文。

正文搜索使用固定 DSH `7ecf564f2e09b829240c5553687223bdd1e2df73` 的显式部分搜索接口：Host 将 RWB 已创建、未删除且符合当前模式的 ID 范围传给原生层，再与原生列表可见范围取交集。响应必须包含完整范围内的 `unavailableSessionCount`；Web 返回 `unavailable_count` 并在零命中时仍提示部分历史未搜索。旧格式源记录保持不变，不授予恢复执行；I/O、损坏及取消仍失败。未升级的旧接口缺少覆盖信息时明确报错，不假称搜索完整。

resident更新锁按研究准入EX→原lifecycle顺序持有。HTTP写操作、send/approve/answer、
Automation准入/执行/恢复使用共享锁；已排队或运行研究使更新延期，native session.list含子会话。
候选启动期间自动任务等待维护解除；失败或中断恢复旧代码后才释放栅栏，不触发新模型请求。

只读session.search映射固定session/search {request:{query,sessionIds,unsupportedSessionPolicy:"report"}}，复用原认证并保留其他RPC拒绝。原生provider不可用不回退为假全文；hasMore原样作为缩小关键词提示，不生成cursor或messageId。搜索不恢复/启动Agent，Host不直接读取原生数据库或维护第二份正文库。

固定 DSH base 已挂载 `session-query-sqlite`，其默认 `openAt: never` 禁用全文搜索。Research Web 启动 overlay 只覆盖同一插件的 `openAt: first-search` 与 `path: ':memory:'`，不重复挂载。首次搜索才由原生 provider 打开已有派生内存索引，重启后按原生历史重新派生；不新建持久搜索库；本轮仅升级固定 DSH 查询代码，不改变依赖锁或研究工具权限。本轮隔离 macOS Native 候选已验证该 overlay 的原生 RPC 与真实正文搜索；生成配置回归和原生命中各自留证，产品归属过滤由 Host 继续校验。Windows/Linux 原生验收保持 NOT_RUN，不从本机结果推断跨平台通过。

显式试跑可用真实任务名或精确ID，含配对引号、刚创建/修改限定及版本号；后续仅白名单约束句，不是通用自然语言授权。版本不符返回 automation_version_conflict，未知/含混仍拒绝；原提问上下文、幂等Run及手动运行不改下一计划时间保持。Runtime将允许的Automation拒绝码加入原4KiB脱敏投影，不自动重试。

工程资源收尾不是研究执行状态。交付入口确认候选合并及CI通过后才归档任务日志、回收依赖/退休测试对象和缓存，再走原Git安全清理；资源blocked不改变研究会话成功/失败或触发重试模型。复制失败保留证据原件，重放须逐文件验证；状态与证据保存在common Git私有目录，任务worktree删除后仍可审查。

Native 私网 HTTPS opt-in 只改变浏览器到 Host 的精确 origin 准入；内部 DSH RPC、
DataHub 认证、会话协议、SSE 流与研究预算保持原实现。不因 HTTP/TLS 连通宣称模型
推理或流式输出已验收；跨设备与真实任务证据单独记录。
点击外站链接的根路径 GET 文档导航只加载原浏览器壳；后续 API/SSE 仍由同源浏览器
请求，未放宽运行时协议、内部认证、会话权限或模型执行准入。

周期简报的一次性Word子执行是既有report_documents投影，不进入DSH session.prompt。
其固定执行身份绑定periodic run与brief hash，先存不可变原件/回执，再条件提交任务完成。
正式研究的run/session/deliveryKey映射保持；报告可用与研究failed仍分开，不追加模型预算。

普通任务现在附带当前能力admitted/status/missing_codes与数据工具可调用性提示；这是规划事实，
不是授权，执行前仍走实时nativeAdmission。缺合约或来源的能力不应反复加载，不能改用脚本绕过。
非2xx DataHub响应只提取4KiB以内JSON的稳定error.code白名单，不向模型回传message或供应商原文。
DataHub领域status=failed投影为失败活动；complete/snapshot/partial/empty保留原状态和数据局限。

兼容模型支持原生工具声明、tool-call/reasoning/usage 流和历史工具结果，推理块在正文或工具块前关闭。
未明确披露容量时上下文压缩预算为32768，显式配置由范围校验后覆盖；预算不是能力证明。
固定 DSH compaction 组在隔离域加载，persona 保留资料口径、文件验证、权限与四子任务约束。
普通请求等待期间仍可独立停止；超时不自动重发，正文重试与普通发送共用交付/运行时门。

Hot offline evaluation只读冻结原件/已计费响应及规则，不启动worker/DSH/SDK，不重发模型、不改变18/77375的正式scope。三个既有回执只覆盖different_event；四项其他关系参考保留模型NOT_RUN。

times人工纠错不调用模型；已知日期需引用当前事件原材料版本及原文摘录，自动重跑保存日期主张并拒绝移出依据。撤回只释放日期专属限制，不解除已有其他人工保护；旧模型scope/预算保持。

Hot分页仍由一个hot.collect claim执行，整轮25秒/三页；逐页hot.parse复用同一pg-boss和owner fence。没有新研究引擎或模型调用。

首次目录激活在事务内重新检查实际列权限，不依赖UI缓存。已完成UUID重放仍先返回原回执，即使权限后来撤销也不重新写。已知permission_missing停止新提交并提示setup；提交未知沿既有UUID/body恢复，不发起第二请求。

catalog激活在当前owner事务内核对旧运营主体、配置版本，更新adapter/catalogId并使next_due立即到期；暂停源仍暂停。相同UUID先复用原审计回执，不因后续目录不可读而重复激活；未知回执保留UUID。旧owner拒绝，停机不删除已有材料。

stage默认关闭旧Automation不再阻止Hot计划管理：Hot列表/运行读取不调度，明确配置仍由Hot owner/controller执行。旧Automation关闭继续拒绝其create/send/投递；不因管理aliases可读而恢复旧执行。

历史pre-AES stage替换仅接受created/exited且Running=false的原登记容器；两次核对后用固定ID普通rm，运行态变化会拒绝删除，不使用force。新container沿现有up流程挂载原model_key，旧Native/Docker任务和凭据不会转移或自动重新执行。

周期简报的稳定身份由计划ID、配置版本和due时点派生。事务同时登记运行、入队和推进next_due；重复heartbeat不多触发。资料按固定due和发布时间窗口选择，选材先持久化；发布及终态回执写前/写后复核owner、claim、signal和有效计划版本。停用或版本变化取消尚未执行运行，PG错误保留errorCode/queueState；有限重试后仍显示失败，不生成模型执行。

Hot guest 的进程身份由内核 boot ID、启动 ticks、UID 与精确 argv 双读固定；状态
缺失拒绝，PID 复用拒绝，不依赖镜像中的 ps。初始化后宿主写状态失败时优先让
原 worker 通过 SIGTERM 暂停自己代次；强退/缺回执仍须独立核对 PG 状态。

联合封存只选 Hot 会话的输入、输出、冻结清单和原交付回执；HMAC 绑定 PG 清单与文件哈希。
文件恢复要求新目标，同一签名日志只允许中断重试；不恢复模型凭据或 Native 执行历史。
Docker Hot 子进程由 Web 角色监督，不接收 Native 模型 bootstrap，明确保留不可用状态。

新增Hot正式执行API固定问题/格式的deliveryKey，PG先记录execution_starting再发送。
回复丢失或重启只查根会话稳定原生marker，不重发；无Store receipt的确定前置失败标failed，
未知是否已执行返回null。已接受后的failed保持True或未知，不冒充未提交。

Hot模型流增加hot-model/hot-model-stream：请求冻结、prepared单发、预算登记、回执先存后输出。
managed子会话沿祖先绑定根Hot run；普通外部会话透传。默认official retry=5会被拒绝，
专用零重试装配与真实研究尚待验收。

Hot 内部控制/读取服务与研究执行分离：`rwb hot setup/start/stop/restart` 管理独立进程和指定库，
未启用模型时，启动、只读查询和 `rwb hot configure/status/doctor`
不调用模型；所有 Hot 模型步骤都不创建研究会话。Native worker 现按显式 model 配置装配
受控 DSH 文本上下文，仅绑定已有持久预算；研究交接仍未接入，不能从私有服务的
`initialized` 推导研究可用。后续交接必须沿本页原有会话归属、幂等受理和原生回执规则实施。
Hot 备份导出持有运行代次 fence 的一致快照，恢复默认暂停；当前不包含研究会话快照。
采集与分批解析任务由同一 PG 后端持有；准确 claim 进入 handler，旧 attempt 不得认领新租约。
来源级待执行/活动任务和未解析 inbox 会阻止重复获取，水位提交检查取得时间单调性。
来源暂停在取得前登记取消信号，并在解析提交前检查真实 enabled；重新启用恢复保存的 inbox。
配置请求 UUID 对相同参数幂等，响应未知保留 ID，不用新请求掩盖可能已提交的操作。
Hot 模型预算先有持久预留和发送状态；scope 不随日期/重启重置。派发前再次检查预算暂停，
回执与缓存可在旧运行代次失效后保存，但正式业务仍经当前 claim 提交。固定验收入口已做两次真实生成。
Hot text adapter 复用 DSH prepareCall/stream，调用不创建 session 或 tools。
完整截断/拒绝回复仍先保存计费事实；取消只禁止业务返回，不丢已取得的完整用量。
模型 scope 同时保存累计/每日上限；日限额按数据库时钟和显式时区计算，跨日派发重新准入。
固定 Native 验收与后续 DSH 研究使用同一个任务 scope；研究流程尚未接入，不能另开 scope 重置额度。
Native Hot CLI 已增加事件/频道读取和条件配置/纠错；读取不创建研究任务或调用模型。
控制回执验证请求的具体结果，不确定时保留原 UUID 和非零退出码，重启后用同一参数重放。
Node/PG 往返与父 Python 退出后的独立 Manager.stop 已验证；凭据 backend/解释器选择为隔离fixture。
Web Hot桥最多四个在途线程，超时/取消后容量直到实际线程完成才释放。关闭后待容量的请求
不能继续获准执行。条件写入Host超时保留原UUID；普通导航/读取没有模型或研究调用。

显式 docker-text 仅在已认证受管 AES 身份下读取已有预算；默认不发现账本。Fernet/Native 无认证实例身份时拒绝该模式，普通运行不变。固定 DSH 官方 Messages endpoint 为 https://api.deepseek.com/anthropic；此模式禁工具、附件、重试和 Tabbit，并绑定已授权输出上限。身份验证不认证 dev/stage/prod 角色。

研究 preset 装配固定 DSH 已有 `@deepseek-ai/dsh-tool-todo`，显式配置
`allowParallelInProgress: true`，依赖原生 `tools` 与 `sessionProjections` 服务。
guard 仅新增精确 `todo_write`，仍要求研究已启用及当前 Agent，沿用每回合48工具/4子任务
预算。此配置不承诺实际并行执行，不新增编排器、DSH pin 或依赖。

Web 从同会话原生日志投影 Todo。`todo/write.data.todos` 是完整替换列表，项仅有
`content` 与 pending/in_progress/completed；`turn/start` 清空，turn/end 保留最后快照。
`plan.version` 是 `<turn>:<seq>` 写入版本，不是跨版本 item 身份。无 Todo 的会话没有计划；
缺失所属回合不猜测，序列间断或历史起点缺失提示不完整，坏快照/冲突重复不保留绿色计划。
相同重复事件可重读。错误日志仅记录安全事件计数，不记录计划正文。失败与取消使用研究终态，
Todo 完成不参与独立文件交付判定。分页仍沿现有100页硬上限失败关闭，不能截断冒充完整。
历史首页、分页、SSE 与详情恢复缓存按序号归并时保留冲突标记，不覆盖掉不同内容的同序号
事件。标记仅存在于内存记录外层，不修改原生事件或持久日志；投影据此拒绝当前不确定计划。

Docker 模型桥由 owned launcher 显式绑定后端、随机实例身份、密文根与主密钥根。
私有 Python 子进程保持 `-I -B` 和清洁环境，只从自身受管产品安装路径加载模块。
模型保存/清除/未知提交与真实生成语义不变，Linux 研究沙箱守卫不放宽。

ETF工程模拟不进入DSH会话循环；用户提交冻结输入，由Host同一事务保存结果。
回放与前向共用 `PaperEngine.step`，输入摘要绑定恢复/幂等，失败不产生部分资金账。
尚不接Automation/Tool，真实运行BLOCKED；见[数据与文件](03-data-files.md#etf-工程模拟与真实准入边界)。

每次成功受理的研究请求向原生prompt附加同一时刻的UTC及本机时间，明确它不是资料、交易日或网页访问证据；用户指定历史研究日期保留原意。时钟在幂等摘要和reserve之后生成，跨日重复请求仍只发送一次，不以新时钟重放旧任务。检索摘要与未访问链接必须区别于真实全文访问。

工作区侧栏切换保留当前会话及待确认事项，文件预览只是既有Host文件读取响应，不触发新的研究、日程或模型调用。Markdown预览的纯文本MIME不改变DSH事件、Run版本、完成状态或文件字节。

研究型 Automation 执行会话在原生 `agent/pre-step` 使用固定 DSH 的会话上下文 `tools.restrict({allow})`，目录范围来自认证的会话级 `visible_tools`，只包含任务批准工具与 todo 记录工具。目录核验失败拒绝当前 step，执行期全局 veto 仍保留；普通会话不套用研究任务工具清单，不改变全局目录。通用 persona 不强制派出两个子 Agent，委派须实际获准且可用。

执行详情的 `execution_context` 来自唯一匹配 Run 的不可变定义快照；研究任务续答保持原批准工具、模型及输出格式。工具活动保留真实 call 序号、名称、独立 arguments/result 和实际错误；显示值递归脱敏并有共享大小、节点和深度上限，历史未定位记录不补造序号。DataHub 摘要保留 query/provider_query/coverage；已注册不等于来源当前可调用，错误仅返回受限业务代码。Wind 指数 quotes 是当前快照，不接受历史 date，不对错误参数静默改写。

固定 DSH 的 `session/list` 通过 `parentSessionId` 暴露父子归属；SDK Session Header 内部仍叫 `parentSession`。
Workbench 子 Agent 投影只使用已核实的 API 字段，继续交叉验证父目录、`origin=subagent` 和严格布尔 running；缺失、外来父会话、非子任务来源或未知活动仍失败关闭，不以空目录释放活动保护。
模型设置的空闲检查采用内部 `activityOnly=true`：历史 `mode=unknown` 只可在父归属、subagent 来源和布尔运行状态全部验证后提供活动事实。父会话列表与详情也可读取核实后的活动；unknown 子会话只显示受限提示，不读取历史或推断执行模式；不推断历史执行地址，不删改记录，也不把未知活动当作已结束。

## Docker 模型凭据绑定

模型 provider 由 owned launcher 显式绑定后端：Native 保持 macOS Keychain；已验证 staged
Docker Runtime 只接受 `/run/rwb-secrets/private`，在私有 stdio 参数中传递非秘密绑定。
子进程继续清理环境，两个固定模型 ref 不回退旧 resolver；Host 认证 record 接口和锁保持。
Docker `describe/resolve` 的来源为 `docker-encrypted-file`，Host 仅投影 `docker_encrypted_file`，
不回传秘密。保存、Runtime 应用、重启恢复和真实生成仍由原有产品 API 各自记录。

## Claw 日程提出与确认

`rwb_prepare_automation` 沿现有 research-tools 与最终 guard 注册，先核对原生会话范围，再通过实例私有控制通道提出日程草稿。
普通日程直接承载 research_task；缺少研究内容、模型、时间、时区、输出或权限时通过既有 ask_user_question 提问。原生 rwb_list_automations 查询真实任务与最新运行结果；rwb_prepare_automation_update 提出同 ID/expected_version 的修改。
工具只返回草稿，不创建、启用、执行或投递 Automation，也不授予 MCP 权限。
Host 的确认卡明确创建并启用研究任务，启用失败保留停用任务，重试不重复创建。rwb_run_automation 只接受最新人的明确肯定试跑指令，绑定任务与单次请求，不把增加/否定/解释视为运行授权。独立执行会话锁定模型和工具，所有工具仍经过原 guard 与资料准入。
每周 weekdays 支持多个星期日，旧 weekday 兼容，周一至周五不等于交易日历。
Host 确认保存仍使用现有 AutomationService、版本哈希锁与日程校验；正文、研究循环和原生子 Agent 沿 DSH，不增加第二引擎。

原生提问的试跑授权只接受完整匹配的肯定选择，并绑定问题、最新用户消息、任务 ID 和定义版本。试跑问题使用规范格式 `是否试跑「任务名称」（任务 完整任务ID，定义 v版本）？`，整串精确核对名称、ID、版本；名称子串、混合目标或模糊问题继续澄清。RPC 未确认、否定、解释或其他任务选项不能授予运行权限。
owned launcher 将 DeepSeek 单次输出预算固定为 16384 tokens，避免复杂文件生成在原 4096 上限截断；这不是总执行预算或完成保证。原生 max-tokens 仍投影为 incomplete，Automation 保留失败运行，不自动重试或伪造文件交付。

## FinGPT 深度与计划

NewSession 的 research_depth 默认为 instant，deep 启用完整研究底稿提示；source_scope 默认 datahub/web/uploads。两者在创建时锁定，旧行使用缺省。未知深度/来源和重复来源在注册前拒绝；深入研究须满足现有模型工具事实，不能绕过准入。

固定 DSH 的 @deepseek-ai/dsh-tool-todo 声明 tools/sessionProjections 注入，allowParallelInProgress=true 仅允许计划状态并列。guard 精确放行 todo_write，48 工具/4 子任务预算保持。todo/write 是 {todos:[{content,status}]} 全量替换；turn/start 清空，turn/end 保留。Web 的 research_plan 只投影该事实，不生成阶段执行或完成证据。


Mac mini 的 dev/stage/prod 使用同一既有 Web＋DSH 协议，各实例独立 data/runtime 工作目录、
认证 tmpfs 和身份账本；stage/prod 在固定镜像内执行，不读编辑中的worktree。
管理员入口只管理容器生命周期，不创建第二套研究任务、调度、恢复或自动重试事实源。
stage/dev 关闭 Automation；任务排空、全机重研究配额和 Linux 严格沙箱留给G3，
不能从候选健康推出真实模型/研究已验收。操作见 [Docker 手册](../../research-web-docker.md)。

Docker 资源生命周期由 host 标准库 `docker_resources.py` 提供只读预览、精确清理和离线卷备份恢复校验。
它复用现有生命周期锁与安装记录锁，不创建另一个产品运行时，不停止正式实例。
新资源命名、回滚保护、任务收尾及操作入口见[安装指南](../../research-web-installation.md#docker-资源命名与收尾)。

## 资讯雷达 · 2026-10-09

资讯雷达不执行 DSH prompt、不触发模型生成，也不修改固定 DSH 构建、凭据或会话。外部资讯离线时单独报错，不改变 Runtime 的 connected/health 状态。

Automation 异常退出恢复只监控原会话/报告 Run，不重建或重发。普通会话须有原生执行或终止状态证据，idle/created/未知响应为 native_submission_unconfirmed；未确认 send 也不进入成功监控。报告恢复以报告 Run 为优先事实源，持续核对 workflow/version，等待其 validating/completed 与真实产物；显式停止保持原有 interrupted 语义，不冒充自动恢复。

已验证运行中的实际 NativeRuntime 仅在显式 `--stop-current` 且公开 stop 成功后，
等待停止前捕获的 Native 两端口可由原 `port_busy` 判定释放。内部预算默认45秒，
只接受有限的精确 int/float、0至45秒；bool与数值子类在停止前拒绝。
单调期限下每轮最多睡眠0.1秒；超时返回 `runtime_stop_failed` 并保留旧模式。
等待不捕获或刷新外来观察，不处理外来默认端口或 Docker 内部端口；原 switch_select
锁、scope、两模式新状态与原快照 CAS 仍在等待后执行，任一变化照原边界拒绝。

模式切换最终复查的 `runtime_stop_failed` 保持原返回与检查优先级；日志区分控制器模式及
`report_not_ok` / `still_running`，不增加状态探测、重试或改变 lifecycle lease / mode CAS。
Native status 三个原失败阶段用固定日志区分；安全检查、子进程次数、40秒预算和原报告原样保留。

Python 内部端口选项以 TypedDict 标明允许的键，仍只转发显式提供的值；端点与控制记录的
类型说明复用原有运行时校验。同步脱敏回调和失败恢复回调显式绑定当次值，不延迟执行、
不改变重试次数、回滚顺序或生命周期权限。

Docker fresh-root 首装接受与启动为两个独立 lifecycle 调用：no-start 不创建产品根或 controls/端点；普通 start 重新验证缺失状态后实际 mkdir 并 pin。只读 Native 状态未知并不被改写为 idle；只有该调用的真实 lease、根/父身份、缺失 Native 元数据、无容器和稳定 PID/argv/start 观察齐备时可处理原默认监听。up 前撤销分配权限；本次失败不重新获取 fresh 或重试分配，普通已有根的原 bind-race 重试保留。外层候选发布/abort 在同一真实 lease 内复核恢复，未知状态保留原错误与稳定恢复诊断，不改变认证交换。

## 模型配置与显式验收

受管启动在固定 CLI 加载前安装产品 `auth-bootstrap.mjs`：启动认证输出按完整行截获（包含跨chunk情况），仅向现有私有 `runtime/auth.json` 写入临时bootstrap_token及实例绑定。管理器从该受控文件完成原Cookie交换，原子替换为正常认证记录，不再从runtime.log解析token；普通日志只出现固定脱敏标记。没有新HTTP接口、daemon或模型凭据后端。解析/绑定/私有文件校验失败则认证失败关闭，不回退旧日志。

模型 Provider 固定为 `deepseek-official`，模型 ID 由固定 DSH 的真实目录校验。保存与显式测试共用串行边界；保存共享凭据前拒绝活动父/子任务。已有会话保留模型，新会话在创建时应用默认值；凭据由Runtime共享，替换后用于所有后续模型请求。凭据变更前先持久化旧模型与 `model_configuration_uncertain`，成功后才提交新默认值并清标记。写入前只读拒绝不改旧状态；RPC开始后的拒绝、取消、进程退出、传输或最终保存失败均保留未知标记，冷恢复也阻断后续模型请求。固定DSH的credential/rejected也可能代表提交后的observer失败，不能当作回滚收据。不会读取秘密来制作回滚副本。

留空保留凭据，非空替换，`clear_api_key` 独立清除，两个动作不得同时提交。清除后的新消息被阻断；普通配置及最近测试不含密钥。macOS Native 的 `credentials` 服务通过产品 `runtime/model-credentials.mjs` 与 `model_credentials.py` 仅在系统 Keychain 解析固定模型 ref；不读取 Codex、Claude 或其他工程配置补齐。Host record 接口继续继承固定 DSH 文件 provider，使用独立 `.browser-credentials.yaml`。

1A收口中，API拒绝明显掩码/空白作为新Key；普通新研究请求在创建受理收据与Native prompt之前检查凭据，缺失或未知均失败关闭。Runtime的凭据来源由describe事实映射，不能将环境/旧.env来源硬编码成系统库。新 provider 覆盖全部 ref 方法，不委托旧解析器；后端不可用仍保持 credentials 服务挂载，使 DeepSeek 不进入 ambient 分支。桥接失败只输出稳定错误码，保存的不确定性仍沿现有状态机阻断，不新增事务框架。

`runtime_applied` 只在当前Runtime认证文件代际内，已有新会话实际完成 `session.selectModel` 且选择与默认值一致时为真；保存或端口可达不会设为真。代际标识仅由认证文件设备、inode与修改时间产生，不保存或散列秘密；Runtime重启更换认证文件后必须重新应用到新会话，旧证明不能冒充当前已应用。

显式生成测试复用 `create/send` 与 DSH 原生日志，不创建另一个执行循环。前置所有权/凭据RPC各15秒上限，create/send/history生成段60秒预算，取消最多3秒，总上限93秒；只有原生 `turn/end completed`、最终 `assistant/message` 和非空文本齐全才通过。结果绑定模型选择，配置变化使旧测试失效；设置 GET/Doctor 不进行付费生成。工具调用另由用户显式最小研究验收。研究工具的子进程测试依赖作为调用参数传递，不访问未在 `inject` 声明的 Cordis 服务。

Docker Doctor schema 1 的 volumes.state 显示 tmpfs，新增固定 volumes.logs=bind；只读投影不创建日志目录、不改变认证或生命周期，verified 仍取决于实际 inspect 的完整归属核验。

运行状态目录原 guard 的拒绝日志区分进入、打开FD、yield前后阶段，身份变化仅列字段名。
认证写入、健康探测、原校验顺序、异常类型/错误码和生命周期不变；取证不授权自动重试。
额外方向分类来自同一次已拒绝的before/current所有权对，不能据日志推断Cookie writer层或修复权限。

Docker `/state/runtime` 位于私有 `/state` tmpfs，正常严格 guard 创建和验证该叶。
正常容器与既有 control-preparer 都以 HostConfig.Tmpfs 核对必需 tmpfs；Engine 可省略
Mounts 的重复 tmpfs 条目，任何显式条目仍核对类型/来源/RW。临时 guest 仍只绑定产品 data，
其原四个私有 tmpfs profile、无网络/无端口、image/nonce/command 与精确 cleanup 合同不变。
每次启动/重启由原 auth_reset、认证交换、Popen/probe 顺序重新建立认证；停止容器丢弃状态。
删除写映射初始化与已有状态叶例外，不生成认证预写、空临时文件或持久 marker。
宿主日志子目录独立持久绑定，产品数据与凭据不迁移；Native 状态路径和协议保持原合同。

发布运行目录中的 `doc/docs` 名称不再导致运行实现漏包；生产依赖图、optional peer、
虚拟 Profile alias 搜索和 launcher 模块验证保持原链路，Node 加载回归验证派生资产完整性。

Docker staging 补齐固定 DSH 虚拟 Profile 锚点所需的根 `node_modules` optional peer 别名。
目标必须已属于生产图；原始完整闭包、派生 manifest 和 launcher 私有模块验证继续分别执行。

构建成功仍须退出码0及候选image身份验证。大输出不截断当成功；每路超过2MiB继续runtime_output_limit并精确终止本次进程树，其他metadata命令仍64KiB。

固定 Docker DSH 构建的原生 fs-ext 使用同 node-runtime stage 的完整本地 headers；builder
npm_config_nodedir=/usr/local 只影响编译，最终 runtime/协议/生命周期不继承该目录或 ENV。

DSH builder 的 pnpm 下载并发 8、单请求期限 120 秒只作用于现有 install 命令，
不改变默认重试、运行协议或生命周期，详见[安装指南](../../research-web-installation.md)。

research-tools 注册时不读取 ctx.spawnProcess getter；仅自有 data descriptor.value 为函数时
使用测试覆盖，否则用原 imported spawn。队列、终止、close 后释放和 poison 恢复合同保留；
这项注册回归不等同真实 fixed Cordis preset 加载或成功 session 创建，后者须独立实测。

Docker._environment仅在host CLI添加校验后的HTTP_PROXY/HTTPS_PROXY/NO_PROXY双大小写。
不安全值在status/Doctor/stop过滤并报告稳定warning；install/build返回docker_proxy_configuration_invalid，
避免静默直连。固定argv、隐式.env禁用及进程/容器归属检查保留；Native共享minimal环境不放宽。

_installation_start_scope 只从 manager 真实 lease/mkdir 取得创建事实，覆盖 DSH/runtime
build-lock/manifest；_start_installed(lease) 复核同一实际对象和根身份，执行正常安装门与端点
生命周期，不重复 acquire、不接受 bool/tuple 跳锁。no-start/失败/scope 退出清证明；既有根
不因 reinstall 成为 fresh。公开重执行仅进入 owned venv，不跨进程借 lease。

## 实际端点与公开生命周期

macOS 缺少目标 Native 记录而已有产品根时，可以只发现 OS 当前用户的标准产品根。
现有 `web_bootstrap` 私有 reader 认证该根的完整 Web/Runtime pair：同 project/data root、
准确 signature 与 PID/start/listener 集合；其他 checkout、稳定 PID 或端口可达都不足以授权。
只读桥报告当前事实；写入另在目标真实 LifecycleLock 中 pin 两个不同 canonical 私有根、
父目录与两份记录 FD，绑定同 controller/manager、作用域与精确 lease。每个控制写入、
spawn、restart、switch 选择或 rollback 前复查，记录/根/进程事实变化即拒绝，finally 关闭
FD 并清除观察；不会刷新变化后的基线或跨调用转移。Docker 不以 Native 安装为前置条件。
force restart 先验证此边界，再停止精确健康容器；未知 pair 不先停后拒绝。

该 scope 内启动 Native 时，Popen 句柄和本次 atomic state writer 的原 FD 一同保留；
Root pair 观察之外，own child 的记录 inode/metadata、实际 start、完整 argv 与准确 listener
另作调用内绑定。launcher→owned-listen 属于初始阶段，首次稳定 owned-listen 后仅比较原
基线；重复登记不能刷新。正常 stop 只有已验证的精确 child 才进入 stopping/stopped 阶段。
首次/第二次登记在 Popen 后丢锁时，由已有精确 child 句柄清理并保留原锁错误；记录/进程
变化后的普通 rollback 拒绝，不把恢复错误替代原 health 错误。

`EndpointStore(home)` 只在私有 `install/endpoints.json` 保存 schema 1 的 `records`，Native
含不同的 `web_port`/`runtime_port`，Docker 仅含宿主 `web_port`，各模式带独立 opaque revision。
`read(mode)` 缺失返回 `None`，纯只读；`publish(mode, web_port, runtime_port=None, expected=...)`
在已有私有锁中按该模式快照 CAS，保留另一模式并返回新快照。损坏/冲突不回落默认值。
`verify_facts()` 仅比较调用方已验证的端口，不证明 PID、监听者或容器归属。
`select_port(preferred, explicit=False, excluded=())` 首选指定端口，再有界 bind 回环 0 获得候选；
socket 关闭后没有预留保证，调用方仍须验证真实监听并有界重试。显式冲突拒绝自动换端口。

`ControlOriginTransaction(data_root, previous_origin, next_origin, quiescent=callback)` 要求调用方
持有生命周期锁。`prepare()` 在 exact `True` 静止证明下同时验证两份既有控制记录，再只修改 URL；
`commit()` 在启动成功后丢弃本事务标记，`rollback()` 在目标停止后恢复内存中的原始字节。
缺失记录留给正常 creator，origin 不变不写入。事务 helper 不启动或停止服务，不迁移业务数据。
公开 start/restart 使用这些接口；Native 健康条件仍包含准确 PID/argv/启动时间、监听者、
认证和页面 readiness，Docker 仍核对不可变镜像、安装/launch label、挂载与实际 Web mapping。
只读后备入口从相同端点或一致的旧 run-state 读取，不创建记录；畸形端点不回退默认值。
旧 state 的私有读取结果在单次 bootstrap 诊断内复用，避免瞬时替换被第二次读取掩盖。

Native/Docker 写生命周期共用原 `run/lifecycle.lock`，模式切换先由旧 public stop 持锁停止，
再获取同一把锁重新验证两模式及原 mode snapshot 后 CAS；持锁区不调用跨进程 public stop。
安装候选通过实际 `LifecycleLock.assert_held()` 对象复核进入内部启动，锁顺序固定为
lifecycle→短时 install/runtime 元数据锁。`EndpointStore.restore(mode, previous, expected=publication)`
只回滚本次仍为当前的发布；恢复已有端口生成新 revision，另一模式不变，首建失败可移除本模式记录。
候选 origin 事务保留到安装摘要和模式发布完成；失败在精确容器清理和静止证明后恢复。

Native 仅在本次日志窗口（保留 inode/偏移、上限64KiB）包含明确 bind 错误，原PID已退出、
新监听可证明不是同安装写者时分类为 bind race；不输出日志原文。Docker 仅解析有界CLI的
明确bind错误为稳定code。两者最多三次尝试；未知归属、协议/认证或回滚失败不重试。
已有停止Docker容器若需改host绑定，当前仍拒绝 `docker_stopped_port_conflict`，该分支未达完整设计验收。

origin commit 失败与健康失败共用精确清理：本次新建容器清除，本次启动的既有停止容器
在重新核对 ID、镜像、安装、挂载和 launch 身份后仅 stop，保留容器。静止证明先于端点 CAS
恢复与 origin 回滚。Native 缺失运行账本仍检查当前端口监听者；未知或同数据根监听者拒绝
分配和模式切换，只有可证明属于其他实例的监听允许避让。缺少 Native 环境时，既有数据根
的监听通过标准库 PID/argv/启动身份与监听复查核验；已证明的外来监听允许继续，未知或同根
写者失败关闭。受管 Docker 仍须独立通过容器身份、实际 mapping 与健康检查。补齐控制文件前先只读验证全部既有记录和一致 origin，MCP-only
动态 origin 不会被默认 DataHub origin 污染。Docker 安装摘要回滚同时核对发布写 FD 的身份
和精确字节，内容相同的新 inode 也保留并报告 recovery_unverified。

`listener_argv_is_foreign` 是既有标准库合同里的共享纯判定，供后备桥、Native 静止检查和
bind-race 分类使用；可识别 Web/DSH 命令缺少数据根证据时拒绝，不能从其他 checkout 推断不同
数据根，也不读取进程环境或配置。缺端点记录的既有根同时观察选定端口和旧默认8088/3081，
显式指定新端口不会绕过旧 writer。fresh 证明仅来自本次持有已验证 lease 时成功 mkdir 的
根 inode，既有根或 inode 替换不认领；证明在首个 spawn 前和 start finally 清除，不用于失败重试。

Native 从有效 fresh 证明捕获本次事务的 RAM-only 恢复基线：原 lease/根 inode、选定与旧默认
端口的监听集合，以及监听 PID/argv/启动身份；已捕获身份不刷新。spawn 后分配证明仍失效，
只有本次所有对象精确退出且基线未变，才可用于端点 CAS/origin 回滚。Popen 后、状态写入和
健康等待前记录 PID，内部清理不丢弃记录；已退出对象不重复停止。恢复未知时保留原始启动
错误，附加受控 recovery_issues/日志并保留 journal；该失败不得触发 bind 重试。

Native 模式切换桥复用服务管理器的 state/PID/精确 argv/启动时间/监听者事实链，停止调用同一
排他生命周期入口；状态查询不隔离或删除 stale/invalid 文件。Native 日志读取也复用精确进程
身份，并在输出前核对状态文件内容和 inode，不能凭命令行子串或重用的 PID 证明归属。

Docker supervisor 的启动顺序先准备 `/state/runtime` 与 `/run/rwb-secrets/private` 私有叶，
再清理本次认证状态、启动 DSH、探测并启动 Web。健康检查复用 `/state/runtime/auth.json`；
Web 每轮三项页面请求共用最多 3 秒，与独立健康检查默认预算一致；DSH 仍为 0.25 秒。
单轮预算取角色预算与剩余启动时间的较小值，角色启动 35 秒和停止 8 秒期限保持。
重启重新创建状态叶和认证，保留凭据内容并重新检查 owner/权限/alias，不修改 Native 状态路径。
固定缺失叶的准备先用保留父FD创建，再由原runtime_state_directory完整重pin；不会捕获
任意校验失败后无条件重试。data-root/logs使用相同首建顺序，自定义目录维持原严格create路径。
启动失败额外记录固定阶段、受控异常类别、数字 errno 与 runtime/web 已知退出码；
日志初始化前后使用同一安全字段，原失败退出及有界清理流程保持不变。
Runtime launcher 失败进一步区分 Node 版本、prepare、模块 fallback、Tabbit 包/adapter、配置写入和 exec 阶段，仍以原退出码 1 失败。

模式选择只决定进程部署：Native 由服务管理器管理两个宿主进程，Docker 由单容器 supervisor 管理 DSH/Web；研究提交、双 WebSocket、SSE、审批与恢复协议共用。`rwb runtime status --json` 读取当前模式与安装身份；`rwb runtime use docker|native` 在旧模式运行时要求 `--stop-current` 且必须验证旧实例归属。两模式不可并发写同一研究数据。Docker `rwb web status|doctor --json` 将稳定 `issues` 返回给操作者，状态或镜像归属不明不自动接管。Windows Docker 凭据 ACL 当前未通过可证安全边界，不作为已验收模式。

Docker 公开 start 与 Doctor 从私有接受摘要读取不可变 image ID，并检查依赖/Compose 合同及
容器实际 image ID；每次安装构建独立候选 tag，不能通过覆盖共享 tag 改变选定镜像。
候选启动仅由安装事务调用，公开 start 每次重新加载接受摘要。启动在默认 120 秒健康等待
预算内轮询（各 Docker 命令仍有独立超时），只在 DSH/Web 健康时返回成功；退出、unhealthy、
超时均失败。本次创建容器的回滚再次验证不可变 ID 和归属；失败回滚不删除既有容器。
up自身失败时，controller单次有界重枚举并校验一次性launch label及候选image；匹配才回滚，
未知归属保留并附加恢复未验证issue。原up错误始终保留，回滚失败不隐式二次删除。
显式离线 repair 可在候选启动前非 force 删除已再次验证的停止容器，但保留旧接受镜像、
摘要、数据及凭据；失败后可按仍匹配的旧合同重新创建旧实例。运行中的容器不会被自动停止或删除。
Doctor 保留 `dsh` 字段，区分健康 ready、摘要构建证据 build_verified、固定 commit 和宿主
不适用项，不填造宿主 DSH/Node 版本。Native `web status --json` 同样输出安全服务投影，
不会序列化日志路径，原有非 JSON 输出保持不变。

合同读取使用 dirfd/no-follow；祖先目录比较节点 identity（设备、inode、mode、uid/gid），
无关祖先 sibling 创建/删除不会被误判为合同替换。合同文件和直接父目录仍比较完整 metadata，
保留瞬时 rename/alias/restore 攻击检测；直接父目录发生内容活动仍保守失败关闭。

一键安装固定 DSH 来源、提交、pnpm 与构建闭包，但不改变消息受理、双 WebSocket、SSE、恢复、
审批或取消协议。安装失败不会启动候选 Runtime，也不会接管当前 3081/8088。
服务管理器在 spawn 前消费 Doctor 的安装 issue；只有安装状态 `ok` 才进入 3081/8088 生命周期。
启动生命周期由排他锁覆盖。管理器先有界读取私有 state，再核对 PID 存活、精确 argv、真实启动时间、
端口监听 PID 与带认证的 DSH `session/list`；任何一个事实无法确认都不会把 PID 或开放端口当作
owned/healthy。死 PID 与关闭端口形成可恢复 stale state；归属明确但不健康时先停止受管 Web，
再重建 DSH 与 Web；foreign/unknown 进程保持原状并返回稳定错误。非强制重启只使用现有认证材料
只读核对活动研究，核对失败即拒绝。Runtime auth 只在安全受管重建时更新。
Web 进程就绪还要求 Runtime API、首页 HTML 与主 ES 模块实际读取成功；随后才打开浏览器。
模型目录或凭据缺失只影响 `model_ready`，不改变 `product_ready` 与设置页可访问性。
这是一条进程前置门，不新增 Runtime 状态，也不改变会话恢复、幂等受理或活动研究重启门禁。
纯 `rwb web status` 不加载 DSH 启动功能图；固定提交来自轻量共享合同，构建闭包扫描仅由 Doctor
和安装诊断延迟加载，因此状态核对不会提前装配 Capability、MCP 或 DataHub Runtime。
安装事务会把已验证 DSH commit、closure SHA、文件数与 build mode 原子写入 Runtime build lock；
锁与当前受管 DSH 不一致时 Doctor 返回 `dsh_runtime_lock_mismatch`，启动不会进入 DSH 执行链。
首次启动会在任何 Tabbit/Profile 变更前由固定 DSH 模板创建 `web` Profile；Windows 用 CIM 核对
PID 命令行、用 PowerShell 探测 PID 存活并按受管进程树停止，POSIX 仍按进程组停止。pnpm 的 Windows
junction 和 POSIX symlink 都只在解析目标仍位于固定源码树时接受。这些平台分支不改变 Runtime 协议。
安装阶段的 Web import readiness 只验证 checkout 入口可加载，不执行 FastAPI lifespan、不启动框架
调度器、集成探测或 3081/8088；实际进程和健康状态仍只由 `rwb web start` 建立。
未安装环境中的顶层 `rwb --help` 仅输出标准库静态帮助，不进入 DSH 会话、认证、启动或恢复链；
`web start/restart/stop` 仍由原安装门拒绝。

Docker 构建先对完整 DSH checkout 执行相同的固定 remote、commit、pnpm 与完整构建闭包验证，
通过后才按已安装的 production dependency graph 和上游 package `files` 字段生成运行资产目录。
开发依赖、测试、fixture、文档、benchmark、website 和 Git 历史不会进入该目录；CLI、profile
模块、上游声明的运行资源及所需第三方生产依赖保留。pnpm 共享 hoist 别名仅在目标已属于所选生产图时保留，确保原生 addon 从跨包加载器基址仍能解析平台实现；不会通过 hoist 扩大开发依赖集合。`.rwb-dsh-runtime.json` 是构建时派生的
资产清单，不是第二份依赖配置：它记录原始固定来源和完整闭包事实，以及目录、普通文件、符号
链接的确定性清单和摘要。镜像 launcher 在创建运行状态前拒绝缺失、额外、篡改、越界链接、
alias、错误 schema 或超限清单，并继续把原始已验证闭包写入既有 build lock。仅镜像环境明确
设置 `RWB_DSH_STAGED=1` 时启用该路径；supervisor 只向 DSH launcher 子进程传递这个精确值。
未设置、空值、`0` 或其他值均不启用，Native 即使存在伪造或损坏的 staged 清单也忽略它，始终
执行原有 Git identity 和 `calculate_build_closure` 路径。最终镜像还以非 root
用户导入 Web、CLI、supervisor、healthcheck 和 iFinD HTTP 路径，避免宿主源码掩盖镜像漏包。

Framework Runtime 在 Research Web 生命周期内只启动和关闭一次，一个 `AsyncIOScheduler` 管理 Gold 与 Dollar 的分频采集。采集器按区块提交最后成功值；单源失败只更新该区块的 `checked_at`、`failure_code` 与 stale/partial 状态。

框架页面 Bot 仍由本运行时承载：`framework-explain` 是无工具的快照解释预设，用户显式触发的 `framework-verify` 才装配只读检索和公共数据工具。验证会话与解释会话分离，并绑定框架 slug、章节、缺口、方法版本和同一精确快照 revision；旧 revision 返回 409，Bot 不修改评分或快照，也没有第二个 Agent Runtime。

Phase 2A 的 Registry 读取仍不进入研究执行链。Phase 2B 只把用户已安装、探测、启用且授权的
MCP 工具加入专属 DSH：Host 生成 `mcp__{installation}__{tool}` 声明和 schema 哈希，DSH adapter
经私有 loopback 回调 Host；Host 每次复核安装版本、schema、会话授权、风险等级与人工审批后才由
官方 SDK 调用 MCP Server。安装/启停会等待当前研究归零并仅重启 DSH，失败恢复旧激活清单；Web
进程与既有提交、SSE、恢复和报告状态契约不变。
本地 PyPI 安装在当前解释器提供 pip 时保持原路径；uv 管理的精简环境没有 pip 时，仅使用宿主已存在
的 uv 执行等价离线安装，并把 uv 配置与缓存限制在 staging 内。两条路径都不使用 shell，不改变
已解析的 `--no-index`、完整哈希、无依赖和目标目录约束；没有 pip 和 uv 时关闭失败。
staging、安装 payload、清单与确认令牌重放目录在 Windows 上校验真实目录、符号链接和重解析点，
但不把 POSIX `st_mode` 投影解释为 ACL；POSIX 继续校验 group/other mode 与当前用户所有权。

Phase 2C 的 Automation 只从锁定的 Skill、普通 Workflow 或报告 Workflow 版本创建独立 Claw
会话。APScheduler 仅持有下一次内存触发，原子索引保存任务与 Run 事实；启动时只合并最近一次遗漏，
重叠触发记录 `skipped_overlap`，无法确认的旧会话记录 `interrupted`。研究失败不自动重试，手动
重试生成带 `retry_of` 的新 Run。无人值守 MCP 调用还须通过任务锁定、只读、明确允许和 schema
哈希复核，不能绕过会话授权或高风险人工审批。

## 集成探测与 DataHub 工具

Research Web Host 启动时先恢复 `IntegrationCoordinator` 的安全快照，再异步运行启动探测批次；
用户在设置页执行“重新检测全部”时创建独立手动批次。协调器只编排既有 DataHub Provider、本机发现
和 Tabbit 状态，不进入 DSH 的研究事件链，也不改变 Automation 会话或恢复语义。

Runtime 常驻 15 个品牌无关 DataHub 工具。每次业务查询由 Broker 按最新配置、授权、探测和 Provider
状态选源；缺少可调用来源时返回明确错误。这个动态路由取代启动时裁剪 `enabledTools` 的旧行为，
但不放宽来源白名单、会话归属、参数校验、取消或禁止回退语义。

## 持久化本地启动边界

`rwb web start|status|stop|restart` 由 `app/research_web/service_manager.py` 管理专属 DSH 3081 与 Web 8088。默认 DSH 源码是 `~/.research-workbench/dsh-source/` 中经过固定提交构建的项目私有副本，避免修改或依赖用户其他 DSH 实例使用的工作树；必要时可用 `RESEARCH_DSH_SOURCE` 显式覆盖。管理器把 PID、进程组、启动命令指纹、最终 Node CLI/overlay 归属签名、项目路径和日志位置写入 `~/.research-workbench/`。新版 Typert Gateway 启动后，管理器从受限日志尾部提取一次性启动令牌，换取 `dsh-auth-*` Cookie，并把 authority、工作目录、固定提交与版本原子写入 `runtime/auth.json`；POSIX 要求文件权限 `0600`，Windows 则拒绝重解析点并核对普通文件、单硬链接、大小及打开前后身份，不把 POSIX mode bit 当作 ACL 证明。健康检查以该 Cookie 调用真实 `session/list`，随后才启动 FastAPI 并检查 `/api/research/runtime`。重复启动是幂等操作；失败回滚只处理本次创建且归属签名匹配的进程，既有 3080 不在其所有权范围内。普通重启发现活动研究时拒绝执行，只有显式 `--force` 才允许中断。备用验收可为管理器指定独立端口，不复用生产状态目录。

`runtime/auth.json` 由客户端和服务管理器通过 `runtime_auth.py` 读取。读取器限制 4 KiB，拒绝非普通文件、硬链接、符号链接、Windows 重解析点及打开前后身份变化；POSIX 要求 group/other 无权限，Windows 不把 `st_mode` 的 POSIX 投影解释为 ACL。

服务管理器创建数据、运行状态和日志目录时采用相同的平台边界：所有平台拒绝非目录、符号链接与 Windows 重解析点，仅 POSIX 使用 group/other mode 位判断目录权限；Windows 不以该投影替代 ACL 结论。

断电或系统重启会结束后台进程，本轮没有安装开机登录项；恢复时重新执行 `rwb web start`。如果状态文件来自先前 checkout 或命令版本，管理器只有在记录的 PID 已确认不存在时才移除该 stale 状态并重建；PID 仍存在、状态损坏或归属无法确认时继续失败关闭，绝不接管或终止未知进程。

研究协议本身仍是下述 DSH RPC、Remote 复用流和 Web SSE 投影。Workbench 兼容桥把既有白名单方法映射到新版斜杠端点与 `{payload:{args}}` 信封；Cookie 只进入 HTTP/WS Header，不进入请求正文、会话记录或浏览器接口。服务管理器只负责本机进程生命周期，不创建第二套研究运行时，也不改变会话、审批或恢复语义。

## Tabbit 实时页面上下文

设置页分别控制浏览器自动化和 Tabbit `web_fetch` 接管。前者默认开启、后者默认关闭；打开 `web_fetch` 必须同时打开浏览器。多实例环境要求选择 16 位实例 ID。配置变更标记 `restart_required=true`，活动研究期间沿用既有重启门禁并保留待应用配置。

Tabbit 配置和 Runtime 锁文件固定按 UTF-8 读写。POSIX 继续使用文件权限位；Windows 在临时文件句柄关闭后执行原子替换并跳过不受支持的目录 `fsync`。供应归档文件名按 tar 的 POSIX 语义比较，adapter 入口在 overlay 中统一为正斜杠。

用户首次展开 `@` 标签菜单时，BFF 才为当前会话申请页面访问授权并读取所选实例的可 claim HTTP(S) 标签页；不会后台预取。消息最多携带 8 个有序 `{tab_id, instance_id}` 引用，且必须带实时接管二次确认。发送前 BFF 重新向 Runtime 读取清单并校验标签、实例、协议及可用状态，不信任浏览器提交的标题或 URL。

`runtime/tabbit-adapter.mjs` 只使用官方插件提供的唯一 `ctx.tabbit` 执行器，以 `rwb-mention-<session4>-<request8>` 原子 claim 所选标签，并在一次只读求值中按选择顺序读取当前 DOM。每页最多 60,000 字符、总计 120,000 字符；总量超限时按标签数公平截断并在折叠上下文中标记。无论成功或失败都在 `finally` 调用 `finishTask(..., {keep:true})`，标签保持打开，但分组可能改变。claim、求值或释放任一失败都会阻止消息提交并保留前端草稿。

正文仅写入 DSH 内存 token：绑定当前会话、只能消费一次、10 分钟过期。消息正文只携带短标记，`agent/pre-step` 再将内容注入默认折叠的插件上下文。会话授权后，声明为 `read_only:true` 的浏览器调用可自动执行；缺失或为 `false` 的调用逐次进入原生审批。该声明来自调用方，不能静态证明 Playwright 代码无写操作，系统提示明确禁止把写操作伪装为只读。日志只记录会话 ID、数量、阶段、耗时和稳定错误码，不记录标题、URL、正文或执行代码。

`GET/PUT /api/research/runtime/tabbit` 提供安全状态与配置；`POST .../tabbit-access` 管理本会话授权；`GET .../tabbit-tabs` 提供候选清单。Runtime 状态只允许 `ready | disabled | launcher_missing | browser_offline | unsupported_version | instance_selection_required | error`。安装器显式禁用；缺失、离线或版本过低时只返回诊断和官方手动安装指引。

`ResearchService` 同时持有进程内本机集成诊断管理器，并在服务关闭时取消未完成的发现或验证任务。发现只读取宿主事实；真实验证必须由设置页显式触发，目标限于 Excel、Word、PowerPoint 与 Wind Excel，并在独立进程组及对应 Office 容器的受管临时目录内执行。PowerPoint 保存后按随机文件名重新绑定本轮对象；Wind 通过 LaunchServices 启动或复用已登录的 Excel 应用，只创建并关闭验证器独占的空白工作簿，绝不把用户既有 Excel 进程登记为清理目标。该管理器只服务设置页的安全主机事实投影，不进入 DSH 会话、工具注册、研究执行或事件恢复链。

`app/research_web/operations.py` 只读取上述原生历史、当前投影和服务管理器状态，生成不含问题正文、审批参数或凭据的监控结果。它不参与提交、恢复或取消；历史事件未提供 usage 时返回未知，不以零替代。研究台通过 `workbench.py` 创建目标 DSH 会话后，后续提交仍完全遵守本页协议。

## 提交与流式

1. `POST /api/research/sessions` 创建真实 DSH 会话和产品归属目录。
2. `POST /api/research/sessions/{sid}/messages` 必须带 `Idempotency-Key`。BFF 先检查连接、运行中任务、附件归属、能力、交付要求和 Tabbit 实时引用；存在标签页时完成再次校验与单次提取后，才由兼容桥调用原生 `session/prompt`，每次请求生成独立 `requestId`。
3. HTTP 202 只表示受理。传输超时不是模型执行超时，且不能自动重发可能已受理的问题。
4. DSH Remote 的 `$events` 与 `session/control` 复用流分别提供 API 事件和控制基线；兼容桥把 `api-session/*`、waterfall 审批／提问及取消事件投影为稳定 BFF 信封。Web 通过 `GET .../{sid}/events` 接收 `snapshot` 或 `runtime_error`，心跳不代表执行进度。
5. 刷新读取同一会话。历史通过 `session/follow` 的 opening snapshot 与 `session/page` 分页恢复，并结合 `session/list` 和 `subagents/list` 恢复真实状态。恢复不另建会话、不重提消息。

会话删除使用 `DELETE /api/research/sessions/{sid}` 做产品内软删除，先写入墓碑并保留 DSH 原生日志与 Workbench 文件；30 天内可通过 `POST /api/research/sessions/{sid}/restore` 恢复。用户主动永久删除，或服务启动／每 6 小时在线任务发现墓碑到期时，BFF 调用 DSH `session/delete`。级联子会话删除由 Session Controller 负责；只有 DSH 明确返回包含根会话 ID 的 `deletedSessionIds`，或明确返回 `session/not-found` 证明原生记录已不存在后，才清理 Workbench 会话目录与索引。其他失败保留墓碑并继续重试，不能把隐藏状态误报为永久删除。所有操作都校验会话归属，不能用于发现、修改或删除其他 DSH 实例的会话。

相同键与相同内容返回原受理收据；同键换内容拒绝。受理结果未知时先查历史中的本任务标记，不能以 UI 重试按钮无限重复执行。

## 运行状态（不是 Workflow 节点状态）

| 状态 | 来源或条件 | 用户可理解的含义 |
|---|---|---|
| `idle` | 原生日志未出现当前执行 | 可准备新问题 |
| `running` | 父回合或真实子 Agent 运行 | 研究仍在进行 |
| `awaiting_approval` | 当前归属内存在原生审批请求 | 等待用户允许或拒绝 |
| `completed` | 原生 `turn/end` completed 且无子任务运行 | 回合结束，文件另行检查 |
| `cancelled` | 原生 aborted | 已记录取消结果，不等于发送取消请求时即结束 |
| `failed` | 原生 error 或受理/执行错误 | 错误必须展示 |
| `interrupted` | interrupted 或历史运行但原生已不运行 | 无正常完成证据；交付仍pending时不能直接发送 |
| `blocked` | 原生 blocked | 原生执行阻塞 |
| `incomplete` | 原生 max-tokens | 本轮未完整执行 |
| `disconnected` | 任一下行通道断开 | 当前状态未知，不能伪报完成 |

`can_cancel` 根据父/子 Agent 的真实运行状态计算。工具失败保留活动级错误，并不必然将整轮改为 failed。子任务历史当前读取最近 100 条；若截断则明确标记，用量和耗时不冒充全量。

## 审批、问题与停止

原生审批通过 `POST .../{sid}/approvals/{aid}` 响应 approve/deny，校验待审批 ID 与会话归属。批准允许原工具继续；拒绝不得发起相应外部请求。原生问题经 `questions/{qid}` 回答，保留单选/多选语义。

停止调用父 `session.cancel` 与本会话真实子 Agent 的 `subagent.interrupt`。请求受理后仍等待原生状态确认。脚本取消需终止实际子进程，不能仅改变前端标签。

已受理且非运行、交付仍pending时，`can_recheck_stop` 提供「重新核对停止」。停止意图绑定当前任务与幂等键；真实受理后，完整历史精确当前标记、唯一空闲父任务、全部空闲子任务及可用父连接、双事件通道和无待处理审批/提问缺一不可。若仅缺原生终止事件，显示failed/结果未确认，独立交付verification_failed；不补造turn/end、不运行解析器。同键不重发，新键可继续，持久化后可冷恢复。证据不全保持等待，普通原生aborted仍正常显示cancelled。

DSH 不可用时明确报错，无 LangGraph、固定答案或第二 Supervisor 回退。已有资料和能力目录的只读可用性与运行能力分开。

本机 Office/Wind 显式验证证据在 TTL 截止时刻即失效；`verification_ttl_seconds=0` 不允许同一时钟刻度继续复用。Workbook 单阶段 timeout 显式不超过 180 秒总预算减 10 秒协调余量，避免平台浮点舍入越界。POSIX 进程组与 Windows `taskkill /T /F` 由各自平台测试独立覆盖。

## 代码与测试

关键来源：`runtime_auth.py`、`client.py`、`service.py`、`projection.py`、`ui/core.mjs`。协议、认证文件与投影回归位于 `tests/research_web/`，前端幂等、路由竞态、刷新、SSE 清理测试位于 `tests/javascript/research_web_ui.test.mjs`。真实模型验收另记，不以传输模拟代替。

MCP Runtime 与 Automation 默认启用后仍按原有探测、授权、版本锁和风险策略运行；默认启用不等于自动安装 Server、自动授予工具或自动创建任务。显式环境开关关闭时继续失败关闭。

2026-09-11 的格式基线维护不改变本机验证 TTL、状态转换、进程清理或 Runtime 调用路径。

CLI 启动前固定项目根与 Node 选择：Codex Desktop 优先使用 bundled Node，其他宿主使用 `RESEARCH_NODE_BINARY` 或 `PATH`。所选绝对路径进入既有进程命令指纹，因此后续 `status/stop/restart` 仍按同一归属失败关闭。

Method 请求在提交前按 `required > user-selected > recommended > model-supplemented` 解析，去重后
最多三个，并锁定产品版本、语义版本、原生名称和来源。DSH 原生加载包装后，实际采用须调用
`rwb_record_method_use`；本轮收据保存提交前的追踪偏移，旧轮记录不能满足新轮完成检查。必需或
用户选择缺记录时完成状态转为失败，推荐或模型补选缺记录时保留结果并降级标记。

## 2026-09-23 重启与刷新稳定性回执

非强制 `rwb web restart` 先通过已认证 DSH 的 `session/list` 获取活动事实；任一会话仍在运行即拒绝
重启，只有显式 `--force` 才进入既有中断路径。会话目录恢复仍先读取一次 `session.list`，再对每个
合格父会话读取 `subagent.list`，50 个父会话的扇出并发上限为 8。仅已创建、存储为 `running`、原生
父会话空闲且子会话均空闲的陈旧行才进入 `detail()` 恢复；恢复复用不超过 8 的上限并保留目录顺序。
未创建、原生运行或子会话运行的行绝不恢复。任一读取、恢复异常或调用方取消都会取消并等待未完成任务
收敛后再传播原异常，避免遗留后台请求。本轮只收紧重启授权和目录读取界限，不改变 DSH、SSE、会话状态、
Automation 或交付拓扑。

## 2026-09-28 Windows 停止升级回执

Windows 受管进程停止现在允许非强制 `taskkill /T` 失败后进入既有等待与 `/F` 升级；只有已通过状态文件、
PID 与命令签名归属核对的进程可进入该路径，强制失败仍返回错误。DSH 会话、SSE、恢复、取消与研究状态
协议均未改变。

## 独立真实验收的最小调用控制

本机受管启动器可接收非秘密 `RESEARCH_ACCEPTANCE_CONTROL` JSON，仅在其中 `dataHome` 与当前规范化目录精确相同且 DSH 端口不是生产默认3081时启用。字段仅为 `dataHome`、`modelCalls`（1—6整数）及固定公开工具 `datahub_get_fund_data`（eastmoney_fund/nav/000001/limit1，禁止其他源、回退或刷新）；错误配置失败关闭，不打印参数内容。该模式沿原产品overlay和正式research-web preset工作，不替换固定DSH。

现有最终guard在原生全局llm/stream seam同步预留计数：跨会话/turn共用实例上限，达到上限后不进入适配器；只允许纯文本，拒绝图片/文件/音频，避免附件回退产生额外供应商请求。原重试插件禁用、DeepSeek原retryPolicy.maxRetries=0。工具veto仅允许所选公开DataHub工具执行一次，拒绝子代理、脚本、其他数据工具或第二次执行；原guard权限仍适用。仅记录序号与稳定错误码，无Prompt、请求体、认证值或秘密哈希。

这是单次独立验收的进程内控制，不是用户配额或持久预算系统。退出/重启不能作为补额度手段；调用方仍须维持该轮真实请求总账。默认不启用，既有生产、日常研究、provider/Keychain语义不改变。达到限制只能报告未完成，不能自动重试。合同及固定DSH无网络合成验证与真实供应商验收分别记证据。

模型启动preload的认证文件绑定已验证的RWB_RUNTIME_STATE，与data/runtime/home分离；authority、cwd、固定源码commit和所属Runtime PID共同绑定临时bootstrap。stdout/stderr保持脱敏，所属supervisor只在启动阶段读取私有handoff，独立healthcheck不交换Cookie、不写控制文件。

认证bootstrap的source_commit与能力目录从同一runtimes/research_web.json读取，避免旧标识残留。新版Profile解析由固定DSH原生解析表提供，不再调用已移除的healProfilesModuleFallback；表为空、非法或路径越界时拒绝启动。

## 设置闭环阶段3：当前能力范围

声明式data_requirements在提交前、Skill模型工具加载、/skill用户注入、子任务和后续查询中复用当前范围。预检不登记载入；只有最终成功载入或已校验的原生注入才登记固定版本，失败/未知登记阻断后续执行。硬依赖不满足拒绝；可选依赖缺失返回省略章节。


## 单一兼容模型连接

兼容模型沿既有create/send及同一DSH loop。正常owned overlay挂载文本/流式LlmAdapter，连接/凭据绑定公共revision，读取前后及发出请求前检查；无Key不访问秘密，停止/冷启动后从本实例已保存连接恢复。既有会话保留选模，地址/协议/认证方式改变时下一提交拒绝改投；活动父/子研究阻止设置修改。

研究脚本仍要求严格沙箱，当前仅 macOS Native 有实现。非 Mac/Docker 明确 unsupported；平台能力声明与任务验收分开，不用健康检查推导研究任务可执行。

生产包图 staging 必须可实际加载已发布 runtime；文件 manifest 自洽不证明依赖完整。YAML dist/doc 属于代码载荷，必须由 Node 导入回归与真实 DSH 启动验证。

历史 Docker Desktop 属性同步方案未能保证状态 bind 完整启动，已在私有 tmpfs 修复中撤回。
当前状态叶由原严格 guard 创建；固定凭据和产品日志 bind 叶仍仅使用既有两阶段首建。
没有属性修复、chmod/chown 或新增 owner 例外，自定义目录维持原严格边界。

Docker Engine 可只在 `HostConfig.Tmpfs` 中表示 tmpfs，不将它们列入 `Mounts`；控制器兼容列表完全省略或完整三项表示，仍强制 HostConfig 的固定路径、UID/GID、权限和安全选项。部分、重复、别名或额外挂载均拒绝。

macOS Docker 停止后回环端口的非监听绑定保留可能延迟释放；默认最多等待120秒，其余宿主默认10秒，显式等待参数保持。仍必须实际释放IPv4/IPv6绑定，超时失败关闭；不使用SO_REUSEADDR或只做连接探测来绕过占用。具体内核延迟原因未独立证实。

model-authorize/model-attempts/model-terminate 已接入 CLI；未知控制回执保留 UUID、阻止启动并允许同参数重放。终止可能已发送的尝试只标记 abandoned，不退款；迟到回执可 settled/received，业务结果仍受原有 owner/claim 条件保护。记录/日志失败不丢原 UUID。

Native 定价加载支持私有当日记录；坏记录不回退包内文件。日期/指纹在处理、预留和派发前重查，变更后 blocked_model，重启加载新值。缓存身份和累计授权不随价格改变。

真实两事件Host/Node/PG浏览器读取已由隔离凭据和离线研究客户端验收；未运行正式DSH研究。原任务额度仍4/1417/659，独立Node经自身Manager归属检查停止，來源开关恢复；Host退出不等于Hot进程退出。

Hot内部持久简报使用现有签名传输与controller owner fence；准备资料只读，发布事务复验UUID缓存和expectedVersion，重启重放不多生成版本。迁移15要求先停Hot/setup，普通worker不获简报写权限；不新建调度器或研究执行。

HotManager简报创建经过现有控制事务桥，HTTP显式动作/Origin门保持；列表、详情和Markdown只读且不启动服务。导出维持同owner/reader/版本和完整哈希，Host超时仍保持容量至真实线程结束。Node不新建简报调度器或研究运行；DOCX与正式handoff待接入。

等待只覆盖已经由容器 inspect 验证的宿主 Web 映射；DSH 3081 为容器内部端口，不能将
不同根 Native 的宿主监听纳入 Docker 停止等待。外来占用者保持原样，不停止或接管。
停止前先沿原只读 status 校验映射，Legacy 无端点记录时恢复实际宿主端口；固定本次
ID/image 与端口观察，停止前及每轮等待重新核验。错误或变化的映射在 stop 前拒绝，
不借动态端口重新认领容器，不写入模式或端点记录。

## 本机验证与研究 Runtime 边界

Office受控自动验证在Host既有批次内串行执行，与DSH研究循环分离；同意仅限所属实例的三款Office，不向模型或厂商发送请求。读取本机状态和证据到期刷新不创建研究任务；取消/冷启动不重放旧验证。协议与进程管理保持原合同，详见[协调器](09-integration-coordinator.md)。


## 研究情报统一入口 · 2026-10-12

主导航统一为“研究情报”，本地热点与事件在 `#/intel/hot`，现有外部8栏目仍在 `#/intel/*`。旧 `#/workbench/hot` 链接保留视图/事件参数后转入本地页。两类页面共用栏目导航、主题与Host；本地版本证据和Golddata外部只读数据保持身份与覆盖来源区分，外部读取不写Hot、领取任务或调用模型。Hot未启用时，外部栏目与设置继续可用。

恢复的DOCX切片通过 `GET /api/research/hot/briefs/{brief_id}/docx?version=<固定版本>` 从签名/哈希核对的冻结输入生成并保留私有产物，复用报告DOCX生成器；导出不创建会话、不调用模型、不外发。该路径尚需完整产品/恢复验收，局部测试不代表研究闭环完成。


Hot研究交接的原件读取已进入既有reader签名桥；独立Node不创建DSH会话，Host只重建固定版本证据。正常ResearchService/DSH受理、Hot run→session映射和未知受理恢复尚待接入，当前读取成功不能被显示为研究已经启动。


Hot交接准备已接入ResearchService与DataHub：PG先预留session ID，Host保留匹配归属并查询DSH已有会话；创建回执丢失时复用已存在会话，未知缺席保持待恢复。原件快照私有目录提交后CAS绑定dataset/manifest hash。snapshot_ready仅表示研究草稿与证据已准备，不表示session.prompt已受理。execution_starting/execution_outcome_unknown的恢复须查询既有Delivery/原生历史，禁止自动重发；本轮未新增正式付费执行。


2026-10-13续跑：native_admission在既有capability/model工具许可后验证Hot冻结快照归属并提供单dataset只读路径；Seatbelt不开放datasets父目录、写入或网络。真实原会话读取已验证，模型报告仍未完成。

当前固定 DSH 的 tool/result 使用 role=tool 消息、顶层 toolCallId/isError 和直接 content；投影兼容旧嵌套 tool-result，同时按脚本 JSON outcome 判定成功/失败。真实验收曾发现旧解析将成功脚本读为空而误报，现通过原生历史重放与协议回归核对，保留真实失败活动。

## 历史子会话模式兼容 · 2026-10-13

列表及父详情复用 activityOnly=True 查询，unknown模式只提供已验证的running活动状态。未知模式不会被猜成one-shot/continuable，子历史保留不可用提示；父列表和父历史继续可读，严格控制查询保持缺省路径。

POSIX运行记录读取的共享祖先在stat/open与退出复查均采用dev/inode/mode及UID/GID，
允许无关sibling目录变化；直接私有parent与记录文件保留完整元数据、单链接及权限校验。
目录替换/alias/owner或mode变化仍拒绝；私有UID异常继续unsafe_path，不改变格式或端点。

PR96 与既有 Fernet 模型桥共用唯一私有 stdio 接口；默认 `native-keychain`、常规 staged `docker-encrypted-file` 语义保留，管理器仅显式绑定 `docker-encrypted` 选择 AES-GCM。两种 Docker 格式与主密钥布局独立，混合绑定或外来格式失败关闭，不转换密文、不删除旧 Key、不回退。四操作与固定 ref 保持；来源如实区分，configured/Doctor 不证明真实生成。

AES 绑定先验证已有树及两个固定 ref 的完整认证，不允许外来实例记录被当前 namespace 遮蔽；resolve/describe/set/unset 与原活动守卫保持。

## 框架嵌入核心闭环 · 2026-10-14

Gold／Dollar 看板确认宿主已读 snapshot revision 后，Bot 才沿原解释／显式深度验证 preset 请求 DSH；已有会话仍绑定旧 revision，刷新不改变绑定。静态九项拒绝框架 Bot，不生成第二套执行链。

会话列表和详情把本机持有的原生未决question按ownerSessionId投影为waiting_input（优先于运行标记），解除提问后回到原生运行状态；不改调度、取消能力或执行器。浏览器查看完成标记仅关联该会话updated_at，未查看显示圆环，查看后隐藏。
## 网关静态部署的运行时边界

显式 `apply-ui` 要求产品等于当前 primary，工具独立验收。沿用准入锁、空闲核验、出生栅栏和 HTTP 排空；只对已识别网关发送原有优雅停止信号，不切换或重启研究 Web/DSH。发信号后的未完成事务保留 journal 并报告 recovery_required。

## 命名模型连接

Host 非秘密 model_profiles 索引记录 items、active_id 和各协议当前路由，旧账号固定绑定 legacy profile；DSH 的两个逻辑 ref 不改变，由产品凭据桥按索引解析为独立物理账号。会话创建与续研验证 model_profile_id；旧会话按 legacy 身份处理。research_task 日程在新建/显式修改研究定义时锁定 profile，旧日程维持 legacy；create 持同一服务锁再次检查，避免切换竞态。运行/断流、未知受理、活动子研究及未完成交付阻止切换；历史子研究只用 activityOnly 的 inactive 判定，不要求恢复其历史执行模式。

Skill/Workflow/Report Workflow 自动化原本没有批准的服务商身份字段，继续保留其既有执行时默认模型语义；本次不补造历史模型审批。profile 身份固定专用于已声明 provider/model 的 research_task。

2026-10-23 资产v6封闭部署配置绑定常驻c1a260fa与已合并PR197产品eac68068；仅此配置使用固定ZIP日志读取器，旧恢复合同和严格全账号保全不变。详见[部署合同](../../research-web-gateway-upgrade.md#资产筹码与精炼布局固定部署v6)。

## 2026-10-23：长期研究档案与机会预警

跨会话研究使用 Host 冻结档案版本、hash 与证据句柄，交接只准备草稿。仅用户实际提交的 Prompt 结构化字段 `dossier_handoff_id` 可将 receipt 绑定目标 sid；浏览、@ 候选预创建会话、上传和普通 create-session 均不绑定，草稿文本本身不授予权限。来源范围不得扩张，读取继续复核原件及当前授权，再进入唯一 DSH 和原 Host 质量链。A股跟踪默认关闭，既有 Automation 只执行冻结材料的确定性重查，不采集或调用模型；详见[研究交接](../../research-web-dossiers.md#http-与研究交接)及[持续跟踪](../../research-web-dossier-scans.md#持续跟踪)。


2026-10-23：v7沿原运行时、会话和模型配置；来源查询/市场inflight活动或未知延后切换，不调用模型或启动第二研究引擎。



档案固定部署使用 `apply-dossiers`／`reviewed-research-dossiers-v1`：前版固定已核验 `5343e18d9f203a87f2d958218e4288afa527711f`，产品固定包含 PR209／PR212／PR213 的已合并主线 `1780064b712afb61ff18f2f1811650fc31fd3038`。复用原 version4 维护锁、BirthFence、Native／RuntimePool／市场及 DataHub 空闲检查、全账号64MiB业务索引与档案保全和恢复；依赖锁、DSH、自动兼容清单、凭据及付费调用保持原合同。源码、CI、实际服务切换和登录后跨会话验收分别留证，未执行的层级不标通过。

今日发现组合固定Native部署复用既有v4操作员、BirthFence与全账号索引/档案/模型保全，新增closed profile及同一idle内离线零后台任务门；不改变本模块既有运行节点、HTTP/数据schema、Docker/平台执行职责或DSH质量判据。新mode每次首次/恢复均拒绝启用自动化/周报日程、活动或未知执行，不通过启动账号后端取得空闲证明。Mac本机、操作员CI与实际切换/认证页面分别取证，Windows/Linux产品状态保持未执行；详见research-web-gateway-upgrade.md的今日发现组合固定部署。
