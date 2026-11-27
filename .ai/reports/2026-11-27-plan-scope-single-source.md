# 仓库规划判定的唯一来源

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"把 warehouse 内联的规划前置条件收敛到 planning.plannable，并将可规划能力显式列为常量；Provider、Broker 选源、存储表、快照与调度拓扑不变，实际可规划能力范围维持只有原始日线。","diagrams":[]} -->

宿主：macOS arm64 Mac mini；任务类型：Web 后端结构收敛；本平台范围为本地 Python 合同。
Windows/Linux 产品验收为 NOT_RUN。
任务：`datahub-plan-scope-20261127`；基线：`1e0d173f`。

## 问题

仓库规划的前置条件存在两份：`datahub/planning.py::plannable` 一份，
`datahub/warehouse.py::WarehouseBridge.missing_queries` 内联一份，措辞与顺序不同。
前者只被同样无人调用的 `plan()` 使用，真正执行的是后者。
两份条件一旦漂移，某个 capability 会无声地获得或失去规划，而测试不会发现。

## 变更

- `planning.py`：新增 `PLANNABLE_CAPABILITIES` 常量，显式声明当前只有 `market_bars`；
  `plannable()` 改为按「非 refresh、无 as_of、能力在清单内、日线且不复权」判定，
  并说明为何其它 capability 暂不纳入（快照只有单时点行、身份检索无日期、
  财务与活动尚未审计按日期存储行）。
- `warehouse.py`：`missing_queries` 改为直接调用 `plannable(query)`，删除内联重复条件。

**行为未扩张**：可规划范围仍只有原始日线。这是把两处判定并成一处，不是新增规划能力。

## 验证

`test_datahub_planning.py` 33 项、含 broker 与资产加载的集合 130 项通过。
新增三项断言：`missing_queries` 确实调用 `plannable` 且不再内联 `capability != "market_bars"`；
`PLANNABLE_CAPABILITIES` 精确等于 `{market_bars}`；
快照、财务、身份检索仍走直连。

## 未验证与边界

- 未把 `plannable()` 接入 `Broker` 的选源前置，仅在 warehouse 内统一判定。
- 未做金融/活动/快照的按日期存储行审计，因此它们仍不可规划。
- 未执行真实取数或常驻服务验证。
