# 02 FinGPT、Claw 与研究工作区

## 职责

FinGPT 是单研究会话入口，Claw 是受控 Agent Team 入口；二者共享 Workspace、Research Run、Skill、Runtime Router 和审计，不形成两套研究系统。现有 LangGraph Research Run 保持权威执行状态，DSH 只作为可选 `RuntimeProvider` 侧车。

Workspace 承载项目隔离的会话与记忆；Run 承载可恢复、证据优先的执行；Note 是用户显式选择的 Claim 或段落的版本化置顶。模型全文、临时聊天和 Agent 黑板都不是事实。

## 数据归属

- `research_workspace`：项目范围、标题、状态和归档策略。
- `research_session` / `research_message`：临时或项目会话；Message 不重复保存 `workspace_id`，查询必须先由 Session 推导并验证 Workspace scope。
- 现有 `research_run` 及其 task/artifact/claim/quality_gate：Run 权威状态与不可变产物。
- `research_note`：`workspace_id`、revision、source_kind 与互斥来源；Claim Note 只保存 `claim_id` 并由 Claim 推导 Run，Paragraph Note 保存 `run_id + paragraph_ref`。
- `runtime_provider`：`langgraph` 或 `dsh` 的能力声明、健康和配置引用。
- `skill_definition`：持久化公共 `SkillManifest`，包含声明式 prompt/template、输入 schema、allowed tools 与版本。
- `agent_team` / `agent_schedule`：Supervisor、角色、预算、deadline、并发与日程。
- Shared Blackboard 使用已有 Agent View/冲突能力或 service 内受控投影；不允许 DSH 自建数据库。

## 禁止依赖

- DSH 不得直连数据库、持有数据库凭据、导入 ORM/repository，或向事实 API 写入。
- Skill 不得声明 Shell、任意文件写、任意 HTTP、浏览器自动化、券商/交易工具或未注册 MCP；Manifest 只能引用工具，不能用自身字段授权。
- Agent 不自由互聊；Worker 只向 Shared Blackboard 写类型化结果，Supervisor 负责分派与汇总。
- Claw 不允许退化成单 Agent 后仍标记成功；缺少 `agent_team` 能力必须阻断。
- Note 不保存未选择的完整 Run 文本，不跨 Workspace 注入记忆，不覆盖旧 revision。
- Run 状态不能只存在于 DSH session、进程内存、SSE 或前端。

## 公共 API 与类型

| API | 请求/响应要点 |
|---|---|
| `POST /api/research-workspaces` | 创建项目 Workspace，支持幂等键 |
| `POST /api/research-sessions` | 创建 `temporary|workspace` Session，可关联 Workspace |
| `GET|POST /api/research-sessions/{id}/messages` | 分页读取或追加消息；写入支持幂等键 |
| `POST /api/research-sessions/{id}/promote` | 原子升级临时 Session，冲突返回既有资源 |
| `POST /api/research-runs`、`/{id}/execute|resume` | 复用现有 Research Run 契约 |
| `GET /api/research-runs/{id}/events` | SSE 只发送状态、阶段、序号和事件 ID |
| `POST /api/research-workspaces/{id}/notes` | 仅接受 Claim/段落引用与用户编辑摘要 |
| `/api/runtime-providers` | Provider 声明、能力与健康状态 |
| `/api/research-skills` | Skill 声明、版本、校验与启停 |
| `/api/agent-teams` | Team 定义、预算和 Supervisor 配置 |
| `/api/agent-schedules` | Agent 日程 CRUD、触发、暂停和最近执行状态 |

公共类型包含 `ResearchWorkspace`、`ResearchSession`、`ResearchMessage`、`ResearchNote`、`RuntimeProvider`、`SkillManifest`、`AgentTeamDefinition`、`AgentSchedule`、`AgentBudget`、`BlackboardEntry` 与现有 `ResearchRun`/`ResearchClaim`。错误使用稳定代码：`blocked_runtime`、`tool_denied`、`budget_exhausted`、`deadline_exceeded`、`quality_gate_failed`。

