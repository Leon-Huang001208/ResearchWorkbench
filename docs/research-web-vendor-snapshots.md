# 供应商原生研究快照

华安历史验收不扩大vendor-native数据集或凭据范围。已有Wind Excel原件/真实数据日、采集与冻结时间继续保存并由Host重放，历史用途来自冻结Run而非供应商或模型自报；质量通过不升级为当期正式、PIT或跨源等价证据。

今日发现golddata_intel使用专用discovery_evidence文件归档，不扩展本页vendor-native来源/数据集白名单。事件revision与预览投影Hash核对后才取报道正文；冻结raw和manifest可复核，但第三方已有判断、二手内容、未知时间/原始披露缺口均保留，不以外层HTTP成功声明厂商数据、PIT或完整网页已核验。细则见[今日发现](research-web-discovery.md)。

## SPDR 完整四指标捕获

`ext_spdr/gld` 仅接受 `spdr-gld-trust-snapshot-v1` 的四项投影。`SnapshotSeries` 将当前单位、
first_observed、非历史 PIT 声明和四项数量与原件重解析结果、字段定义逐项绑定；未知版本、伪造值、
布尔冒充数值、改写单位、缺原件、partial 或分页不完整均拒绝入仓。只开放空 arguments 的固定 GLD/NYSE/en 请求。
scope、完整参数、schema 和单位身份分别参加版本索引；权限撤销后已有库命中仍拒绝。

每项保留独立 reference_date、原日期字符串、原单位、value_decimal 和 source_value；
原始 JSON 响应体也保留。吨、ounces、shares 和 USD 沿用供应商标签，不归并其他来源或换算标准。
原件是标准 HTTP 解压后的响应体，不表示网络帧。GLD 网站持仓为交易日口径，金条清单为结算日口径，分别处理。
冻结和恢复只证明同一已捕获版本可重现；formal_backtest_eligible 与 historical_point_in_time 保持 False。

终端v2日线来源单列sina、source_url、请求symbol、retrieved_at及price_index收益口径，报价保留eastmoney及真实行情时间。400条日线严格排除当日报价日，最后前日收盘与东财昨收交叉核验；错码、错配、重复日期、超界或网络失败不给合成替代。

2026-10-23 四个外部端点的 `external-envelope-v1` 只修响应判定，不扩本页native白名单。
Nasdaq history 的status.rCode非200与data=null、CLS hot-list errno非零明确失败，
不把HTTP200或错误封包当业务数据；没有猜CLS签名或改用telegram。Nasdaq/CLS真实成功业务
形状尚未核实，成功码的未知内容也返回external_business_schema_unverified，不发布外层envelope。
Danjuan history 的index_eva_pe_growths=[]只证明未取得观测，horizontal_lines不算历史行；
结果为partial/no_observation_rows，raw空数组及参考线原样保留，data_success=False且不作成功缓存。
result_code非零失败；非空历史字段合同未核实时也失败关闭，不伪造日期/PE投影或全历史覆盖。

旧external-envelope-v1的KAPSARC production仅该端点用分号CSV，精确country/sub_commodity/year/production四列，
年份、非空身份、有限非负数及重复业务键校验；零是有效值，字段与HTTP原件保留，单位未知。
逗号CSV等其他解析器不改。单次导出行数不证明完整历史或厂商总覆盖，limit截断明确partial。
当时这四pair的新session查询须匹配schema_version=external-envelope-v1；现KAPSARC生产查询已升级为下述独立kg合同，旧假成功缓存跳过；旧
call_id及显式历史证据保留，不改授权配置摘要。原生研究仓、正式回测或PIT资格不因本修复扩大。
真实反例来自本任务remaining-public-probes；Nasdaq/CLS/Dan非空成功路径仍NOT_RUN，
合成正码封包只用于证明未知形状失败关闭，不代表真实成功验收。

