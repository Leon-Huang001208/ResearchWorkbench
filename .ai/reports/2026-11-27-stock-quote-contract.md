# 股票快照共享契约与可导出字段修复

<!-- architecture-review {"group":"inbound-mcp-readonly","structure":"unchanged","reason":"get_stock_quote 改为调用 datahub.contracts 的共享契约函数，与 get_stock_kline 同构；复用原 OAuth、Host、Broker 选源、查询 id、status 分页和冻结快照，不新增路由、服务、执行器或权限范围。","diagrams":[]} -->

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"新增 stock_quote_query 纯函数并在既有 akshare market_snapshot 分支内计算可导出的涨跌幅与总市值；Provider、Broker 选源、仓库和快照拓扑不变，未新增数据源或存储介质。","diagrams":[]} -->

宿主：macOS arm64 Mac mini；任务类型：Web 后端功能修复；本平台范围为本地 Python 合同与真实公开源取数。
Windows/Linux 产品验收为 NOT_RUN。
任务：`datahub-quote-contract-20261127`；基线：`71b2cf2a`。

## 问题

`get_stock_kline` 走 `datahub/contracts.py::stock_kline_query` 的共享契约，
而 `get_stock_quote` 只在 MCP 层做参数校验后直接透传，没有同层契约。更实际的缺陷是：
akshare 的 `market_snapshot` 分支把 `涨跌幅`、`总市值` 硬编码为 `None`，
但日线响应本身已带 `close`、上一交易日 `close` 与 `outstanding_share`，
这些值本来可以导出。结果是工具声称返回快照，实际 `change_pct` 永远为空。

## 变更

- `datahub/contracts.py`：新增 `stock_quote_query`，固定 `market_snapshot` capability、
  规范证券身份、1–20 只上限、字段白名单与去重；拒绝空列表、重复资产、非法代码、
  空字段、未知字段与重复字段。新增 `STOCK_QUOTE_MAX_ASSETS`、`STOCK_QUOTE_FIELDS` 常量。
- `mcp_facade/task_contracts.py`：`get_stock_quote` 与 `get_stock_kline` 同构，
  直接返回共享契约构造的 `BusinessQuery`。
- `datahub/providers_akshare.py`：在既有 `market_snapshot` 分支由
  前收/今收计算 `涨跌幅`，由 `close × outstanding_share` 计算 `总市值`；
  缺少任一输入时保持 `None`，不猜测、不补零。

## 验证（真实公开源，2026-11-27）

`broker.resolve` 选源为 `akshare`，`fetch` 返回 `status=complete`、2 行：

```text
600519.SH  price=1469.0  change_pct=-0.396  market_cap=1836369871869.0  as_of=2026-11-26
000001.SZ  price=12.45   change_pct=0.4032  market_cap=241600778137.95   as_of=2026-11-26
```

离线回归：`test_mcp_task_contracts.py`、`test_mcp_facade_datahub.py`、
`test_datahub_planning.py`、`test_asset_loading.py` 共 143 项通过（含 13 subtests）。
`ruff`、`black --check`、`isort --check-only` 通过；架构检查 0 违规。

## 未验证与边界

- 本次只打通 `get_stock_quote` 一条链路；`plannable()` 仍只覆盖 `market_bars`，
  快照与其他 capability 没有仓库规划与增量补齐。
- 东财全市场 spot 接口在当前网络被代理阻断，因此采用已可用的日线接口导出字段；
  `名称`、`市盈率-动态` 仍为空，未用其他来源补。
- 未执行常驻服务切换、真实定时采集或 PIT 验收；字段单位仍只有 akshare 自述。
