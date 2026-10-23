# 供应商原生研究快照

2026-10-23：同批f350/f351与已有日线资金只补充MarketService的公开缓存口径；不是新增provider-native研究快照能力，不伪造原件/首次观测时间，不改变固定12指数捕获、私有周报或授权边界。 具体来源、缺口与缓存合同见[DataHub](research-web-datahub.md#无会话全市场数据)。

CJPY个股筹码输入继续冻结原始换手响应、完整证券/日期和供应商单位；同复权VWAP/换手衰减作为有版本的派生说明保留，raw行不覆盖。前端万/亿是显示倍率，不改变厂商数量单位、原JSON、费用或回测时点证据；三角均价缺口不由演示数据补齐。

2026-10-23固定公开指数桥：额外仅接受source=eastmoney、capability=market_snapshot、asset_type=index、assets严格等于`providers_market.INDEXES`的12个有序身份及固定price/change/change_pct/as_of/series字段。不存在任意market_snapshot扩权。Host把完整MarketProvider响应放在单个`rows[0].response`封包并保留该规范JSON字节为原件；这是Provider响应捕获，不冒充未由适配器暴露的HTTP wire原字节。完整12行、分页完整、missing均为零、每行报价/时间/有界分时齐备才可入仓；partial/failed和无原件仍拒绝。原生点位/百分比与分时语义原样保留，不证明第二来源单位等价。读取仍遵守下文300秒display+allow_stale规则，显式refresh绕过读取。具体Host/profile授权及降级见[DataHub](research-web-datahub.md)。

完整字段捕获还逐行核对固定code/name/stale=False、price/change/change_pct有限数值、上海时区完整ISO秒报价时间；每个分时点须为含time/price/change_pct的对象，有限数值、同报价日、严格递增且不超过供应商已有5分钟未来容差。顶层as_of/quote_trade_date/temporal_complete和精确三项missing零计数必须一致。现Provider的_number可输出None，且其complete主要声明端点覆盖；这样的原响应仍原样交给市场页，但必需字段为null/缺字段/畸形时间或分时不得入仓，warehouse标为incomplete并保护旧完整捕获，不擅自改写原complete字段含义。

`datahub/research_snapshot_store.py` 的 `SnapshotSeries(service, actor, scope)` 是既有 `MarketStoreService` 的受信 Host 适配器，不创建连接或 schema。actor、StoreScope、schema_identity、units_identity 必须由 Host 提供，不能从浏览器接受 owner。每次读取、归档、冻结仍经过 service 的当前 read/write/export 授权；权限撤销后缓存也不能读。

支持 financials、market_activity、factor_macro、fund_data、index_data 及 asset_type 为 etf/index 的 market_bars。原生快照与股票规范行情不同。天软股票在单位尚未审核时也只走此原生合同，不提升为规范行情。已登记厂商限 akshare、baostock、wind、tinysoft 和既有 eastmoney_fund 基金来源。external_data 仅允许显式清单 `ext_fred/series`、`ext_bls/series`、`ext_worldbank/inflation`，以及当前账户的官方 `ext_ths/cmd_history_quotation`、`basic_data_service`、`real_time_quotation` 数值接口；目录、新闻、日历网页、凭据入口、用户数据库和其他自定义接口均排除。来源权限仍由 Host policy 决定，白名单本身不授予许可。

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