2026-10-23 官方公开数值合同 `official-numeric-v2` 只扩展 `ext_nyfed/rates` 与
`ext_treasury/cash` 两个原生快照入口，并加严现有 `ext_worldbank/inflation`。
NYFed 校验 refRates、六种固定利率身份、effectiveDate 和请求起止日期，SOFRAI 保留独立
average30day/90day/180day/index；普通利率及已核百分位/目标区间单位为 percent，
volumeInBillions 为 USD_billion，SOFRAI 未核单位保持 provider_defined。
Treasury 核对 data/meta/links、count/total-count/total-pages、页尺寸、日期过滤和
Operating Cash Balance 表 I 身份；四个现金字段仅在官方 meta 同时声明 CURRENCY0 与
`$1,000,000` 时标记 USD_million。保留字符串数值和结构性 `close_today_bal="null"`，
不把它补零或改成别的列。实际两行/四行样本为 partial，不能入仓；不自动补页。

世界银行固定 WLD/1W 与 FP.CPI.TOTL.ZG，校验年份、date过滤、分页身份及页数/总量一致性；
value 是年度通胀百分数（percent_per_year），混合或全 null 观测原样保留且为
partial/numeric_values_missing。分页完整和数值缺失分别记录；Treasury 每行四个现金值
全部缺失才标 partial，NYFed 必需数值缺失也标 partial。HTML、错误封包、错日期/身份、
重复观测和不自洽页数失败关闭。仅支持经核验的 query 过滤语法，其他过滤先于 HTTP 拒绝。

