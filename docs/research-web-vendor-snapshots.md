# 供应商原生研究快照

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
