# Research Workbench Development Map

本文件只回答四个问题：改哪片源码、先读哪份权威文档、跑哪些测试、什么变化需要同步文档。文件和公开符号的机械清单由 [生成索引](generated/py_file_index.md) 负责。

## 当前 Research Web

| 源码区域 | 职责 | 权威文档 | 主要测试 | 文档更新触发 |
| --- | --- | --- | --- | --- |
| `app/research_web/main.py`、`service.py`、`client.py` | HTTP/SSE、会话和 DSH 投影 | `architecture/research-web/01-system.md`、`02-research-runtime.md`、`04-api.md` | `tests/research_web/test_api.py`、`test_protocol.py` | 路由、状态、恢复或认证变化 |
| `app/research_web/ui/`、`app/research_web/asset_workspace.py`、`app/research_web/asset_routes.py` | 当前产品原生 UI 与 Asset Workbench backend | `research-web-ui.md`、`research-web-appearance.md` | 验证策略 focused closure：`ui/asset-workspace.mjs` → `tests/javascript/research_web_workbench.test.mjs`；`asset_workspace.py` / `asset_routes.py` → `tests/javascript/research_web_workbench.test.mjs` + `tests/research_web/test_asset_workspace.py`，并累积架构与 Project Constraints 检查；其他 UI 运行相关测试和 E2E | 导航、DOM、可访问性、交互或 Asset Workbench API 合同变化 |
| `app/research_web/datahub/` | 目录、Provider、Broker、快照 | `research-web-datahub.md`、`architecture/research-web/03-data-files.md` | `providers_akshare.py` → `tests/research_web/test_datahub_catalog.py` + `tests/research_web/test_datahub.py`；其他已登记 DataHub 测试 | 能力、来源、字段、路由或快照合同变化 |
| `app/research_web/integrations/` | 五阶段集成状态和探测编排 | `architecture/research-web/09-integration-coordinator.md` | `tests/research_web/test_integration*.py` | 状态、归因、授权或探测变化 |
| `app/research_web/frameworks/`、`ui/frameworks*` | Gold／Dollar 专用框架 | `architecture/research-web/08-research-frameworks.md` | `test_frameworks*.py`、`research_web_frameworks*.test.mjs` | 方法版本、快照、评分、renderer 或会话绑定变化 |
| `app/research_web/capabilities/`、`skills/` | Skill、Method、Tool、Workflow | `research-web-capabilities.md`、`architecture/research-web/07-capabilities.md` | `test_capabilities*.py`、能力 UI 测试 | 目录、包版本、资源、权限或发现变化 |
| `mcp_registry/`、`mcp_runtime/` | MCP 目录、安装、Host 和授权 | `research-web-capabilities.md`、Research Web 架构模块文档 | `test_mcp_*.py`、marketplace 测试 | Registry、安装、OAuth、策略或调用边界变化 |
| `automation/` | 定时任务、Run 和投递 | Research Web 架构模块文档 | `test_automation*.py`、计划 UI 测试 | 调度、重叠、恢复、投递或秘密边界变化 |
| `report_workflows/` | 报告模板、底稿、运行和交付 | `architecture/research-web/03-data-files.md`、`04-api.md` | `test_report_workflow*.py` | 模板、资源、运行、Excel 或交付变化 |
| `documentation.py`、文档检查脚本 | 安全只读文档入口和离线门禁 | `research-web-documentation.md`、`architecture/research-web/06-documentation-contract.md` | 文档治理、架构和路由测试 | 文档 schema、索引、图文或检查策略变化 |

`architecture/research-web/architecture-map.json` 是 Research Web 架构 source/document/test/diagram inventory 的机器真源；`.agents/verification-policy.json` 是 changed-file → impact → validation route 的唯一机器真源。两者互补且不互相推导：新增 Research Web 源文件仍须进入架构清单，而本表的测试闭包说明不能替代 verification policy。

上述 DataHub 专项映射仅登记策略中明确允许的路径。未登记 DataHub 路径继续 fallback / fail closed，不能仅凭目录位置推断为低风险。`asset_workspace.py` / `asset_routes.py` → `research_web_workbench.test.mjs` + `test_asset_workspace.py` 只说明验证策略的 focused closure，不表示本次修改了 `architecture-map.json` 或从架构 inventory 推导了验收路由。

## 兼容平台

下列代码仍受维护，但不是当前 Research Web 的默认依赖：

