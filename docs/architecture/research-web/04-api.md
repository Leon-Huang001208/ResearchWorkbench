# Research Web 接口清单

apply-assets-v8仅为原Native操作员的封闭CLI分派，无新增HTTP、账号权限或任意SHA参数。固定前版b4384470和包含PR216/217/219的真实合并组合；旧v1-v7及其它固定入口保持，实际切换仍需全部资格、空闲与保全证据。

`POST /api/research/report-workflows/{workflow_id}/historical-acceptance-runs` 只为已发布华安Wind Excel周报创建非正式验收Run，重查当前绑定主管理员资格；普通`/runs`默认formal。用途由Host固定并冻结，不接受模型或snapshot字段提升；重试/恢复保持，未知提交不得重复。该入口不修改正式稿和日程权限。

资产图表“幅”合并显示复用既有历史响应，不新增 HTTP、查询参数或字段，不修改观察/历史任务与冻结合同；百分比及价差继续在前端按上一同周期收盘计算。

`apply-etf-weekly-v2` 为封闭操作员CLI分派，前版5343e18d、组合产品56709a8d，不新增HTTP、账号权限或任意目标参数。v1入口保留；新增产品须在最终验证后明确授权部署，周报日程关闭。

`apply-etf-weekly` 为固定Native操作员CLI模式，前版5343e18d、产品988046d；不增加HTTP端点、账号权限或任意目标覆盖。实际执行须另行明确授权，并沿原version4保全/恢复；不触发周报生产或启用日程。

## 今日发现接口（2026-10-23）

新增统一前缀/api/research/discovery：GET feed、handoffs、requests/{request_id}、handoffs/{handoff_id}、tracks；POST prepare、handoffs/{handoff_id}/execute、tracks、tracks/{track_id}/enable与disable。11条声明由真实routes.py和API Atlas逐项登记，新增GET /selection（feed_id/theme_id/horizon）只从当前用户owned预览选择读取完整详情、返回独立scope feed，不写Store/创建会话/调用模型、不污染首页；网关另有GET /api/server/discovery-tracking-status只读当前认证账号恢复状态，不返回其他用户或启动后端。写操作要求原同源认证及X-Research-User-Action:?1；选择只用Host登记ID，不接收客户端正文/URL/归属。GET恢复不创建/配置/发送DSH；启停验证定义版本，泛用Automation接口仍受tenant拒绝。请求/响应及失败状态见[完整合同](../../research-web-discovery.md)。


