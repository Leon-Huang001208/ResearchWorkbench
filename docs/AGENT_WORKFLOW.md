# Agent 任务路由指南

本指南用于在开始工作前选择合适的执行方式，并定义可复核的交付证据。共享规则以仓库根目录的 `AGENTS.md` 为准；`.agents/skills/` 中存放已跟踪的项目 skills。`.claude/` 仅是本机可选配置，不能作为共享规则来源。

数据能力仅在对应任务中按需加载：`wind-find-finance-skill` 负责金融能力发现，`wind-mcp-skill` 负责受支持的 Wind 查询；`cls`、`cnstock` 和 `data-connector-development` 只维护 legacy crawler/Connector 层，不能把代码存在误报为当前 Research Web DataHub Provider 可调用。全局目录不再承载这些项目专属 Skill。

## 任务路由（Routing rules）

先按下列优先级路由，而不是只凭任务大小选择。后台/远程是执行通道，worktree 是本地仓库修改隔离；二者可以组合，长时本身不要求 worktree。选择最小但足够的方式，不因任务看似复杂而跳过验证。

### 路由优先级与决策顺序

1. **先应用桌面端例外。** 只要改动影响桌面端，就必须先满足“桌面端例外”中的原生平台验证和发版前烟测要求；执行方式仍按后续规则选择。
2. **再判断是否必须使用独立 worktree。** 任何并发改动、已有无关工作区改动、涉及公开接口、数据库、安装流程，或无法局部回滚的高风险变更，必须使用独立 worktree。高风险指影响公开契约、数据迁移、桌面安装/更新、跨平台行为，或无法快速还原的变更；此隔离要求可与后台/远程执行通道同时适用。
3. **再判断是否适合后台/远程。** 验收稳定且确定、但执行耗时的工作，使用后台/远程；例如只读仓库研究、CI 日志分析、审查或有界实现。后台/远程任务若编辑仓库且有并发或风险，必须在独立 worktree 或等效隔离的远端 workspace 中执行。
4. **最后才使用本地快环。** 仅当变更单一、局部、可快速验证且无冲突时，才使用本地快环。

多文件本身不是自动进入独立 worktree 的条件；只有存在冲突、风险、并行需求或需要干净比较时，才需要隔离 worktree。

| 路由 | 适用条件 | 交付证据 | 不适用场景 |
|---|---|---|---|
| 本地快环 | 变更窄、需立即判断、不与活跃修改冲突 | 目标命令或浏览器结果 + 简洁 diff | 长任务、并发公共区域、或需要探索替代方案 |
| 独立 worktree | 并发、已有无关工作区改动、高风险或需干净比较分支 | 路径、分支、针对验证、明确集成计划 | 只读或一行确认；仅因多文件而隔离 |
| 后台/远程 | 验收稳定且确定但耗时，如只读仓库探索、CI 日志分析、审查或有界实现；若编辑且有并发/风险则与独立 worktree 或等效远端隔离组合 | 任务范围、diff/报告、命令、未验证约束 | 交互秘密、破坏操作、发版决定、持续设计判断 |

选择后仍应先阅读相关规则、目标文件及其直接依赖；任务范围、所有权或验收不明确时，先同步并拆分，而不是扩大执行范围。

## 最小验收规划（Verification planning）

在决定具体测试和交付范围前，用项目内只读规划器为全部改动路径生成机器可读计划：

```bash
node scripts/plan_verification.mjs --project . \
  --changed-file <changed-file> \
  --changed-file <another-changed-file>
```

`.agents/verification-policy.json` 是唯一政策真源；规划器只输出计划，不运行测试、Git、CI、发布或策略中的命令。`.agents/project-constraints.json` 保持独立架构门，不拥有或复制路由表。

所有聚焦 `tests/research_web/` 的 Python catalog 必须带 `--confcutdir=tests/research_web`，与 GitHub
Research Web Checks 使用同一测试边界。这样本机 `.env`、根 `tests/conftest.py` 的兼容平台数据库
fixture 和旧平台依赖不会污染 Research Web 验收；根 conftest 与非 Research Web 测试本身保持不变。

### L0-L4 分层

| 等级 | 最小验收语义 | 典型证据 |
| --- | --- | --- |
| L0 | 静态合法性 | syntax、format/lint、JSON/config、文档治理、生成索引 |
| L1 | 修改模块局部单元 | 与变更组件直接映射的测试 |
| L2 | 上下游依赖闭包 | 架构约束、直接接口与依赖链测试 |
| L3 | 相关关键路径 smoke | 跨越本次边界的最短 API/runtime/user 路径 |
| L4 | 完整相关验收 | full relevant suite/build、交付与必需平台/CI 门 |

`requiredLevel` 是完整 changed set 的最高必要等级；`validationsByLevel` 是实际执行真源。等级是累积责任，但不会凭空加入不相关平台门。Web-only 的 L4 仍不能伪称已执行桌面 Windows 验收；只有规划器实际输出的外部门才进入回执。

### Change → Impact → Validation

每次迭代必须读取并保留：

- `changeSummary` 与 `changedFiles`：改了什么；
- `impact` 与 `reasons`：影响模块、耦合和边界；
- `validationsByLevel`：最能证明影响的最小测试、文档和外部门；
- `escalations` 与 `uncoveredRisks`：为何扩大、仍未覆盖什么。

多个高耦合模块由策略自动提升到至少 L3。公开契约、schema/config、核心抽象/共享工具、数据模型/迁移、依赖、CI、安全、桌面、发布和未知边界保持 L4/fail-closed；parser、workflow 和 agent orchestration 等已知关键链至少 L3。具体路径与命令只在策略中维护，本文不复制。

### 执行、升级与回执

