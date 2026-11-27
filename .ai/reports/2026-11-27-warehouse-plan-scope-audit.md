# 仓库规划可覆盖能力的审计

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"只补注释与回归断言，说明哪些 capability 已被仓库覆盖、走的是哪条 ingest 路径、为何当前不能并入规划；Provider、Broker、存储表、快照与调度拓扑均未改动。","diagrams":[]} -->

宿主：macOS arm64 Mac mini；任务类型：Web 后端只读审计；本平台范围为本地代码与测试。
Windows/Linux 产品验收为 NOT_RUN。
任务：`datahub-plan-audit-20261127`；基线：`151f0f66`。

## 要回答的问题

上一轮把 `plannable()` 收敛为唯一判定后，遗留的问题是：能不能把
`financials`、`market_activity` 加进 `PLANNABLE_CAPABILITIES`，让它们也走缺口规划。

## 结论

**不能，至少不是改一个常量。** 三条路径互不相同：

| 能力 | 存储路径 | 是否有 `find_gaps` | 能否并入本规划器 |
| --- | --- | --- | --- |
| `market_bars` | `WarehouseBridge` + `Fact.business_date` | 是 | 已并入 |
| `financials` | `research_snapshot_store.SnapshotSeries` | 否 | 需先建按期间 gap 语义 |
| `market_activity` | 同上（`SnapshotSeries`） | 否 | 同上 |
| `market_snapshot` | 单时点行 | 不适用 | 日期区间 gap 无定义 |
| `search_assets` / `trading_calendar` | 无 dataset 行 | 不适用 | 无行可 diff |

`SnapshotSeries.read` 的命中条件是 `display` + `allow_stale` 且未超 TTL；
严格研究请求一律回源。它**从不调用** `find_gaps`，所以规划器拿不到缺口列表。
把能力名加进常量只会让 `missing_queries` 走进一条本就没有 gap 语义的路径。

## 第三处门

`DataHub._can_plan_wind_gaps` 还有一份更窄的判定：
`source in {auto, wind}` 且 `asset_type == stock`，理由是只有受信 wind 原始日线
可以推迟原 span 上限。即便前两处放开，这里仍会拒绝。三份判定并存是本轮审计的
主要发现；上一轮已消除 `warehouse` 与 `planning` 之间的重复，这一处按原授权语义保留。

## 本次变更

只加注释与回归断言，不改行为：

- `planning.py`：在 `PLANNABLE_CAPABILITIES` 上方写明各能力为何不能并入，
  以及 `_can_plan_wind_gaps` 第三处门的存在。
- `test_datahub_planning.py`：新增断言钉住「`SnapshotSeries` 不调用 `find_gaps` /
  `plan_queries`」与「可规划集合精确等于 `{market_bars}`」。

## 验证

`test_datahub_planning.py` 34 项通过（含 3 subtests）。

## 未验证与下一步

要让 `financials` 真正可规划，需要先定义"某个报告期的数据是否已入库"的判定，
包括期间语义（季度/年度）、可用时点与修订版本；这是新设计，不是开关。
本次未做该设计，也未改动任何 Provider 或存储行为。