## 主流程

1. 用户在 FinGPT 或 Claw 创建 Session；临时 Session 可在事务内升级为 Workspace Session。
2. Skill Compiler 从声明式 manifest 生成有界计划；Task 6 服务在编译/执行前必须把平台持有的已授权 tool ID registry 传给 `validate_tool_registry`。internal 引用必须同时属于封闭的 `SAFE_INTERNAL_TOOL_IDS` 并存在于 registry，MCP 引用必须存在于 registry；因此即使 registry 误配，也不能暴露 Bash、Shell、CMD、OS 或文件写入能力。附件读取和受控网页仍是固定能力，不由 Manifest 自授权。
3. Runtime Router 根据模式与能力选择 provider：FinGPT 首选可用 DSH，否则回退 LangGraph；Claw 要求 `agent_team`。
4. Claw 的 Supervisor 把任务写入 Shared Blackboard，Worker 读取分派、写类型化结果；步骤、并发、token/费用和 deadline 逐次检查。
5. DSH 的成功或失败结果必须经 FastAPI 回传 `run_id`、幂等键、provider result ID 和类型化终态；Run Service 校验映射后再持久化 task、artifact、claim 和 quality gate。重复回传返回既有终态，DSH 自身状态不成为权威；SSE 仅投影阶段变化。
6. completed Run 自动关联并归档到 Workspace；用户选择 Claim 或段落生成新 revision Note，并可置顶。服务必须通过 Session/Claim/Run 查询验证 Workspace 归属，不能信任消息或 Note 请求中的重复归属字段。

## 状态与失败

- Session：`temporary → promoted → archived`；升级必须原子且幂等。
- Run：`draft → planning → collecting → analyzing → validating → publishing → completed`；可进入 `blocked|failed|cancelled`，blocked 可补证 resume。
- FinGPT：DSH unavailable/timeout 时记录 `runtime_fallback_total` 并从 LangGraph 重新开始确定性阶段；不复用未知的 DSH 中间副作用。
- Claw：provider 缺 `agent_team`、预算不足或白名单不满足即 `blocked_runtime`；不得回退为 FinGPT。
- Tool/MCP：未注册、参数超 schema、超 deadline 或返回敏感字段时拒绝并审计；其它 Worker 可继续时由 Supervisor 局部降级。
- Agent Schedule：默认禁止并发重入；同一日程错过多次时只合并并执行最近一次，租约过期后才允许接管。
- 完成后自动归档失败不回滚 completed Run，但产生可重试 `archive_pending` 运维事件。

## 可观测性

日志字段包括 `workspace_id`、`session_id`、`run_id`、`provider_id`、`skill_key/version`、`team_id`、`agent_role`、`tool_key`、`budget_remaining`、`stage` 和 `status`。指标覆盖 provider 可用性/回退、Run 阶段耗时、blocked 原因、工具拒绝、MCP 超时、Blackboard 冲突、token/费用、自动归档和 Note revision。日志只记录 prompt/output hash 与安全摘要。

## 测试与验收

- Workspace 隔离测试确认 A 项目的 Note/消息不会进入 B 项目上下文。
- Runtime 测试确认 FinGPT DSH→LangGraph 回退；Claw 缺能力精确返回 `blocked_runtime`。
- Skill/Tool 测试确认 Manifest 无法自授权，且 registry 误配置时仍拒绝 Bash/Shell/CMD/OS/file-write/Python/browser 等非封闭 internal 引用、任意网络、未注册 MCP 和越界参数，同时允许平台注册的封闭安全 internal 与授权 MCP。
- Team 测试覆盖 Supervisor/Blackboard、最大步骤、并发、token/费用和 deadline。
- Schedule 测试覆盖禁止并发重入、租约接管和 missed runs 只合并最近一次。
- Run 回归覆盖现有 create/execute/resume/Claim/quality gate/export，并验证 completed 自动归档和 Note revision 不覆盖。
- SSE 测试确认事件有序、可重连、不包含密钥、完整 prompt、附件或大 artifact。
