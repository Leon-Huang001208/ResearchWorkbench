# DataHub 业务工具与供应商契约

源码实现，不代表常驻部署或 WeKnora 已刷新。业务工具使用原 OAuth scopes、账号 Host、
BusinessQuery、查询 id、status 分页、原件和冻结快照，不创建第二套取数任务。

## 工具目录

Wind 七域用于分类。当前实现股票、基金、指数、宏观域的 7 个工具及跨域的 2 个公共工具；
债券、通用 analytics、新闻检索、公告和 MySQL 新工具未注册，不能把设计候选当作已交付。
权威输入 schema 由 `mcp_facade/task_contracts.py` 的模型生成，拒绝额外参数。

| 域 | 工具 | 本批范围 |
| --- | --- | --- |
| stock_data | get_stock_kline | 单股、截至昨日的 daily/none；当日数据走快照，不开放未验证复权与基准日 |
| stock_data | get_stock_quote | 1–20 股；默认 price，源不支持字段时沿原准入拒绝 |
| stock_data | get_stock_financials | summary/income_statement/profitability/cash_flow |
| stock_data | get_stock_activity | 资金流、两融、股东户数与前十名股东；大宗/筹码本批不开放 |
| fund_data | get_fund_detail | 净值、档案、分红、已披露持仓 |
| index_data | get_index_quote | 单个 index 最新报价；000/93开头.SH或399开头.SZ，不接受date或批量indexes |
| economic_data | get_economic_series | 固定四个中国宏观数据集，起止日期必填，不提供PIT |
| shared | search_assets | query/market；asset_type仅stock，不接受尚无映射的limit |
| shared | get_trading_calendar | 已发布的 CN 交易日历 |

提交返回原 `id`；用 `rwb_datahub_status(query_id=id)` 读取。查询的 `source=auto` 是请求策略，
实际来源看 `result.manifest.provider`，上游细分看 `provider_metadata.upstream_id`。
三项 scope 仍须有效：`rwb.read rwb.data.query rwb.data.configured`。
旧授权不可发现新业务工具；服务端也检查调用权限，不能仅靠目录隐藏。
新工具与原 raw 工具同时存在，尚未执行 raw 隐藏切换；全 scoped 目录由 9 增到 18。

## K 线与仓库规划

资产入口保留既有裸代码及 SH600519/SZ000001 厂商格式解析；MCP仍要求规范后缀代码。
北交所显式前缀/后缀请求不进入本次沪深共享合同，继续原原生历史路径。

资产观察的普通 history 区块在明确 stock/daily/none 且截止日早于上海今日时，
与 MCP get_stock_kline 共用 `datahub/contracts.py::stock_kline_query`。
该函数固定规范证券身份、历史日期与 CNY/股原始日线语义，再交原 DataHub.query，
Broker、仓库规划、Provider 和冻结结果保持同一执行路径；页面不调用 MCP HTTP。
页面指定的 source 和 refresh 由原受信资产 API 传入；MCP 不开放这些参数。
懒加载新增 raw 历史区块继承观察的来源，不把 auto 改成显式 tinysoft。

本次只接首条已覆盖合同：截至昨日的日频不复权区块。
复权、周/月线、非股票、含当日的原历史请求，以及 canonical 历史任务/分时仍用原路径。
新合同不会让单位尚未满足规范 raw 的来源自动通过；显式来源不支持时按原质量门失败。
本地测试使用合成数据、真实 DataHub/Broker/快照，未证明真实供应商或生产部署。

主图的 history-jobs 继续原任务/分段/缓存/复权及取消链；其中已固定
cn_stock_daily_cny_share_v1 的历史 raw 行情分段也共用 stock_kline_query，
保留任务冻结的来源与 refresh=True。天软原生/复权输入、交易日历/因子请求、
含当日的既有任务分段仍沿原合同，不被截至昨日的业务工具限制覆盖。

```json
{"request_id":"kline-example-1","asset":"600519.SH","start_date":"2026-11-10","end_date":"2026-11-13"}
```