按 L0→`requiredLevel` 执行输出项，并为每个实际检查记录状态、耗时和证据路径。局部失败后用 `--signal validation_failure` 重新规划；非预期行为用 `--signal unexpected_behavior`。两种 signal 均逐级扩大范围并保留升级原因。

最终 receipt 必须包含变更摘要、精确 changed set、计划/实际等级、影响判断、已执行项、`external` 门、结果、`uncoveredRisks` 与升级决定，然后运行：

```bash
node scripts/validate_verification_receipt.mjs --project . \
  --plan <plan-json> \
  --receipt <receipt-json>
```

回执校验失败就不是完成。`full-delivery` 的外部门不得写成 `not_required`；未运行时必须以 `blocked` 和对应未覆盖风险保留，不能用本机检查冒充 CI/平台证据。

计划必须覆盖完整 changed set，并按最高风险合并。未知路径不能降级；非法策略、符号链接或越界路径必须先失败，不能退回猜测计划。

普通 `app/research_web/` 与 `app/web/` Web-only 改动只选择相关 Web、文档与轻量 CI 门，desktop、Windows、Tauri、sidecar 和 installer 门数量必须为 0。只有桌面专属路径才附加原生 Windows 与 [`desktop_packaging.md`](desktop_packaging.md) 门。

Research Web 框架的 backend、renderer 与已登记测试按组件影响合并；单个 renderer 可停在局部闭包，backend+renderer 等高耦合跨模块集合自动扩大到依赖和 smoke 闭包。其他未登记测试继续 fail closed，不能用通用测试目录规则批量降级。

`app/research_web/datahub/` subtree 由全局 delegated namespace 机制交给 namespace owners：只有策略显式 allowlist 的公共 Provider 才能使用 L1-L3 专项闭包。多个 delegated prefixes 同时命中时只采用最长 prefix；owner 只能由该 namespace 内的正向 `match.files` 或 `match.prefixes` 建立，`segments`、`suffixes` 和 namespace 外的父 prefix 都不算 owner。命中 delegated namespace 后只有这些 owner rules 参与匹配；没有 owner 接住时必须回到 L4 fallback。Broker、contracts、security、snapshots、专业 Provider 和未来新增路径都不能被通用目录、segment 或 suffix 规则降级。

Asset Workbench UI 与 backend 使用彼此独立的专项规则。公共 Provider 与 UI 同时变化会形成两个 high-coupling impacts，自动提升到 L3，并执行覆盖 API、快照与呈现的资产观察 smoke；这不会扩大到桌面平台门。

## 桌面端例外（Desktop exception）

worktree 只隔离文件冲突，绝不取代桌面端原生 Windows CI，也不能取代真实 Windows 安装级烟测。凡影响 `src-tauri/`、`desktop/`、`scripts/desktop/`、sidecar、桌面配置或路径、安装包、自动更新、Excel/Wind 集成的改动，都必须以 [`desktop_packaging.md`](desktop_packaging.md) 的跨平台开发与发布验证流程为准。

当前产品迭代阶段为 **Web-only**。仅修改 `app/web/`、`app/research_web/`、通用 Web API/Runtime、共享 Python/Node 依赖或 Web 文档时，不进入桌面端例外，也不运行 sidecar、Tauri、安装包或原生桌面 CI。只有用户明确重新开启桌面工作，或任务直接修改 `src-tauri/`、`desktop/`、`scripts/desktop/`、`services/desktop_platform/` 等桌面专属路径时，才恢复下列桌面验收。

交付时应明确以下不可省略的验收范围：

1. 原生 Windows CI 至少覆盖依赖安装、Python sidecar（`.exe`）构建、Tauri Windows 安装包构建、真实 PostgreSQL + pgvector 的 `ready` `/health` 检查，以及数据库不可达时的 `setup_required` `/health` 检查。
2. 原生 macOS CI 也必须完成对应平台的 sidecar 与桌面包构建，并验证 `ready` 和 `setup_required` 的 `/health` 契约。
3. 发版前仍须在真实 Windows 设备上验证 CI 产物的安装、卸载、升级、主窗口、sidecar、`/health`、用户数据目录和日志；涉及 Excel/Wind、系统权限或自动更新时，还须验证相应功能。

macOS 本地运行或隔离 worktree 都不能证明 Windows 可用。

## 证据与交接（Evidence and handoff）

交接应让接手者无需猜测即可复核结果，至少包含：

- 任务范围和未触及的边界；
- 修改文件、简洁 diff 摘要，以及 worktree 时的路径和分支；
- 实际运行的验证命令和结果，或浏览器检查结果；
- 未运行的验证、环境限制和风险；
- 后续集成步骤、依赖的 CI 或人工验收责任人。

不得将未运行的检查写成已验证。后台或远程任务必须报告可审阅的 diff 或结论，并保留未验证约束；涉及秘密、破坏性操作、发版决定或需要持续设计判断时，必须回到可交互的人工决策流程。

## 示例（Examples）

- 修正文档中的单个链接并立即确认渲染：使用本地快环，交付检查命令与简洁 diff。
- 为独立功能修改多份配置和测试：使用独立 worktree，交付 worktree 路径、分支、针对性测试和合并计划。
- 分析失败的 Windows CI 日志并提出有界修复：可用后台/远程执行，交付日志范围、分析报告、修复 diff、运行命令及未在真实 Windows 复测的限制。
- 修改 Tauri sidecar 或 Wind/Excel 集成：即使在独立 worktree 中完成，也必须等待原生 Windows CI；若准备发布，还要安排真实 Windows 安装级烟测。
- 只修改 Research Web 页面、Web API 或 Runtime：按 Web 测试与项目约束交付，不运行 Desktop Verify。
