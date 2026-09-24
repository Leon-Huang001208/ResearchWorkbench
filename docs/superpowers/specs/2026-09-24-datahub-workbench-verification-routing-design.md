# DataHub Provider and Asset Workbench Verification Routing Design

## 背景与证据

2026-09-24 的资产财务缺失值修复同时修改了 AKShare Provider、资产观察 renderer 及其直接测试。现有
`.agents/verification-policy.json` 没有 DataHub 或 Asset Workbench 专项规则：

- `tests/research_web/test_datahub_catalog.py` 落入 `unknown_path`，把完整任务提升为 L4；
- `tests/javascript/research_web_workbench.test.mjs` 被误归入 `research-web-framework-ui`，因此选择
  Gold／Dollar 框架测试；
- `app/research_web/datahub/**` 被通用 `research-web` 前缀接住，即使是 Broker、contracts、security、
  snapshots、Wind、MySQL 或 CJPY，也只得到 L1。

结果同时存在误升级、无关验证和真实高风险边界验收过窄。本设计将三者一起校正；不得只登记一个测试
文件来掩盖其余问题。

## 目标与非目标

目标：

1. AKShare 公共 Provider 的已知源码与直接测试获得 DataHub 专项 L2 闭包。
2. Asset Workbench UI 与 backend 获得独立专项路由，不再借用 framework 规则。
3. Provider 与 Workbench 跨模块 changed set 由两个高耦合 impact 自动升到 L3，并运行最短资产观察
   API／快照／呈现 smoke。
4. DataHub 中未显式允许的核心、安全、快照、专业／本机 Provider 和未来新增路径继续进入 L4 fallback。
5. 规划器仍只读，外部 CI、桌面和 Windows 门仍由 level 与路径决定，不因本设计自动扩大。

非目标：

- 不修改 DataHub、Asset Workbench 或框架产品行为。
- 不把整个 `tests/research_web/` 或 `app/research_web/datahub/` 降为 local-only。
- 不为 Wind、MySQL、CJPY、Broker、contracts、security 或 snapshots 设计较低等级闭包。
- 不改变 L0-L4、receipt、运行时 signal、CI 或交付控制器协议。

## 方案比较

### 方案 1：带安全排除的限定组件路由（采用）

给通用 `research-web` 规则增加可选的 `excludePrefixes`，仅排除
`app/research_web/datahub/`。随后用精确 allowlist 登记 AKShare 公共 Provider；未被专项规则接住的
DataHub 路径自然落回既有 L4 fallback。Asset Workbench 使用精确文件规则，不需要排除整个 UI。

优点：能同时减少误升级并修复当前 DataHub 高风险源码被通用 L1 吞掉的问题；未来新 DataHub 文件默认
fail closed。缺点：规划器 match schema 增加一个受控字段，需要严格反向测试。

### 方案 2：只登记 `test_datahub_catalog.py`（拒绝）

改动最小，但 AKShare 源码仍只有通用 L1，Workbench 测试仍误跑框架闭包，其他 DataHub 高风险源码仍
被低估，不能满足目标。

### 方案 3：把整个 DataHub 映射到一个 L2/L3 规则（拒绝）

可减少 fallback，但会把安全、快照、专业 Provider 和未来未知文件错误降级，破坏 fail-closed。

## Match 语义扩展

`match` 新增可选 `excludePrefixes: string[]`。规则匹配流程固定为：

1. 先规范化并校验 changed path；
2. 若路径命中任一 `excludePrefixes`，该规则不匹配；
3. 否则再按现有 `files | prefixes | segments | suffixes` 任一命中规则处理；
4. 若所有规则都不匹配，继续使用现有 fallback。

`excludePrefixes` 不是风险覆盖、优先级或降级机制；它只能让当前规则退出。不能抵消其他规则，不能让
路径跳过 fallback，也不能接受绝对路径、反斜杠、遍历、控制字符或符号链接组件。字段缺失等价于空
数组，保持旧策略兼容；未知 match 字段仍失败关闭。

通用 `research-web` 规则设置：

```json
{"excludePrefixes":["app/research_web/datahub/"]}
```

这样未来新增 DataHub 文件不会被通用 L1 吸收。只有下面的精确 allowlist 可以得到低于 L4 的计划。

## Catalog 设计

`catalogs.tests` 新增五个稳定 ID：

| ID | Level | 命令与职责 |
| --- | --- | --- |
| `research-web-datahub-public-provider` | L1 | `pytest test_datahub_catalog.py --confcutdir=...`；公共 Provider 目录与转换 |
| `research-web-datahub-core` | L2 | `pytest test_datahub.py --confcutdir=...`；快照发布与 DataHub 核心消费闭包 |
| `research-web-asset-workbench-ui` | L1 | `node --test research_web_workbench.test.mjs`；renderer、状态和缺失值呈现 |
| `research-web-asset-workspace-python` | L2 | `pytest test_asset_workspace.py --confcutdir=...`；API、区块、数据集和交接 |
| `research-web-asset-workspace-smoke` | L3 | 运行 `test_asset_observation_tracks_each_block_and_freezes_handoff_context`；最短端到端资产观察路径 |

全部 Python 命令必须保留 `--confcutdir=tests/research_web`。不复用框架 catalog，不新增依赖。

## Rule 设计

### `research-web-datahub-public-provider`

- 精确匹配：
  - `app/research_web/datahub/providers_akshare.py`
  - `tests/research_web/test_datahub_catalog.py`
- `risk=local-only`，`minimumLevel=L2`，`impact=["datahub-public-provider"]`，
  `coupling=high`。
- 选择 Provider L1、DataHub core L2、架构 L1、Project Constraints L2、资产 smoke L3、文档治理和
  Python 索引。
