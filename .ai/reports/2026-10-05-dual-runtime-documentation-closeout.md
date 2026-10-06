# Native/Docker 完整分支文档收尾

基线 `4d6a4eff6`；代码修复以 `ff941a56f` 为当前已提交证据。本文记录对现有模块说明和文档治理清单的同步；实际部署、平台和远端验收须看独立回执。未修改产品源、接口清单或旧任务报告。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"服务管理与安全状态投影按所选模式处理启动和诊断，既有 8088 API、Gold/Dollar 会话和集成协调器边界没有增加路由或节点；对应模块文档已同步。","diagrams":[]} -->
<!-- architecture-review {"group":"mcp-registry","structure":"unchanged","reason":"Registry 认证改由共享后端选择 Native keyring 或 Docker 私有目录，保留原服务命名空间、Registry 路由与只读目录关系。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"DataHub 连接秘密改走按模式选择的凭据后端，静态目录、Provider 适配、Broker 动态选源、快照和协调器关系没有改变。","diagrams":[]} -->
<!-- architecture-review {"group":"mcp-runtime","structure":"unchanged","reason":"MCP 安装凭据和完整性密钥复用共享后端，固定制品、Host 授权与 DSH 激活关系继续使用原边界。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"投递渠道秘密改由共享后端存取，任务锁定、Run、研究与投递双状态和原有审批策略不变。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"治理 JSON 仅澄清历史任务回执与现役产品说明的权威分界；图文检查器、路由策略、Web 文档入口和图节点均未改变。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"Runtime 仍是固定 DSH 与 Web 的同一研究链，模式仅改变服务部署位置；既有 01-deployment 已在完整分支更新并验证，此处没有新的 runtime 图源结构变化。","diagrams":["01-deployment"]} -->

## 结构依据

- `architecture-map.json` 的 `dual-runtime` 组将入口、模式、Docker controller、共享凭据后端映射到 `01-deployment`；该图源、HTML、deliver 与视觉回执已随分支变更。本轮不重绘相同拓扑。
- `app/research_web/credential_backend.py` 在没有 `RESEARCH_CREDENTIAL_HOME` 时使用系统 keyring，显式配置时才选择 POSIX 私有文件目录；DataHub、MCP Registry、MCP Runtime 与 Delivery 各保留服务命名空间。DSH 模型密钥不由此后端迁移。
- `research_workbench_entrypoint/docker_runtime.py` 与 `scripts/setup_web.py` 的修复要求候选镜像合同和不可变 image ID、健康等待及明确旧容器处置；`--no-start` 不证明服务 ready。`app/cli/main.py` 的 Native `status --json` 是安全投影。以上不增 HTTP API。
- Docker 容器健康不证明宿主 Office/Wind/Tabbit 可用；Windows Docker 凭据 ACL 仍失败关闭。模块说明不将这些能力或平台标成已验收。

## 文档变更

更新 `04-api`、`08-research-frameworks`、`09-integration-coordinator`、`07-capabilities`、`06-documentation-contract`、Tabbit、能力、DataHub、UI、文档门户、文档门禁，以及 CLI 参考入口和 scripts 模块文档，共 13 份 Markdown；`documentation-governance.json` 只澄清 `.ai/` 历史证据的用途，未调整状态、匹配规则或权威路径。后两份由完整分支 `check_doc_sync.py` 的 Python owner 映射触发：`app/cli/main.py` 对应 `docs/REFERENCE.md`，`scripts/setup_web.py` 对应 `docs/modules/scripts.md`，补充了实际 CLI 状态及 Docker 安装语义。

## 验证与剩余门

以下命令均在当前 worktree 执行；脚本在 `logs/research-architecture-check.jsonl` 与
`logs/documentation-governance.jsonl` 留有非敏感本地检查记录：

| 命令 | 结果 |
| --- | --- |
| `node scripts/check_documentation_governance.mjs --project .` | exit 0；518 Markdown、73 current、0 违规 |
| `node --test tests/javascript/documentation_governance.test.mjs tests/javascript/research_web_architecture.test.mjs` | exit 0；71 passed、0 failed |
| `node scripts/check_research_architecture.mjs --project . --base 4d6a4eff6` | exit 0；0 违规，包含未提交报告与 Task13 plan/receipt |
| `node .agents/project-constraints.mjs --project .` 加入从 `git diff --name-only -z 4d6a4eff6` 与 `git ls-files --others --exclude-standard -z` 合并的逐项 `--changed-file` | exit 0；104 个完整分支/当前工作区变更文件，0 违规 |
| `git diff --check` | exit 0 |
| `.venv/bin/python scripts/check_doc_sync.py --project . --base 4d6a4eff6` | 初次 exit 1：架构、治理、索引子项通过，但缺两份 Python owner 文档；主代理扩展范围并补齐后 exit 0，`/private/tmp/rwb-task14-doc-sync-final.log` |

首次使用系统 `python scripts/check_doc_sync.py` 在导入阶段因缺少 `pydantic` 失败；随后复用
工作树既有 `.venv`，没有安装依赖。补文档前 `.venv` 的真实 owner 失败输出保留在本轮工具回执；
补后完整通过，最终日志如上。
真实 Docker 构建/健康与持久化往返、GitHub macOS 干净安装、Docker 平台门和 Windows 实机证据
仍需独立取得；不得把文档检查或模拟测试记作这些门通过。
