# DataHub 九业务工具真实取数复核

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"只修 Provider 到业务行的映射与执行短路：天软中文检索、交易日历展开、指数快照、股东前十过滤、Wind 未探测短路、akshare 资金流代理旁路；Broker 拓扑、存储表、快照格式与调度均未改变。","diagrams":[]} -->

宿主：macOS arm64 Mac mini；任务类型：Web 后端功能修复与真实取数验证；
本平台范围为本地代码、测试和真实上游调用。Windows/Linux 产品验收为 NOT_RUN。
任务：`datahub-provider-fixes-20261127`；基线 `7041a1bd`。

## 修复项

| 工具/数据集 | 现象 | 根因 | 处理 |
| --- | --- | --- | --- |
| `search_assets` | 中文名查询 `data_not_equivalent` | 天软目录只回代码，中文名在因子表 | 单次批量取因子表名称后匹配 |
| `get_trading_calendar` | 返回 `{"value":"20261124"}` | 天软只回开市日 | 展开为区间内每日 `is_trading_day` |
| `get_index_quote` | `data_capability_unavailable` | `IMPLEMENTED_BINDINGS` 未登记天软 | 新增 `index_data` 取最新指数快照 |
| `get_stock_activity(holder_*)` | `tinysoft_holder_rank_invalid` | 历史期存在第 11–13 名 | 只取最新报告期前 10 名 |
| `get_stock_activity(fund_flow)` | 61 秒超时 | `auto` 落到未登录 Wind | Wind 未探测后移并执行前短路 |
| `get_stock_activity(fund_flow)` | `vendor_schema_invalid` | guest 15 字段按 16 列配对 | 按真实字段顺序重排 |

## 真实取数结果

真实凭据、真实上游、隔离 Store（不写常驻实例），逐项经 MCP 业务工具的参数契约执行。

| 工具 | 结果 | 来源 | 行数 | 关键值 |
| --- | --- | --- | --- | --- |
| `get_stock_kline` | complete | tinysoft/akshare | 8 | 600519.SH 2026-11-17 收 1457.7 |
| `get_stock_quote` | complete | akshare | 2 | 600519.SH 1469.0 |
| `get_stock_financials(summary)` | partial | tinysoft | 12 | 2024 年报 roe 36.99 |
| `get_stock_financials(income)` | snapshot | akshare | 2 | 2026-09-30 |
| `get_stock_activity(holder_data)` | complete | tinysoft | 1 | 2026-09-30 top10 67.737% |
| `get_stock_activity(holder_details)` | complete | tinysoft | 10 | 茅台集团 54.4991% |
| `get_stock_activity(margin)` | complete | tinysoft | 8 | 2026-11-17 起 |
| `get_stock_activity(fund_flow)` | **failed** | akshare | 0 | 东财当前拒绝连接 |
| `search_assets` | complete | tinysoft | 1 | 600519.SH 贵州茅台 |
| `get_trading_calendar` | complete | tinysoft | 10 | 每日 is_trading_day |
| `get_fund_detail(nav)` | snapshot | eastmoney_fund | 20 | 110022 单位净值 2.871 |
| `get_fund_detail(profile)` | snapshot | eastmoney_fund | 16 | 档案字段 |
| `get_index_quote` | complete | tinysoft | 1 | 沪深300 3903.961 |
| `get_economic_series` | snapshot | akshare | 10 | CPI 同比 0.7 |

## 未完成

`fund_flow` 的 SDK 与 guest 在同一时段均被东财断开（`http=000`），本次未能取得
端到端成功证据。字段映射已用真实 15 字段样本做离线校验（主力 = 小单+中单+大单+超大单），
统计结果自洽。恢复取数需上游解除限制后重跑。

## 验证

`pytest` 295 项通过（含 72 subtests）；`ruff` 改动文件全部通过；
`black` 改动文件通过。以上均为本机真实执行结果。