工具补 `asset_type=stock/frequency=daily/adjustment=none`。规划按来源与配置摘要检查覆盖，
周五和周一连续缺失合成一段；中间有已覆盖交易日则拆开。Wind 缺口再按 60 自然日切段。
原 `_can_plan_wind_gaps` 的延后校验条件保留，未把布尔准入机械替换成 Plan。
实际补齐范围写入 manifest.provider_metadata.plan，有界保存最多 16 个范围及总段数；
不伪造当前实现未计算的事实/证明日数。

## Finance MCP 正式行情绑定

`ext_finance_mcp / market_bars / gangtise_raw_daily` 固定调用岗底斯“查询A股日K线”，
保持原外部 envelope 查询可用。新绑定位于既有候选之后，不改变旧来源优先级。
单次最多 367 自然日、单个沪深 A 股、日频不复权、拒绝 PIT/backtest。
源 total 与实际行数不符、错证券、重复/越界日期、非法数值、OHLC 矛盾均失败。
`securityCode/tradeDate/amount` 映射到 `asset/date/turnover`；不解释 adjustFactor。

2026-11-25：600519.SH、11 月 10–13 日四行，与 BaoStock 不复权原始日线对照；
OHLC、成交量一致，成交额差异不超过 1 元。对应股/元口径是有限跨源样本核验，
不是取得了厂商完整单位说明，更不证明长期稳定性、复权或历史可知时点。
元数据保留此限制。total=4 与返回 4 行一致，新的归一化入口另一次真实调用通过。
仓库作用域以来源配置区分；此 binding 的 upstream_id 固定 gangtise，不混入 DM/iFinD。

## 财务字段字典与不能归一化的部分

财务摘要、比率、利润表保留不同的数据形状；业务工具不声称它们都是完整三大报表。
manifest.fields 为实际字段字典；provider_metadata 保留 schema、原生报告期与可得性证据。

| dataset | 来源/字段 | 单位与限制 |
| --- | --- | --- |
| summary | 天软或 Wind：revenue/net_profit/eps/roe 等，以该源固定 schema 为准 | 源字段不可跨源猜等价；Wind schema 区分 CNY、CNY/股、percent |
| profitability | BaoStock：roeAvg/npMargin/gpMargin/netProfit/epsTTM/MBRevenue/totalShare/liqaShare | netProfit、MBRevenue 已有 CNY 字典与有限原件核对；其余原生字段单位保持 null，不猜倍数或百分数 |
| cash_flow | BaoStock：CAToAsset/NCAToAsset/tangibleAssetToAsset/ebitToInterest/CFOToOR/CFOToNP/CFOToGr | 全部为原生比率，scale 未验证；禁止当作元或完整现金流量表 |
| income_statement | AKShare 新浪披露：report_period/publication_date/publication_precision/data[]；明细含 item_title/item_value | 保留来源币种与原文，单位/累计口径未知不得换算；最多 8 期 |

profitability/cash_flow 必须传一个明确季度末列表（2017 年起）；income_statement 最多 8 期。
单季、累计、归母与非归母不可合并。原生比率和未核单位可以作为带限制的原始资料展示，
不能声称满足标准单位财务数值合同或用作正式历史回测。

源证据继续使用 `providers_baostock_reference.py`、`providers_baostock_cashflow.py`、
`providers_akshare.py:sina_income_metadata()` 的固定字典及证据身份；
本批未制造新的 ratio 单位结论或将 source schema 声明冒充本轮厂商实测。

## 跨层契约复核后的固定映射

- 对外宏观 `cn_cpi/cn_gdp/cn_pmi/cn_m2` 分别转换为原provider的 `cpi/gdp/pmi/m2`，
  start_date/end_date必填；原生主要列分别为NATIONAL_SAME/SUM_SAME/MAKE_INDEX/BASIC_CURRENCY_SAME，
  字段说明传入实际MCP schema，不假设输出统一成单一value列。
- 公共行情price在Wind请求中转换成close；公共turnover表示成交额，不能拿Wind原生turnover换手率替代。
  请求Wind不提供的量额/涨跌字段时先跳过该候选；多股快照跳过只支持单股的天软。
- holder_count固定Wind的股东户数；holder_data/holder_details固定天软的前十名股东合计/明细，
  不跨语义替代。资金流/两融必须日期窗口且起止相差少于60天，股东仅最新报告期，不带日期。
- 指数当前仅最新快照，日期字段不暴露；证券检索当前仅A股，不把股票结果当作基金或指数。
