# Research Web DataHub

## 同版本筹码输入合同（2026-10-23）

固定 tinysoft 的 `market_activity` 新增 `dataset=chip_turnover`：只接受单一A股和1–32个唯一有序合法ISO日期。SDK限定预定义“换手率”因子，核对固定名称/公式/说明，响应精确覆盖证券和日期，单位为百分数。保留0，拒绝负值、错身份、重复/缺日期及非有限值。不开放任意因子/表表达式，不从旧全局环境取密。

历史任务 `include_chip_inputs=true` 时，在原始日线、因子和逐日换手全部冻结并重验授权后，生成独立规范版本。VWAP只在原量额单位为股/元已核实时计算，再乘相同复权倍率；平价OHLC的唯一价格单独处理。raw_rows不被改写，返回行附turnover_rate_pct/vwap，manifest附chip_inputs合同版本、单位、摘要、有效条数及导出依据。失败、取消或不完整输入保留旧 canonical 指针；真实SDK Future仍须排空。重试保留原include flag及范围。Wind60日门、因子预检与原来源限制保持。


2026-10-23 免费官方数值读取沿原 Host → DataHub → Provider → 原生研究仓链，新增的可入仓
清单仅为 NYFed rates 与 Treasury cash；WorldBank inflation 同步加严身份/年份/分页验证。
三者使用 official-numeric-v2 版本隔离新缓存，旧会话/冻结证据保留。分页 partial、缺值和
错误封包不能成为完整仓库命中；原始响应、原字段与百万/十亿美元或百分数的官方单位声明
均随原件保存，未核单位不猜测。详见[官方数值边界](research-web-vendor-snapshots.md)。

## 华安ETF周报私有同源取数

`DataHub.collect_report_weekly`仅供受信Report Run使用，不新增`datahub_*`公开工具或放宽通用Wind
参数。沿原连接准入、单调用容量、配置复查、原始响应/哈希、会话快照与幂等回执，由封闭WindPy适配
取得周报映射数据。SDK可导入不认证具体字段或许可；日历/经济日历未核实、数据过期或无真实同源
对照时明确阻断，未经证明的组不静默切源。原通用Wind仍经Excel；这两条路径不能按品牌混称已验证。
完整来源、交易期、工作簿投影与未验证项见[数据合同](research-web-etf-weekly-data.md)和[生产合同](research-web-etf-weekly-production.md)。

默认Host已挂入可选ResearchWarehouse；数据设置与能力中心复用同一配置及有界免费验证面板，保存不会连接，Doctor只报告脱敏配置/驱动状态。实际调用健康按来源、能力和配置摘要独立记录，最长300秒、最多256条；改配、撤权或过期即失效。数据库/会话缓存不刷新上游健康，显式探测与实际取数证据分开。连接中心的“部分能力已验证”只覆盖列明的能力与时间，不代表整个供应商或正式回测合格。