| 源码区域 | 权威参考 | 更新触发 |
| --- | --- | --- |
| `app/api/`、`app/cli/commands/`、`app/web/` | `docs/modules/app_*.md`、`REFERENCE.md` | 兼容路由、命令或旧 UI 合同变化 |
| `core/`、`services/` | `docs/modules/core_*.md`、`docs/modules/services.md` | 领域契约、服务边界或模型网关变化 |
| `connectors/`、`data_layer/`、`ingestion/`、`cron_jobs/` | `DATA_SOURCES.md`、对应 `docs/modules/` | Connector 生命周期、来源或持久化变化 |
| `storage/`、`data_layer/repositories/` | `DATA_STORAGE.md`、仓储模块文档 | schema、迁移、Repository 或事务变化 |
| `knowledge_layer/`、`reasoning/`、`cognitive_agents/` | 对应 `docs/modules/` | 提取、证据、推理或旧 Agent 合同变化 |
| `signal_lab/`、`timing_engine/`、`memory_learning/`、`reporting/` | 对应 `docs/modules/` | 计算、回测、记忆或报告投影变化 |
| `src-tauri/`、`desktop/`、`scripts/desktop/` | `desktop_packaging.md` | 任何桌面运行、安装、更新或平台行为变化 |

兼容模块文档不应把自身描述成 Research Web 现役入口。文件增删或公开符号变化时更新生成索引；纯内部行为变化不需要制造索引 diff。

## 规则与交付

- `AGENTS.md`：共享工程规则真身；`CLAUDE.md` 只保留 Claude 专属差异。
- `docs/AGENT_WORKFLOW.md`：选择本地快环、worktree 或后台／远程执行。
- `.agents/project-constraints.json`：架构、平台和文档治理门禁配置。
- `.agents/verification-policy.json`：改动路径到影响、L0-L4、测试、文档和 CI 门的唯一机器真源。
- `scripts/plan_verification.mjs`：只读合并全部改动的 Change → Impact → Validation 计划；不执行计划中的命令。
- `scripts/validate_verification_receipt.mjs`：只读核对 plan 与真实 receipt，禁止漏项、降级、假通过和丢失外部门。
- `tests/javascript/verification_policy.test.mjs`、`verification_receipt.test.mjs`：规划、升级、安全与证据合同。
- `.agents/skills/incremental-validation/`：Codex/Claude 共用的项目增量验收流程；只引用策略和脚本，不复制路由表。
- `docs/actions-budget.md`：GitHub Actions 免费额度、冻结状态、平台路由与保留策略。
- `.ai/reports/`：每个实现任务的真实证据及 `architecture-review` 标记。
- 源码结构或导入发生变化时运行 `python scripts/generate_py_file_index.py --check`；需要更新时先生成再复核。
- `Research Web Tabbit Verify` 当前仅手动触发；Tabbit 契约变化或平台支持声明必须显式运行双平台工作流，自动 Project Constraints 继续检查其触发器契约。
- 普通 Research Web 改动由 Ubuntu `Research Web Checks` 承担；Bootstrap、Windows Verify 和 Desktop Verify 必须依路径命中，不能由 docs-only 提交触发。

## 最小验证

```bash
node scripts/plan_verification.mjs --project . --changed-file <path>
node scripts/validate_verification_receipt.mjs --project . --plan <plan-json> --receipt <receipt-json>
node scripts/check_documentation_governance.mjs --project .
python scripts/generate_py_file_index.py --check
node scripts/check_research_architecture.mjs --project . --base <base>
python scripts/check_doc_sync.py --project . --base <base>
node .agents/project-constraints.mjs --project . --changed-file <path>
```

先对完整 changed set 重复传入 `--changed-file`，再按 `validationsByLevel` 从 L0 执行到 `requiredLevel`；多文件取最高风险并合并去重。局部失败或非预期行为必须带 signal 重新规划。receipt 保存摘要、影响、实际执行、结果、外部门、未覆盖风险和升级判断，并通过 validator 才能交接。Project Constraints 保持独立的架构/平台/文档门，不复制策略内容。

已知组件可以在策略中映射不同等级的候选验证：低等级只选择局部项，耦合或 signal 升级后才纳入依赖/smoke/full 项。未登记测试仍按 `unknown_path` 升级 L4/`full-delivery`，不得仅凭位于 `tests/` 目录推断低风险。