2026-10-23：`apply-market-terminal`是封闭本机操作员命令，不新增HTTP或租户权限。主实例与网关仍通过原认证／租户／维护门，GET市场空闲见证不采集上游；组合预览／确认和现有研究、资讯、周报接口合同保持。固定候选、原三CI和实际切换另证，见[部署合同](../../research-web-gateway-upgrade.md#全市场终端固定部署2026-10-23)。

## 筹码输入与偏好可选字段（2026-10-23）

原POST history-jobs正文可选严格布尔 `include_chip_inputs`，缺省false，仅固定tinysoft可设true；响应在true时带同名字段。重复幂等键必须保留语义，retry_of必须保留原旗标、截止、范围、来源和复权。进度phase=chip_inputs时带chip_batches_total/completed。没有新增HTTP路径；取消、排空、归属和冻结检查保持。

原GET/PUT chart-preferences增可选chip_settings对象；旧panels正文仍兼容且保留已有设置。只接受algorithm(triangle/uniform)、decay(0–10)、peakUpperPct/peakLowerPct(0–100)、showPeak/overlayEnabled(布尔)、ageShort/ageMiddle/ageLong/overlayDays(1–10000整数)、visibleAges(唯一合法枚举)；龄阈值严格递增。非法/超大JSON整数返回校验错误，不产生500或隐式转换。


资产v5索引修复只改变Native操作员的内部verify_primary读取绑定，不新增HTTP、CLI参数、账号权限或请求格式；合流PR188后API inventory为321声明／318唯一接口，新增路径按研究仓原合同保留。64 MiB业务读取与1 MB部署元数据明确分开，旧profile不变。阅读页使用已提交组合产品88ef3817，v5一行读取修复另指8f2cb39a；当前PAYLOAD为88ef、PREVIOUS仍51f09。旧a114三CI全PASS不认证新组合，文档与本机结果也不表示常驻已切换。

资产交互v5（2026-10-22）增加的是操作员CLI封闭命令apply-assets-v5，不新增HTTP、请求参数或权限入口。原目录search、区块load、历史as_of及账号／会话归属合同保持，API inventory仍为318条源码声明／315个唯一接口；Atlas只将源码链接固定到PR185真实merge9bc4。最终部署资格与固定旧51f09的恢复见[操作合同](../../research-web-gateway-upgrade.md#资产交互与数据-v5-2026-10-22)，HTTP或产品CI成功不表示v5已切换。

行情缺口部署使用封闭 `reviewed-market-gaps-v1` / `apply-market-gaps`：旧版固定 `99d3ee34977c47189a5638207c109a555f52a687`，产品源码检查点固定 `9faeeca3003a912ca75799fb27b635ba1bb87a1a`。检查点为本轮产品修复的不可变祖先，最终操作员/产品组合目标仍必须最新已合并 master、独立评审和原三项 exact-tree CI（含 Mac 干净安装）合格；不把检查点冒充合并版本。复用原 version4 保全/恢复，并在原维护锁内额外核对 MarketService 的 inflight 明确为空；未知或正在采集时不切换。旧 profile、controller/evidence/网关模块字节及模型/账号权限保持，无新部署节点、HTTP或依赖，原图准确。

全市场缺口修复（2026-10-22）：股票列表增加东财官网 f292 交易状态；同身份、同日单股接口有界补取空成交额与停牌参考价。停牌、未上市单列，不计平盘；已上市股票成交额全部覆盖后才合计。沪深大盘日线资金改用已实测访客端点，使用自己的来源、日期、采集时间与返回行数，不沿用板块元数据。无新依赖、来源权限或研究会话；原 Host/MarketService/DataHub/东财拓扑不变，现有图及 API Atlas 不重画。

2026-10-22 全市场常驻部署使用封闭 `reviewed-market-overview-v1` / `apply-market`：旧版固定 `4d2e3c408663b64be9e58b03213f4ca8f1152733`，产品固定已合并 PR179 `5de7e5f2db95b8b501905af9cfdc30e8fe84db0b`。复用原 version4 事务、空闲准入、BirthFence、全部账号索引冻结和内容寻址恢复；旧 profile、控制器、证据读取器及自动兼容白名单保持。操作员候选须独立评审及原三项 CI／同候选 Mac 安装通过，再按用户授权切换并在真实认证页面验收。 该封闭部署事务本身不新增服务、HTTP、持久格式或依赖；它沿用当时已审的图与 API Atlas，不要求重画 HTML/PNG。Windows/Linux 原生与 Docker 产品层保持各自未执行状态。

## 资产目录搜索与区块按需加载

2026-10-22新增两条既有认证Host端点；目录没有研究会话或模型副作用，区块沿原观察／会话的DataHub快照归属。

| 方法 | 路径 | 合同 |
| --- | --- | --- |
| GET | `/api/research/assets/search?q=&limit=20` | q最多80字符，limit为1至50、默认20；200返回当前目录状态与最多limit个匹配项，冷启动合并后台加载 |
| POST | `/api/research/assets/observations/{observation_id}/blocks/{block}/load` | 必需Idempotency-Key；受理202和原公开观察投影，支持旧观察缺块补建与缓存命中 |

搜索响应保留items、status（loading／ready／stale／error／unavailable）、total_count、provider、limitations及安全failure_code；正常／缓存响应另含matched_count、as_of、retrieved_at，不可用时这些元数据可省略。total_count是完整目录数量，不是返回候选数。目录24小时内且账号／配置授权指纹相同才可复用；过期可返回stale并后台刷新，失败有重试节流，配置或授权变化禁止回传旧items。冷启动loading和202都不是数据完整／成功证明，HTTP请求取消也不使真实SDK Future变成空闲。

load正文只允许`source`（可省略或auto／封闭来源ID）、`refresh`（默认false）、完整ISO日期对`start_date/end_date`。日期只接受history／activity／margin且开始不晚于结束，半对／非法日期／额外字段拒绝。允许区块为overview／history／valuation／financials／activity／margin／holders／research／industry／holder_details／events；news和announcements继续独立阅读，不由该入口重复查询。旧create和refresh端点不移除。

新缺失activity／margin省略日期时，以上海时区当日或保存end_date为截止、向前59日生成完整60日范围并持久到section_ranges；已有显式范围不覆盖。events不接受新增RangeBlock参数，内部按保存截止日或当日派生60日业务区间，避免仅有end_date的无效Provider请求。旧create／refresh已存日期语义保持，财务使用报告期／公布日而非该行情窗口。

缺失overview／history默认tinysoft，其余缺失业务块默认auto；已有观察沿保存的section_sources或原source，显式source变化作为新查询条件并保存，不能返回另一来源的缓存。普通区块同来源／范围15分钟内复用，refresh=true绕过缓存；auto按dataset真实实现选源，显式来源无隐式fallback。history已有规范版本时只能读取旧快照，更改来源／区间或refresh须走历史任务，不能覆盖冻结数据。

初始观察、旧refresh和新load共用区块锁。同块同条件加载合并；加载中来源／区间冲突409，同一Idempotency-Key换区块、来源、范围或refresh条件也409，原有效任务继续。每次成功受理，包括缓存与合并，先持久键摘要和正文签名；保存失败503 `asset_observation_save_failed`，不启动新查询，并仅原位回滚本次修改，保留其他活动对象。公开响应隐藏内部键、原request和sample；失败保留旧dataset与本次失败，客户端不能把旧值当作新成功。

新增industry／holder_details／events复用market_activity，valuation的固定字段为close／pe_ttm／pb／pb_mrq／ps_ttm／total_shares；天软财务按报告期／公布日读取，Wind既有60日行情等价门保持。GET resident的active覆盖目录后台任务、区块task、历史非终态及真实Future，未知witness不能作为可部署空闲证明。来源与文件细则见[DataHub](../../research-web-datahub.md#资产目录与结构化区块)和[存储](03-data-files.md#资产目录与按需区块缓存)。

研究仓新增 `GET/POST /api/research/data/warehouse`：读取当前实例安全状态，以及显式保存、初始化、停用；保存不连接数据库，初始化只在已存在的独立数据库建表。服务器租户模式暂拒绝此配置路径，不能用浏览器 owner 自行取得共享仓权限。另增加 `POST /api/research/data/sources/{source_id}/configuration/verify`，当前仅支持 `ext_ths` 的既有 refresh_token 换取 access_token 授权检查，要求显式用户操作头；不查询行情、不轮换 token、不声称数据权限已通过。

研究仓基座扩展既有DataHub业务请求（业务取数路径保持）：`purpose`默认research、`quality`默认strict、`as_of`为带时区且不晚于当前的时点；backtest必须给as_of，allow_stale只允许display。结果新增data_success及白名单provider_metadata（真实execution_attempts、仓版本/命中/持久化及PIT证据）。未知历史返回409/data_pit_unavailable；前台18秒超时返回504/data_query_deadline，原call_id对应任务继续排空至真实终态，不得换ID盲重发。收据可记录warehouse_committed及已提交版本，即使最终查询取消或超时也不声称回滚。


2026-10-22 MCP隔离：仅macOS固定离线Python在新增权限、policy/runtime/安装树/schema复审后条件开放；逐次重验并在受管Seatbelt内执行。Node/npm、其他平台、凭据环境、网络和子进程需求保持受限或失败关闭。解析前字节/连接时限与真实进程回收分别核验，回收未知保留准入栅栏；固定远程及非受管Native维持各自合同。具体包就绪不由Doctor入口存在推断。

2026-10-22 插件新增 /api/research/plugins 固定包/文件/审批/lifecycle/MCP操作、/api/server/plugins 真实cookie角色共享/个人分发与固定owner审批队列，以及 /api/research/internal/plugin-runtime 的 freeze/commit/rollback/unfreeze 私有管理回调。完整Method/Path由architecture-map与API Atlas逐项登记；同源、tenant边界、一次性证明、body上限和错误状态详见[插件合同](../../research-web-plugins.md)。

2026-10-22 `apply-assets-v4`为封闭本机操作员CLI，固定旧5495与PR180产品`9b436613aad9136f4959c992c89dd72fc7354ed5`；无新HTTP方法/路径/字段、DSH或API权限。旧v1/v2/v3及version4 journal保持，产品原接口和API Atlas未变，不重建架构HTML/PNG。产品三CI与v4最终测试/评审/CI/部署分开，只有完整资格及原锁/空闲/保全通过后才允许实际切换。

2026-10-22 `model_provider_upgrade apply-assets-v3`是本机操作员CLI，封闭绑定旧5495和已合并产品a0ff3ae2；无新HTTP方法/路径/请求字段、DSH协议或API权限。原产品6项历史/偏好端点与现有Atlas保持，部署profile不重新生成架构HTML/PNG。最终工具三CI与实际切换/保全独立验收，旧v1/v2恢复、controller/evidence不变；见[部署合同](../../research-web-gateway-upgrade.md#资产观察固定版本联合部署)。

## 资产历史任务与图表偏好

历史任务正文兼容可选ISO日期`as_of`；省略／None沿原观察截止与旧请求行为，不能使旧任务／旧证据失效。同一任务键改变实际as_of仍属于参数冲突。报价的实际交易日晚于旧规范锚点时，可用新as_of创建独立历史版本；已完成全历史须重新生成完整版本，不以新证券recent两年窗口截掉原覆盖，旧版本和输入证据保持不可变。

最后核对：2026-10-22。下列6个新增端点由 `asset_routes.py` 声明，经既有 `/api/research` 前缀挂载；认证身份及账号 Store 隔离保持。任务受理与规范数据发布是两个事实，`202` 不代表历史完整。

| 方法 | 路径 | 合同 |
| --- | --- | --- |
| POST | `/api/research/assets/observations/{observation_id}/history-jobs` | 必需 `Idempotency-Key`，受理202，正文见下文 |
| GET | `/api/research/assets/observations/{observation_id}/history-jobs` | 只读列表 `{items:[job]}` |
| GET | `/api/research/assets/observations/{observation_id}/history-jobs/{job_id}` | 只读单任务与进度 |
| POST | `/api/research/assets/observations/{observation_id}/history-jobs/{job_id}/cancel` | 无正文，202；终态重复取消返回原终态，真实Future结束前仍排空 |
| GET | `/api/research/assets/chart-preferences` | 当前账号的 `{panels,revision}`；默认 `volume,macd` |
| PUT | `/api/research/assets/chart-preferences` | 正文 `{panels:[...]}`，保序、唯一、0至4项，枚举 `volume/macd/kdj/rsi` |

历史任务正文严格为 `{scope:"recent"|"older"|"all", adjustment:"none"|"qfq"|"hfq", source?:"auto"|"tinysoft"|"wind"|"akshare"|"baostock", retry_of?:<UUID>, as_of?:<ISO日期>}`，拒绝额外字段；键为8至128个字母、数字、`_.:-`字符。同观察同键同参数返回原任务，改参数返回409 `history_key_conflict`。已有活动任务或行情刷新时409 `history_busy`；`older` 要求现有规范历史且复权相同。重试只接受同口径、可重试的失败/取消/中断任务，新键显式提交；缓存或因子版本冲突要求重建。保存失败不启动任务。未传source保持旧客户端tinysoft语义；非tinysoft只开放recent/none。auto按现有Broker等价候选降级，固定来源失败不切源；Wind超60自然日只在auto候选准入跳过，不拆块或当作transient。重试冻结source、adjustment与requested_as_of，不能随UI或新报价变化。

公开 job 含 `id/observation_id/state/status/scope/adjustment/source/requested_as_of/created_at/updated_at/progress/coverage/current_dataset/failure_code/failure/retryable/retry_of/request_key`。`state` 与 `status` 相同，非终态为 `queued/running/cancelling/draining`，终态为 `completed/failed/cancelled/interrupted`；`progress` 包含 `chunks_completed/chunks_total/rows`，coverage 区分实际日期、扫描区间、上市日及完整历史边界证明。失败只有安全业务码，公开 dataset 不暴露内部原始行、因子、输入或路径。观察投影附最近 `history_job`。`request_key` 用于核对未知提交，不是认证秘密。

`recent` 取截止前2自然年；`older` 在已扫描最早日向前4年；`all` 从近到远分块至上市日或明确声明的1990-01-01下界。每块Provider限制保持，规范总行数不受5000行的单次Provider上限截断。完整数据与同版本 metadata 原子切换、旧材料兼容和复权失败关闭见[文件合同](03-data-files.md#资产历史与图表偏好存储)及[DataHub](../../research-web-datahub.md#资产历史任务与固定复权)。

既有 `GET /api/research/resident` 的 `active` 同时包含真实 CJPY Future和历史任务非终态，无法读取witness为未知，不伪报false。操作员只在研究/观察/DataHub/历史任务全部明确空闲后允许切换；`cancelled`查询终态不抵消仍运行的Future。

## 全市场概览接口

2026-10-23不新增路径：报价行/CSV追加`limit_up_price/limit_down_price/limit_status`，summary追加`limit_up/limit_down/limit_covered/limit_unknown`，未知不补0。`previous_amount`返回本次已上市池的上一交易日全天金额、日期、scope_count/missing_count、source_snapshot_id/retrieved_at或不可用reason；内部逐股基线不进入公开投影。资金`row_count/provider_total`保持本次返回行数，`history_rows/history_count`是本账号实取留存，每日有来源/采集时间，30日目标与实际缺口分开。历史日线不随板块今日/5日/10日开关变化，不等价为分时。详情见[数据口径](../../research-web-datahub.md#无会话全市场数据)。

indices响应可附加`warehouse`对象：status、persisted、hit、source=eastmoney、source_count=1、version（本次写入返回版本）、snapshot_sha256/observed_at/display_cache_ttl_seconds（仓命中证据）及固定False的quality_accepted/formal_backtest_eligible。原响应字段含义和HTTP请求不变；仓不可用而上游成功时明确persisted=False，授权失败不降级取数。GET仍零上游调用，POST显式刷新不冒充仓命中刷新；内部缓存读不是新HTTP入口。

`GET /api/research/market` 读取各区快照、覆盖、错误、交易日历状态与活动采集；GET不联网。`POST /market/refresh` 接受固定 `sections`（quotes、indices、industry、concept、flows、calendar、members）、行业／概念 `kind`、today／5d／10d `period` 和已登记 `board_id`，202返回独立 `request_id`；同 key 后台合并，`Idempotency-Key`可复用同次请求。`GET /market/refresh/{request_id}` 轮询，`DELETE`释放本请求订阅，最后读者离开才取消共享采集。

`GET /market/quotes` 支持 `snapshot_id`、exchange、board、search、sort、direction、offset、limit（最多200）；`GET /market/quotes/export` 导出相同筛选的完整 CSV，要求完整来源股票池。板块过滤必须先显式刷新 members，成员与同份行情池相交，不重取个股报价。响应保留来源、行情／采集时间、provider_total、pages_fetched、pagination_complete、complete、missing、limitations、stale和本次错误；失败不冒充完整数据。不接收会话ID、凭据、路径或任意上游端点。

报价行 `listing_date` 来自供应商上市日期（无效时为null），summary 的 `upcoming_count` 记录目录内未来上市数量。未来上市不参加有效广度、分布或排行；缺报价仍计入unknown。`complete` 仅证明来源范围和分页，不能证明报价／停牌／涨跌停字段齐全；成交额缺口保持null，不能把页面的unknown或待上市当作零成交。

`model_provider_upgrade apply-assets-v2` 属于显式本机操作员 CLI；新增封闭版本身份不增加或改变公开 HTTP 方法、路径、请求字段、认证边界和 Observation 响应。资产／DataHub 状态只读用于原空闲证明，业务 API 与研究执行链路保持，现有 API 图和索引继续准确。

资产估值与来源摘要仍是浏览器DTO，按当前区块动态统计状态；纯折叠、主题切换只投影已取得数据，进入资产或专题按上述load合同按需取数。原手工create／refresh保留，不沿用此前纯静态迭代“无新端点／取数”的结论。

旧ObservationRequest保留section_sources及section_ranges，旧记录缺省为空映射。AssetBlock现在包括原十块及industry／holder_details／events，来源、实际范围和报告期分别回显；valuation固定请求close／pe_ttm／pb／pb_mrq／ps_ttm／total_shares。业务source／range有效条件、15分钟缓存与新增两条HTTP见本章“资产目录搜索与区块按需加载”；显式来源不隐式回退，Wind原60日等价门保持，财务按各Provider报告合同读取。

本轮部署只调整已有GitHub CI日志读取的有界时限并固定工具摘要，没有增加或更改HTTP路由、方法、身份边界和请求字段；完整checkout/树及三CI条件保留。

## 资产观察区块刷新

`POST /api/research/assets/observations/{observation_id}/blocks/{block}/refresh`保持原Idempotency-Key头和无正文语义，202返回公开观察。目标必须是观察已有的封闭区块（原十块及industry／holder_details／events）；沿保存会话、资产、来源与日期，只以refresh=true重取目标。补缺块用新增load，普通GET观察／列表始终只读，目录search GET的显式后台加载另见上节。

同一观察、同一键和区块返回当前观察，不重复启动取数；同一键改区块、或观察仍有任一区块 `loading` 时返回 `409`。刷新保存失败返回 `503 asset_observation_save_failed` 且不启动查询。刷新中保留旧 dataset，失败/取消/中断同时保留旧快照与新失败码；客户端轮询状态，不把 `202` 或旧数据当作本次成功。键只保存 SHA-256 摘要，不向浏览器返回内部 request、refresh_keys 或 sample。旧 Golddata 新闻/公告 GET 接口保留，仅页面入口迁到资产观察，不新增采集或模型调用。

## 接口与协议约定

本机显式操作员增加 `model_provider_upgrade apply-assets`，只选封闭的资产产品profile；`recover` 从已验证journal恢复对应旧版本。不新增HTTP参数、业务端点或用户可配置的任意旧版/产品SHA。

独立发布仓库身份修补不新增接口或命令参数；未知 origin、目录/inode 变化及目标对象缺失仍通过现有 blocked 通道在停机前返回。

PR168 导航随原 `model_provider_upgrade apply/recover` 交付，没有新增参数或 HTTP 接口；显式操作员仅对固定五个 UI 文件使用独立产品身份，后端查询/交接协议不变。

模型服务商联合部署仅新增本机 `model_provider_upgrade apply/recover --home [--source]` 显式入口，无新 HTTP/DSH 接口。只读 resident/runtime/model-profiles 与 server health 用于真实版本、活动及凭据是否配置核对，不发送模型请求或读出 Key。

无新增CLI参数或HTTP接口；恢复任务工具缺失仍以既有blocked错误返回。优雅等待延长不改变deferred/recovery_required的语义。

操作员apply-ui新增显式--preserve-primary，允许经三段受限差异证明的不同target；默认仍要求primary=target。HTTP身份、管理、退出和研究接口不变。

新增的 stage-primary-ui 属于本机显式操作员模块命令，不新增 HTTP API、浏览器权限或研究工具。网关 apply-ui 的 helper 同 blob 校验由源码与冻结恢复包共同执行。

新增浏览器路由 `#/account` 与管理员专属 `#/settings/users`，旧 `/account` 页面脚本及 `#/settings/account` 兼容到 `/#/account`。HTTP接口保持现有me/users/password/stop/logout；不新增参数、身份来源或后端接口。账号资料仅展示认证用户名/角色，普通用户不请求管理列表。

操作员 CLI 新增 `apply-ui --expected-gateway SHA --primary SHA --target SHA`；primary 必须等于 target，工具 HEAD 必须为最新已验收 master。业务 HTTP 接口不变。停止前不确定返回 deferred；停止后待恢复返回 recovery_required，不能当作部署成功。

不新增HTTP端点。新轮次网页研究receipt增加report_binding_policy；受信report_context按冻结问题可增加body_target，模型不能覆盖。report_plan.analysis使用{{fact:准确已选id或$计算id}}和{{formula:$计算id}}，全标签引用由系统展开；不能手写数值、日期或算式。规范JSON增加system_plan/presentation和可选body_target，audit_attachment指向同版本实际审计JSON；business_calculations新增annual_change/gdp_implicit_deflator。原生格式列表保持HTML/DOCX/PDF，审计附件是独立绑定文件，report_delivery.files及历史归档包含它。旧receipt和默认格式保持读取兼容。

无新HTTP端点。原research_run_script(report_plan)新增可选calculations数组，元素为id/operation/operands/decimal_places，sections可选择$计算id；summary对无工作簿请求可省略。report_context新增Host冻结formats，不接收调用方task/hash/格式覆盖。规范JSON新增business_calculations及可读trace，Host独立重建并核对；report_formats记录所选交付，必需格式仍按冻结要求核对。旧参数和默认三格式兼容。

操作员新增稳定诊断gateway_journal_invalid/oversized；只用于私有升级journal读取或首个信号前预算拒绝，不增加HTTP接口。退休等待未知时仍deferred，不对变化后的PID追加信号。

Mac内核映像核验仅作用于显式网关操作员入口，不新增HTTP端点或修改健康字段。无法读取PID映像或映像不符时，停止前拒绝，不放宽认证或参数匹配。

显式常驻网关的廉价 `GET /api/server/health` 增加 `deployment_fenced` 布尔事实，不启动pair或探测primary。安全更新journal存在时，除该健康端点外全部请求（含GET与login）返回503 server_maintenance；旧cutover语义保留。真实primary验证由操作员入口执行，不把缓存的primary_last_verified当作即时空闲证明。

现有来源 read 回包新增 numeric_observations/numeric_claim_guidance，来自 Host 完整字节；研究 detail 的版本项增加 is_current 和 quality_binding。网页来源 date_evidence/date_status 解释实际发布时间及冲突，未知不按搜索或 URL 补齐。无新端点、模型参数、凭据或执行授权。

原code路径继续保留；report_context仍只在Host合同有效且为字典时提供，不信任模型提交绑定。扩展仅在原工具数据参数内，补查许可由原Host回执管理。

GET session detail 新增 research_report_delivery（status/task_id/version_id/report_content_sha256/quality_status/files/aliases）；research_check_quality 结果的 report_delivery 使用同一Host投影。未绑定返回空files/aliases，accepted还要求当前检查绑定。arithmetic_checks含有界字面表达式、reported/expected/status和section_id；matching只证明该算术，不免除原数字、期间、单位和来源检查。原始消息保留，当前报告链接由UI核对并允许resolver拒绝直接API绕过。无新增端点、凭据或写参数。

research_sources 对 Host 已抓取网页仅返回原 web 身份，不再同时给出 file 上传别名；实际文件列表及下载路径保留。无新增端点或用户字段，错误 provenance 以原 research_source_integrity_failed 拒绝，web 范围和截止日保持原规则。

research_run_script 接受且仅接受 code 或 report_plan 其中一项；report_plan 是有界 JSON，无任意代码、路径、来源身份或评分覆盖字段。既有 private nativeAdmission 仅对合法冻结合同返回 report_context（task_id、contract_sha256、as_of、requirement_ids），浏览器/模型不能提供可信绑定。不增加 HTTP 端点，research_check_quality 与 invalid 下载 409 不变。

新增内部 POST /api/research/internal/data/research-source 接受 {session_id,call_id,operation:list|read,source_id?,search_activities?}；身份和有界已完成搜索活动仅由可信原生插件提供，模型参数只允许 operation/source_id。list 返回真实来源身份，read 返回 source、observation_id、正文前24000字符及 truncated 和实际 inputs 路径。POST 同前缀 /research-source/cancel 只接受 session_id/call_id。两者须实例私有数据 key，浏览器和其他用户不可调用；普通研究 GET 不取正文或触发模型。

质量回执新增 report_content_sha256 指向当前规范 JSON 实际字节；每版本引用 Host 已保存检查 ID，不由调用方写 passed。原有 research_quality、file_state、research_accepted 语义与损坏文件409门保持。

新增select_business_evidence、write_summary_workbook与render_markdown均为原沙箱Python资源函数，不新增API。source_references额外接受完整file:24位十六进制ID的斜杠连接，仍逐项核对Host身份；不接受路径、文件名或未知ID。evidence_section输出统一四列表，重复父来源去重且不修改正文可信状态。

load_business_evidence(task_id,contract_sha256)与source_references(value,Host sources)只是已打包Python资源函数，不增加HTTP/RPC。前者读取本回合便利投影，后者接受规范ID或“规范ID · 准确Host标题 · 定位”，不从文件名/定位猜来源。Host评分不读取投影文件。

HTTP/RPC端点和check请求不变；质量返回evidence_context增加business_observations，包含规范句、metric/period/unit/value、全部source_ids、原文spans/full SHA、算法及作用域摘要。该字段只由Host从实际允许输入产生，不接受报告/工具参数传入。SDK只是格式辅助；numeric_summary仅为独立验收器的显式展示精度，不放宽Host判定，原invalid下载409保持。

calculation_evidence仅是沙箱内报告Python格式helper，不新增HTTP/RPC入口。模型输出仍由原research_check_quality独立校验；伪造观测、悬空数值claim和真实缺口不获passed，原报告下载409规则保持。

HTTP端点不增加。research_check_quality返回有界evidence_context（规范sources及Host独立计算observations）；旧错误身份、伪造数值和谱系缺口仍拒绝。研究回合切换时返回409 research_quality_scope_changed；invalid报告下载仍409 research_report_invalid。

POST /api/research/sessions/{sid}/messages 的必需 Idempotency-Key 由私网网关透传；不提供时仍由后端422拒绝。Cookie、Authorization不转发，内部用户密钥仍由认证网关生成。

不新增HTTP端点。满槽仍返回503 runtime_capacity_exceeded，已驻留用户仍可访问；容量只由管理员私有配置/CLI指定，浏览器不能通过owner或header提高上限。Doctor JSON增加capacity配置事实（additional_instances/total_instances），不认证模型与重型研究容量。

用户实例恢复若原回调端口被占用，返回503 runtime_port_unavailable；不安全或不一致的控制记录为runtime_control_invalid（权限类仍保留runtime_path_unsafe）。不自动改址或驱逐其他实例；匿名健康不触发这些恢复操作。

附接 primary 的原 /api/research/aihot/ 只读请求沿认证代理送原 backend，避免升级网关时改变其资讯响应合同；新用户共享资讯 API 保持，管理接口仍验 admin。/static 按认证 UUID 选择固定界面版本并 no-store。

常驻附接模式增加匿名 `GET /api/server/health`，廉价返回网关 status/revision/primary_last_verified，后者只是先前验证标记，不表示当前模型可调用；独立 serve 返回 runtime=not_started_by_health。me 增加 primary，users 增加 primary_user_id。primary 停用/停止返回 409 primary_account_protected。切换 journal 存在时业务写操作返回 503 server_maintenance，登录和退出仍可用。

AI资讯自主化本轮在隔离实例接入原版API/worker与独立库，保持DSH研究执行及当前常驻内容。零调用和后续切换边界见[自主资讯合同](../../research-web-ai-news.md)。

## 可选服务器账号 API

以下接口只由显式 `rwb server serve` 的独立网关提供，原单用户 Host 不挂载。`/auth` 为登录页、`/account` 为已登录账号页、`/` 为现有研究 UI。所有请求固定精确 Host/origin；写请求要求同源 Origin，无 CORS。HTTPS 登录使用 12 小时 `rwb_session` HttpOnly、Secure、SameSite=Strict Cookie，数据库仅保存令牌哈希。

| 方法与路径 | 输入与权限 | 结果 |
| --- | --- | --- |
| `POST /api/server/login` | `{username,password}`，限速 | 设置 Cookie，返回非秘密 `user` |
| `POST /api/server/logout` | 当前 Cookie | 撤销当前登录态并清除 Cookie |
| `GET /api/server/me` | 已登录 | 当前账号的非秘密投影 |
| `GET /api/server/users` | 管理员 | `items` 账号投影 |
| `POST /api/server/users` | 管理员，`{username,password,role?}`，默认 role=user | 201 `user`；无公开注册 |
| `PATCH /api/server/users/{user_id}` | 管理员，`{enabled:boolean}` | 账号投影；停用即时撤销登录并停止受管实例 |
| `POST /api/server/users/{user_id}/password` | 管理员，`{password}` | 撤销该账号全部登录态，研究继续 |
| `POST /api/server/users/{user_id}/stop` | 管理员 | 只停止该账号的受管 pair，释放实例槽 |

请求体拒绝多余字段；密码最少 12 字符，账号 UUID 由服务端生成，最后一个活动管理员不能停用。未登录 401、管理员权限不足 403，失败只返回稳定错误码。除下述共享AI资讯外，`/api/research/**` 和框架嵌入请求按已认证用户绑定固定回环 backend，不接受 owner、上游 URL 或外部内部认证标头；网关剥离浏览器 Cookie/Authorization/代理标头，拒绝 internal、编码路径及上游重定向。后端再验证私有逐实例网关令牌；内部回调仅走既有白名单与独立数据密钥，不对浏览器转发。

`/api/research/aihot/*` 阅读与 `/api/research/ai-news/feeds/{kind}.xml` 六种RSS由网关的共享service直接提供，所有已登录成员可读；`GET /api/research/ai-news/status`、`POST /api/research/ai-news/control`仅admin。control先流式限制64KiB，再重验登录态/admin和页面账号；读取返回前也重验撤销。未知AI路径/方法不落入用户backend；tenant profile连有效实例key也拒绝全部全局AI路径。共享home为server_root/shared，原Node认证不对浏览器暴露，不新增CSRF协议。

页面身份头 `X-RWB-Page-User`、SSE 的 `rwb_user` 只用于拒绝换账号后仍打开的旧页面，不授予用户选择权限；读取可省略，产品写请求必须至少携带一项且所有提供值均匹配当前账号。登录撤销后正在进行的流按一秒间隔重验后停止交付字节；后端研究不因此自动取消。容量满返回 503 `runtime_capacity_exceeded`，不创建队列或驱逐实例。服务器 profile 的禁用接口返回 403 `server_capability_disabled`，官方模型连接限制也在后端执行；网关登录成功不证明模型或研究可用。

新增阅读GET（服务器须登录）：`/api/research/aihot/items/{item_id}`、`/items/{item_id}/original`、`/stories/{story_id}`、`/topics/{slug}?page=1`、`/groups/{fact_id}/reports`，均在相同前缀内。标识/页码严格限定，响应校验身份；专题308仅接受UUID合并目标，由浏览器在本地路由内最多跟进四次，不跟随HTTP跳转。正文以body.content惰性阅读树替代上游HTML。no-store来源清单不缓存。

AI资讯保持 `/api/research/aihot/…` 阅读合同，由Host读取本机原版API，无外站回退。新增 `/api/research/ai-news/status`、`POST /control` 和同源 `/feeds/{kind}.xml`；管理采用有限动作，不提供任意URL/SQL或秘密输入。未配置真实503；内容与日期身份仍严格校验。
来源改版/响应身份不匹配明确502，不以精简数据伪造完整页面。旧三个v1阅读路由仍兼容。
日期/ISO周/月严格验证，404保持404；429/503保留秒数或HTTP-date等待期，超时504，
重定向/格式/大小异常502。JSON解压后2MiB、总期限20秒、最多64份内存LRU、至少60秒TTL，
过期带ETag复验；缓存命中不等待另一端点的网络锁。
图片仅将已返回的固定img-proxy签名路径登记为不透明 `/media/{sha256}`，不接受用户URL；
每次缓存读取重新登记映射。图片无凭据、不跟随重定向，最多4并发、总期限12秒、4MiB及栅格MIME白名单。

FinGPT 的既有 sessions/messages API 可携带 research_mode=quick|deep|agent，旧 research_depth=instant|deep 保持兼容。messages 另接受可选 research_requirements（最多30项，每项4000字符）和 research_as_of（ISO日期）；后续用户要求累积保留。详情新增 research_quality、execution_status、research_accepted 与 research_report_versions，原生状态语义保留。

POST /api/research/internal/data/research-quality 仅接受可信插件私有认证，严格 JSON 为 {session_id,operation:"check"}。调用方不能写通过状态、补查次数或合同；返回状态、缺口和一次补查许可，同任务同报告重放不重复授权。浏览器 GET 不执行补查或模型请求；当前报告完整性无效时输出下载/预览返回409，输入附件仍可读。

正文搜索使用固定 DSH `7ecf564f2e09b829240c5553687223bdd1e2df73` 的显式部分搜索接口：Host 将 RWB 已创建、未删除且符合当前模式的 ID 范围传给原生层，再与原生列表可见范围取交集。响应必须包含完整范围内的 `unavailableSessionCount`；Web 返回 `unavailable_count` 并在零命中时仍提示部分历史未搜索。旧格式源记录保持不变，不授予恢复执行；I/O、损坏及取消仍失败。未升级的旧接口缺少覆盖信息时明确报错，不假称搜索完整。

`GET /api/research/resident` 返回运行中 Host 的 `enabled`、启动时绑定的 `revision`（完整 SHA 或 null）、
`maintenance`、`active`（Host待处理研究/审批/问题/Automation；未知为null）；只读且不访问 GitHub、凭据或模型。保留原 Host/Origin 校验。
显式启用 resident 后，维护期间用户写请求返回 503 `deployment_busy` / Retry-After=5；
已认证 internal callbacks 继续原认证，不被维护栅栏阻塞。默认未启用时行为不变。

POST `/api/research/sessions/search` 使用严格JSON `{query,mode?}` 进行只读原生全文搜索；查询不放入URL，避免出现在正常访问日志。query trim后1–500 UTF-16单元，无NUL/孤立代理；mode可选。通过既有私有 session.search RPC返回最多20项{id,title,mode,snippet}、has_more和source=native_dsh，过滤未知/未成功创建/已删除/模式不符会话；标题缺失或无效时返回“未命名会话”。无原生支持时明确503，不降级伪称正文成功；不提供cursor、角色筛选或命中消息ID。

既有 POST `/api/research/internal/data/automation-action` 的run接受绑定真实任务名/精确ID的有限明确长句及可选版本；没有新增请求字段。旧版本409 automation_version_conflict，含混/否定/条件/引用仍拒绝。Runtime仅保留8个既有Automation稳定拒绝码，继续丢弃message/detail、未知或非法码、非JSON、超过4KiB及重定向响应，不自动重试。

`GET /` 接受用户触发的跨站顶层文档导航（navigate/document/?1，Origin 缺失或同源）。
例外只返回静态应用壳；`/api/research/**`、静态资源和其他路径不继承此入口例外。

`GET /api/research/runtime` 新增只读 `web_access: {mode, origin}`，mode 为 `loopback`
或 `tailscale`；默认 origin 为 null，启用后为操作员指定的精确 HTTPS origin。
Native Doctor 同名投影取运行中 Host，未就绪或旧 Host 无此字段时为 `unknown`/null；
不表示 Serve、远端设备或真实研究已验证。启动配置与安全边界见安装文档及安全清单。

`GET /api/research/hot/periodic/runs/{run_id}/report`下载PG中已保存的一次性Word子执行。
固定run ID沿reader签名分块读取，Host核对完整hash/长度/身份；GET不渲染、不启动研究，
响应带X-Hot-Execution-Id、X-Hot-Content-Hash和X-Hot-Artifact-Hash。

DataHub无可调用来源仍返回400，但稳定error.code为data_source_unavailable；
不等价AKShare查询为data_not_equivalent，旧授权摘要缓存为data_cache_authorization_changed。
Runtime仅传播受限code，不传播错误message/原始上游数据。GET会话活动会把DataHub failed结果
显示为failed，而不是仅凭原生isError=false显示执行成功；原生回合完成和领域数据成功仍分开。

既有 DataHub 查询 API 新增 external_data 能力，参数为 dataset、arguments_json 和 limit；
source=auto 只读取外部总目录，具名查询使用登记端点且禁止自定义目的地址/认证字段。
连接 API 同步四类外部来源凭据，HTTP认证返回 credential_transport_blocked。
会话详情的 assistant 消息可增加 reasoning，活动可增加原生 seq；原有计划、来源、报告字段保留。
写请求前端超时表示结果未确认，不改变 API 幂等键或后台任务的实际状态。

离线真实样本检查无HTTP接口或写操作；只通过显式Node命令读取版本化artifact。页面刷新/模型路由/预算授权合同保持。输出NOT_RUN关系与候选上下文重叠，不把评价状态映射为产品ready。

现有events/correct的change可为type=times，除id/expected外必须同时给occurred/effective nullable严格日期主张；没有新endpoint。Manager核对manual.times、完整dateEvidence及两个值，不匹配保留原UUID。Node稳定time_invalid/time_evidence_invalid拒绝非法日期或未关联/不匹配原文；读取详情携带dateEvidence。

Hot status增加backfill=publisher_next_links、backfillDays及maxPages=3；来源覆盖沿已有raw_page的partial/gap投影。没有新增公开写接口或自定义URL输入。

来源GET新增collection_state、catalog_activation_allowed/code及adapter/catalog_id；status新增sourceControl.catalogActivation权限诊断。字段缺失不能推断ready。POST目录激活新增稳定hot_source_catalog_permission_missing错误，读路径不授予控制权限，旧URI/参数/UUID合同保持。

POST `/api/research/hot/sources/configure`可显式带严格bool useCatalog=true及1–1000字符非空reason，沿同源/user-action/UUID和expectedRevision合同激活固定目录源。旧调用省略新字段保持原参数及重放哈希。reason不能单独提交；缺动作403、非法字段/URL400，旧owner/运营主体冲突拒绝。成功含catalogActivation审计指纹；不增加付费许可。

`/api/research/automations/hot-brief-plans`三个管理aliases不受旧`RESEARCH_AUTOMATIONS_ENABLED`控制，直接使用Hot列表、运行读取、条件配置合同；缺显式动作403、非法输入400、Hot不可用503保持。旧`/automations`与投递接口仍沿原开关拒绝，路径/参数和公开符号未变化。

关注入口为GET /api/research/hot/follows及POST /api/research/hot/follows/configure。周期计划为GET /api/research/hot/brief-plans、GET /api/research/hot/brief-plans/{plan_id}/runs、POST /api/research/hot/brief-plans/configure；Automation路径 /api/research/automations/hot-brief-plans 提供相同list/configure/runs适配。GET只读；POST沿同源、明确动作、64KiB body、严格版本/布尔类型和UUID重放合同。新计划必须停用创建，再显式启用。

新增POST `/api/research/hot/research-runs/{run_id}/execute`，要求同源明确用户动作，
JSON question及md/docx formats；复用准备好的根会话和快照。deliveryKey不可绑定另一问题。
executionStarted为true/false/null，分别表示已受理、确定未提交、证据不明；不以受理证明报告完成。

新增POST `/api/research/internal/data/hot-model`，只接受既有DataHub私有key和owned Runtime。
operation为binding/reserve/dispatch/unknown/cancel/receipt；根session/run/instance/manifest
同时核对Store和PG。请求/返回有界，browser user-action不能授权预算票据。

Hot接口统一在 `/api/research/hot`：status/configuration/channels/events/events/{id}/sources只读，
PUT configuration及POST lifecycle/channels/configure/events/correct/sources/configure为明确操作。
后者要求同源、X-Research-User-Action、JSON <=64KiB；条件配置/纠错有规范UUID。查询字段沿用
受控投影合同，未知字段拒绝。版本/参数冲突409、未授权403、格式400、过大413、服务故障503。
Host桥有界，业务写入未知时返回原UUID；声明来自实际源码清单，不能推导研究交接已实现。

文本验收预算没有新增公开 HTTP API；只通过显式 launcher 控制和内部 Linux Python stdio RPC 读取/扣票。stdin 仅操作与输出上限，不包含 prompt 或 Key；固定错误码区分过期、耗尽、不确定提交。

主线 `research_plan` 保持 turn/seq/status/history_complete/items 字段；与兼容计划投影
共用原生日志折叠。available 才提供已确认条目，incomplete/invalid 不保留绿色旧快照。

会话详情与 SSE snapshot 新增只读计划投影字段：`plan` 为 null 或
`{turn, seq, version, todos:[{content,status}]}`；`plan_history_incomplete` 标记原生日志
缺失/间断，`plan_error` 仅在无法确认计划时存在。`version` 绑定原生回合及日志写入序列，
不提供稳定 item ID。新回合、无 Todo、错误 Todo 不复用旧快照；原生空列表与无计划不同。
计划状态不修改会话终态或 `delivery`，不新增路由、提交操作或正文存储。

模型设置和最小生成沿现有 API；Docker 后端来源投影为 `credential_storage=docker_encrypted`，
Native 为 `system_keychain`。固定 DSH 的 source 是 provider 自定义字符串；不返回 Key。

ETF工程模拟新增以下同源入口；合同见[数据与文件](03-data-files.md#etf-工程模拟与真实准入边界)。
POST须有 `X-Research-User-Action: ?1` 与 `Idempotency-Key`，流式输入≤8MiB，只接受工程标记。
真实准入始终BLOCKED；冲突409、非法合同422、输入预算413、存储失败503。

| Method | 路径 | 源码 |
| --- | --- | --- |
| GET | `/api/research/portfolio-decisions/readiness` | `app/research_web/portfolio_decisions/routes.py` |
| GET | `/api/research/portfolio-decisions/runs` | `app/research_web/portfolio_decisions/routes.py` |
| GET | `/api/research/portfolio-decisions/runs/{run_id}` | `app/research_web/portfolio_decisions/routes.py` |
| POST | `/api/research/portfolio-decisions/runs` | `app/research_web/portfolio_decisions/routes.py` |

资料业务查询对未适配/当前不可用来源分别返回503 `data_capability_not_integrated`/`data_capability_unavailable`；请求字段、来源排序及显式fallback合同不变。研究发送的当前时钟由Host在受理后注入原生prompt，不新增客户端字段、不改变幂等请求摘要。

`GET /api/research/sessions/{sid}/files/{fid}/preview`对Markdown返回`text/plain`供沙箱iframe显示原始字节；同一文件的`download`仍使用原Markdown类型。请求参数、归属/错误契约、CSP与nosniff保持原状，不增加API或转换执行。

Session 详情与原生 snapshot 增量投影工具活动 `seq`、`tool`、`arguments`、`result`，保留旧 `detail` 兼容；参数、结果和错误使用限长脱敏后的显示值。研究型 Automation 执行详情增加 `execution_context={run_id,automation_id,definition_version,trigger,definition_snapshot}`，来源是该执行 Run，不是当前可修改的任务。旧 Skill/Workflow 执行保持原契约。研究型执行续答不接受新的能力、方法、额外工具或不同输出格式；未确认快照失败关闭。没有增加另一套调度或研究接口。

## Claw 项目与日程草稿 API

`claw_routes.py` 提供 `/claw/projects` 列表/创建与 `/{project_id}` 查询/改名/归档，`/sessions/{sid}/project` 显式移组，`/sessions/{sid}/file-references` 显式复制所选同项目文件。
`GET/POST /projects?mode=claw|fingpt` 与 `GET/PATCH /projects/{project_id}?mode=claw|fingpt` 提供相同项目合同，模式参数必填且严格校验；旧 `/claw/projects` 路由保持 Claw 语义。`POST /sessions` 的可选 `project_id` 只接受当前模式的未归档项目；旧请求保持各模式原默认研究空间。移组和显式文件引用从所属会话的 mode 选择项目服务，拒绝跨模式或跨项目引用。

`GET/PATCH /navigation/{mode}` 管理 Claw/FinGPT 独立的置顶及项目排序，返回 `{mode, revision, pinned:[{kind:'session'|'project',id}], project_order:[project_id]}`。初始 revision 为 0；PATCH 必须提交 revision、pinned 与 project_order，拒绝额外字段、类型错误、重复项、其他模式/已删除会话和归档项目。project_order 可为当前有效项目的子集，客户端追加未列出的项目。成功持久化后 revision 加一；版本冲突返回 409 `navigation_changed`，源状态不变。GET 过滤已失效 ID，不写回索引；存储失败恢复原内存状态。导航更新不调用模型或创建执行会话。
会话摘要包含 project_id 与可选 history_warning；Claw 详情包含原生已回答 question_history（仅成功且问答 ID 匹配）、automation_drafts、automation_runs（来源对话的 Run、原生结果、活动、文件）。
`/internal/data/automation-draft` 继续使用现有实例私有认证，拒绝普通浏览器提交；它只生成经 AutomationCreate 校验的锁版本草稿。
`POST /internal/data/automation-action` 受既有私有实例认证，operation 为 list/prepare_update/run；list 可按 automation_id 查任务及最近 20 条 Run 的持久状态、摘要和产物，避免把 queued 当完成；执行会话禁止管理和递归试跑。prepare_update 使用 AutomationUpdate、同任务 ID 与 expected_version，run 额外核验最新真实用户指令。
`/sessions/{sid}/automation-drafts` 查询、`/{draft_id}/confirm?enable=true` 明确创建并启用 research_task，旧目标省略 enable 仍只保存；update 草稿确认接收 AutomationUpdate、`/{draft_id}/dismiss` 取消属于会话；确认可编辑名称、目标描述与日程，不可改换锁定能力或增加外发/MCP权限，且结果默认停用。
新增请求拒绝额外字段；非法归属、归档、失效版本和已取消草稿给出明确错误。API Atlas 由机器清单同步生成。

创建后的启用失败重试仅能启用确认回执绑定的定义版本。Automation 在同一定义事务锁内校验 `expected_version` 后才启用；任务已改版时返回 `automation_version_conflict`（409），保留任务停用和旧确认快照。旧草稿缺少有效 `confirmed_version` / `confirmed_definition` 回执时返回 `draft_confirmation_receipt_invalid`（409），不从当前任务猜测版本。已完成启用的草稿重放不会重新启用用户后来停用的任务；删除重放仍拒绝。

## FinGPT 会话扩展

POST /api/research/sessions 增加 research_depth=instant|deep（缺省 instant）与 source_scope=[datahub,web,uploads]（非空且不重复）；其余 mode/workspace 与旧请求兼容。会话摘要公开同名锁定值；详情/SSE 增加 research_plan、research_sources、research_report。

Prompt.expected_formats 与能力 default_formats 向后兼容接受 pdf。未知模型工具事实的 deep 提交返回 deep_research_tools_unverified；既有技能准入、凭据未知与幂等收据不弱化。内部 skill-preflight 仅在既有响应中拒绝被排除的来源，不新增权限或控制端点。


DSH 0.2.1 升级保持公开 HTTP 合同。内部 `subagent.list` 适配已移除的上游方法：读取权威父会话 `subagentCatalog` 投影，并与实时 `session/list` 的子会话归属、模式和 running 状态交叉核对；输出映射为既有 `kind=child` 与 `activity=running/inactive`，供详情、归属、取消及空闲保护共同消费；缺失或未知状态返回协议失败，不用空列表解除活动保护。空实例默认 `deepseek-flash`，已保存旧模型值继续保留。保存、应用、真实推理仍分别返回事实，不因默认值更新自动调用模型。

Automation 兼容旧目标，新增 research_task 版本定义、weekdays、expected_version 与 Run 快照；本轮 Claw 控制接口见上节。现有运行记录在执行中可返回已保存原生关联；failure_code 可报告 automation_reference_invalid、automation_reference_conflict、automation_reference_persistence_failed 或 native_submission_unconfirmed。关联错误不触发自动研究重试，报告成功仍取原报告校验/产物事实。

macOS 异根私有 Native pair 认证只修复公开 CLI 的后续生命周期准入：已有根的完整不同根
pair 可继续 start/force restart，未知/变化/同根写者仍返回 `runtime_ownership_unknown`。
桥内 hint 不序列化到 CLI/HTTP 响应，不新增参数、配置开关、HTTP 路由或字段；force 不绕过
重检，安装未就绪的首次 Native 切换仍在停止健康 Docker 前拒绝。

内部端口 TypedDict 与显式默认值整理不改变公开参数、返回字段或错误类型；
省略 Web/Runtime 端口仍沿原选择合同，控制与回滚错误码保持。

1A收口：`ModelConfig.api_key`拒绝明显掩码、redacted/hidden占位及空白，错误响应仍固定invalid_request且不回显输入。普通新消息在受理收据/Native prompt之前检查凭据，configured严格为true才继续；缺失为model_credentials_missing，未确认形状为model_credential_state_unavailable。Runtime credential_storage来自受控source映射，未知不猜测为Keychain。

模型页新增 `POST /api/research/runtime/model/test`：用户显式最小生成，通过现有 DSH 会话与最终事件验收，返回 `status`、`selection`、`checked_at`、可选 `session_id/code`；不返回密钥或推理正文。`PUT /runtime/model` 增加互斥的 `clear_api_key`，返回 `configured/applied_to/inference_verified`，保存不代表推理通过。Runtime GET 分开展示已保存、新会话应用、凭据配置、后端类型、提交结果未知及最近测试。
显式 Docker 模型后端的受控来源 `docker-encrypted-file` 投影为
`credential_storage=docker_encrypted_file`；未配置时 configured=false，损坏/拒绝读取时仍为
unknown/unavailable，不能推导真实生成通过。HTTP 不增加取密入口或秘密返回字段。
保存模型的空闲保护读取真实子会话活动，不要求已结束历史的执行模式仍可恢复。内部活动查询仍校验父归属、原生子任务来源与严格布尔 running；历史 unknown 模式不能由此执行，未知活动或正在运行仍拒绝保存。HTTP 请求/响应和凭据边界保持。

macOS Native 模型 bridge 失败时，Runtime GET 保留成功的 Host `connected/health_check_passed`，仅将 `credential_configured` 设为 null、`credential_storage` 设为 unknown、`credential_code` 设为稳定 `model_credential_backend_unavailable`。不回显 Keychain 异常、不把未知当作可用；保存/请求仍沿既有失败关闭与 uncertain 处理。

公开 Native installer auto-start 在同次持锁创建根后完成安装门并启动，不新增 CLI 参数
或 HTTP 字段。check-only/Docker/no-start 不重执行 Native auto-start；已有根未知写者仍拒绝。

公开启动入口在运行账本缺失且监听归属未知时返回 `runtime_ownership_unknown`；Docker
origin commit 失败进入与健康失败相同的归属核验和恢复顺序。

缺运行账本/端点时，显式 --web-port/--runtime-port 也须核验旧默认端口写者；其他 checkout
的 Web/DSH 数据根未知时仍返回 runtime_ownership_unknown，不把换端口作为新的写者权限。

本次启动原错误（例如 web_health_timeout）在失败恢复未获证明时仍为主错误；附加诊断进入
受控日志/异常 recovery_issues，不把恢复失败伪装为新的可重试 bind 错误或新增 HTTP 字段。

内部控制 JSON/URL parser 提取与独立端点/origin helper 不增加 HTTP 路由或响应字段；
DataHub/MCP 原 reader 错误与权限合同保持。公开启动路径现消费端点/origin事务；CLI新增
`--web-port` 和 Native-only `--runtime-port`，HTTP路由、研究协议、业务响应字段不因此增加。

Native/Docker 模式选择、Docker 镜像接受摘要与健康等待均在公开 CLI/安装边界；本轮不增加
HTTP 路由或响应字段。Native `rwb web status --json` 是稳定的安全状态投影，不返回日志路径；
Doctor 仍独立校验 DSH 的 ready、build_verified、commit 和 host_applicable。Docker 的
`status/doctor --json` 也只报告可认证的归属和健康事实，不能把构建或 `--no-start` 当成服务 ready。
DataHub、MCP Registry、MCP Runtime 和 Automation 原有 API 的凭据读写改走按运行模式选择的
后端；服务命名空间、请求/响应与错误边界未因此改变，HTTP 响应仍不包含秘密。

本批没有新增 HTTP 路由。`rwb web doctor [--json]` 是本机 CLI 诊断，现有连接目录继续通过
`GET /api/research/data/connections` 投影天软的依赖、配置、探测和可调用事实；响应仍不含凭据。
本轮仍不新增 HTTP 路由；CLI Doctor JSON 升为 schema 2，保留 `ok` 的安装语义，并增加
`installation_ok`、`product_ready`、`model_ready`、安全化 issues/warnings 和每服务的
state/process/ownership/port/protocol/ready。模型 warning 不改变 Web ready。
`rwb web status` 与 Doctor 即使发现问题也在形成完整投影时退出 0；无 `.venv` 时受限后备入口
只提供诊断。既有 `/api/research/runtime` 与 `/api/research/models` 仅供只读就绪/模型事实核对，
不提交研究消息、不生成内容或泄漏 Provider failure 正文。
未安装环境的顶层 `rwb --help` 现在由后备入口直接输出静态帮助；它不请求任何 HTTP API，
不改变本页路由、响应字段或错误码。
`rwb web start` 现在在任何进程创建前消费 Doctor 的固定安装 issue；失败只改变 CLI 错误精度和
等待时长，不新增 HTTP 字段、路由或状态码，也不会暴露本机路径与凭据。
Doctor 的安全 CLI JSON 在 `dsh.runtime_lock_matches` 报告已验证安装闭包是否等于 Runtime build
lock；不匹配加入 `dsh_runtime_lock_mismatch`。该字段不进入 HTTP API，也不返回文件路径。
`rwb web status` 的轻量导入边界同样不新增 HTTP 路由、字段或状态码；Doctor 需要构建证明时仍执行
完整 DSH 闭包校验，status 仅报告既有进程与健康投影。
安装器新增的 Web import readiness 发生在任何服务启动前，只决定安装能否标记完成，不监听端口、
不运行 lifespan，也不新增或修改 HTTP 响应契约。
全新 Profile 初始化、Windows Git 长路径和跨平台进程管理同样不新增 HTTP 路由；3081 健康通过后
才启动既有 8088 API，启动失败不会暴露半就绪接口。

框架 API 固定登记 Gold 与 Dollar，并按 slug 返回版本化专用快照。解释与深度验证均要求客户端提交当前 `snapshot_revision`；版本漂移返回 409，跨框架会话返回 404，避免混合结论。详细字段与模式边界见 [研究框架](08-research-frameworks.md)。全局 `/artifacts` 只遍历未删除会话；显式查询软删除会话返回 410，恢复后重新可见。

能力工作区的 Method 复用现有能力接口，没有新增路由。`#/skills` 以
`kind=skill|tool|workflow|method|data` 作为五个主分区，
`view=library|mine|plans|connections|market` 只表示类型内二级视图；这些都是纯前端路由参数，继续读取
本页已有的 capabilities、tools、data catalog、data connections 与 report-workflows 接口。
旧 kind 深链保持兼容，无 kind 的 plans/connections 分别归一到 Workflow/Tool；`market` 只在 Tool
分区有效。Phase 2A 已增加功能开关保护的只读 MCP Registry API；Phase 2B 增加安装预览、
不可变安装记录、健康探测、Runtime 启停、OAuth、会话授权、资源/提示读取、高风险审批及 DSH
私有工具代理。Phase 2C 增加通用 Automation、运行查询/重试、报告日程显式迁移与投递渠道接口。

本轮跨平台修复不新增或修改 HTTP 路由。Windows 上的 Runtime 认证读取、DataHub 快照接口和会话文件下载在进入既有响应契约前执行规范路径、重解析点、普通文件及打开前后身份校验；Profile junction containment 与 PowerShell PID 探针只修复 3081 生命周期，不改变响应 schema。失败继续返回既有安全错误，不暴露本机路径或文件内容。waterfall/cancel 的空或非字符串标识在协议边界统一返回 `protocol_error`。
MCP staging、安装 payload、清单与确认令牌目录的 Windows mode 修正发生在服务装配和安装预览
边界，不改变请求或响应 schema；目录类型、符号链接和重解析点仍关闭失败，POSIX 私有权限检查
保持不变。
本地 PyPI 执行器在精简环境缺少 pip 时可使用已安装的 uv 完成同一份离线计划；这是 Host 内部实现
选择，不新增 API 字段、错误码或安装能力，也不改变浏览器确认摘要。

路由由源码声明、架构清单与 OpenAPI 双向核对；唯一操作数由生成检查更新，不以手写计数替代。`report_workflow_routes.py` 提供具体报告 Workflow 的资源、版本、Provider 探测、运行、重试、交付和日程接口；`mcp_registry/routes.py` 提供只读目录、同步与外部 Publisher 交接；`mcp_runtime/routes.py` 提供功能开关保护的安装、运行、授权和 Host 代理契约；`automation/routes.py` 提供任务、Run、迁移和渠道契约；`operations.py` 只聚合真实运行证据。目录与消息使用当前原生能力版本契约；API 不是旧 `/api/research-runs`。

| Method | 路径 | 源码 |
|---|---|---|
| GET | `/api/research/capabilities?kind=method` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/mcp/registries` | `app/research_web/mcp_registry/routes.py` |
| POST | `/api/research/mcp/registries` | `app/research_web/mcp_registry/routes.py` |
| GET | `/api/research/mcp/registries/{registry_id}` | `app/research_web/mcp_registry/routes.py` |
| PATCH | `/api/research/mcp/registries/{registry_id}` | `app/research_web/mcp_registry/routes.py` |
| DELETE | `/api/research/mcp/registries/{registry_id}` | `app/research_web/mcp_registry/routes.py` |
| POST | `/api/research/mcp/registries/{registry_id}/sync` | `app/research_web/mcp_registry/routes.py` |
| GET | `/api/research/mcp/servers` | `app/research_web/mcp_registry/routes.py` |
| GET | `/api/research/mcp/servers/{registry_id}/{server_name:path}/versions/{version}` | `app/research_web/mcp_registry/routes.py` |
| POST | `/api/research/mcp/publisher/preview` | `app/research_web/mcp_registry/routes.py` |
| POST | `/api/research/mcp/publisher/validate` | `app/research_web/mcp_registry/routes.py` |
| GET / POST | `/api/research/mcp/installations` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/installations/preview` | `app/research_web/mcp_runtime/routes.py` |
| GET / PATCH / DELETE | `/api/research/mcp/installations/{installation_id}` | `app/research_web/mcp_runtime/routes.py` |
| GET | `/api/research/mcp/installations/{installation_id}/status` | `app/research_web/mcp_runtime/routes.py` |
| GET | `/api/research/mcp/installations/{installation_id}/capabilities` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/installations/{installation_id}/probe` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/installations/{installation_id}/enable` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/installations/{installation_id}/disable` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/installations/{installation_id}/update` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/installations/{installation_id}/oauth/start` | `app/research_web/mcp_runtime/routes.py` |
| GET | `/api/research/mcp/oauth/callback` | `app/research_web/mcp_runtime/routes.py` |
| GET | `/api/research/mcp/approvals` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/approvals/{approval_id}/approve` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/approvals/{approval_id}/deny` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/sessions/{session_id}/mcp-authorizations` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/sessions/{session_id}/mcp/resources/read` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/sessions/{session_id}/mcp/prompts/get` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/internal/mcp/tools/call` | `app/research_web/mcp_runtime/routes.py` |
| GET | `/api/research/automations` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automations` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automations/migrations/report-schedules/preview` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automations/migrations/report-schedules/apply` | `app/research_web/automation/routes.py` |
| GET | `/api/research/automations/{automation_id}` | `app/research_web/automation/routes.py` |
| PATCH | `/api/research/automations/{automation_id}` | `app/research_web/automation/routes.py` |
| DELETE | `/api/research/automations/{automation_id}` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automations/{automation_id}/enable` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automations/{automation_id}/disable` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automations/{automation_id}/run` | `app/research_web/automation/routes.py` |
| GET | `/api/research/automation-runs` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automation-runs/{run_id}/retry` | `app/research_web/automation/routes.py` |
| GET | `/api/research/delivery-channels` | `app/research_web/automation/routes.py` |
| PUT | `/api/research/delivery-channels` | `app/research_web/automation/routes.py` |
| GET | `/api/research/runtime` | `app/research_web/main.py` |
| GET | `/api/research/runtime/tabbit` | `app/research_web/main.py` |
| PUT | `/api/research/runtime/tabbit` | `app/research_web/main.py` |
| GET | `/api/research/models` | `app/research_web/main.py` |
| GET | `/api/research/model-profiles` | `app/research_web/main.py` |
| POST | `/api/research/model-profiles` | `app/research_web/main.py` |
| PUT | `/api/research/model-profiles/{identity}` | `app/research_web/main.py` |
| POST | `/api/research/model-profiles/{identity}/activate` | `app/research_web/main.py` |
| DELETE | `/api/research/model-profiles/{identity}` | `app/research_web/main.py` |
| PUT | `/api/research/runtime/model` | `app/research_web/main.py` |
| POST | `/api/research/runtime/model/test` | `app/research_web/main.py` |
| GET | `/api/research/workspaces` | `app/research_web/main.py` |
| GET | `/api/research/sessions` | `app/research_web/main.py` |
| POST | `/api/research/sessions` | `app/research_web/main.py` |
| GET | `/api/research/sessions/{sid}` | `app/research_web/main.py` |
| PATCH | `/api/research/sessions/{sid}` | `app/research_web/main.py` |
| DELETE | `/api/research/sessions/{sid}` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/restore` | `app/research_web/main.py` |
| DELETE | `/api/research/sessions/{sid}/permanent` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/messages` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/tabbit-access` | `app/research_web/main.py` |
| GET | `/api/research/sessions/{sid}/tabbit-tabs` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/cancel` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/approvals/{aid}` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/questions/{qid}` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/upgrade` | `app/research_web/main.py` |
| GET | `/api/research/sessions/{sid}/events` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/uploads` | `app/research_web/main.py`；Office附件含docx/xlsx/pptx，保留原会话归属与30MB限制，上传不执行Office |
| POST | `/api/research/sessions/{session_id}/document-operations` | `app/research_web/report_routes.py`；显式format/operation/mode，输入file_id、修改expected_sha256，文件执行复用报告sandbox；原生业务尚未接通时返回unavailable，禁止静默回退 |
| POST | `/api/research/internal/data/document-operation` | `app/research_web/report_routes.py`；Runtime有限文档工具，沿既有实例私有鉴权，可信会话绑定，不接收宿主路径 |
| GET | `/api/research/sessions/{sid}/files` | `app/research_web/main.py` |
| GET | `/api/research/sessions/{sid}/files/{fid}/{action}` | `app/research_web/main.py` |
| GET | `/api/research/skills` | `app/research_web/main.py` |
| GET | `/` | `app/research_web/main.py` |
| POST | `/api/research/data/queries` | `app/research_web/workbench.py` |
| GET | `/api/research/data/queries` | `app/research_web/workbench.py` |
| GET | `/api/research/data/queries/{query_id}` | `app/research_web/workbench.py` |
| POST | `/api/research/handoffs` | `app/research_web/workbench.py` |
| GET | `/api/research/artifacts` | `app/research_web/workbench.py` |
| GET | `/api/research/assets/observations` | `app/research_web/asset_routes.py` |
| POST | `/api/research/assets/observations` | `app/research_web/asset_routes.py` |
| GET | `/api/research/assets/observations/{observation_id}` | `app/research_web/asset_routes.py` |
| POST | `/api/research/assets/observations/{observation_id}/blocks/{block}/refresh` | `app/research_web/asset_routes.py` |
| GET | `/api/research/watchlists` | `app/research_web/asset_routes.py` |
| POST | `/api/research/watchlists` | `app/research_web/asset_routes.py` |
| POST | `/api/research/watchlists/{watchlist_id}/items` | `app/research_web/asset_routes.py` |
| GET | `/api/research/asset-notes` | `app/research_web/asset_routes.py` |
| POST | `/api/research/asset-notes` | `app/research_web/asset_routes.py` |
| PATCH | `/api/research/asset-notes/{note_id}` | `app/research_web/asset_routes.py` |
| GET | `/api/research/asset-alerts` | `app/research_web/asset_routes.py` |
| POST | `/api/research/asset-alerts` | `app/research_web/asset_routes.py` |
| PATCH | `/api/research/asset-alerts/{alert_id}` | `app/research_web/asset_routes.py` |
| GET | `/api/research/asset-notifications` | `app/research_web/asset_routes.py` |
| GET | `/api/research/operations/summary` | `app/research_web/operations.py` |
| GET | `/api/research/operations/usage` | `app/research_web/operations.py` |
| GET | `/api/research/operations/tools` | `app/research_web/operations.py` |
| GET | `/api/research/operations/datahub` | `app/research_web/operations.py` |
| GET | `/api/research/operations/services` | `app/research_web/operations.py` |
| GET | `/api/research/operations/storage` | `app/research_web/operations.py` |
| GET | `/api/research/local-integrations` | `app/research_web/local_integrations/routes.py` |
| POST | `/api/research/local-integrations/probes` | `app/research_web/local_integrations/routes.py` |
| GET | `/api/research/local-integrations/probes/{probe_id}` | `app/research_web/local_integrations/routes.py` |
| POST | `/api/research/local-integrations/verifications` | `app/research_web/local_integrations/routes.py` |
| GET | `/api/research/local-integrations/verifications/{verification_id}` | `app/research_web/local_integrations/routes.py` |
| GET | `/api/research/data/catalog` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/data/capabilities/{capability_id}` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/data/sources/{source_id}` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/data/connections` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/data/connections/migration-preview` | `app/research_web/datahub/routes.py` |
| POST | `/api/research/data/connections/migrations` | `app/research_web/datahub/routes.py` |
| GET / PUT / DELETE | `/api/research/data/sources/{source_id}/configuration` | `app/research_web/datahub/routes.py` |
| POST | `/api/research/data/sources/{source_id}/probes` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/data/probes/{probe_id}` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/sessions/{sid}/datasets` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/sessions/{sid}/datasets/{did}` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/sessions/{sid}/datasets/{did}/rows` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/sessions/{sid}/datasets/{did}/files/{name}` | `app/research_web/datahub/routes.py` |
| POST | `/api/research/internal/data/business-query` | `app/research_web/datahub/routes.py` |
| POST | `/api/research/internal/data/cancel` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/capabilities` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/tools` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/workflows` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/import` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/creation-sessions` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/from-artifact` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/capabilities/{cid}` | `app/research_web/capabilities/routes.py` |
| PATCH | `/api/research/capabilities/{cid}/draft` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/{cid}/copy` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/{cid}/check` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/{cid}/publish` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/{cid}/disable` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/{cid}/enable` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/{cid}/rollback` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/capabilities/{cid}/versions` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/capabilities/{cid}/versions/{version}/export` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/capabilities/{cid}/versions/{version}` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/report-workflows` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/providers` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/providers/{provider_id}/probe` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/migrations` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/{workflow_id}` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/weekly-production/prepare` | `app/research_web/report_workflow_routes.py` |
| PATCH | `/api/research/report-workflows/{workflow_id}/draft` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/copy` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/resources` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/{workflow_id}/versions` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/versions` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/versions/{version}/publish` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/versions/{version}/rollback` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/versions/{version}/preflight` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/{workflow_id}/versions/{version}/resources` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/{workflow_id}/versions/{version}/resources/{resource_path:path}` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/disable` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/{workflow_id}/runs` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/runs` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/{workflow_id}/schedule` | `app/research_web/report_workflow_routes.py` |
| PUT | `/api/research/report-workflows/{workflow_id}/schedule` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-runs/{run_id}` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-runs/{run_id}/cancel` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-runs/{run_id}/retry` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-runs/{run_id}/refresh-manifests` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-runs/{run_id}/delivery` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-projects` | `app/research_web/report_routes.py` |
| POST | `/api/research/report-projects` | `app/research_web/report_routes.py` |
| GET | `/api/research/report-projects/{project_id}` | `app/research_web/report_routes.py` |
| PATCH | `/api/research/report-projects/{project_id}` | `app/research_web/report_routes.py` |
| POST | `/api/research/report-projects/{project_id}/files` | `app/research_web/report_routes.py` |
| GET | `/api/research/report-projects/{project_id}/versions` | `app/research_web/report_routes.py` |
| POST | `/api/research/report-projects/{project_id}/versions` | `app/research_web/report_routes.py` |
| POST | `/api/research/report-projects/{project_id}/rollback` | `app/research_web/report_routes.py` |
| GET | `/api/research/report-projects/{project_id}/runs` | `app/research_web/report_routes.py` |
| POST | `/api/research/report-projects/{project_id}/runs` | `app/research_web/report_routes.py` |
| GET | `/api/research/report-projects/{project_id}/schedule` | `app/research_web/report_routes.py` |
| PUT | `/api/research/report-projects/{project_id}/schedule` | `app/research_web/report_routes.py` |
| GET | `/api/research/report-projects/{project_id}/artifacts` | `app/research_web/report_routes.py` |
| GET | `/api/research/report-projects/{project_id}/artifacts/{artifact_id}` | `app/research_web/report_routes.py` |
| GET | `/api/research/documentation/{name}` | `app/research_web/documentation.py` |

## 约束与错误

- 消息提交使用 `Idempotency-Key`；受理返回 202，不是执行或交付成功。受理未知时不自动重试。
- Tabbit `web_fetch` 接管依赖浏览器自动化；多实例必须选择 16 位实例 ID。会话授权后才可读取候选，消息最多引用 8 个不重复且同实例的标签页，并要求 `tabbit_live_confirmed=true`。发送前重新验证可用性；claim、提取、释放或 token 生成任一步失败均不提交消息。
- Tabbit 配置 JSON 固定使用 UTF-8；Windows 原子替换只在临时文件句柄关闭后执行。清理异常不得覆盖原始保存错误，接口继续返回既有稳定错误契约。
- 会话、附件、文件、数据集必须属于产品索引中的当前会话；模型参数不能选择任意宿主路径。
- `GET /sessions` 默认只返回正常会话，`view=deleted|all` 显式读取墓碑；软删除写入 30 天可恢复窗口，恢复不触碰 DSH。永久删除和到期清理先调用 DSH `session.delete(cascade=true)`，确认根 ID 位于 `deletedSessionIds` 后才清理本产品目录与索引；运行中或删除已开始的会话拒绝恢复。服务启动与每 6 小时的在线保留期任务都会重试过期墓碑。
- `GET /data/catalog` 与详情接口只读取静态目录；`POST /data/sources/{id}/probes` 才检测一个指定来源，使用 `Idempotency-Key` 去重。探测结果只返回安全化错误码和耗时，不返回凭据或上游正文。
- `GET /data/connections` 汇总 22 个来源的配置、检测、适配和可调用状态；通用 configuration 接口只回传非秘密字段与 `secret_configured`。旧环境迁移必须先预览、再携带明确来源与二次确认执行，任一步失败均补偿恢复配置、凭据和 `.env`。
- `GET /local-integrations` 返回本机集成的安全四维状态；`POST /local-integrations/probes` 要求 `Idempotency-Key` 并返回 202 与独立任务 ID，查询接口只返回安全化状态或错误。服务端只允许一个真实探测执行，使用固定字段与安全操作路由白名单，并对无副作用检测设置时限；超时结果不会落盘。v0 探测不启动软件，不返回命中路径、注册表值、命令参数或环境变量。
- `GET /integrations/status?scope=all|data|local` 返回统一五阶段状态和五类汇总；`POST /integrations/probe-batches` 创建启动或手动全量探测，`GET /integrations/probe-batches/{id}` 返回批次进度，`PUT /integrations/{id}/auto-probe-consent` 管理收费、登录或厂商来源的自动探测授权。活动 scope 去重；公共来源最多并发 4，厂商来源串行。原数据源和本机单项接口继续作为兼容层。
- `POST /local-integrations/verifications` 仅接受 Excel、Word、PowerPoint 与 Wind Excel 白名单目标并要求 `Idempotency-Key`；查询接口返回安全化进度与结果。Office 验证只操作服务生成的临时文件；Wind 只在独占空白工作簿执行最小厂商公式并把二维码安全验证映射为待授权。PowerPoint 不要求 `python-pptx`；Workbook 阶段 timeout 显式受 180 秒总预算减 10 秒协调余量约束，进程及超时清理由服务端绑定本轮真实所有权，既有用户 Excel 不得成为清理目标。
- 本机验证结果只有在上下文指纹一致且尚未到达 TTL 截止时才参与 `callable` 投影；TTL 为 `0` 时立即失效。
- 研究取数只使用 `internal/data/business-query`，接受稳定业务能力、白名单来源 ID 和能力限定参数；旧产品前缀工具及其平行查询接口已经移除。浏览器不能直接调用 internal 入口。
- 资产与主题查询和交接均使用 `Idempotency-Key` 并经过串行准入。前端业务入口重分组不改变这些 HTTP API、历史 section 值或持久化格式。交接在创建目标会话前验证请求中的数据集归属，并限制页面上下文为 64 KiB；查询受理或 DSH 回合结束均不等于报告交付完成。
- 报告 Workflow API 管理具体报告版本包；运行只允许已启用且有当前版本的项目。`weekly-production/prepare`仅为`huaan-etf-weekly`准备未发布的新合同版本，重验主管理员归属，不运行模型、不发布或启用日程；其他workflow返回明确拒绝。详情新增`weekly_production`安全摘要，包含策略、待发布版本、owner/Provider状态、最近运行及停用的默认周五15:30日程。Run分别保留执行、交付、质量、定稿与绑定状态；启用新合同日程须当前版本真实手动运行已定稿。来源配置、路径、厂商表达式和凭据不由该接口接收。`report-projects`是迁移期兼容接口，没有独立产品导航或第二引擎。完整合同见[华安周报](../../research-web-etf-weekly-production.md)。
- operations 接口只返回安全化聚合。`summary` 是页面首选的一次性聚合，同一请求对每个会话的 DSH 历史只读取一次；服务进程状态还会核对状态指纹、项目/数据根与实际 PID 命令签名。分项接口保留给精确读取和测试。没有 usage 或价格时返回未知/未配置，不伪造零和费用。
- 结构错误返回明确 4xx；DSH 协议/连接故障不回退演示。服务端日志不输出密钥。
- MCP Registry 路由在 `RESEARCH_MCP_REGISTRY_ENABLED` 关闭时返回 404。同步固定官方 `/v0.1` 与不透明游标，失败只返回带 `stale` 的最后成功缓存；身份三元组不跨 Registry 合并。认证 Registry 必须使用 HTTPS，无认证 HTTP 仅限精确 loopback，OAuth 端点始终使用 HTTPS。服务器 API 返回有界 Unicode plain text；包记录分别返回 `package_type_supported` 与 `immutable_reference`，不返回 `supported/installable` 或 Stage 2A 可安装承诺。Publisher 两个接口只返回规范 JSON、摘要、完整 argv 和 `executed:false`，从不启动 CLI。
- MCP Runtime 路由在 `RESEARCH_MCP_RUNTIME_ENABLED` 关闭时返回 404。安装必须先生成绑定完整摘要的短期确认令牌；本地目标只接受固定版本、逐制品哈希、直接 argv、最小环境和安全解包，远程目标只接受 HTTPS 或显式 loopback。安装、探测、启用与授权分离；每次调用重核安装版本、工具名、schema 哈希、风险分级和会话快照。无人值守只允许任务显式锁定且标记为可无人值守的只读工具；高风险调用必须完成一次性人工审批。内部工具代理只接受私有 loopback 控制密钥，不向浏览器公开。
- Automation 路由在 `RESEARCH_AUTOMATIONS_ENABLED` 关闭时返回 404。任务保存服务端解析的目标版本与内容 SHA；启动只补最近一次遗漏，重叠、版本漂移和中断均写入独立 Run。研究失败不自动重试，投递失败按固定退避独立重试且不改研究状态。渠道秘密只进入当前模式的凭据后端；报告日程迁移必须显式预览、逐项选择并原子应用。
- SSE 为 `snapshot`、`runtime_error` 和心跳；重连通过原生日志恢复。取消和审批复用真实原生 RPC。
- 输出格式和独立交付状态见 [数据与文件](03-data-files.md)。文件下载与 HTML 预览不是任意静态仓库服务。

本清单与 `architecture-map.json` 同步维护。检查接口路径存在不能替代请求/响应契约测试。

Windows 专项作业实际启动 `127.0.0.1:8088`，读取 `/local-integrations` 并完成一次幂等探测轮询。该验证覆盖服务初始化与接口生命周期，不新增 API，也不将未安装厂商软件的 runner 投影为可调用。服务启动使用与生产相同的私有目录校验和 DSH 认证控制文件读取器；CI 占位元数据不表示 DSH 或厂商服务在线。

Phase 2A/2B/2C 路由现在在未设置环境变量时默认启用；显式 `RESEARCH_MCP_REGISTRY_ENABLED=0`、`RESEARCH_MCP_RUNTIME_ENABLED=0` 或 `RESEARCH_AUTOMATIONS_ENABLED=0` 时，既有 404/禁用契约保持不变。接口路径和 schema 未变化。

2026-09-11 的格式基线维护未新增或修改任何 HTTP 路由、请求字段、响应字段或错误码。

启动器项目根与 Node ABI 固定只影响 3081/8088 进程装配；不新增 HTTP 路由，也不改变任何框架、Artifacts 或研究会话契约。

2026-09-14 消息请求增加可选 `method_ids`（最多三个）；能力条目元数据增加 `method_policy`，
会话详情增加解析后的 `methods`、`method_trace` 及可选 `method_trace_incomplete`。方法冲突、超限、
排除或版本不可用在原生提交前返回结构化 409；方法本身不能作为 `capability_id` 运行。现有端点路径
和幂等键语义不变。

## 2026-09-23 稳定性变更回执

本轮未新增或修改 HTTP 路由、请求字段、响应字段或错误码。`rwb web restart` 在 CLI 内通过已认证
DSH `session/list` 判断活动会话；目录聚合在服务内部执行一次 `session.list` 和全部合格父作用域
`subagent.list`，50 个父会话的扇出并发上限为 8。仅已创建、存储为 `running`、原生父会话和全部子
会话均空闲的陈旧行才追加 `detail()` 恢复；恢复同样不超过 8、保留目录顺序，并在异常或取消时取消并
等待剩余任务。未创建、原生运行或子会话运行的行不恢复。各浏览器目录独立维护 pending count
与 generation，逐资源 settled 且 latest request wins；只有 runtime pending/settled failure 会分别
投影为 UI/Composer/submit 的可见 connecting/offline。这些均为既有响应上的客户端语义，不形成新
API 或 Automation 契约。

## 2026-09-28 Windows 停止回执

本轮未新增或修改 HTTP 路由、请求/响应字段或错误码。变化仅在 `rwb web stop` 的 Windows 受管进程
实现：非强制终止失败后允许进入既有强制升级；归属不明或强制失败仍返回 CLI 错误。

## 设置闭环阶段3：当前能力范围

新增内部POST /api/research/internal/data/skill-preflight，复用X-Research-Data-Key、专属Runtime及所属会话边界，body仅含session_id、可选native_name/tool_name和确认加载标记loaded；响应仅为范围，不返回凭据。capabilities列表/详情附readiness；会话详情与受理回执附capability_readiness。预检只读，确认加载才记录固定版本。


## 单一兼容模型连接请求合同（1B实施中）

ModelConfig 对原 deepseek-official 固定端点保持限制。新增的 openai-compatible 请求合同只识别 openai-completions、显式 base_url/model 和 credential_mode；URL 拒绝 userinfo、query、fragment、非HTTP协议及控制字符。HTTP和无Key模式仅接受本机loopback，无Key模式拒绝任何Key输入/清除请求，有Key模式留空表示保留。

这是请求验证，不证明Runtime已安装适配器或能推理。服务和页面现已接通单一兼容连接；固定DSH扩展与独立系统ref已完成合成合同；页面/API保存与合成冷重启恢复已验证，还须真实新增模型和当前代码CI后才完整验收，禁止只宽松Provider字符串求成功。


内部GET model-connection复用现有实例私有DataHub鉴权，只返回五项已验证非秘密连接事实及可选公共revision；拒绝凭据字段和含认证信息URL，未知事务拒绝投影，绝不返回秘密。元数据查询不持有 mutation lock，避免本机模型查找回调死锁。适配器对连接/系统ref读取前后比对公共配置版本，并在真正发送前重检，配置变更不会把新Key发送到旧地址。


兼容连接PUT沿原串行事务和活动父/子任务门，专用系统ref及uncertain/cleared状态独立于官方服务。任意配置/凭据保存或清除更新公共revision；换地址不继承旧Key，旧会话绑定地址/协议/认证方式，变化后下一提交拒绝改投。无Key模式credential_required=false、credential_configured=null、storage=not_required，不冒充已存Key或已生成。Runtime应用还绑定当前connection revision与Runtime实例。

Doctor 的 capability 字段表示安全实现边界，validated=false 不替代平台回执；缺安全读取 primitive 的架构路由返回 501 documentation_platform_unsupported，不开放其他文件路径。

## 本机状态及Office自动验证

GET `/api/research/local-integrations`附带`integration_status`，其中`scope=local`、`generated_at`、`local_revision`与本次明细同快照；GET或POST发现probe不触发真实操作。协调器新增unverified/stale/not_detected/not_applicable分类，Excel桥保留事实但不重复计数。现有auto-probe-consent接口仅扩展`local:excel_app`、`local:word_app`、`local:powerpoint_app`，写入仍要求精确同源与用户动作头。Office开启请求在既有批次消费，厂商不包含在内；API与证据期限细节见[协调器](09-integration-coordinator.md)。

## 资讯雷达只读 API

全部路径前缀为 `/api/research/intel`，仅支持 GET，返回解包后的上游 `data` 对象或列表：

| 本地路径 | 上游路径 | 参数 |
| --- | --- | --- |
| `/overview` | `/intelligence` | impact=all/medium_high/high，view 固定 compact |
| `/story-focus`、`/breakfast-focus` | `/intelligence/story-focus`、`/intelligence/breakfast-focus` | 无 |
| `/events/{event_id}` | `/intelligence/events/{event_id}` | ID 为 1–160 位字母数字下划线/连字符 |
| `/reports` | `/report-records` | limit 1–50，默认 20；offset 0–100000 |
| `/reports/{report_id}` | `/report-records/{report_id}` | 同上 ID 校验 |
| `/radar` | `/radar` | 无 |
| `/wsc` | `/wsc/live` | cursor 最多 256 字符 |
| `/social` | `/social/accounts` | 无 |
| `/news`、`/announcements` | `/news`、`/announcements` | code 必须为六位数字 |

参数不合法返回 422；上游内容不存在返回 404；连接、状态、格式异常返回 502；超时返回 504。错误响应 `detail` 包含固定 `code/message`，不暴露上游正文。无任意 URL、POST、模型调用或采集触发入口。事件概率不提供数据接口。


## 研究情报统一入口 · 2026-10-12

主导航统一为“研究情报”，本地热点与事件在 `#/intel/hot`，现有外部8栏目仍在 `#/intel/*`。旧 `#/workbench/hot` 链接保留视图/事件参数后转入本地页。两类页面共用栏目导航、主题与Host；本地版本证据和Golddata外部只读数据保持身份与覆盖来源区分，外部读取不写Hot、领取任务或调用模型。Hot未启用时，外部栏目与设置继续可用。

恢复的DOCX切片通过 `GET /api/research/hot/briefs/{brief_id}/docx?version=<固定版本>` 从签名/哈希核对的冻结输入生成并保留私有产物，复用报告DOCX生成器；导出不创建会话、不调用模型、不外发。该路径尚需完整产品/恢复验收，局部测试不代表研究闭环完成。


`POST /api/research/hot/research/handoffs`要求同源、显式动作和有界JSON，字段为runId/requestId/briefId/正version/materialIds(1–20)/targetMode(fingpt|claw)。相同固定请求准备同一目标会话和快照，返回snapshot_ready与研究草稿；不提交付费研究。`GET /api/research/hot/research/runs/{run_id}`只读映射与真实状态，不创建或执行任务。未知会话创建与未知研究执行分别保留状态。


2026-10-13续跑：新增Native管理CLI model-amend-tokens（scope、max-tokens、daily-max-tokens、authorize-paid、reason、可复用request-id），通过既有私有stdin管理进程；不新增浏览器付费管理API。

## 历史子会话模式兼容 · 2026-10-13

GET会话列表及父详情不因已验证活动的历史子mode=unknown整体返回503。父详情沿用subagents的status/error字段显示运行中或历史不可用；真实活动/归属未知仍返回协议错误，响应schema不增加字段。

## 框架展示元数据 · 2026-10-14

框架目录 item 和 data 响应中的 framework 附加 display：kind 为 native-embed 或 static-embed，url 为本站 /frameworks-embed/{slug}/，imported_at 为资产导入日期，bot_enabled 表示本站框架 Bot 是否接入。Gold／Dollar 的定义字段与 snapshot 保持原合同；该附加对象不参与快照 revision。九个静态看板 Bot API 返回 409 framework_bot_unavailable，不发起 DSH 会话。

会话列表/详情已有status枚举继续使用waiting_input：原生未决提问（包括映射父会话的子研究提问）优先显示待答，原生仍运行不把待答伪装为转圈执行中。无需读取每个会话详情，问题解除后恢复真实执行状态；已读完成圈为本浏览器显示偏好，不增加写API。

旧网页记录只有as_of值、没有可追溯出版meta/header证据时，当前只读投影保守返回unknown；有正文header但与旧日期冲突时同样保留unknown。旧索引和原文不回写，此状态不能被当成来源已核验；新读取会保存实际出版证据，未来发布日期继续触发原截止日门。

原交付层与报告格式器共用同一task_id的冻结required_formats；显式UI/能力选择优先，deep无选择时才从用户明确格式文本取默认。上下文和Host投影均读取Store中的同一回执，拒绝错任务和未知格式，不能由模型或传入的交付投影减项。

### 模型连接管理 API

GET /model-profiles 返回 items/active_id；每项只含 id/name/provider/model/base_url/protocol/credential_mode、active、credential_required/configured 及 uncertain，无 Key 或物理 credential_ref。POST/PUT 使用原 ModelConfig 字段加 name；Key 可省略保留，但新地址不能继承旧端点凭据。POST /{identity}/activate 从服务端已保存配置激活，禁止客户端携带新的连接参数。DELETE 只归档，无自动凭据删除；被会话/日程引用或当前协议路由拒绝归档。运行/未知活动拒绝修改，凭据写入回执未知保留 durable uncertain。旧 PUT /runtime/model 保持字段和返回契约，同步当前 profile。服务器邀请制仍只允许 DeepSeek 官方，不能通过新路径添加/激活任意兼容上游。


2026-10-23 插件原生审核：expected仅接受manifest/artifacts/schemas三项或再加sandbox四项；未知键失败关闭，实际值仍与当前不可变原生快照逐项核对。此修复保留远程三项兼容，避免受管离线Python的合法四项指纹被旧HTTP模型误拒绝。

2026-10-23 既有内部`POST /api/research/internal/data/business-query`的BusinessQuery新增可选typed `required_semantics: "cn_stock_daily_cny_share_v1" | null`，默认null保持旧请求指纹；仅market_bars/规范沪深stock/daily/none合法，其他组合输入422。它由Host规范历史设置，不成为Runtime/DSH普通数据工具的可传业务参数。新job公开投影及canonical metadata记录required_semantics，retry冻结原值，缺字段旧job保null；manifest和缓存指纹绑定合同，旧原生数据不能冒充已证明价格单位的规范数据。无新HTTP端点或SQL迁移。

## 全市场终端v2 API

旧GET市场缓存、POST刷新／任务查询取消、行情筛选导出保持。POST刷新新增可选`index_set=core-v1|terminal-v2`，默认core-v1兼容旧12；终端请求terminal-v2独立缓存24指数。

| 方法 | 路径（/api/research/market） | 合同 |
|---|---|---|
| GET | /indices/catalog | 本地固定版本目录、分组、身份及默认置顶，不采集 |
| GET | /analysis?horizon=intraday|swing|allocation | 缓存六维特征、分项、风格、来源、历史及验证缺口；正式total_score/allocation无有效证据时为null |
| GET | /portfolios/readiness | 金元只读接入条件及未接通原因，不接收凭据 |
| GET | /portfolios | 本账号已确认快照、受日期／陈旧门约束的估值，金元接入待确认 |
| POST | /portfolios/preview | 256KiB有界manual/csv输入；as_of为上海日期，currency/cash/holdings及可选cost、risk_profile；返回账号确认令牌 |
| POST | /portfolios | 显式confirmation_token保存已预览快照，不接收任意持仓替换正文 |

预览最多500行，asset/quantity或asset/quantity/cost CSV列；风险字段risk_tolerance、equity_min/max、single_name_max、sector_max使用0—1比例。预览票据15分钟，存储有界。无正式预测有效性证据时不输出综合择时分、配置区间或个人调整金额；HTTP客户端参数不能开启。所有GET不创建文件或访问上游，POST沿原维护准入与账号根隔离。

2026-10-23 资产v6封闭部署配置绑定常驻c1a260fa与已合并PR197产品eac68068；仅此配置使用固定ZIP日志读取器，旧恢复合同和严格全账号保全不变。详见[部署合同](../../research-web-gateway-upgrade.md#资产筹码与精炼布局固定部署v6)。

2026-10-23：资产行情数值采用A股红涨绿跌，开高低收各自对真实前收比较；涨跌额/幅按正负着色，零、无效及缺失基准保持中性。沿原主题红/绿变量，只给数值上色；历史十字线、日周月与局部报价刷新同步，计算和冻结数据不变。


2026-10-23：现有GET/PUT /api/research/assets/chart-preferences兼容原panels与chip_settings；可选favorites/indicator_settings仅接受封闭ID与有界数值，额外键/NaN/Infinity/布尔/字符串拒绝，周期顺序验证。账号沿原认证Store；无新HTTP或任意查询入口。

## 2026-10-23：既有BusinessQuery的明确来源范围

不新增HTTP端点。financials的`statements=["income_statement"]`选择新浪来源限定利润表，`periods`最多8；公告日只有日期精度且历史版本未知，as_of/backtest拒绝。factor_macro的`source=bea_archive`只接受`series=us_real_gdp_qoq_saar,start_date=end_date=2024-06-30`；先非历史首捕获，再在`2024-07-25T12:30Z <= as_of < 2024-09-26T04:00Z`读取官方发布版本，历史refresh或miss不会转实时取数。正式截止选择仍通过当前来源和仓库授权；该有限例外不开放通用native正式PIT。详见[DataHub](../../research-web-datahub.md)。


2026-10-23：新增apply-assets-v7仅是本机受管CLI分派；不增加HTTP接口、账号权限、公开服务或任意目标覆盖入口。

## 2026-10-23：BaoStock盈利能力来源

沿既有BusinessQuery入口使用financials/source=baostock、statements=[profitability]、periods单个2017年起季度末。auto仅选择该数据集，不能换成Sina income_statement或财务摘要。拒as_of/backtest；日期精度pubDate不是精确历史可得时刻。保存与显示allow_stale读仓仍检查当前授权，严格最新研究重新取数，旧显式冻结可读。

## 2026-10-23：长期研究档案与机会预警

新增账户绑定域 `/api/research/dossiers`，包含档案、记录修订、时间线、证据／成果关联、冻结 handoff、signals、scan 与 tracking；写入沿用 expected_revision／幂等键，争用返回409，客户端不能提交 owner、源 hash、披露日期或质量通过声明。handoff 返回 `auto_send:false`，仅实际 Prompt 的 `dossier_handoff_id` 绑定研究；受管插件固定凭据／评估动作保持独立审批。完整字段见[档案 API](../../research-web-dossiers-ui.md#ui-接口合同)与[候选动作](../../research-web-seek-alpha.md#个人凭据)，本段不替代主任务生成的 API inventory。

## 华安 ETF Excel 生产来源

本次无新 HTTP 路由；原华安策略新增显式 data_source=wind_excel，旧 wind_client_api 保留。Excel schedule enable 明确拒绝，旧持久化计划停止执行。私有 collector 仅消费 Host 锁定资源和归属，浏览器/模型不能提交认证材料；API Atlas 路由清单不变。
schema4 来源合同将本期伦敦金历史的单点补查作为独立版本资源绑定，Host 从原 EDB、WSD 和 TDAYS
重放，不增加通用补数接口或改变原始行情。普通租户、旧合同与定时权限保持原边界。


今日发现组合固定Native部署复用既有v4操作员、BirthFence与全账号索引/档案/模型保全，新增closed profile及同一idle内离线零后台任务门；不改变本模块既有运行节点、HTTP/数据schema、Docker/平台执行职责或DSH质量判据。新mode每次首次/恢复均拒绝启用自动化/周报日程、活动或未知执行，不通过启动账号后端取得空闲证明。Mac本机、操作员CI与实际切换/认证页面分别取证，Windows/Linux产品状态保持未执行；详见research-web-gateway-upgrade.md的今日发现组合固定部署。

档案固定部署使用 `apply-dossiers`／`reviewed-research-dossiers-v1`：前版固定已核验 `5343e18d9f203a87f2d958218e4288afa527711f`，产品固定包含 PR209／PR212／PR213 的已合并主线 `1780064b712afb61ff18f2f1811650fc31fd3038`。复用原 version4 维护锁、BirthFence、Native／RuntimePool／市场及 DataHub 空闲检查、全账号64MiB业务索引与档案保全和恢复；依赖锁、DSH、自动兼容清单、凭据及付费调用保持原合同。源码、CI、实际服务切换和登录后跨会话验收分别留证，未执行的层级不标通过。

2026-10-23：资产周/月读数与副图入口修复不新增HTTP；仍复用原观察、历史分页和封闭图表偏好API。单一＋只是原目录入口合并，关闭副图保留既有账号隔离保存合同。