官方数值响应按封闭合同展开：世界银行分页头与观测分开，未取完分页返回partial；BLS逐series的year/period/value保留，不把M13年均值冒充月份；iFinD历史time数组与table指标逐项核对长度后展开。未知单位保持provider_defined。完整源字节仍冻结，账号/刷新令牌入口不入仓；详见[原生快照](research-web-vendor-snapshots.md)。官方说明：[世界银行](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures)、[BLS](https://www.bls.gov/developers/api_signature_v2.htm)、[iFinD](https://quantapi.51ifind.com/gwstatic/static/ds_web/quantapi-web/example.html)。

## 研究仓及可靠性基座（2026-10-22，隔离实现）

本阶段新增可选的 `MarketStore` 与可信 `WarehouseBridge` 注入接口，原有会话快照继续读取；正式数据根/数据库配置与自动采集尚未启用。仓库按明确交易日历检查内部缺口，原始日线按缺失连续区间补数后重新检查整窗覆盖；未知空结果不会证明停牌或无交易。显式 refresh 重取请求区间以发现修订；源间自动切换仅开放经过审核的沪深股票原始日线口径，复权行情和财务/资金流不依据同名字段猜测等价性。内核及权限/恢复合同见[研究仓](research-web-market-store.md)。

Wind 日线的60自然日限制只约束实际供应商取数。完整仓库读取仍检查沪深股票身份、频率、复权及日期语义，但不以总窗口长度拒绝已有数据；来源授权、配置摘要与仓库owner仍逐次复验。仅在可信Host的仓库启用、refresh=false、无as_of、沪深股票原始日线长窗时，先有界规划Wind缺口，再对每个实际缺口执行正常60日准入。规划绑定请求指纹和来源配置；空库、失效或过大的缺口不会被盲拆或整段送SDK。auto可按真实原因跳过该Wind候选，固定Wind明确拒绝；预规划及执行共用原总预算，取消继续等待实际存储Future排空。显式refresh=true不进入此路径。

只有auto请求遇到明确的来源专属data_outside_declared_scope时才重新resolve并完整准入；固定来源、缓存来源和全局冻结/能力拒绝不借此切源。候选排除与真实skip原因保留，重复返回同一已拒来源立即停止，不重复调用admission。

`BusinessQuery` 新增 `purpose=display|research|backtest`、`quality=strict|allow_stale`、有时区的 `as_of`；默认请求指纹保持兼容，正式回测必须提供历史时点。未证明的历史视图返回 `data_pit_unavailable`，不以当日下载补造过去版本。实际尝试在 `provider_metadata.execution_attempts`，数据成功在 `data_success`；调用完成不代表数据可用。前台总预算18秒，超时返回504及稳定代码；原call_id保留，已启动SDK/数据库在后台排空、真实结束前仍占容量，迟到结果不能发布。断连不取消owned计时器；重复call_id不重发。

BaoStock 0.9.4新增公开沪深股票原始日线、股票目录和交易日历适配，其财务/新闻绑定仍未实现；无账号SDK不等于厂商数据再分发许可。BaoStock与AKShare由固定模块、最小环境和私有临时HOME的自有子进程执行，每次12秒上限；这仅是生命周期隔离，不是插件沙箱。AKShare新浪日线量为股、换手率比例转百分数且不当作成交额，东方财富手数转股；所有未知指数/ETF量单位仍明确标记。

真实免费验收：AKShare provider 新浪历史日线7行、2.04秒、结束后无活动Future；BaoStock首次provider请求12.01秒超时、零行、已回收。其他来源、认证页面及最终CI验收不能由这些样例推定通过。

## 资产目录与结构化区块

2026-10-22新增账号内无会话目录读取：`GET /api/research/assets/search`触发一个合并的后台目录任务，显式通过Broker核验`search_assets/tinysoft`，在同一凭据namespace读取秘密前后及Provider返回后复核配置／授权指纹。它不创建研究会话或启动模型。完整目录按代码／名称／GB2312简拼排序，并兼容常用多音字首字母候选（如银行、重庆、西藏）；不改证券名称、代码或旧缓存格式，不引入拼音依赖。搜索只返回最多50个匹配项（默认20），完整记录不在5000条截断。固定SDK调用保持每次≤5000行、15秒及一个真实Future；名称按≤500证券一批取得，不放宽底层上限。

目录状态为loading／ready／stale／error／unavailable，当前账号`asset-directory/index.json`保留24小时同指纹缓存，最多20000条／8MiB。冷启动立即返回loading并轮询，旧缓存过期可读并后台刷新，失败有30秒重试间隔；配置或授权变化禁止复用旧目录。固定`.pending.json`只按本次创建的文件身份清理，未知遗留不删且明确刷新失败。后台任务跨SDK批次始终进入resident活动／关闭等待，真实Future未结束不放行空闲。目录实际读取持有既有resident共享准入租约；事务围栏期间不启动SDK，返回deployment_busy，取消时等待真实SDK退出后才释放租约。

`POST .../blocks/{block}/load`为旧观察补齐区块并按相同来源／区间复用15分钟缓存，显式refresh绕过普通缓存。新缺失activity／margin无显式区间时，按上海时区和保存截止日（缺省当日）持久近60个日历日；events按同一截止规则固定派生60日业务范围，不开放events的RangeBlock参数。旧create／refresh已保存日期语义保留，财务报告期不套此窗口。所有成功受理（包括缓存和合并）先保存幂等签名；来源／区间冲突或同键换条件返回409，保存失败不启动新查询，也不替换其他活动区块共享引用。初始观察、旧refresh、新load共用区块锁；失败保留旧快照，规范历史只能由history-job发布。接口和文件见[API](architecture/research-web/04-api.md#资产目录搜索与区块按需加载)与[存储](architecture/research-web/03-data-files.md#资产目录与按需区块缓存)。

天软结构化适配在`providers_cjpy_assets.py`封闭表、字段及预定义因子，读取前核验SDK metadata，不接受任意repo／表达式。market_snapshot提供PETTM、PBLF、独立PBMRQ、PSTTM、总股本和来源总市值；普通PB与PB-MRQ分开，源市值单位为万元。financials读取主要财务指标及同报告期的合并利润表，必要时使用金融利润表；以报告截止／公布日约束，不套用行情60日区间，不混不同报告版本。market_activity支持holder_data汇总、holder_details名单、industry分类、margin_trading和events公告标题／类型／日期；行业PE／PB没有提供，events不生成分析，fund_flow不选择未实现此dataset的天软。

财务及两融源单位为元，币种未单列时不猜CNY；原字段、来源字段、日期、报告期与单位metadata随快照保留。AKShare保留中文原列并增加已证明等价的财务／净额标准字段，不构造流出或资金构成。auto按capability及dataset的真实实现选源，显式来源不能静默替换；未取到的新估值字段保持partial，不填伪值。CJPY宏观、ETF和指数不因本轮沪深北A股目录与固定表接入而获得支持声明，原复权factor_macro白名单保持。

本机有限预检读取完整5577条目录及603986相关七类结构化区块，原始证据只留私有`logs/asset-data-preflight/`；这不是全证券、全历史、真实浏览器链路、同候选安装CI或部署验收。各级状态见[任务报告](../.ai/reports/test_report_asset_interaction_data_20261022.md)。

## 资产历史任务与固定复权

2026-10-23 来源合同：新页面观察使用auto，初次历史请求明确recent/daily/none/source:auto。未传source的旧客户端仍固定tinysoft；旧观察不批量改源，用户可显式切换历史来源。只有近期原始日线开放auto/Wind/AKShare/BaoStock；qfq/hfq、older/all保持原Tinysoft因子与固定锚点合同。Broker在执行前跳过超过Wind60自然日上限的auto候选，继续同证券、同daily/none口径的等价来源；显式Wind仍报参数错误。不会拆分换源，也不扩大transient集合。

非Tinysoft请求的原始输入必须核验证券身份、请求日期、OHLC与量额声明单位：价格为CNY/share、量为share、金额为CNY；turnover只有声明CNY金额时才映射amount。每个有值OHLC/量额别名均须声明相同单位且数值一致，不能默选首字段；可选量额全为空仍保持缺失，不填零。未知单位、错证券、区间外日期或同日冲突停止规范发布，旧图保持；这种失败不声称已经质量降级。规范版本`asset-history-raw-2`逐输入绑定真实provider/URL/manifest/hash/配置摘要。最终发布及缓存命中复验实际来源授权，取消和partial按所有涉及来源的真实Future排空。无上市证据保持listing_date:null、boundary_verified:false、full_history:false。

历史任务可选as_of为新一版冻结的截止／锚点输入，省略时保持旧行为。重新进入个股时，若来源实际报价交易日超过旧全历史的截止锚点，按新日期独立重建完整历史版本，原全历史／因子／研究冻结材料不改写；新证券首次recent默认不变。不能按HTTP读取日冒充报价交易日，也不能用一次recent替换已完成全历史。新版本仍受全部因子／覆盖／代次与原子发布门约束，失败继续保留旧版本。

2026-10-22 启动保全热修复限定Store持久化边界：旧磁盘缺失且仍为精确默认的历史jobs/keys和图表偏好只在内存提供；启动或Automation无关save不将其写入旧index，首次真实变化才落盘。原有键（含空值）及写入后恢复默认的键继续保留，原子替换失败不误记已持久化。DataHub Provider、raw/factors/canonical、业务API与严格保全门不变，不追加厂商调用或放宽来源权限；同候选Mac安装与真实恢复/部署另证，详见[文件合同](architecture/research-web/03-data-files.md#资产历史与图表偏好存储)。

最后核对：2026-10-22。历史工作区沿用当前账号的 Host → DataHub Broker → 天软 CJPY → 会话快照链路，不建立另一研究引擎或全局行情数据库。`asset_history_jobs.py` 负责持久任务、分块、取消与发布，`asset_history.py` 负责日线校验、合并及复权。任务范围为近期2自然年、向前续取4年、全部至上市日；没有上市日证明时仅声明1990-01-01扫描下界。每块最多4自然年且边界日重叠，按从近到远顺序处理；同日同值去重，冲突失败，不任选一条。每次 Provider 调用仍≤5000行、15秒、每来源一个真实 Future；规范合并结果可以超过5000行，不能因此截断客户端读取。

`factor_macro` 的天软绑定只开放封闭的 `series=adjustment_metadata|listing_date|adjustment_factors`；后两者只接受一个规范沪深A股证券，逐日因子每次1至500个唯一、非未来 ISO 日期。拒绝任意仓库、公式、宏观全集及额外参数；这不代表通用宏观或因子库已经接入。metadata版本为 `tinysoft-adjustment-v1`，定义 SHA-256 为 `76fb444109d027db7657b8baea96a4299b5d8ddb826aac7edc31dfb09df82fc5`。

产品规范前复权为 `P(t) × A(t) / A(as_of)`，后复权为 `P(t) × A(t) / A(listing_date)`；`as_of` 是当前已得到的最后交易日，续取更早区间保留原锚点。复权前校验真实上市日行情、上市日因子等于1、全部交易日期有精确正因子、定义及来源配置版本一致。只调整 OHLC，量额保留供应商原值。缺因子、上市日/锚点未证明、哈希不符、重叠冲突或版本变化一律失败关闭，不向前填因子、不回退原始价；旧规范快照继续可用。

已授权独立预检在两只股票、676个交易日及上市日上完成18次实际调用，审阅报告 SHA-256 为 `85fc23ae55255cdaec3e693753d4202c972a56ba29b9bd41b93750c273849cf3`；独立 gate 为 PASS。原始市场行、因子、授权与 wire 文件仅留私有 `logs/wind-adjustment-preflight/`，不提交仓库。此有限实测不证明全市场或全历史已验证；厂商原生前复权与本规范存在全局尺度差异，其精确全局锚点未知，不承诺 SDK 的按截止日复权保证。OHLC币种和单位未声明；成交量“股”、成交额“元”仅引用供应商目录声明，不升级为独立单位核验。

原始块、因子与来源 manifest 不可变，并按账号保存缓存、配置摘要与因子版本。每次发布把全部累计规范行和同版本 metadata 一起写成新快照，再比较观察代次与旧 dataset 指针并原子切换；不能拼接不同锚点下的已复权块。重试只有显式请求才发生，复用缓存仍复验授权、来源 hash 与因子；旧观察与旧研究冻结材料继续可读。研究交接复制规范行、原始响应、因子和 metadata，脱离原任务后仍可复核。

取消将子 DataHub `call_id` 联动取消，但同步SDK的真实 Future 结束前仍为 `cancelling/draining`，不释放来源容量、不发布迟到结果。Host关闭、会话取消/清理及恢复都覆盖历史任务；遗留无owner任务恢复为 `interrupted`，不自动重试。常驻空闲证明同时检查 Store 非终态任务和真实 CJPY Future，未知 witness 保持未知并阻止切换。API、持久化及UI合同分别见[接口](architecture/research-web/04-api.md#资产历史任务与图表偏好)、[文件](architecture/research-web/03-data-files.md#资产历史与图表偏好存储)与[工作台](research-web-ui.md#资产观察工作台)。

## 无会话全市场数据

2026-10-23：同批列表新增f350涨停价/f351跌停价和`limit_status=up/down/none/unknown/not_applicable`。仅同日有效现价在正数限价区间内才比较相等；缺失/非正/冲突/无现价记未知，停牌/未上市/退市不参与，不套固定涨跌幅或ST名称规则。总览与CSV明示确认值及覆盖缺口。

昨日基线优先保留较新日期/采集时间，并可从上一完整缓存恢复，持久化重启后继续使用。来源明确收盘的逐股时间不得早于15:00；昨日成交额按本次已上市股票池逐股重算上一交易日完整收盘快照；日历必须确认精确前一交易日。来源f292=5为已收盘；旧缓存只在逐股同日15:30后时间、完整分页/金额和收盘后采集均可核验时认证。旧未上市股票只有同日来源明确返回0，才可覆盖次日新上市证券的昨日金额；不补造零，不以指数成交额替代。内部`previous_close`保留逐股金额、原snapshot_id/采集时间，反复刷新仍保留昨日见证；公开`previous_amount`只投影重算金额、scope_count/missing_count或明确reason。缺证券、日期/金额或收盘见证时留空。

大盘资金在原同用户、同板块key内按Eastmoney/SH+SZ/daily定义逐日留存最近30条实际记录；`rows/row_count/provider_total`仍指本次供应商响应，`history_rows/history_count/history_requested/history_status`单独指已留存/目标/缺口，每日保留来源URL和原采集时间。重复日期由本次真实记录更新，不生成空白日或声称连续完整。首次仅1日时明确历史未补齐，失败保留旧值与stale/error；不混用其他资金分类。盘前来源rc=100/data=null保持缺口，不能当零资金。历史端点连接中断/访客仅1日/其他报表无等价合同均如实记录。

`datahub/providers_market.py` 在现有依赖内对东方财富固定端点进行有界异步读取，沪、深、北按独立范围完整分页；北交所身份不能仅由上游 `f13=0` 推为深圳。保留来源总数、页数、行情时间、日期分布与缺口，重复、漏页、总数变化和容量超界不能标为完整。市场采集使用独立容量边界，其他 Provider 的5000行限制保持。

公开报价、指数分时、沪深大盘日线资金固定使用 `82.push2.eastmoney.com/webguest/api/qt/`。旧 `push2his` 资金端点连接中断，访客端点已返回真实当日沪深合计；参数 `secid=1.000001&secid2=0.399001` 及15列日线定义与[AKShare原适配](https://github.com/akfamily/akshare/blob/main/akshare/stock/stock_fund_em.py)一致。每次保留实际返回的交易日数，不把请求30日解释为已取得30日；缺失、无效金额、重复/逆序及未来日期拒绝。大盘资金使用自身元数据并继承所属采集的陈旧/错误；本轮仅资金失败时保留同用户同key的上次完整日线及stale/error，成功后恢复。资金按东财订单分类，不等于Wind机构净买入，也不含北交所。没有改代理、证书或重定向边界。

股票池继续使用[东财当前官网脚本](https://quote.eastmoney.com/center/static/build/index.js)的沪、深、北独立范围；`f292` 状态定义来自[官网报价脚本](https://quote.eastmoney.com/newstatic/build/vendor.js)：6停牌、8暂停上市、14盘中停牌、9未上市。未上市不补造当日价格；停牌价格为来源参考价，`price_basis` 区分 quote / suspended_reference / last_traded_reference / previous_close_reference / unlisted，不当作当日成交。单股 `stock/get?fltt=2` 中 f43/f60 已按价格单位返回，而 f301 仍依 f59 缩放，不能直接当元。空成交额/量只用同身份、同日单股 f48（元）/f47（手→股）明确数值补回，零值不当缺失；最多100只、共享3并发及10秒明细预算，沿用单响应/总字节和外层期限。失败保留缺口，不覆盖已有可靠字段；`quote_detail` 保存来源、字段、原时间和采集时间。

广度增加 suspended/unlisted；unknown 仅代表其余证券的实际报价缺口，六类合计仍对账完整股票池。成交额从同批股票池中已上市范围计算，`amount_scope_count`、`amount_missing` 明示分母与缺口，停牌的真实零成交额参与合计，未上市单列。上市日期只在 f26 提供时显示，不从名称或价格猜测。CSV追加 `trade_status`/`price_basis`，旧缓存与原列仍兼容；源码不迁移业务 index。2026-10-22完整实采5581（沪2319/深2908/北354），停牌7、未上市4、真实交易样本5570；报价及已上市成交额缺口0，单位和时点另留证，不把来源目录完整性当独立交易所目录证明。

腾讯、与新浪访客报价已做只读对照：腾讯明确停牌标记及参考价格与东财吻合；新浪对部分停牌返回零价/旧日，北交所样本为空。不将不同源状态/单位默混进本批；本轮现有东财接口已补齐目标缺口，不新增依赖或登录。实测、合同与保全部署记录见[任务报告](../.ai/reports/2026-10-22-market-gaps.md)。

`MarketService`使用当前用户market-cache/保存当前及上一完整快照，GET消费缓存、POST显式刷新；不产生研究会话、研究receipt或DSH调用。indices的默认Host链路现通过`datahub/market_reader.py`接入个人ResearchWarehouse；完整固定12指数响应作为一个原生响应封包入仓，既有GET不读上游也不主动读仓。POST始终实际取上游；仅受信内部`refresh=False`读可使用同来源、同配置摘要、300秒内的仓库捕获。行业／概念按东方财富分类，沪深大盘资金不含北交所；其余分区仍走既有公开适配。本次不改变天软权限，也不注册未经等价性核实的第二来源。

公开eastmoney访客合同目前没有独立来源授权开关，不能声称已实现该来源grant撤销；真实可撤销边界为Host生命周期与个人仓库profile。读写前后复核Host未关闭、用户根/仓库根一致，以及profile的id、owner、enabled和脱敏配置摘要、来源配置/固定合同摘要。profile停用或换配置后不能再命中旧仓库，进行中变化拒绝交付；每次底层read/write/export仍走MarketStore授权。浏览器不能提交actor/scope。新增`warehouse`元数据准确区分hit/persisted/incomplete/disabled/not_configured及数据库不可用；仅数据库busy/unavailable/operation_failed允许继续上游，授权和合同错误不降级。partial/失败/缺指数/缺分时不替换旧完整捕获；不提升研究质量、PIT或正式回测资格。公开源可达、字段可用、分页完整和真实验收分别记录。

资产页估值与coverageRows仍是浏览器DTO，但本轮另增加上述目录／load HTTP和缓存合同。来源摘要按当前区块动态统计已取得／待加载／查询失败／未接入，成功空结果与未读取快照分开，新闻／公告不计入DataHub统计。数据日、as_of、retrieved_at、报告期、请求／实际／已载入区间保留，不能合并为一个“最新”。

AssetWorkspace保持旧create／refresh；新页面进入专题后按需调用load，旧观察可补缺块。section_sources覆盖原source，未指定时沿保存值；显式source变化必须保存并按该来源重新查询，显式专业来源失败不能隐式fallback。section_ranges仅允许history／activity／margin的完整ISO日期对；holders.end_date仍为报告期，不参与历史日期覆盖。

valuation沿market_snapshot请求close／pe_ttm／pb／pb_mrq／ps_ttm／total_shares；天软按上节的预定义因子取得新字段。普通PB不升级MRQ，PS-TTM不以市值／单期营收补造；Wind未提供的新字段保持partial，未核验股本数量级不派生市值。财务仍从业务financials进入，按所选Provider实际支持的报告期／报表合同读取，不能把本轮最新披露数据称为多年财务历史。

新观察默认概览auto、近期历史明确auto/none，旧观察固定源及其余缺块auto，Broker按dataset真实实现选源，fund_flow不选未实现该dataset的天软。Wind60日硬门保持，不截断或拆分、不泛化为天软财务与历史任务限制。真实全历史、首次自动加载和逐区刷新仍分别留厂商证据；有限预检或离线fixtures不替代完整验收。新闻／公告仍按证券读取既有Golddata接口，和旧DataHub news／announcements快照的来源身份分开。

正文读取通过原实例私有数据桥按本会话已登记来源 ID 执行，不增加 Provider 凭据或修改已有取数合同。取消使用受信原生 call_id，有限请求的实际输入字节与来源身份保全，搜索摘要继续未核验；正文范围及网络保护见架构 03–05。

FinGPT 数值验收读取本会话真实 DataHub 快照及上传文本，不复制候选分支的直接腾讯/东财/iFinD 调用路径。未经现有 Provider 合同和环境验收的来源继续未接入。检索摘要不作为全文证据，缺口不伪装成可调用或已核实。

原生日程动作复用的DataHub内部桥只补充Automation稳定拒绝码白名单；具体拒绝原因可被模型识别，错误message/detail与未知、超界响应仍不透传。全文会话搜索走DSH既有session.search，不通过DataHub注册新来源或复制聊天正文。

Broker在没有已适配的候选来源时返回`data_capability_not_integrated`，已适配但配置/依赖/授权/健康条件未满足时返回`data_capability_unavailable`，均为503；非法来源或参数保留原校验。模型工具说明要求说明缺口，不能通过改写同一查询重复尝试，也不授予其他工具或供应商权限。当前`search_web`的Tavily/Bing绑定仍未完成适配；本轮未接入新供应商，不把已注册称为可调用。

原生桥的 manifest 摘要保留 query/provider_query/coverage，便于核对标的、日期与统计范围；行数及哈希一致不能证明单一证券等于市场汇总。工具注册描述明确来源须逐次验证。Wind index_data 的 quotes 是当前快照，不接受历史 date；错误不静默改写，桥接仅返回受限业务代码。

Claw 日程研究在独立 DSH 会话锁定 approved_data_sources 与 approved_tools，仍由原 DataHub/原生准入校验。资料未就绪时保留缺口，定时定义不证明金融来源可调用；试跑文件也不能把合成数据作为真实市场数据。

Hot模型预算HTTP复用既有实例私有控制文件和key；只核对根研究归属及同一Hot账本。
公开Provider能力和查询合同保持，模型回执不能证明来源/厂商可调用。

Claw 项目只聚合成员会话的 DataHub 快照摘要与来源链接；文件引用独立复制已显式选择的附件，不扩大新会话 DataHub 准入或自动复制源会话快照。日程草稿沿既有私有控制认证，不触发数据查询。

DataHub 内部控制 reader 复用 `control_origin.py` 的纯 JSON/回环 URL parser，原错误与
额外有效字段保持兼容；macOS启动链现以静止证明接入显式 origin 事务，只重绑内部URL，
保留既有 token，不迁移供应商凭据。Docker临时准备guest仅用原creator补齐缺失控制文件。

Native 和 Docker 复用 16 项业务能力、64 个来源条目、Broker 动态选源和会话快照合同。
来源条目包含外部总目录及尚待授权/配置的登记，不表示64个厂商已验证可调用。连接秘密沿用
`ResearchWorkbench.DataHub.<canonical-data-home-sha256>` 实例服务命名空间：Native 默认存于宿主 keyring，Docker 仅存于
显式配置的受检私有凭据目录；模式切换不迁移秘密。容器内缺少宿主 Wind/Office 驱动、GUI 或
已登录会话时，不能把 Native 的旧探测结果当作 Docker 当前可调用证明。

DataHub是`app/research_web/datahub/`内的FastAPI进程模块，不是新守护进程、调度器或全局行情数据库。
DSH仍是唯一研究引擎；Web只读资料，原生插件通过受控回环桥接查询同一DataHub。已配置且可用的来源自动执行，不逐次确认。
不导入旧Connector.run、AKShare生命周期或旧报告编译链。通用 MySQL Provider 使用项目依赖 PyMySQL 与当前模式的凭据后端；它不是固定阿里云账号适配器。

## 当前定位与命名

Hot 的公开后台来源扩展目录为 `datahub/hot_public_sources.json`：OpenAI、Google DeepMind、
Federal Reserve 与 ECB 四个固定官方 RSS/Atom 来源。不保存凭据，不导入 ResearchService。
Hot Node 适配器读取这个目录并持久采集到独立 PG schema；原文和待解析条目先入库，
然后按单轮上限分批生成不可变材料版本。此目录尚未注册到既有 Broker 的 15 项业务 Tool
或来源设置页，不能把四个后台来源的实测提升为全部 DataHub 已连通。
`channelHint` 仅帮助后续频道配置，当前尚无事件或频道模型判断。

DataHub 是后台数据总机：统一描述“能查什么”、选择“从哪里查”、把供应商参数翻译成稳定业务参数、标准化结果，并把本次研究使用的数据保存为会话隔离快照。它不替代 DSH、Skill 或 Tool，也不是前端直接执行的能力类型。

```text
FinGPT / Claw / Skill
          ↓
datahub_* 业务 Tool
          ↓
DataHub：静态目录 → 白名单路由 → Provider → 快照与审计
          ↓
东方财富 / 财联社 / 用户 MySQL / 后续完成适配的来源
```

Tool 统一使用 `datahub_*` 子系统前缀，而不是 `rwb_*` 产品品牌前缀。这样未来产品改名不会破坏 Skill、会话历史或 DSH 工具协议。`datahub_get_fund_data` 是基金数据能力的正式工具名。

## 全源静态目录

`catalog.py` 始终声明并供页面展示 15 项业务能力和 22 个来源；读取目录不会连接数据库、导入旧 Connector、访问外网、启动 Excel 或产生供应商费用。15 个品牌无关 Runtime 工具始终注册，目录和协调器状态只决定 Broker 调用时能否找到真实 Provider，不再要求连接变化后重启 Runtime。

业务能力在原有十三项基础上增加数据库目录和数据库单表查询。登记来源增加通用 `mysql`，显示名为“用户 MySQL 数据库”；连接名称可由本机用户命名为“阿里云因子库”等，不把品牌、主机、账号或口令固化到技术标识。

每个来源分别展示：

- `code_exists`：仓库存在相应请求或适配代码。
- `integration_state`：是否已经抽取为 DataHub Provider。
- `configured` / `dependency_ready`：当前配置与依赖是否具备。
- `allowed` / `callable`：是否允许进入业务路由、当前是否实际可调用。
- `health` / `last_checked_at`：最近一次显式探测结果，而不是页面加载时偷偷检测。

数据源设置页由 `GET /data/connections` 提供不含秘密的统一来源投影。MySQL、iFinD、知丘、天软、Tushare、Tavily 与 Bing 的非秘密配置写入 `<RESEARCH_DATA_HOME>/connections/`，秘密使用 `ResearchWorkbench.DataHub` 凭据服务命名空间；Wind 只记录接入偏好，不接收账号密码。Wind Client API 探测只读取当前会话连接状态且不会代为登录；配置保存、来源探测、Provider 适配和 Runtime 可调用是四个独立事实。`#/settings/local` 不再消费此响应或 `local_cache` 投影；它使用专用本机诊断接口，DataHub 的既有接口和研究查询保持兼容。

iFinD HTTP 探测在用户完成现有数据源配置后执行真实登录、健康检查、最小只读基础数据查询和登出；登录成功但空响应、权限或配额失败都不会标记健康。Token 只存在于客户端会话与当前模式的凭据后端，不返回本机集成页或写入日志。

东方财富基金和财联社无需专业配置即可调用。天软 CJPY 已完成证券目录、交易日历、历史行情、实时快照及上述三种封闭复权查询的 Provider 适配；只有 `cjpy` 依赖存在且 `CJ_KEY` 已配置时，对应绑定才可调用。AKShare 已实现 `search_assets`、`market_bars`、`market_snapshot`、`financials` 和 `market_activity`，但仅在 `akshare` 依赖就绪时 callable；其财务摘要把供应商布尔缺失哨兵规范化为 JSON `null`，不把 `false` 作为财务数值写入新快照，其他 capability 的真实布尔字段不受影响。Wind 新增受限 DataHub binding，只复用现有 xlwings/Excel `WindAdapter` 的封闭方法映射：股票日线行情、快照、指数实时行情 `quotes`、固定财务指标，以及资金流、融资融券和股东数据；现有 `fetch_block_trades` 实际返回龙虎榜，不能等价为大宗交易，因此不登记。Wind `market_bars` binding 的资产范围固定为股票，BusinessQuery 与 Runtime 工具接受显式 `asset_type` 上下文，但 Wind Provider 只允许 `stock`；缺失、指数或 ETF 均在 adapter 初始化前返回 `data_not_equivalent`，不会只凭六位代码推断。指数继续通过 `index_data` 的 points 口径查询。每个 capability/dataset 都投影到固定输出字段、类型、单位和日期语义，并拒绝 adapter 返回的任何未知列、其他证券或越界日期；指数身份也必须与请求一致。指数点位使用 points，融券余量使用 share，不能按 CNY/share 或 CNY 发布。业务请求只接受 `.SH`、`.SZ`、`.BJ` A 股代码及封闭字段、日期和复权枚举；不接受 Wind 公式、表达式、路径、凭据或任意字段。只有 xlwings/Excel 路径构成该 Provider 的依赖就绪条件，只有 WindPy 或配置 `preferred_adapter=client_api` 时不能进入 Runtime callable 计算。未登录返回 `wind_not_logged_in`，当前适配器缺方法返回 `wind_method_unavailable`，身份、单位、日期、复权或数据集不等价返回 `data_not_equivalent`。指数成分、宏观/利率及基金持仓没有已核实的现有适配器等价方法，因此不登记为 Wind 已实现绑定。天软的其他登记能力继续显示“能力仅登记”，不会由来源级“已适配”状态错误放行。真正尚未实现的其余来源只用于展示真实覆盖规划与缺口，不会因为“代码存在”被伪报为已连接。手动探测一次只检查一个来源，重复 Idempotency-Key 返回同一 probe；未适配来源直接返回安全化不可用结果且不联网。

Wind `market_bars` 与 `market_snapshot` 都要求显式 `asset_type=stock`；对应 binding 只显示股票，
缺失、指数或 ETF 在 adapter 初始化和可用性检查前失败关闭。通用能力仍允许其他 Provider 按真实
实现声明指数或 ETF 子集。

Wind 的日线、资金流与融资融券入口在 adapter 初始化前验证 ISO 日期、正向区间及含首尾日期最多
60 个日历日的硬跨度；超界不会触碰本机 Excel/Wind 会话。该上限保证现有 WSD 1,000 行边界和
回退路径不会把长区间截断后误报完整；返回记录未覆盖请求终点时标记 `partial`。

## 稳定业务 Tool

静态业务工具集合在原有十三项之外增加 `datahub_get_database_schema` 与 `datahub_query_table`。启动器把全部 15 个稳定工具 ID 写入 Runtime 的 `enabledTools`；保存 MySQL 或其他来源配置后可立即探测并由 Broker 在下一次调用时选用，不需要为工具注册重启 Runtime。

工具只接受对应能力的业务参数及可选 `source`/`allow_fallback`。`source` 必须是目录中的 ID；URL、请求头、凭据、模块名和磁盘路径在 Pydantic 边界被拒绝。已配置、已授权且可用的来源会自动查询，不再弹出逐次确认。15 个业务工具常驻 Runtime；没有可调用来源时 Broker 返回明确失败，Agent 不应盲目重试，也不能降级成网页猜测或演示结果。

天软 Provider 通过固定的 CJPY SDK 0.5.2 专用客户端访问 SDK 固定服务，Provider 边界限制 15 秒和 5000 行；授权值只在 Provider 内使用，不进入结果、普通日志或提示词。供应商成功响应若反射当前 Token，会以 `credential_reflection` 失败关闭且不生成 rows/raw；其余返回数据保留供应商原字段和 raw JSON，不猜测单位。项目在 `tinysoft` 可选依赖中精确声明 `cjpy==0.5.2`，避免未使用天软的基础安装被私有制品阻断；公开 Python 索引截至本批验证仅提供到 0.3.6。厂商环境须先安装普通项目依赖，再从批准的本地 wheelhouse 使用 `--no-index --no-deps --require-hashes` 和 `requirements/tinysoft.lock` 安装经 SHA-256 锁定的厂商 wheel；不能从混合索引解析未来同名版本。缺少可复现制品时继续显示 `blocked_dependency`。

自动执行只移除 DataHub 的逐次确认，不放宽其他边界：回环 token、`trustedDirectory` 父系验证、能力/来源白名单与固定参数 schema、会话隔离快照、取消联动、22 秒原生桥接超时均继续生效。Wind 使用容量为 1 的专用 worker 和 18 秒 Provider deadline；超时或调用方取消后，底层 Excel 调用完成并关闭前保持 `provider_busy`，不会启动重叠调用。

`broker.py` 根据能力绑定、覆盖范围、完成适配、配置、依赖和允许状态选源。`source=auto` 只选择一个最终 Provider，不拼接不同口径；显式来源默认不换源，只有请求明确 `allow_fallback=true` 才允许继续选择。结果记录实际 Provider 与尝试来源。

### 用户 MySQL 边界

- 非秘密字段 `label`、`host`、`port`、`user`、`charset`、`tls_mode` 原子写入 `<RESEARCH_DATA_HOME>/connections/mysql.json`。密码使用按规范化 data home 隔离的凭据服务 `ResearchWorkbench.DataHub.<canonical-data-home-sha256>`、稳定账户 `mysql:default:password`；API 只返回 `secret_configured`，不回填密码。
- 凭据库不可用、锁定或写入失败返回 `credential_store_unavailable`，不降级到环境变量或明文。保存与删除使用补偿流程；删除连接不级联删除既有会话快照。
- `required_no_verify` 使用显式 SSLContext 强制 TLS、关闭证书验证，不允许明文降级。来源详情和每份快照均含 `tls_certificate_unverified`。
- 每次探测与查询先执行 `SHOW GRANTS`；仅允许 `USAGE`、`SELECT`、`SHOW VIEW`，检测到写入、DDL、管理、`ALL PRIVILEGES` 或 `GRANT OPTION` 即以 `unsafe_privileges` 阻断。
- schema 工具按数据库→表/视图→列逐级枚举，排除 `information_schema`、`mysql`、`performance_schema`、`sys`。表查询只生成单表参数化 SELECT，标识符必须精确来自 information_schema；禁止原始 SQL、JOIN、子查询、表达式、聚合、存储过程与 DDL/DML。
- 表查询默认 500 行、最多 5000 行，offset 最大 100000；最多 20 个过滤、100 个 IN 值和 5 个排序项。同步驱动运行在独立容量为 1 的线程执行器内，deadline 15 秒，原始响应 16 MiB。事务只读，成功或失败均 rollback 并关闭连接。

## 查询与来源

| source | 固定公开来源 | 范围 |
| --- | --- | --- |
| fund_nav | `https://api.fund.eastmoney.com/f10/lsjz` | 六位code；成对start_date/end_date按实际分页取得范围，最多十年且不含未来；旧limit只取最近一页、最多100条 |
| cls_telegraph | `https://www.cls.cn/api/cache?name=telegraphList` | 最新limit 1–100条公开快照 |
| fund_profile | `https://fundf10.eastmoney.com/jbgk_<code>.html` | 当前基金身份、规模、经理、费率、基准文字等已核实字段；不是历史时点资料 |
| fund_distributions | `https://fundf10.eastmoney.com/fhsp_<code>.html` | 权益登记/除息/发放日期、每10份分红原文；不构建复权总回报 |
| fund_holdings | `https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc` | code、topline=100、year可选1990..当前年；不填year请求最新可用期。仅解析content的JSON字符串，不执行JS |

source/code/limit/start_date/end_date/year/refresh是业务参数；工具不接受会话、目录、URL、头、cookie、代理或凭据。
日期以Asia/Shanghai校验。基金代码保留前后端份额原文，不合并证券身份。
持仓保留报告期、标题、股票代码/名称、占净值比例、万股/万元原文；报告期不等于披露日期，完整持仓覆盖未知。
HTML资料将换行表头仅用于匹配时去空白，原文字段名仍保留；缺闭合td在下一th/td前截断，避免字段串联。
`---（每年）`等缺失保留original_value而value=null，不解读成零费率。
分红每10份金额保留来源原文；币种未独立核实，currency统一null并标记verified_currency缺失，不由“元”或基金代码猜测币种。

## 限额与状态

内置直接 HTTP Provider 使用固定目的地、不跟重定向、`trust_env=False`，不继承认证或代理，也不自动重试；这些约束不表示 AKShare 或天软 SDK 的底层 HTTP 实现具备同一组限制。直接 HTTP 响应限制为每个1MiB、总原始响应16MiB和最多100页；DataHub Provider deadline 为15秒，原生桥接总超时为22秒，标准化结果最多5000行。
实际NAV响应的TotalCount/PageSize/PageIndex在顶层，记录在Data.LSJZList。请求100实际可能仅20；不能用“少于请求数量”当完成。
实际页码、页大小、总量和日期逐页验证，重复页/总量或页大小变化停止并保留已经得到的原始响应与解析记录。
无穷值、坏日期、超出请求范围、必填数值缺失均明确失败/不完整。

Wind Provider 同样保留 DataHub 单查询 5,000 行；超限返回 `row_limit` 且不截断后继续。专业来源
只在当前本机已登录会话和依赖就绪时调用，不访问网络测试，也不在 Windows 契约测试中启动 Excel。
每次调用创建隐藏的独立 Excel 应用和专用工作簿，公式不得选择用户现有工作簿；成功、失败均关闭且
不保存该工作簿并退出专用应用。若 workbook/app 清理无法确认，稳定返回 `wind_cleanup_failed` 并将
Provider 保持 poisoned busy；进程重启前不创建新 Excel 实例。每个 schema 均验证最低有效字段；关键字段全空失败，请求字段部分
缺失时返回 `partial` 与稳定限制说明。
股票日线、资金流与融资融券历史入口另有取数前硬边界：起止日必须是合法字符串且正序，跨度最多
60 个日历日；超长区间返回 `workload_too_large`，不构造或探测 adapter，更不会先取数再截断。

- `complete`：日期范围请求的来源分页结束且没有已检测到的覆盖异常；不是市场全量的独立验证。
- `snapshot`：单次公开快照已取得，不能宣称完整历史。
- `empty`：来源成功返回零条，和取数失败区分。
- `partial`：已经取得部分可用行但后来失败/触限/冲突；不得自动命中完整缓存。
- `failed`：没有可用行且取数或解析失败；manifest明确标记失败，不伪装报告交付。

AKShare 业务查询和天软是同步 SDK/库 Provider，其底层线程在 Python 内不能被安全强杀。两者分别使用专用单线程执行器、并发容量 1 和15秒 Provider deadline：首次超时返回带 `deadline` 限制的 `failed` dataset；线程真正退出前，后续请求立即返回带 `provider_busy` 限制的 `failed` dataset，不排队、不另起线程。该 Provider 释放容量后才接受下一次查询，不影响其他 Provider 的独立容量。AKShare 自动探测改用可取消的异步 HTTP 流，直接访问固定新浪交易日历 URL，禁用环境代理和重定向，限制响应为 16 KiB；3 秒连接与 8 秒读超时受外层 10 秒总墙钟 deadline 约束，取消时关闭网络流并在 `finally` 立即释放与查询共享的容量。业务查询仍按能力使用真实 AKShare 接口，不把“可导入”当健康。

天软与 MySQL 的供应商异常只投影为有限错误码：配置/依赖、认证、权限、限流、网络/TLS、数据库不存在、供应商 schema 或通用 Provider 失败。SDK、驱动或服务器返回的原始错误正文不会进入 API、快照或日志。MySQL 使用项目声明的 `PyMySQL>=1.2.0`；探测和查询复用同一只读授权、TLS、事务与容量边界。

同值重复日期去重并记录；唯一日期数少于供应商总量时status=partial，即使来源页确已结束、pagination_complete=true。
冲突日期从可用解析记录移除、不任选其一，原始响应保留。直接 HTTP Provider 的取消会立即停止 HTTP；同步 SDK Provider 的取消只终止等待且不发布快照，底层线程按上一段约束隔离至自然退出。私有调用收据保留 cancelled。
BFF关闭及现有会话cancel均取消相关请求。原生abort通过独立短超时取消请求联动；取消先到的调用ID写入tombstone。

## 私有控制与会话存储

启动器/服务创建独立随机控制凭据`.control/datahub.json`，POSIX 为0600且父目录0700。
原生可信插件在trustedDirectory沿实际DSH父系验证后读取固定文件；DataHub 调用按当前可用工具自动执行。
拒绝symlink、hardlink、错误属主或过宽权限；token不进入脚本环境、prompt、普通API或日志，不读取/复用模型密钥。
地址默认`http://127.0.0.1:8088`，首次可信启动可用`--datahub-url http://127.0.0.1:<port>`指定隔离BFF端口；只接受无userinfo/query/fragment/path的回环HTTP origin。已有地址不符报错，不静默覆盖。

Windows 不使用 POSIX mode bit 作为 ACL 证明。控制文件、调用收据和快照通过产品根内的规范路径访问，拒绝链接、重解析点、非普通文件、硬链接、超限内容和打开前后身份变化；快照临时目录写完后才同目录原子改名。POSIX 继续使用 `dir_fd`、`O_DIRECTORY`、`O_NOFOLLOW` 和目录 `fsync`。

```text
.control/datahub.json                         # 新产品控制凭据，只给可信服务/原生插件
connections/mysql.json                        # MySQL非秘密配置；密码在当前模式的凭据后端
.control/calls/<sid>/<call-hash>.json          # 稳定调用ID + 参数指纹 + 受理/结果
.control/snapshots/<sid>/<dataset_id>/         # 原始响应 + 权威manifest
sessions/<sid>/inputs/datasets/<dataset_id>/   # 只读rows.json、rows.csv、manifest.json
```

每次新查询使用独立UUID，临时目录写完后先rename并fsync公共输入，最后rename私有目录作为目录提交标记，不覆盖旧快照。
若进程在两次rename之间退出，公共孤儿目录与私有.pending目录均不进入资料枚举，不阻塞健康资料或新查询，也不自动删除；原pending调用重启后仍不自动重发HTTP。
数据文件创建0600并拒绝链接逃逸；读路径用NOFOLLOW目录描述符逐级打开。
私有manifest作为校验基线，每次目录/详情/分页/下载复核public manifest及解析文件hash。原始文件没有普通Web下载路由，不进附件或报告产物清单。
manifest含schema_version、query、source/source_url、retrieved_at/as_of、字段单位/币种（未知null）、请求/实际日期、行数/总量/页数/分页、coverage、missing/limitations和原始/解析文件相对路径+SHA256。
manifest自身SHA256由详情返回，避免自引用。CSV把外部公式样式文本前置单引号，合法数字不转义；JSON和私有原始响应保留原值。

同会话、同参数、同schema_version的完整请求快照可复用：资讯60秒、NAV/补充资料15分钟，保持原retrieved_at，返回cache_hit=true。
refresh=true始终新建；同原生调用ID重放返回同一结果，同ID不同参数拒绝，重启后pending状态不自动重发。
自动缓存不跨会话。用户显式FinGPT→Claw升级会先校验原资料与原始hash，再复制为新ID、新owner、不用链接、不发HTTP，并保留origin_dataset_id/origin_manifest_sha256及原retrieved_at。
升级draft保留原消息正文，追加旧→新dataset_id映射、原/新manifest hash、原取数时间及当前会话manifest/rows相对路径与文件hash；明确旧路径不适用于新会话，不替换历史正文。

## API契约

- `GET /api/research/data/catalog`：15 项能力、22 个来源、绑定矩阵和诚实汇总；不连接来源。
- `GET /api/research/data/connections`：22 个来源的安全连接摘要、分组、当前平台能力、迁移状态和允许操作；不返回秘密。
- `GET|PUT|DELETE /api/research/data/sources/{source_id}/configuration`：对支持配置的来源读取安全状态、原子保存非秘密配置与可选新秘密，或删除本机配置；响应永不包含密码、Token 或 Key。MySQL 既有 URL 和响应字段保持兼容。
- `GET /api/research/data/connections/migration-preview`：只列旧环境变量是否存在、冲突与目标来源，不返回值。
- `POST /api/research/data/connections/migrations`：仅在请求含明确来源与二次确认时迁移；先写入并回读凭据库，再原子清理对应 `.env`，失败时补偿恢复。
- `GET /api/research/data/capabilities/{id}`：能力参数、字段、覆盖范围和全部候选来源。
- `GET /api/research/data/sources/{id}`：来源鉴权/依赖、状态、限制和支持的数据集。
- `POST /api/research/data/sources/{id}/probes`：以 `Idempotency-Key` 异步检测单一来源。
- `GET /api/research/data/probes/{id}`：读取安全化探测状态、耗时和失败代码。
- `GET /api/research/sessions/{sid}/datasets`：`{items:[summary]}`；老会话返回空数组。
- `GET /api/research/sessions/{sid}/datasets/{did}`：完整manifest、manifest_sha256及下载引用。
- `GET .../{did}/rows?offset=0&limit=100`：`{items,offset,limit,total}`，limit最大500。
- `GET .../{did}/files/{rows.json|rows.csv|manifest.json}`：已校验的当前会话数据文件下载。
- `POST /api/research/internal/data/business-query`：`{session_id,call_id,query:{capability,parameters,source,allow_fallback,refresh}}`；新 `datahub_*` 入口。
- `POST /api/research/internal/data/cancel`：`{session_id,call_id}`。
- `POST /api/research/data/queries`：研究台按业务能力发起幂等查询并创建源会话快照。
- `GET /api/research/data/queries` / `GET /api/research/data/queries/{id}`：读取查询历史、状态和安全化失败原因。
- `POST /api/research/handoffs`：复制并核验所选快照，把页面上下文交给新 FinGPT/Claw 会话。
- `GET /api/research/artifacts`：汇总已有会话的实际输出文件，不扫描任意目录。

所有internal入口在解析请求体之前检查`X-Research-Data-Key`；无认证浏览器不能绕过受控回环桥接直接取数。
公开GET不发起上游请求。浏览器API仍受现有同源边界限制，无CORS、多用户登录或远程部署支持。
`service.detail.datasets`供SSE/UI：id/dataset_id/name/source/source_url/status/row_count/requested_range/actual_range/pagination_complete/retrieved_at/cache_hit/limitations/missing/pages_fetched/provider_total/as_of/files；不推全部行、fields或raw_files。
files条目包含name/path/sha256/size/url/kind=dataset；url为上述专用下载路径。
原生工具返回字符串字段dataset_id/source/status/manifest_json/files_json/sample_json，最多三行样本；Python从只读路径读取全数据，不把历史全部塞进上下文。

## Skill与研究口径

五个专用研究 Skill 及 persona 要求：父 Agent 只调用当前 Runtime 已暴露的 `datahub_*` 工具；可用来源自动查询，不逐次确认。工具未暴露时不调用、不重试；读取 manifest 核对缺失后，复杂 Claw 任务再分两个子 Agent 复用父 Agent 已取得的同一数据集，不重复取数。
六个 CPU 资讯/事件 Skill 不直接连接 Provider，只消费上述工具已经形成的会话 JSON 与
`dataset_refs`。`daily-market-brief` 映射市场快照/日线、市场活动与新闻；`policy-sentinel` 映射新闻
证据并要求输入给定政策关键词、日期和影响对象；`event-review` 映射股票日线及输入给定的基准日线；
`etf-flow-monitor` 需要 ETF 份额、前值、NAV/价格和用户分类；两类业绩监控映射固定财务字段及用户
提供的披露/预告记录。包内 `field-mapping.json` 固定首选 Wind 字段、单位、日期与复权口径，并由
输入 `data_contract` 在运行时逐项核验；provider、mapping/version、单位、日期语义或复权不匹配时
固定返回 `data_not_equivalent`，记录及 dataset ref 晚于结果 `as_of` 时固定返回 `future_data`。当前
日期输入只接受 `YYYY-MM-DD`；每日简报和 ETF 资金流固定使用 CNY。可选 `source_hashes` 存在时逐项
校验规范非空 key 与 SHA-256 value，显式 null、带首尾空白或包含 CR/LF/Unicode 行段分隔符的 key 固定失败；字段缺失时保留空哈希
并以 partial/limitation 降级，不补造、静默改名或合并来源证据。
Wind Provider 没有等价 ETF 份额、宏观、基金/北向暴露或研究覆盖方法时明确
`data_not_equivalent`，必须经过其他可调用来源或用户数据 fallback gate，不声称 Wind callable。
真实 Wind/Excel 对照尚未执行，因此六项内置 Skill 当前可发现但初始 disabled；登记成功的 macOS
Wind/Excel evidence artifact 是启用前置条件。catalog 只接受 artifact 路径并重算输入来源、仓库
golden、实际结果与当前脚本摘要后派生 receipt，状态切换再次验证；synthetic golden 不能替代实测证据。
计算限定已获得数据；累计净值不是总回报指数。未取得期初前一估值日及分红复权口径时只称“首末观测区间净值变动”，不冒称完整日历年度收益。
业绩基准文字不是基准序列；目前未取得可靠基准序列、合同/报告下载服务。20行最近快照不能证明三年表现。
XLSX应包含原始解析记录和公式/计算说明、dataset_id/hash；DOCX/HTML使用同一ID/日期。输入快照不算报告产物。

## 验证与限制

离线：`python -m pytest tests/research_web --confcutdir=tests/research_web -q`及`DSH_SOURCE_ROOT=/Users/leon/Developer/deepseek-harness node --test tests/javascript/research_web*.test.mjs`。
还执行ruff/black/isort/mypy及项目任务完整性检查；2026-09-04 全源目录、真实公开探测、Web 五视口和 Archify 证据见`.ai/reports/2026-09-04-datahub-full-source-catalog.md`，早期 DataHub 实现记录见`.ai/reports/2026-09-02-datahub-implementation.md`。

2026-09-16 现有 Provider 闭环复验中，AKShare、财联社和东方财富基金均通过真实只读探测；三者分别完成 `market_bars`、`search_news`、`fund_data/nav` 查询、会话隔离快照和真实 `datahub_*` Runtime 调用。天软与 MySQL 只完成依赖、契约和安全错误映射验证；由于没有在产品配置中获得天软 Token、厂商许可和可达只读 MySQL 测试库，不能把它们写成真实成功。详细证据见 `.ai/reports/test_report_integration_providers_20260916_b2.md`。

Web 一键环境只接受随包且哈希匹配的 `cjpy==0.5.2`，并同时验证 `requests`、`urllib3`。缺包返回
`blocked_dependency`，CJPY 版本错误返回 `dependency_version_mismatch`。`CJ_KEY` 由当前模式的凭据后端在
每次探测/查询时动态读取，保存后 `restart_required=false`；无凭据的干净安装必须保持
`configured=false`、`callable=false`。安装与升级流程见
[Research Web 一键本地安装](research-web-installation.md)。
真实探测的 `vendor_auth_failed` 和 `vendor_permission_denied` 属于用户可处理的凭据/账号权限问题；
`blocked_dependency` 和 `dependency_version_mismatch` 属于本机环境问题；限流或不可达保留为供应商问题。

MySQL 的单元与界面验收使用模拟凭据后端、PyMySQL 连接和安全化 API 响应，不使用对话中出现过的旧口令。真实连接只有在用户轮换口令、重新保存并显式发起探测后才可验收；Native 系统 keyring 和 Docker 私有凭据目录须按各自平台单独验证，不能用模拟测试代替。桌面 sidecar、Tauri 安装包和安装级烟测不在本次范围内。
Windows 原生本机集成专项已覆盖 DataHub 私有回环控制文件的服务启动读取：路径回退拒绝符号链接/重解析点、目录越界、非普通文件、硬链接和超限内容，并核对打开前后文件身份。POSIX 的 descriptor-relative 路径保持不变；该专项不证明 Windows 上的会话快照发布、连接配置写入或系统凭据库已经完成全量验收。
连接配置原子替换在 POSIX 刷新父目录；Windows 明确跳过不支持的目录 `fsync`。这不降低临时文件刷新和关闭句柄后替换的要求，也不把跳过视为安装级持久化验收。
真实来源只读核对由父任务记录在`.ai/reports/2026-09-02-datahub-source-probes.md`，不把离线测试当真实模型闭环。
2026-09-02集成验收曾按当时机制从Web完成四次原生审批，并取得2025净值13页243条及三类补充资料、完成FinGPT升级复制、两个真实子Agent共享资料，以及DOCX/HTML/XLSX/PNG输出。该记录是旧逐次审批机制的历史证据，不代表当前 Runtime 仍逐次审批；当前行为以上文自动执行和启动时工具物化契约为准。
最终XLSX四张原始表逐值与CSV一致（243/16/25/220行），来源文件hash一致；首末观测区间变动和回撤已独立重算，数值与百分比格式均核对。
首次模型产物曾有回撤百分比放大和无效公式，经真实会话修订后才作为final文件交付；格式检查不是自动语义正确性保证，也不代表任意基金评价已验证。
详细会话、修订、下载和边界证据见[本批真实验收](../.ai/reports/2026-09-02-datahub-acceptance.md)。本批仅更新专属3081/8088；没有修改3080、固定DSH、模型、原生额度或Seatbelt权限。
单Web worker、本机macOS；未验证Linux/Windows、多租户、磁盘总配额或大规模快照目录性能。

## 实例凭据隔离与旧配置

凭据服务后缀只对公开的规范化 data home 路径取 SHA-256，不散列秘密；同一目录重启恢复同一服务，不同目录互不读取、覆盖或删除。所有已适配来源沿现有连接模块复用这一命名空间，不建立第二个 Vault。旧未分实例服务中的记录不会自动读取、迁移或删除；升级后旧非秘密配置保留但凭据显示缺失，用户须在所属实例设置页重新录入。重新录入失败沿现有补偿恢复该实例之前的配置，旧全局秘密不受影响；回滚旧版本仍保留其原记录。既有显式 `.env` 迁移仅针对用户确认的来源，写入当前实例服务，不成为运行时回退。

## 设置闭环阶段3：当前能力范围

ProviderBinding按dataset发布已审阅的语义；未知频率/单位/历史时点不等价于支持。来源健康使用既有healthy状态并绑定配置身份。每次business query在缓存和回执返回之前重检授权，配置/Key替换改变非秘密文件版本，旧缓存不因同样configured=true继承新账户权限。历史下载保留审计用途，不自动成为新的研究授权。


## 单一兼容模型连接

私有GET model-connection只供同一Native模型适配读取非秘密连接字段；鉴权、路径与大小限制复用现有DataHub通道。它不增加业务来源、取密接口、查询权限或缓存授权；模型工具未验证仍由能力准入拒绝，15项数据工具不因文本生成成功而获授权。

## 已整理外部数据源（2026-10-13）

新能力 `external_data`（工具 `datahub_get_external_data`）把用户 2026-10-08 核对的外部来源清单固化为
`app/research_web/datahub/external_sources.json`：41 个取数来源与 102 个 HTTP 入口，另列 10 个参考或未接通来源；
不复制业务项目代码，只保留来源、入口、方法与参数占位。调用先不传参数读取 `ext_registry` 总目录，再按返回的
`source` 与 `dataset` 取数。`arguments_json` 只接受 `params`（填充目录占位符）、`query`（业务筛选）、`body`（POST 业务体）
三个键；URL、凭据、路径、回调、SQL 等键在 Provider 边界直接拒绝。

出口固定为目录内注册的 URL 与方法，拒绝重定向；单响应 1MiB、行数上限 5000，超限保留 `row_limit` 说明。
供应商 HTTP 200 但错误码非零、密钥反弹（凭据出现在响应正文）都失败关闭，不写入快照。四个凭据来源
`ext_ths`、`ext_daole`、`ext_tikhub`、`ext_cicc` 只经 DataHub 凭据后端读取秘密；其中 `ext_ths` 支持用
`refresh_token` 在 Provider 内换取 access token。已保存非空、有界 `access_token` 时优先使用，
只有 refresh-only 配置才交换；业务 401 不自动重试、轮换或回写凭据。换取与业务响应的密钥均不进入参数、结果或日志。

显式 QuantAPI 授权验证对已有 access token（包括旧式纯字符串）只向固定 HTTPS
`https://quantapi.51ifind.com/ds_service_basic/api/v1/get_limit_policy` 发一次 GET，
不跟随重定向、不读取代理环境，总预算12秒，单响应沿用1MiB上限。只接受原生顶层六字段政策形状：
`user_type`／`user_type_cn` 为非空字符串，`qps_limit`／`request_data_limit`／`data_volume_limit`／
`data_range_limit` 为对象；失败、未知形状或秘密反射拒绝认证，不返回用户类型、限额、厂商错误正文或凭据。
refresh-only 配置保持一次显式交换验证。两条路径始终返回 `data_queries=0`、
`data_permission_verified=false`、`token_rotated=false`；元数据认证成功不证明任何市场数据权限。

历史行情保留既有 `ext_ths/cmd_history_quotation` dataset ID 与原生快照白名单，实际固定出口修正为
`POST https://quantapi.51ifind.com/api/v1/history_data`。按已审官方 Skill 1.1.0 的 THS_HQ 合同，
`arguments_json.body` 可为旧式合法扁平对象或仅含 `reqBody` 的对象；Provider 只包装一次，
不接受两种格式混合或 URL query 替代参数。`codes`／`indicators` 为非空、无空白、至多4096字符的
逗号分隔字符串，`startdate`／`enddate` 为有序有效日期（`YYYYMMDD`、`YYYY-MM-DD`、`YYYY/MM/DD`）。
可选 `functionpara` 仅接受官方对象格式及 `Interval`／`SampleInterval`（互斥）、`CPS`、`PriceType`、
`Fill`、`BaseDate`、`Currency`；不猜测历史字符串语法、不丢弃未知字段或补币种／复权／填充默认值。
未知或歧义参数在读取凭据前返回 `quantapi_history_contract_invalid`。

证券列表仅接受显式字母数字、点、下划线、短横线代码；指标仅接受显式英文字母数字与下划线，
均以逗号分隔，拒绝通配符／括号／表达式。Host单次保守预算为5000 cells：
`证券项数 × 指标项数 × 首尾均计入的日历天数`，超限在取密前返回
`quantapi_history_workload_limit`。这是产品安全上限，不是供应商或账户额度，也不是返回行数limit；
周/月Interval及SampleInterval不放宽估算，不自动拆批、截断或添加默认值。

例如旧式 `body={"codes":"600000.SH","indicators":"close","startdate":"2026-10-21",
"enddate":"2026-10-21","functionpara":{"Interval":"D","Currency":"RMB","Fill":"Blank"}}`
转换为 `{"reqBody":body}`。仍按 `tables[].thscode/time/table` 对齐展开并保存完整源字节，
空数组返回 `empty`、坏结构和非零错误码失败；真实 null 不填零，全部指标无值时保留原件与行并返回
`partial/history_values_missing`，不进入原生研究仓的完整快照。请求 RMB 或复权选项不构成单位或
跨源等价的独立核验，未知单位仍为 `provider_defined`，正式回测／历史可得性边界不变。

状态语义：`code_exists` 表示来源在清单中已登记；`integration_completed` 表示已有按需取数适配；
`configured` 对公开来源为真、对凭据来源仅在秘密已保存时为真。外部来源的探测只报告配置与适配状态，不向上游发请求，
避免服务启动的批量探测对数十个外部站点产生周期性流量：登记但可读的来源返回 `degraded/not_live_verified`，
全部入口需要凭据且未配置时返回 `blocked_config`，Morningstar/TradingView 等连接器来源返回 `connector_required`，
总体目录返回 `not_live_verified`。实时可用性以每次显式取数调用的真实结果为准，单次响应是 `snapshot` 语义，
不等于完整历史；来源原字段按供应商口径保存并标记 `provider_native_fields`，不做跨来源换算。
本批没有把任何来源标为“实时可用”。

认证外部入口必须使用清单已登记的 HTTPS 地址。`ext_daole` 的五个入口仍保留原 HTTP
目录记录，未猜测或替换供应商地址；目录、连接状态与探测显示 `credential_transport_blocked`，
业务调用在读取凭据或发送请求之前返回同一稳定错误码。探测只读取非秘密配置状态，不取密。
HTTPS 与密钥反射回归均使用 MockTransport 和合成秘密，不证明真实供应商可用。
模型摘要最多三行，完整 UTF-8 JSON 总预算为 32 KiB；裁剪不改变快照完整 rows.json。
AKShare 日线按显式交易所后缀选源，指数先裁日期再应用行数上限，ETF 使用独立基金历史接口；
离线回归不等于实盘行情与跨来源单位已核实。
指数 OHLC 使用 points，ETF 使用 CNY；新增指数/ETF 成交量保留供应商数值与
`provider_defined` 单位并标记 `volume_unit_not_verified`，不在缺少已核实单位时猜测手/股换算。
ETF 参数边界参考 [AKShare 官方 ETF 历史接口说明](https://akshare.akfamily.xyz/data/fund/fund_public.html#etf)。

凭据反射检查同时覆盖原始响应字节与解析后所有行的字符串（字典键/值及嵌套列表），
在裁剪行数、发布快照或生成样例之前执行。迭代遍历拒绝 JSON Unicode 转义及 HTML 实体
解码后出现的秘密；错误仅记录 `credential_reflection`，不记录秘密或响应内容。

## AKShare 请求口径与旧缓存复用边界

2026-10-23 中国宏观 `factor_macro` 仅接受 `series=cpi|gdp|pmi|m2` 与必需的ISO
`start_date/end_date`，拒绝assets、dates及未知参数。复用owned public worker、原容量与总截止，
按已安装AKShare的macro_china_cpi/gdp/pmi/money_supply固定同上游reportName/columns，
直接请求Eastmoney datacenter-web单个pageSize=2000响应以保留SDK会丢弃的原envelope，
不自动翻页。success/code/pages/count、精确字段、非有限/错误数值、TIME/REPORT_DATE及
重复/顺序/未来参考期均核验；null原样保留且partial，不经SDK errors=coerce变成假成功。
每行保留原字段，月观察期派生月末date与YYYY-MM，GDP派生季末date、YYYY-Qn与
aggregation=year_to_date，`2026年第1-3季度`保持年内累计，绝不当单季。REPORT_DATE/TIME
是供应商参考标签，不制造精确发布日期或历史vintage。CPI当月指数/累计指数/同比与环比、
GDP累计金额与累计同比、PMI指数与变化分别标semantic；金额未知单位保持None，仅M2/M1/M0
数量沿已核(亿元)声明标CNY_100million。完整单次响应为snapshot，不承诺完整历史；分页、
数值缺失或查询窗无观测为partial且不入仓。原件/fields/schema_version=akshare-china-macro-v1
沿既有factor_macro原生仓冻结恢复，正式backtest/as_of供应商请求拒绝。
仅AK+factor_macro的Host schema_identity/units_identity加入独立schema版本；新session查询
必须匹配schema_version，旧call_id及显式冻结原件仍按原身份可读。native额外拒绝旧/错误schema、
分页不完整、partial、null及空行。source_configuration_digest与其他AK能力的v6缓存含义不变。

单股资金流的当前真实Host验收为FAILED：HTTP200但rc100/data=null，不视作数据成功；
以下guest后备只表示封闭实现及离线验收，早先rc0一条样本不能推广当前可用性。

2026-10-23 单股资金流的原 `stock_individual_fund_flow` SDK 实际抛错后，允许在同一个 owned
public worker 内请求已实测的固定 Eastmoney `82.push2.eastmoney.com/webguest` 日线资金端点。
这仍是同一 Eastmoney 上游，不计独立源，不请求大盘 `secid2`，不替代沪深市场整体流向。
固定公开访客 ut 与 fields1/fields2 原参数保留；4秒 HTTP 等待、响应字节上限、禁止重定向及
trust_env=False 沿原12秒子进程总截止与15秒Provider容量契约执行。SDK成功、空frame或本地
schema错误不会触发额外请求。guest核验 code/market、15列、有限数值、合法唯一递增日期，
原始HTTP字节保留；字段f57–f65仅保原字段名，不推断未审核语义。日期按请求裁剪后，上游
provider_total仍保实际返回数。任何有日期请求始终 partial/history_coverage_unverified，
缺日期为partial零行而非empty成功；无日期只提供snapshot/latest单次响应、first_observed。
资金单位保持未知，不补公布时点、完整历史或历史vintage；guest正式backtest/as_of拒绝。
v6语义版本沿既有配置摘要隔离旧缓存；新增回归复用已登记的test_datahub_akshare_semantics模块。

AKShare `market_activity` 当前只实现个股 `fund_flow`；`northbound`、`money_flow` 等未审阅
数据集返回 `data_not_equivalent`，不会用个股大中小单流量冒充北向资金。请求日期先在
完整供应商 frame 上切片，再应用 5,000 行硬门；缺少可验证日期、非法日期或超限分别失败
关闭，不静默发布范围外数据。输出保留原字段并增加标准 `date`，金额/流量单位不猜测。
`market_snapshot` 当前只支持股票；指数/ETF 在 SDK 调用前拒绝，股票身份保留显式交易所后缀。

同一纯支持规则由 Broker 的选择/缓存准入与 Provider 执行共同使用；AKShare 的固定非秘密
语义版本也进入已有配置授权摘要，旧收据返回 `data_cache_authorization_changed`，新调用跳过
旧缓存并按新口径取数。历史快照和 raw 保留供审计，不删除、不改写，也不恢复新查询授权。
无任何可用来源时保留 HTTP 400 与原中文说明，稳定代码为 `data_source_unavailable`。
这些修复只经离线 Mock 回归，不证明真实供应商、收费数据或其他平台已验证。


Hot原件导入属于frozen_evidence/hot_evidence会话快照，不宣称为新的可查询市场Provider，也不伪造业务查询。实际选定的规范清单、完整存储材料JSON和原始响应按哈希独立复制到已确认目标会话；现有私有manifest、dataset读取、copy_selected和升级路径核验并支持它。取得/发表/来源更新与本次快照准备时间区分，显式选材不是来源全量覆盖。


2026-10-13续跑：Hot研究脚本现在可读取本会话授权的冻结资料：创建回执、hot_research目的、run/instance/manifest匹配及所有原件hash必须通过。普通Provider选源/查询仍走原合同；本次仅修复快照只读权限。


资产观察按单查询容量顺序调度 auto、Wind、天软和 AKShare 的同观察区块，避免自身触发 provider_busy；其他会话的占用仍如实返回。CJPY 将业务 daily/weekly/monthly 等价映射到 SDK day/W/M，qfq/hfq 映射前/后复权，保留原始字段与未知单位。资产图表识别原字段“时间/简称/vol”，来源数据日与读取时刻分开，不用读取时间替代交易日。既有 SDK 凭据用于隔离验收并不自动建立其他实例或账号的 DataHub 连接。


2026-10-22 基金NAV入仓：基金NAV已接入原生研究仓：日期范围最多31日且分页完整时，保留adjusted_total_return、benchmark_timeseries、verified_currency三项已声明缺口；第二次展示查询可命中仓库，data_success与正式回测标记仍不提升。

2026-10-23 前台data_query_deadline或其他异常若DataHub仍拥有同一call_id任务，历史job保留child_call_id及draining活动状态，复用DataHub.cancel同调用等待真实SDK Future排空后才失败/开放retry；排空期间新任务history_busy。取消排空期间仍等待原调用，不重发、放宽超时或发布晚结果。

2026-10-23 本次独立CJPY 0.5.2专用CjClient只读markettable_columns一次，HTTP200、53字段，0行情/财务/模型、0配置写与凭据持久化；字典SHA-256为27df9e431be417c522e65151179dcc476822f38e792f8ea497bd19733ac4d829。股票vol明确为股，amount规则仅元，OHLC单位/币种仍未声明。Provider仅在实际SDK.__version__精确0.5.2、显式stock/daily及规范沪深股票身份时，新响应vol字段标share、amount标原生元/currency:null，原始rows/raw不变。证据合同tinysoft-stock-daily-fields-v1及字典hash随新provider_metadata.field_dictionary_evidence保存，不重复取字典。旧/未知SDK、缺类型/频率、ETF/index及未证明volume别名保持未知；不填CNY或OHLC单位，不恢复Tinysoft规范研究仓桥，原raw2价格门仍拒绝。旧快照不改写。

2026-10-23 规范raw历史显式使用Host查询合同`required_semantics=cn_stock_daily_cny_share_v1`，仅market_bars、规范沪深stock、daily/none合法；非法组合在Pydantic输入层拒绝，不读凭据。当前单位合同候选只有Wind/AKShare/BaoStock；Tinysoft即使SDK成功也因OHLC单位/currency未知在候选准入记skipped/price_units_unverified，不先调行情再把complete改failed。通用native及显式Tinysoft旧无合同查询不变，qfq/hfq仍原完整门。该选项由Host历史任务设置，不加入DSH通用工具参数schema，不从call_id推断。

合同进入BusinessQuery指纹、manifest query/provider_query、历史job和块缓存身份；默认None从fingerprint移除，旧receipt/缓存保持兼容。新任务冻结请求策略，显式retry保留原策略，旧job缺字段保None而不在重启或retry时悄悄升级。原生SnapshotSeries不满足该合同并拒绝其缓存读取；规范单位的历史后置证券/日期/OHLC/量额校验仍保留，坏响应不会因policy而变成可重试降级。共享deadline、Future容量与draining合同不变。

CJPY局部成交量声明还必须逐行校验所有已存在asset/code/stock_code/证券代码/代码与请求同身份；任意已返回身份列出现显式冲突、ETF/指数或空值均保持unknown，原rows/raw不改，不凭stock标签覆盖冲突。完全没有身份列时，封闭的单一精确code请求、stock/daily及SDK0.5.2合同可作identity_basis=single_security_request，response_identity_observed=false；全匹配身份列为row_aliases，不向rows/raw补asset。field_dictionary_evidence现进入原生SnapshotSeries受审metadata白名单，冻结/导出/恢复保持完整静态证据对象；仍quality_accepted=false、formal_backtest_eligible=false、historical_point_in_time=false，不恢复天软规范研究仓桥。

2026-10-23 单位策略还逐输入冻结到required_semantics证据字段、query及manifest/query/provider_query，_authorize_inputs复验与任务策略一致，_cache_chunk/_reuse检查块顶层策略；旧缺字段None按原合同处理。离线HTTP链覆盖AK执行失败再Bao可信raw成功，候选skip与实际execution_attempts分别保存，不以skip替代运行失败降级证明。

2026-10-23 本次交付缓存边界：Asset新历史job固定refresh=True，显式重读所请求整段，不是先读取研究仓再只补缺失部分。DataHub普通refresh=False仅按精确策略/来源复用完整匹配缓存；Wind超过60自然日时缓存来源仍受当前fetch准入guard限制。跨来源部分覆盖不在本任务中拼接，研究仓prepare交易日历仍可能联网。这些是实际未完成能力，不能用本轮候选降级、原生冻结或单源完整缓存测试宣称全部缓存/缺口补数已覆盖。

2026-10-23 最新逐源证据快照见[64源验证清单](../.ai/reports/2026-10-23-datahub-source-verification.json)：保留2026-10-22静态旧快照，区分CJPY Native SDK字段元数据、iFinD Windows SDK与ext_ths HTTP渠道、Market表面及逐源事实。真实AK此前API/页面两轮与最终组合真实Bao一次分别记录，57源未重查；局部元数据、单证券485行或页面图表不升级为全源可用、PIT、正式回测或部署。