- CI 仍引用 Project Constraints / Research Web Checks，但只在计划实际达到 L4 时出现。

本轮只允许 AKShare，因为已有真实缺失值问题、Provider 测试和浏览器证据。其他 Provider 必须在单独
任务提供等价证据后显式加入，不能使用 `providers_*.py` 通配降级。

### `research-web-asset-workbench-ui`

- 精确匹配：
  - `app/research_web/ui/asset-workspace.mjs`
  - `tests/javascript/research_web_workbench.test.mjs`
- `minimumLevel=L1`，`impact=["asset-workbench-ui"]`，`coupling=high`。
- 选择 Workbench UI、架构、Asset Workspace Python L2、Project Constraints L2、资产 smoke L3 与
  文档治理。
- 从现有 `research-web-framework-ui.match.files` 删除
  `tests/javascript/research_web_workbench.test.mjs`；其他框架映射不变。

UI-only 改动停在 L1；当运行时 signal、backend 或 Provider impact 把计划提升后，累积执行 L2/L3 项。

### `research-web-asset-workbench-backend`

- 精确匹配：
  - `app/research_web/asset_workspace.py`
  - `app/research_web/asset_routes.py`
  - `tests/research_web/test_asset_workspace.py`
- `minimumLevel=L2`，`impact=["asset-workbench-backend"]`，`coupling=high`。
- 选择 Asset Workspace Python、Workbench UI、架构、Project Constraints、资产 smoke、文档治理和
  Python 索引。

`workbench.py`、`test_workbench_operations.py` 和研究台其他页面暂不移入本规则；它们的边界更广，
需要单独证据，避免借本任务顺手降级。

## 预期路由矩阵

| Changed set | 结果 |
| --- | --- |
| `providers_akshare.py` | L2；Provider + DataHub core + 架构 + Project Constraints |
| `asset-workspace.mjs` | L1；Workbench UI + 架构 |
| `asset_workspace.py` | L2；Asset Workspace Python + UI + 架构 + Project Constraints |
| AKShare Provider + asset UI | L3；两个高耦合 impact，增加 Asset Workspace Python 与 smoke |
| `test_datahub_catalog.py` | L2；已知路径，无 `unknown_path` |
| `research_web_workbench.test.mjs` | L1；不再选择任何 framework 测试 |
| Broker/contracts/security/snapshots/Wind/MySQL/CJPY/未来 DataHub 文件 | L4 fallback |
| 上述任一项 + CI/schema/dependency/security/desktop/release 路径 | 最高风险 L4，不丢失专项检查 |

L3 仍没有桌面、Tauri、sidecar 或 Windows 门。用户要求的发布后 Mac-only Bootstrap 属于交付补充证据，
不写进这些纯 Web 组件规则。

## 错误处理与安全

- 策略解析继续 exact-key 校验；`excludePrefixes` 只接受规范的仓库相对前缀。
- 空 allowlist、非法 catalog 引用、重复 ID、非法 level/execution、符号链接和越界路径继续显式失败。
- 排除通用规则后若专项规则缺失，计划必须出现 `unknown_path`、L4 和
  `unknown_impact_boundary`。
- 规划器不运行 catalog 命令、Git、CI 或发布，也不读取产品数据。
- Receipt validator 不变；失败、unexpected 和未运行外部门仍按现有规则阻止成功。

## 测试设计

先在 `tests/javascript/verification_policy.test.mjs` 写 RED，再修改规划器与策略。合同必须覆盖：

1. 上述路由矩阵的每一行。
2. AKShare + asset UI 的 `multiple_high_coupling_modules` L3 升级及 L0-L3 累积 ID。
3. Workbench 测试不再命中 framework impact 或 framework catalogs。
4. 新的 DataHub 未登记路径只命中 fallback L4。
5. `excludePrefixes` 缺省兼容、命中退出、不能覆盖其他规则、非法路径/字段失败关闭。
6. 所有新增 Python catalogs 含 `--confcutdir=tests/research_web`。
7. 现有 framework、installation、desktop、security、CI、unknown 和 receipt 合同全部不回归。

另外对真实仓库运行代表性 planner：

- Provider-only；
- Workbench UI-only；
- Provider + UI；
- Wind/security/snapshot/未来 DataHub 假路径；
- policy 自身 changed set。

保存 plan/receipt/report，记录命令、时长和外部门，不用期望输出代替真实运行。

## 文档、交付与验收

实施时同步：

- `docs/AGENT_WORKFLOW.md`：说明 DataHub allowlist、Workbench 路由和 DataHub 未登记路径 fallback。
- `docs/DEVELOPMENT_MAP.md`：登记专项源码→测试→文档闭包。
- `.agents/skills/incremental-validation/README.md`：只说明使用行为，不复制路径表；若该 skill 内容变化，
  同步其 README。
- `.ai/reports/`：计划、收据与完整 RED/GREEN/代表性矩阵证据。

由于修改规划器和 verification policy，本任务自身固定为 L4/full-delivery：策略合同、receipt 合同、
incremental-validation skill 合同、完整 verification suite、文档治理、Python 索引、Project Constraints
及选定 GitHub 门必须通过。实现使用隔离 worktree，发布后按用户要求补 Mac-only GitHub Bootstrap，
Windows 保持暂停，最终安全清理受管 worktree/branch。

验收成功要求：

- 代表性矩阵完全符合本设计，没有无关 framework catalog；
- DataHub 未登记路径与所有高风险组合仍为 L4；
- 现有策略测试无 skipped，planner/receipt 继续只读且 fail closed；
- 合并后远端默认分支、GitHub 自动门和 Mac-only Bootstrap 通过；
- Harness receipt、交付状态和本地默认分支收敛到同一最终 SHA。
