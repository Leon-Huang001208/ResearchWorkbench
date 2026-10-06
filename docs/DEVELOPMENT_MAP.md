# Research Workbench Development Map

本文件只回答四个问题：改哪片源码、先读哪份权威文档、跑哪些测试、什么变化需要同步文档。文件和公开符号的机械清单由 [生成索引](generated/py_file_index.md) 负责。

## 当前 Research Web

| 双运行时源码区域 | 职责 | 权威文档 | 主要测试 | 文档更新触发 |
| --- | --- | --- | --- | --- |
| `runtimes/research_web.json`、`app/research_web/runtime_contract.py` | Native/Docker 共用 Python、Node、CJPY、DSH、pnpm 事实 | `research-web-installation.md`、`architecture/research-web/01-system.md` | `test_runtime_contract.py`、`docker_runtime_contract.test.mjs` | 固定版本、闭包或镜像事实变化 |
| `research_workbench_entrypoint/runtime_mode.py`、`bootstrap.py`、`docker_runtime.py` | 无 `.venv` 的模式路由、安全切换、Compose 归属 | `research-web-installation.md`、`architecture/research-web/02-research-runtime.md` | `test_runtime_mode.py`、`test_docker_runtime.py` | mode schema、CLI、归属或错误码变化 |
| `app/research_web/process_spec.py`、`runtime_state.py`、`staged_runtime.py`、`launch_runtime.py`、`service_manager.py` | 共用进程规范，分离认证状态和镜像内已验证 DSH 资产 | `architecture/research-web/01-system.md`、`02-research-runtime.md` | `test_service_manager.py`、`test_runtime_launch.py`、`test_staged_runtime.py` | 生命周期、挂载或 DSH 资产合同变化 |
| `app/research_web/credential_backend.py`、连接/MCP/Automation 调用点 | Native 系统 keyring 与 Docker 私有文件凭据后端的明确选择 | `architecture/research-web/03-data-files.md`、`05-security-validation.md` | `test_credential_backend.py`、相关连接/MCP/Automation 测试 | 凭据存储、ACL 或跨模式边界变化 |
| `Dockerfile`、`compose.yaml`、`.dockerignore`、`docker/` | 非 root 单容器镜像、DSH/Web 监督、认证健康检查 | `research-web-installation.md`、`architecture/research-web/01-system.md` | `test_docker_packaging.py`、`test_container_supervisor.py`、`docker_runtime_contract.test.mjs` | 基础镜像、构建、挂载、端口或健康变化 |

以下原有表继续映射产品模块；上表只添加部署与运行边界，不创建第二套 Web/DSH 引擎。

Docker bind 根与私有叶布局由 Dockerfile/Compose 配置、entrypoint 父目录检查、supervisor
严格创建与 healthcheck 只读消费共同维护；测试闭包为 `test_container_supervisor.py`、
`test_credential_backend.py`、`test_runtime_launch.py`、`test_docker_packaging.py` 与
`docker_runtime_contract.test.mjs`。不得通过放宽 owner、mode 或 no-follow 来适配 bind 映射。
固定bind缺失叶的两阶段首建在supervisor内实现；其确定性测试模拟root→当前UID/GID并覆盖
foreign owner/group、mode/inode变化、alias/替换与自定义路径不豁免，原validator不修改。

`test_docker_runtime.py` 还覆盖Compose创建后返回非零/超时的恢复：本次launch标签识别、
精确容器清理、未知实例保留、既有停止容器保护，以及离线repair失败后旧接受image重建。

| 源码区域 | 职责 | 权威文档 | 主要测试 | 文档更新触发 |
| --- | --- | --- | --- | --- |
| `app/research_web/main.py`、`service.py`、`client.py` | HTTP/SSE、会话和 DSH 投影；按运行模式注入凭据后端 | `architecture/research-web/01-system.md`、`02-research-runtime.md`、`04-api.md` | `tests/research_web/test_api.py`、`test_protocol.py` | 路由、状态、恢复或认证变化 |

| `model_credentials.py`、`runtime/model-credentials.mjs`、`launch_runtime.py` | macOS Native 固定模型 Keychain 私有桥接与 owned overlay；Host record 保留原实现 | `architecture/research-web/05-security-validation.md`、`02-research-runtime.md`、`research-web-installation.md` | `test_model_credentials.py`、`test_runtime_launch.py`、`research_web_model_credentials.test.mjs`；真实 Keychain/固定 DSH 仅显式 opt-in 合成验收 | 后端、命名空间、凭据回退、记录委托或受管解释器变化 |
| `rwb`、`rwb.cmd`、`research_workbench_entrypoint/web_*.py`、`app/research_web/service_manager.py`、`service_diagnostics.py`、`lifecycle_lock.py` | 环境后备诊断、服务事实、排他锁、启动恢复与 Web ready | `research-web-installation.md`、`architecture/research-web/01-system.md`、`02-research-runtime.md`、`05-security-validation.md` | `test_web_contract.py`、`test_web_bootstrap.py`、`test_service_manager.py`、`test_cli_lazy.py` | 公开 CLI、PID/端口归属、健康、错误码、恢复或浏览器时机变化 |
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

