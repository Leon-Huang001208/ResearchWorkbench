# Research Web Framework Verification Routing Design

## 背景与问题

当前 `.agents/verification-policy.json` 把全部 `app/research_web/**` 归为通用 `research-web` 路由。框架源码因此只获得 `research-web-architecture` 测试，没有显式获得现有的框架 Python、采集器和 UI 专项测试。与此同时，`tests/research_web/test_frameworks.py` 等测试文件没有任何规则命中，会落入 `unknown_path` fallback，并把包含这些测试的 changed set 升级为 `full-delivery`。

这会同时产生两个问题：实现改动的最小验收过窄，而已知框架测试改动的交付范围又过宽。后者会增加不必要的 worktree、发布、CI 和模型回合，但没有增加对应组件的验证精度。

## 目标与非目标

本次目标是为 Research Web 框架组件补充可解释、可回滚的专项路由，使框架源码和三个已知框架测试文件获得同一组专项测试，同时保留现有通用 Web、文档、CI 和 fail-closed 语义。

本次不修改框架运行时代码、HTTP API、UI 行为、架构清单、测试实现、桌面路径或依赖；不把整个 `tests/**` 降级为 `local-only`；不从 `architecture-map.json` 动态生成策略；不迁移恢复 worktree 中已被主线替代的旧框架实现；不持久化 Token 插件配置。

## 方案比较与决定

### 方案 1：增量组件规则（采用）

在现有策略中增加框架专项测试目录项和一条 `research-web-frameworks` 规则。规则与通用 `research-web` 规则叠加，规划器继续按最高风险和稳定顺序合并去重。

优点是改动面最小、原因码清晰、无需改变规划器代码；未知测试仍然 fail closed。缺点是每个新增组件仍需显式维护自己的路径和测试映射。

### 方案 2：通用测试目录规则（拒绝）

把 `tests/research_web/**` 和 `tests/javascript/research_web_*` 整体归为 `local-only`。这能快速消除 fallback，但会把尚未建模的安全、契约、桌面或跨平台测试错误降级，削弱未知路径硬门。

### 方案 3：从架构清单动态生成（暂不采用）

让规划器读取 `architecture-map.json` 并推导测试。这能降低长期重复配置，但会引入第二策略真源、跨 schema 依赖和更复杂的错误处理，超出本次窄范围修复。

## 策略数据变更

`catalogs.tests` 新增三个稳定 ID：

- `research-web-frameworks-python`：运行 `python -m pytest tests/research_web/test_frameworks.py`。
- `research-web-framework-collectors`：运行 `python -m pytest tests/research_web/test_framework_collectors.py`。
- `research-web-frameworks-ui`：运行 `node --test tests/javascript/research_web_frameworks_ui.test.mjs`。

新增 `research-web-frameworks` 规则：

- `risk` 为 `local-only`。
- `reason` 为 `research_web_framework_change`。
- `prefixes` 匹配 `app/research_web/frameworks/` 与 `app/research_web/ui/frameworks/`。
- `files` 匹配 `app/research_web/ui/frameworks.mjs` 和三个对应测试文件。
- `tests` 引用上述三个专项目录项。
- `documentation` 继续要求 `documentation-governance` 与 `python-file-index`。
- `ci` 继续要求 `project-constraints` 与 `research-web-checks`。

不修改 `riskOrder`、fallback、桌面规则和现有目录项。无需改变 `scripts/plan_verification.mjs` 的解析或合并算法。

## 路由与合并语义

框架源码会同时命中 `research-web-frameworks` 和现有 `research-web`：风险仍为 `local-only`，测试集合包含通用架构测试和三个框架专项测试，文档与 CI 门去重后保持原有顺序。

三个框架测试文件只命中专项规则，不再使用 fallback；其风险为 `local-only`，输出同一组专项测试、文档门和 Web CI 门。其他未建模测试文件继续命中 `unknown_path`，维持 `full-delivery`。

任何 changed set 只要同时包含契约、schema、依赖、CI、安全、桌面、发布或其他未知路径，整体风险仍取 `full-delivery`。框架规则不得产生 desktop、Windows、Tauri、sidecar 或 installer 门。

## 错误处理与安全边界

策略仍由现有严格 schema 校验：新增目录项必须是非空字符串，规则引用必须存在，ID 必须唯一，匹配路径必须安全且规范化。损坏、未知字段、符号链接、越界路径和弱化 fallback 继续显式失败，不得回退到猜测计划。

规划器仍是纯只读组件，只返回命令字符串，不解释或执行任何测试、Git、CI 或发布命令。新增规则不扩大工具权限，也不改变运行时网络或文件访问。

## 测试设计

先在 `tests/javascript/verification_policy.test.mjs` 增加 RED 合同，再修改策略：

1. 框架源码 changed set 必须为 `local-only`，包含通用架构测试与三个专项测试，且不包含桌面门。
2. 三个框架测试文件 changed set 必须为 `local-only`，不再出现 `unknown_path`。
3. 未建模的其他测试路径仍为 `full-delivery`，原因仍是 `unknown_path`。
4. 框架路径与依赖或 CI 路径组合时，最高风险仍为 `full-delivery`，专项测试不丢失。
5. 多路径和重复路径下专项测试、文档与 CI 门保持稳定顺序并去重。

现有非法 JSON、弱 fallback、符号链接、越界路径、命令不执行、纯 Web 无桌面门等反向测试必须继续通过。策略测试中的 fixture 必须同步真实策略新增的目录项和规则，避免测试样板与生产策略漂移。

## 文档与证据

更新 `docs/AGENT_WORKFLOW.md` 的最小验收说明，明确框架源码与测试文件会选择框架专项门；更新 `docs/DEVELOPMENT_MAP.md` 的规则说明，声明已知组件测试可以显式映射而未知测试保持 fail closed。

新增 `.ai/reports/` 任务报告，记录 RED、GREEN、完整 changed set 计划、文档治理、Python 文件索引、Project Constraints、合并结果验证和远端 CI。不得把未执行命令写成通过。

## Token 与交付影响

当前静态对照显示，新主项目临时禁用八个低频插件后，prompt 从 67,989 字符降至 62,789 字符，减少 5,200 字符（7.65%），且三个核心工程 skill 仍存在。该证据只说明插件路由的静态潜力，不是本次策略变更的 Token 降幅。

本次策略优化的可观察收益是减少已知框架测试被误判为 `full-delivery` 的次数，并让框架实现一次性获得完整专项测试清单。验收只比较规划器输出、执行回合和实际门覆盖；不得用删除必要测试或降低高风险路径来换取 Token 降幅。

由于本次修改 `.agents/verification-policy.json`，它自身命中 CI 治理规则，必须在独立 worktree 中完成受管完整交付：实现提交、`prepare`、integration worktree 合并结果验证、发布、远端 CI 状态和安全清理。优化从后续框架任务开始生效。

## 验收标准

- 框架源码计划为 `local-only`，包含 1 个通用架构测试和 3 个框架专项测试。
- 三个已知框架测试文件计划为 `local-only`，没有 `unknown_path`。
- 未建模测试、契约、schema、依赖、CI、安全、桌面和发布路径的风险不降低。
- 纯 Web 框架计划的桌面相关门数量为 0。
- 策略测试、Research Web 架构测试、文档治理、Python 文件索引和 Project Constraints 全部通过且无 skipped。
- 合并后的默认分支与远端 CI 通过；清理不强删脏 worktree 或未归并分支。