Host 对这三个固定入口的 schema_identity/units_identity 加入 v2 版本，授权配置摘要不变；
新 session 查询跳过未带 v2 schema_version 的旧缓存。旧详情、已完成 call_id 回执及旧
DatasetRef/冻结包按原身份保留；新 as_of 查询不把旧合同快照冒充 v2。原生写入另外要求
v2 metadata 与 pagination_complete=True，partial 仍拒绝。fields、受审 metadata、raw
字节及其 hash 随原有 freeze/export_restore 保存。日期只表原始参考期，不制造精确公开
时点或历史 vintage；正式 backtest 仍拒绝。没有新增依赖、服务、路由或存储 schema。
字段依据：[NYFed 官方 CSV](https://markets.newyorkfed.org/api/rates/all/latest.csv)、
[Treasury 数据字典](https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/operating-cash-balance)、
[世界银行指标](https://data.worldbank.org/indicator/FP.CPI.TOTL.ZG)。

2026-10-23：同批f350/f351与已有日线资金只补充MarketService的公开缓存口径；不是新增provider-native研究快照能力，不伪造原件/首次观测时间，不改变固定12指数捕获、私有周报或授权边界。 具体来源、缺口与缓存合同见[DataHub](research-web-datahub.md#无会话全市场数据)。
华安专用 Excel 来源记录原始 WSD/TDAYS 响应、57项精确映射、13市场日历及原生 EDB/经济日历导出哈希；市场截止与真实冻结分别保留。此输入不授予普通行情摘要正式研究权限，只有原 Host 独立质量与版本绑定通过后才能定稿。

CJPY个股筹码输入继续冻结原始换手响应、完整证券/日期和供应商单位；同复权VWAP/换手衰减作为有版本的派生说明保留，raw行不覆盖。前端万/亿是显示倍率，不改变厂商数量单位、原JSON、费用或回测时点证据；三角均价缺口不由演示数据补齐。

2026-10-23固定公开指数桥：额外仅接受source=eastmoney、capability=market_snapshot、asset_type=index、assets严格等于`providers_market.INDEXES`的12个有序身份及固定price/change/change_pct/as_of/series字段。不存在任意market_snapshot扩权。Host把完整MarketProvider响应放在单个`rows[0].response`封包并保留该规范JSON字节为原件；这是Provider响应捕获，不冒充未由适配器暴露的HTTP wire原字节。完整12行、分页完整、missing均为零、每行报价/时间/有界分时齐备才可入仓；partial/failed和无原件仍拒绝。原生点位/百分比与分时语义原样保留，不证明第二来源单位等价。读取仍遵守下文300秒display+allow_stale规则，显式refresh绕过读取。具体Host/profile授权及降级见[DataHub](research-web-datahub.md)。

完整字段捕获还逐行核对固定code/name/stale=False、price/change/change_pct有限数值、上海时区完整ISO秒报价时间；每个分时点须为含time/price/change_pct的对象，有限数值、同报价日、严格递增且不超过供应商已有5分钟未来容差。顶层as_of/quote_trade_date/temporal_complete和精确三项missing零计数必须一致。现Provider的_number可输出None，且其complete主要声明端点覆盖；这样的原响应仍原样交给市场页，但必需字段为null/缺字段/畸形时间或分时不得入仓，warehouse标为incomplete并保护旧完整捕获，不擅自改写原complete字段含义。

`datahub/research_snapshot_store.py` 的 `SnapshotSeries(service, actor, scope)` 是既有 `MarketStoreService` 的受信 Host 适配器，不创建连接或 schema。actor、StoreScope、schema_identity、units_identity 必须由 Host 提供，不能从浏览器接受 owner。每次读取、归档、冻结仍经过 service 的当前 read/write/export 授权；权限撤销后缓存也不能读。

支持 financials、market_activity、factor_macro、fund_data、index_data 及 asset_type 为 etf/index 的 market_bars。原生快照与股票规范行情不同。天软股票在单位尚未审核时也只走此原生合同，不提升为规范行情。已登记厂商限 akshare、baostock、wind、tinysoft 和既有 eastmoney_fund 基金来源。external_data 仅允许显式清单 `ext_fred/series`、`ext_bls/series`、`ext_worldbank/inflation`、`ext_nyfed/rates`、`ext_treasury/cash`、`ext_spdr/gld`，以及当前账户的官方 `ext_ths/cmd_history_quotation`、`basic_data_service`、`real_time_quotation` 数值接口；目录、新闻、日历网页、凭据入口、用户数据库和其他自定义接口均排除。来源权限仍由 Host policy 决定，白名单本身不授予许可。

dataset key 包含 capability、实际 source、全部 parameters 的规范摘要、受审 schema_identity 与 units_identity；完整 source scope 另绑定 owner、entitlement 和脱敏配置摘要。Host 应为已审供应商接口传入稳定且有版本的 schema/单位合同身份。默认 `provider-native-v1` / `provider-defined-unknown` 只代表不做规范化的原生响应合同。fields 的完整实际定义与摘要另随每次捕获冻结，不推断缺失单位、币种或跨供应商等价。切换会计准则、母公司/合并、初值/终值、成分有效期或单位合同必须改变参数或受信 schema/units 身份。

`ingest(query, result)` 仅接收 complete/snapshot/empty，拒绝 partial、failed、cancelled、未知 missing 字段和缺原件；历史 as_of 请求不能新增当下快照冒充历史。唯一的语义缺口例外为实际来源和响应 provider_id 均为 eastmoney_fund、fund_data 的 nav/fund_nav、明确起止日期相差0至30天（最多31个日历日）、status=complete 且 pagination_complete=True。其 missing 只能是 adjusted_total_return、benchmark_timeseries、verified_currency 的子集；三者原样保留，不补造复权总回报、基准序列或币种。无日期、宽区间、snapshot/partial、其他来源或 dataset 不能借此例外入仓。默认 Host 仍通过既有 ResearchWarehouse → SnapshotSeries 入仓，无新路由、schema 或依赖。

供应商 rows、fields、状态、分页声明、限制和原始 as_of 原样保留；metadata 仅保留模块 `METADATA_KEYS` 的受审字段，账号、token、自定义 metadata 不写入该投影。全部 raw bytes 按原字节 base64 与 SHA-256 放入不可变响应原件，冻结可独立恢复，不依赖原宿主路径。来源适配器仍负责确保原始业务响应不含秘密；本层不把任意认证响应纳入白名单。

每个精确查询使用固定 business_date=1970-01-01、metric=snapshot、period=first-observed、空 dimensions 的单一逻辑键；该日期仅是内部存储槽位，不是报告期、公开日或观测日期，也不声称按观测日做数据库分区。available_at/ingested_at 和 value.observed_at 才是本系统实际捕获时间。供应商报告期/参考期仍留在 rows 内。每次变化生成独立 capture_id 作为 source_version，所有修订仍追加保留，因此同日及跨日 A→B→A 都保留三个捕获。read_range/freeze 沿既有修订投影只返回 cutoff 前最新版本，不遍历到 Host 或导出全历史。紧邻完全相同响应幂等，不增加版本，也不刷新首次捕获时间。相同/倒退系统时刻发生变化时明确拒绝，避免不确定排序。Host 必须序列化同一 series 的写入；实例内 RLock 不代替跨实例/跨进程调度锁。

`read(query)` 的 as_of 只返回 cutoff 前确实已捕获的同一完整查询，之前没有捕获则 miss，历史 API 未返回的过去发布版本不会生成。最新 strict 研究请求始终 miss，由原 Provider 实时获取后归档。仅 display + allow_stale 可使用默认300秒、构造时1–3600秒的有界缓存；refresh 始终 miss。每次命中携带 observed_at、缓存 TTL 和限制。空结果只证明供应商当时返回空，不能证明完整历史覆盖。

结果明示 storage_form=provider_native_snapshot、availability_basis=first_observed、formal_backtest_eligible=False、quality_accepted=False、historical_point_in_time=False。purpose=backtest 失败关闭，待独立规范化与公开时间/PIT 合同验收后再开放。该模块不能提供正式回测、跨源统一字段/单位、供应商真实性认证或全历史覆盖承诺。

命中的 Result.raw 是 `FrozenSnapshot.export()` 可移植包，只含本次选定的一个版本及它引用的完整响应原件，不包含该 series 的全历史。旧捕获通过相应 as_of 分别冻结导出；`service.export_restore(actor, scope, content)` 在当前 restore 授权下恢复该版本后可重读。查询/冻结遵守既有每次操作的事实数和字节预算及 DataHub 16MiB响应限制，超限明确失败，不截断；这些是单次投影/单份原件的预算，不是全部历史累计容量上限。超过10,000次追加修订后查询仍只投影一条事实，后续修订可继续追加；实际长期容量、索引性能与生产备份仍待独立验收。模块没有安装新依赖，没有连接真实 PostgreSQL/厂商，也不代表 Host/UI、安装 CI、生产部署或其他平台已完成验收。

离线验证入口：`.venv-tests/bin/python -m pytest --confcutdir=tests/research_web tests/research_web/test_research_snapshot_store.py -q`。


2026-10-22 iFinD凭据复用：iFinD get_limit_policy仅用于显式授权验证，不进入external_data数值白名单或原生研究快照；不得把权限元数据当行情/财务数据保存。

2026-10-23 iFinD历史行情：`ext_ths/cmd_history_quotation` 保留原dataset身份，固定请求改为官方
`history_data`，合法旧flat body精确包一层`reqBody`，原生`reqBody`不重复包装；参数冲突或未知语法先于取密拒绝。
time/table逐项对齐和raw字节保存保持；全null指标结果标记`partial/history_values_missing`，原生快照不接纳为完整数据。
官方单证券单日收盘价样本、授权元数据、本机Mock和候选Host实际数据验收分别记录，不互相替代。
未知币种／复权等价、历史时点及正式回测仍未认证，不新增EDB、日期序列或PIT接口。

2026-10-23 资产近期原始历史在独立规范发布前核验CNY/share与量额声明、证券及日期；turnover仅在声明CNY金额时映射amount。未知单位完整响应仍可以保留DataHub原生快照，但历史任务不发布规范图；不会把该失败称为已完成质量降级。旧原生快照、唯一来源与raw/hash归属不重写。

2026-10-23 CJPY字段字典的股票日线vol单位股仅成为新响应的精确版本/类型/频率元数据，amount保留原生元且currency未知；OHLC仍未知。它不满足股票规范行情CNY/share合同，Tinysoft仍走原生快照而不恢复规范研究仓bridge。字典证据版本和SHA绑定于field_dictionary_evidence，未知SDK或非适用资产/频率不升级单位，旧冻结快照不重写。

2026-10-23 `METADATA_KEYS`明确纳入静态非秘密`field_dictionary_evidence`（合同/SDK/服务方法/字典hash/适用判定），与fields及raw一起进入原生不可变原件，export_restore后对象与摘要保持，不因metadata白名单而丢来源依据。普通token和任意metadata仍不保留。SnapshotSeries对非空required_semantics返回不适用，不允许未核实价格单位的旧native快照满足规范股票raw合同；默认None维持旧dataset与冻结可读，存储schema不迁移。

2026-10-23 field_dictionary_evidence还显式保存identity_basis与response_identity_observed：完全无身份列可依据封闭单证券请求合同但不补原行；任意实际身份列空或矛盾则不应用股票单位。两项身份依据和其余静态字典证据均由原生freeze/export_restore原样保留，不能据此声称价格币种、正式回测或PIT已证明。

## 财报披露字段及资金流来源合同（2026-10-23）

新浪利润表使用`akshare-sina-financial-disclosure-v1`独立schema/units身份，原动态item和`publish_date`日期精度、`update_time`原Unix时间分别保留。有限8期捕获保留供应商总报告数和pagination_complete=False；明确所需报告期缺失、公告日缺失或任一所选报告数值全null为partial（零值仍有效），不得入仓。完整所选期可保存为有界native捕获，不表示完整历史。公告日期不转午夜/收盘时间，不作为available_at；native仍以真实捕获时间排序，正式backtest拒绝。原metrics/indicators摘要及旧冻结证据保持其原合同。

资金流独立合同`akshare-eastmoney-fund-flow-provenance-v1`同时覆盖SDK/游客通道，保留upstream_id=eastmoney、transport、independent_source=False和first_observed。这些静态来源字段进入冻结/恢复白名单；当前观测时间仍由仓库捕获，不把动态provider observed_at写成供应商历史时刻。没有已审单位、订单分类或iFinD指标定义时不合并、不认证等价。新会话缓存和新仓身份须匹配合同版本，旧明示call_id/冻结包不重写。

BEA官方档案不走本native首见投影，使用[独立受信绑定](research-web-market-store.md#官方档案的有限历史发布回放2026-10-23)；有限PIT例外不扩展本页通用native白名单。


## 2026-10-23：BaoStock盈利能力来源

BaoStock季频盈利能力原件是SDK解析返回的字段/字符串JSON，不是原始网络二进制流。保留statDate、pubDate与来源数值；精确公布时刻、历史修订链、比例/股数尺度和累计口径不得推定。只给netProfit、MBRevenue声明官方文档CNY，未知字段不乘100或万元换算。与新浪income_statement保持独立schema，不能按同名字段自动拼接。


600000.SH/2026-06-30实际双源与发行人半年报核对仅确认两格金额对应集团半年累计，不能当作Q2单季或归母净利。两源公告日8月28日与issuer列表8月27日保留不同来源，不回填精确时刻。两个provider-native版本独立冻结和恢复；样本核对不升级通用跨源等价或财务PIT。详见任务报告。

## 2026-10-23：长期研究档案与机会预警

档案引用既有 provider-native／会话快照的身份、原件 hash、权限及已证实公开时间，不把报告期或取得时刻回填为历史公布版本。MCP 原始 SDK JSON 自动冻结到现有 Snapshots（不是 HTTP wire capture），附工具／schema／参数摘要与费用状态，仍为 clue；无出处产业关系、未知时点、截断或不等价数据不进入正式数值扫描与报告通过项。个人 SQLite 只保存引用／pin，源更新不覆盖旧观点所用原件，详见[证据合同](research-web-dossiers.md#证据与成果)与[候选原件](research-web-seek-alpha.md#原始结果与撤权)。


## WGC 月度吨数与研究时点（2026-10-23）

现有 ext_wgc/etf-holdings 与 etf-flows 只开放固定 Monthly/tonnes 四地区投影，分别保存持仓存量和吨数流量；不推导二者差分，不混入价格、美元或其他频率。完整切片与原件、字段、地区身份、月份连续性和单位绑定后才入既有可选研究仓；截断、错列、错日期、全无数值或合同不符拒绝入仓。来源 asOfDate 与参考月不当作公布日期，首次观察与历史 vintage 分开；旧合同缓存跳过，旧回执保留。WGC 聚合区域不同于单只 SPDR GLD，更不同于 A 股个股资金流；未经证明不归并，也不按包装库重复计独立上游。

AKShare 个股资金流 SDK/guest 同一上游，在执行 SDK 前统一拒绝 as_of 与正式 backtest，不以随后元数据的非 PIT 声明替代守卫。宏观、财务、资金流及 WGC 的首次观测修订可按捕获时点重现，不能据今天下载制造过去可得版本。实际验收使用隔离 Host/PG 与独立 Python 子进程重启读回、空库恢复；当前任务报告区分已执行和待执行，不启用正式库、服务、外盘或周报日程。


## KAPSARC / BGS 年度矿产实物量（2026-10-24）

既有 ext_kapsarc/production 在同一有界 deadline 内读取分号 CSV 与固定官方 metadata。只有 dataset/publisher/Public/四字段类型、kilograms 单位及本次记录数全部核实，才将完整导出投影写入原生研究仓；原 country/sub_commodity/year/production 字符串和两份原件均保留，另有 production_kg 数值列。部分、错数、错单位、错原件或未知合同拒绝入仓，不按国家补年、不做 ISO 映射或 kg/tonne 换算。

BGS 经 KAPSARC 转发不是两个独立上游。矿山年产量、WGC 地区月度 ETF 吨数流量、SPDR 单基金持仓属于不同指标/范围/频率，不能因物理单位可换算就合并；首次观察和修订链不等于历史公布 PIT。metadata 修改/处理日期不作为行级披露日，旧说明年份不覆盖实际导出年份；源注释/估算符号缺口保留。新增 projection_scope 元数据随 freeze/restore 保存，旧快照不补造该字段。

该扩展沿既有 Host/DataHub/Provider/可选研究仓拓扑，无新服务、路由、表、依赖或执行引擎，原图仍准确。只做独立进程和 owned socket-only PG 有界验收、原三CI与同候选Mac安装，不配置正式库、更新常驻服务或操作外盘。


## 2026-10-24：现金流财务比率

既有 BaoStock 公开 worker 增加 `financials` 的 `statements=["cash_flow"]`、单证券及单季度末请求，绑定 `quarterly_cash_flow_ratios` 与独立 `baostock-quarterly-cash-flow-v1`。七项原生比例保留空值，unit/currency=None、scale=unverified；累计/单季、集团/本行口径未知，不能当作现金金额或证券交易资金流。原件重解析结果、行、字段、固定字典哈希和声明完全一致才入原可选研究仓。

披露日保留自然日精度；first_observed、历史PIT和正式回测资格分开，as_of/backtest在公开worker前拒绝。来源隔离、当前授权、旧盈利能力合同及快照兼容不变；没有新依赖、HTTP路由、服务、正式库配置或外盘迁移。真实验证与最终候选证据见[任务报告](../.ai/reports/2026-10-24-finance-flows-warehouse.md)。


2026-10-24：news来源JSON与事件关联不冒充厂商原件、HTML全文或历史PIT；它们在现有discovery_evidence内独立标识。原厂商快照路径、原件/版本和确定性重放保持，无新授权。

## 2026-10-24：公开代理策略与原件绑定v2

匿名AK public worker在既有独立子进程中禁止requests继承系统/环境代理和netrc，清空该session及调用代理；保留4秒网络和12秒进程上限，不修改宿主或系统设置、账号SDK或TLS验证。系统最小环境并不能自动排除macOS系统代理。

中国宏观及新浪利润表的v2来源合同将原件重解析结果与完整行、字段、单位/语义、来源URL、总数、分页和参考时间逐项绑定。GDP保持年内累计/累计同比，单位仍未知，不按字段名猜亿元或百分数，也不与BEA单季QoQ SAAR归并。新浪有限snapshot和未知金额尺度、币种/累计口径、自然日披露精度保持；first_observed不等于历史PIT。旧缓存不冒充v2，旧call_id和冻结证据按原义保留。

实际取数、默认Host入仓、PG重启后的独立进程读回、第二空库恢复及最终候选验收分别见[本轮报告](../.ai/reports/2026-10-24-proxy-pit-warehouse.md)。不启用正式库，不部署现有服务或迁移外盘，无新增依赖。


## 2026-10-24：参考证据合同（宏观／新浪v3、资金流v2）

原SDK四案请求在接收响应头前关闭，仍未恢复；没有用改参数、换客户端或后备成功冒充原端点修好。自然失败现在保留有限error_code，资金流尝试链必须存在且精确验证，旧档按原义可读。

GDP v3依据已固定SHA的东财页面脚本字段映射和统计局方法，把四项累计金额标CNY_100million／现价、四项累计同比标percent／可比价；保持年内累计，不推导单季QoQ SAAR。此前v2“GDP单位未知”的段落为当时历史状态，未回写旧快照。

新浪v3只对600600.SH／2025-06-30／合并期末／CNY的营业收入与集团净利润两格，按原件页5（印刷页4）及精确十进制字符串／整数哈希附加参考匹配。float、bool、别股／别期／别项及值修订不获得认证；原data和全局单位不变，未匹配时单位及basis均未知。供应商日期和发行人发布声称分开，冲突不覆盖；PDF历史版本未知，PIT／正式回测始终false。冻结包保留供应商原件和引用元数据，外部参考原件随单独证据包迁移。

实现及逐阶段实际结果见[本轮报告](../.ai/reports/2026-10-24-origin-reference-evidence.md)。不改现有服务、正式库、系统代理、凭据或外盘，无新依赖／付费。


## 2026-10-25：月度宏观与限定财务参考扩围

宏观v4通过固定东财页面实际引用的CPI/PMI/货币供应量脚本绑定字段定义：仅明确变化率为percent，CPI当月／累计指数的基期仍未知，PMI水平不冒充百分点变化；M2/M1/M0数量亿元和月末存量分别声明。央行原件记录M1自2025-01调整并回溯2024年，供应商采用的修订版本未证明，不自动跨年拼接。统计局2025-09 CPI页声称次月公布，只作时点差异示例，不给当前API值回填历史可得时间。

Bao盈利能力v2以保存的SDK原始字符串重建行、字段、固定元数据与引用，伪造或错原件拒入仓。仅600000.SH／2026H1两格与已归档集团半年报的百万元换元值精确匹配，附集团累计／非归母说明；其他证券、期间、比例或修订值不外推。两源分别入仓，首次观察／历史PIT及正式回测限制保持。旧schema缓存跳过，旧显式冻结可读，无新服务、表、HTTP或依赖，原架构图仍准确。外部定义/PDF原件由独立证据包归档，数值冻结保留引用元数据。SDK原端点交叉路由仍失败，不能以后备成功冒充修复。


## 2026-10-25：NYFed SOFRAI 专用v3

NYFed rates单独使用nyfed-rates-native-v3，Treasury/WorldBank保留official-numeric-v2。官方API Schema原件将SOFRAI与四个数值字段绑定；三个30/90/180日历日均值为ACT/360年化复合百分率，营业日复利、非营业日按前营业日利率单利，发布五位小数。指数为无量纲累计因子，2018-04-02基准1、发布八位；不按百分率解释，也不从已舍入指数重建原均值。

官方首次正式发布2020-03-02与2018指数基准分开；SOFRAI在自身value date发布，普通隔夜SOFR在其value date下一营业日发布。约08:00ET后发布及约14:30ET同日修订只是规则，不证明任一历史API记录的真实可得瞬时或vintage；revisionIndicator保留供应商原字符串。当前捕获仍first_observed、非历史PIT/正式回测不可用。

生产和入仓共享严格JSON原件投影与固定字段/依据；拒绝重复键、错误类型/日期/字段scope、深层递归、超限、被篡改的行/字段/元数据/来源，拒绝时保留已有好版本。源数值不重算；只有NYFed旧v2缓存失效，旧显式证据保留。五份官方HTML/YAML原件随私有证据归档，引用元数据随原生冻结/恢复保存；未新增表、HTTP、服务、依赖或执行引擎，原拓扑仍准确。