Docker CI 由 Linux 真机在指定提交完成本机验收后，通过 `.github/workflows/research-web-docker.yml` 的 `workflow_dispatch` 和必填 `expected_sha` 发起；Mac PR/push 不自动触发，checkout 与 dispatch SHA 不一致时失败关闭。本机 Docker 构建、Native/macOS 安装门及真实 Windows 回执必须分别记录，源码测试不替代平台生命周期。仅 docs 变化按 changed set 的规划器结果验收，不能因旧任务已验收而虚写回执。

Docker 启动/安装修复的目标闭包还覆盖 `test_setup_web.py` 的候选失败与摘要恢复、
`test_cli_lazy.py` 的 Native `status --json` 安全投影。`test_docker_runtime.py` 检查延迟健康、
失败回滚归属、不可变镜像选择及 Doctor 的 `dsh` 公共字段；`test_runtime_contract.py` 成对检查
无关祖先目录活动和合同父目录瞬时 alias。API 与本机集成测试使用每例独立的内存 keyring，
不读取宿主凭据；生产凭据错误仍失败关闭。

本地集成回归另覆盖 `test_web_bootstrap.py` 的工作树环境归属、`test_runtime_mode.py` 的
坏 Native 环境与 PID 重用拒绝，以及 `test_container_supervisor.py` 的完整页面探测总时限。
Docker 控制测试使用临时端口，真实端口冲突断言继续执行，不要求停止开发者正在运行的服务。

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
- `.agents/verification-policy.json`：改动路径到 Component × Risk(L0-L4) × Platform、local/CI/real-machine lane 和 merge/release gate 的唯一机器真源。
- `scripts/plan_verification.mjs`：受管共享内核的只读薄入口，合并全部改动的 changed-set 计划；输出 components、platforms、逐级验证和三个 lane，不执行计划中的命令。
- `scripts/validate_verification_receipt.mjs`：受管共享内核的只读薄入口，核对 plan 与真实 receipt，禁止漏项、降级、跨层假通过和错误的 merge/release readiness；继续只读兼容历史 plan v2/receipt v1。
- `tests/javascript/verification_policy.test.mjs`、`verification_receipt.test.mjs`：规划、升级、平台、状态、安全与证据合同。
- `tests/javascript/repository_cross_platform_contract.test.mjs`：Git 换行、vendor 字节稳定和本机状态忽略合同。
- `.agents/runtime/leon-engineering/manifest.json`：共享验收内核固定版本、source commit、协议和受管文件哈希；不拥有项目策略。
- `.agents/skills/incremental-validation/`：Codex/Claude 共用的项目增量验收流程；只引用策略和脚本，不复制路由表。
- `docs/actions-budget.md`：GitHub Actions 免费额度、冻结状态、平台路由与保留策略。
- `.ai/reports/`：每个实现任务的真实证据及 `architecture-review` 标记。
- 源码结构或导入发生变化时运行 `python scripts/generate_py_file_index.py --check`；需要更新时先生成再复核。
- `Research Web Tabbit Verify` 当前仅手动触发；Tabbit 契约变化或平台支持声明必须显式运行双平台工作流，自动 Project Constraints 继续检查其触发器契约。
- 普通 Research Web 改动由 Ubuntu `Research Web Checks` 承担；Bootstrap 和 Desktop Verify 必须依路径命中，不能由 docs-only 提交触发。Windows Verify 由 policy changed-set 条件选择，但只能从 Windows 真机以 exact SHA `workflow_dispatch`，不能由 Mac PR/push 自动触发。

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

先对完整 changed set 重复传入 `--changed-file`，再按 `validationsByLevel` 从 L0 执行到 `requiredLevel`；多文件取最高风险并合并去重。局部失败或非预期行为必须带 signal 重新规划。receipt 保存摘要、组件、平台、local/CI/real-machine 实际状态、`mergeReady`、`releaseReady`、未覆盖风险和升级判断，并通过 validator 才能交接。选中 gate 未运行时记录 `NOT_RUN` 或 `MANUAL_REQUIRED`，绝不写成 `PASS`。Project Constraints 保持独立的架构/平台/文档门，不复制策略内容。

已知组件可以在策略中映射不同等级的候选验证：低等级只选择局部项，耦合或 signal 升级后才纳入依赖/smoke/full 项。未登记测试仍按 `unknown_path` 升级 L4/`full-delivery`，不得仅凭位于 `tests/` 目录推断低风险。
