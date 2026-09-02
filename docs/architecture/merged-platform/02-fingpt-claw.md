# 02 FinGPT、Claw 与研究工作区

## 职责

FinGPT 是单研究会话入口，Claw 是受控 Agent Team 入口；二者共享 Workspace、Research Run、Skill、Runtime Router 和审计，不形成两套研究系统。现有 LangGraph Research Run 保持权威执行状态，DSH 只作为可选 `RuntimeProvider` 侧车。

Workspace 承载项目隔离的会话与记忆；Run 承载可恢复、证据优先的执行；Note 是用户显式选择的 Claim 或段落的版本化置顶。模型全文、临时聊天和 Agent 黑板都不是事实。

## 数据归属

- `research_workspace`：项目范围、标题、状态和归档策略。
- `research_session` / `research_message`：临时或项目会话；Session mode/scope 由数据库 CHECK 强制一致，`research_session.run_id` 使用可空唯一约束保证一个 Run 只能绑定一个 Session，Message 的 content/content_ref 恰一非空且不重复保存 `workspace_id`，查询必须先由 Session 推导并验证 Workspace scope。
- 现有 `research_run` 及其 task/artifact/claim/quality_gate：Run 权威状态与不可变产物。
- `research_note`：`workspace_id`、revision、source_kind 与互斥来源；Claim Note 只保存 `claim_id` 并由 Claim 推导 Run，Paragraph Note 保存 `run_id + paragraph_ref`。
- `runtime_provider`：`langgraph` 或 `dsh` 的能力声明、健康和配置引用。
- `skill_definition`：持久化公共 `SkillManifest`，包含声明式 prompt/template、输入 schema、allowed tools 与版本；契约 `extra=forbid`，已移除的自授权字段不能被静默吞掉。
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
| `POST /api/research-sessions/{id}/runs` | 在一个事务内创建 Run 并绑定 Session/Workspace；请求显式携带 `project_id`、`workspace_id` 和 `run` |
| `POST /api/research-sessions/{id}/runs/{run_id}/execute` | 在显式项目/Workspace scope 内执行绑定 Run；禁止跨项目或跨 Workspace 执行 |
| `POST /api/research-runs`、`/{id}/execute|resume` | 复用现有 Research Run 契约 |
| `GET /api/research-runs/{id}/events` | SSE 只发送状态、阶段、序号和事件 ID |
| `POST /api/research-workspaces/{id}/notes` | 仅接受 Claim/段落引用与用户编辑摘要 |
| `/api/runtime-providers` | Provider 声明、能力与健康状态；`/{provider_id}/results` 接收带 `provider_result_id` 的类型化幂等终态回传 |
| `/api/research-skills` | Skill 声明、版本、校验与启停 |
| `/api/agent-teams` | Team 定义、预算和 Supervisor 配置 |
| `/api/agent-schedules` | Agent 日程 CRUD、触发、暂停和最近执行状态 |

公共类型包含 `ResearchWorkspace`、`ResearchSession`、`ResearchMessage`、`ResearchNote`、`RuntimeProvider`、`SkillManifest`、`AgentTeamDefinition`、`AgentSchedule`、`AgentBudget`、`BlackboardEntry` 与现有 `ResearchRun`/`ResearchClaim`。错误使用稳定代码：`blocked_runtime`、`tool_denied`、`budget_exhausted`、`deadline_exceeded`、`quality_gate_failed`。

Workspace/Session 调用固定使用以下请求与 scope 规则：

- Workspace 列表必须提供 `project_id`；Workspace 详情和 Note 使用 `X-Project-ID`。
- Workspace Session 的创建体为 `mode/workspace_id/project_id/run_id`，其中 `workspace_id` 出现时 `project_id` 必填；临时 Session 不要求项目 scope。
- Session 提升请求体为 `workspace_id + project_id`。已绑定 Workspace 的 Session/Message 读写必须同时提供 `X-Project-ID` 与 `X-Workspace-ID`。
- Session Run 创建请求体为 `{project_id, workspace_id, run}`；`run` 在原有模板字段之外支持 `mode: fingpt|claw`、`agent_team_id` 与唯一的 `skill_keys`。
- Run 详情、执行、恢复和事件在 Run 已归属 Workspace 时必须同时提供 `X-Project-ID` 与 `X-Workspace-ID`。创建、执行、恢复、消息写入、Session Run 创建与日程触发都使用 `Idempotency-Key`；服务把操作、目标和请求哈希一起持久化，跨操作或跨资源复用同一键返回冲突。

## 主流程

1. 用户在 FinGPT 或 Claw 创建 Session；临时 Session 可在事务内升级为 Workspace Session。
2. Skill Compiler 从声明式 manifest 生成有界计划；Task 6 服务在编译/执行前必须把平台持有的已授权 tool ID registry 传给 `validate_tool_registry`。internal 引用必须同时属于封闭的 `SAFE_INTERNAL_TOOL_IDS`、Manifest 声明和可执行 registry，MCP 必须预注册 callable/config；附件只能通过 Manifest attachment ref resolver，受控网页只能通过预注册 policy 且参数不得携带任意 URL。模型只能返回受 schema 约束的 `tool_requests`，dispatcher 逐个授权、执行并把安全结果回注模型后再次生成/校验。未注册能力必须阻断，不能静默忽略，也不能暴露 Bash、Shell、CMD、OS 或文件写入能力。
3. Runtime Router 根据模式与能力选择 provider：FinGPT 首选可用 DSH；只有明确的 unavailable 或 timeout 才确定性回退 LangGraph。Provider 类型化 `failed`、`blocked`，关联、安全、tool、预算和 deadline 错误必须保持原语义并持久化对应 Run 终态，不能伪装成 unavailable。Claw 要求可用 provider 声明 `agent_team` 能力、请求绑定真实 Team 并存在 Worker，任一条件不满足都持久化原始 `error_code`，不得语义回退。
4. Claw 的 Supervisor 每步读取当前 Shared Blackboard、剩余预算和初始候选计划，动态决定停止、追加或调整下一批 assignment；Worker 只读取分派时的只读 blackboard snapshot，并把类型化结果写回。每次 Supervisor、Agent、Tool 调用前预留 steps、并发、token、费用和硬 deadline 预算，调用后用网关实报 token 与显式价格或受控估价器核销；正 token 使用不得伪报零费用。生产 Worker/Skill adapter 是同步 sandbox 契约，必须把剩余 deadline 与预算传给能够阻止超时调用及副作用的底层客户端；服务不创建会在超时响应后继续运行的后台 future。网关 `Error`、空响应或非 JSON 都是类型化失败，结果须再次经过 JSON Schema 与敏感输出校验。
5. DSH 的成功或失败结果必须经 FastAPI 回传 `request_id`、`run_id`、`request_hash`、provider result ID 和类型化终态；Run Service 与调用前持久化的映射逐项校验后，再持久化 task、artifact、claim 和 quality gate。重复回传返回既有终态，DSH 自身状态不成为权威；SSE 仅投影阶段变化。
6. completed Run 自动关联并归档到 Workspace；用户选择 Claim 或段落生成新 revision Note，并可置顶。服务必须通过 Session/Claim/Run 查询验证 Workspace 归属，不能信任消息或 Note 请求中的重复归属字段。
7. Run 执行输入只注入其唯一归属 Workspace 的最新置顶 Note 和绑定 Session 消息；查询必须同时按 project/workspace/session/run 过滤，并对条数和总字符数设硬上限。其它 Workspace 的 Note/消息不可见，超限内容确定性截断并记录 `truncated`，避免记忆绕过 token 预算。

## 状态与失败

- Session：`temporary → promoted → archived`；升级必须原子且幂等。
- Run：`draft → planning → collecting → analyzing → validating → publishing → completed`；可进入 `blocked|failed|cancelled`，blocked 可补证 resume。
- FinGPT：DSH unavailable/timeout 时记录 `runtime_fallback_total` 并从 LangGraph 重新开始确定性阶段；不复用未知的 DSH 中间副作用。DSH 类型化 failed/blocked、关联错误、安全边界和预算错误不触发 fallback。
- Claw：provider 缺 `agent_team`、预算不足或白名单不满足即 blocked，并保留精确 `error_code`；不得回退为 FinGPT。
- Tool/MCP：未注册、参数超 schema、超 deadline 或返回敏感字段时拒绝并审计；其它 Worker 可继续时由 Supervisor 局部降级。
- Agent Schedule：默认禁止并发重入；同一日程错过多次时按 `max(scheduled_for)` 只合并并执行最近一次，租约过期后才允许接管；`attempt` 同时作为 fencing token，续租与完成必须校验 worker、token 和未过期租约。生产 handler 与手工 `/work` 都必须进入 `RuntimeProviderService` 的 Claw 路由，再由动态 Supervisor/Shared Blackboard 执行，禁止调用静态 Team 遍历捷径。
- Agent Schedule 副作用账本：在首次 Provider/模型/工具调用前，以 `job_id` 写入带 `reservation_expires_at` 的 `agent_schedule.execution_reserved`；终态在 scheduler complete ack 前以同一 aggregate 写入 `agent_schedule.execution_completed|blocked|failed`，包含稳定 `execution_id`、首次/完成 attempt 与安全的 Team 结果。terminal writer 必须同时匹配当前 `scheduled_job.attempt` 和最新 reservation 的 `reservation_attempt`；旧 attempt 在 takeover 后不能写 completed/failed。complete ack 丢失后的新 attempt 读取既有终态，不重复调用 Provider、模型或工具。只有 reservation 而没有终态表示进程崩溃：活跃 reservation 禁止第二执行者，过期并且 scheduler lease 已由更大的 fencing attempt 接管后，写入 takeover 事件并恢复执行；同 attempt 不能续写 takeover。本地 Team 的 reservation 至少覆盖 Team hard deadline，DSH 使用稳定 execution/request ID 保持 provider 幂等。
- 手工 `/work` 与后台 worker 具有相同的租约语义：长执行期间由独立数据库 Session 周期 renew，业务 Session 不跨线程共享；heartbeat 失败会阻止旧 worker complete，租约过期后由新 attempt 接管。成功 terminal 先于 complete ack 持久化，因此旧 worker 已产生的安全结果可被接管者重放，而不会再次调用模型或工具。
- 通用持久调度通过 `register_materializer(name, materializer)`、`register_handler(job_type, handler)`、`enqueue(...)`、`claim_due(...)` 和 `run_due(...)` 消费已注册类型。`DurableSchedulerRuntime` 是进程内唯一后台 worker：各模块在启动前向 `get_default_scheduler_runtime()` 注册 materializer 与 handler，再由 API startup 调用一次 `start()`，shutdown 调用 `stop()`。materializer 接收本轮 UTC `datetime`，必须幂等并在 claim 前把到期领域计划物化成 `scheduled_job`；同名同一 callable 重复注册幂等，同名不同 callable 拒绝。任一 materializer 异常会记录日志、回滚 runtime 本轮事务并跳过 claim。handler 只接收 `ScheduledJob`，业务写入必须在 handler 内使用独立 Session 明确 commit/rollback/close；协调器自己的 claim/renew/complete 使用独立事务，并在 handler 执行期间由另一 Session heartbeat 续租。物化和 claim 使用本轮固定观察时点，但 renew/complete 必须读取可前进的动态 clock；heartbeat 失败且真实租约过期时，旧 worker 的 complete 会被 fencing 拒绝，任务随后允许新 worker 接管。`agent_schedule` 的到期 cron 由 runtime 内建物化，其它类型（例如 `market_home.close_snapshot`、`asset_alert.evaluate`）通过注册 materializer 复用同一 registry，不得各起一套 scheduler。
- Graph/runtime 失败先持久化本次 attempt 的 `failed|blocked` 终态和有序事件，再向 API 返回错误。完成后的自动归档使用独立 `research_run.archive_pending` outbox；归档失败不回滚 completed Run，成功后标记 outbox 已发布，失败项可单独重试。

## 可观测性

日志字段包括 `workspace_id`、`session_id`、`run_id`、`provider_id`、`skill_key/version`、`team_id`、`agent_role`、`tool_key`、`budget_remaining`、`stage` 和 `status`。指标覆盖 provider 可用性/回退、Run 阶段耗时、blocked 原因、工具拒绝、MCP 超时、Blackboard 冲突、token/费用、自动归档和 Note revision。日志只记录 prompt/output hash 与安全摘要。

## 测试与验收

- Workspace 隔离测试确认 A 项目的 Note/消息不会进入 B 项目上下文。
- Runtime 测试确认只有 FinGPT DSH unavailable/timeout 才回退；类型化 failed/blocked 不回退且 Run 终态和原始错误码准确，Claw 缺能力精确 blocked。
- Skill/Tool 测试确认 Manifest 无法自授权，且 registry 误配置时仍拒绝 Bash/Shell/CMD/OS/file-write/Python/browser 等非封闭 internal 引用、任意 URL、越界 attachment ref、未注册 MCP 和越界参数；已注册 MCP 必须被实际调用，其输出回注后再生成和验证终态。
- Team 测试覆盖 Supervisor 实际调用、依据 Worker 结果动态追加第二步、Worker 的只读 Blackboard snapshot、最大步骤、并发、真实 token/费用和 deadline。
- Context 测试确认运行输入只包含自身 Workspace 最新 Note 与绑定 Session 消息，并在固定条数/字符预算内截断。
- Schedule 测试覆盖禁止并发重入、租约接管和 missed runs 只合并最近一次。
- Run 回归覆盖现有 create/execute/resume/Claim/quality gate/export，并验证 completed 自动归档和 Note revision 不覆盖。
- SSE 测试确认事件有序、可重连、不包含密钥、完整 prompt、附件或大 artifact。

## V1 实施导航

研究运行时纵切现由以下边界实现：

- `ResearchWorkspaceRepository` 独占 Workspace、Session、Message、Note、Provider、Skill、Team、Schedule、`scheduled_job` 租约与研究状态事件的持久化访问。常规命令的事务提交/回滚由 FastAPI `get_db` 或调用方负责；Research Run 的可观测进度 checkpoint、终态和归档 outbox 由运行服务在明确的事务边界内提交，保证长时执行期间其他事务可见且归档失败不回滚 completed 终态。
- `ResearchWorkspaceService` 执行 Session 原子升级、Message 幂等、Claim/Run Workspace 归属校验、Artifact 段落引用验证、Note 行锁递增 revision、完成 Run 归档和 `archive_pending` 补偿事件；同一 Run 二次绑定不同 Workspace 会被拒绝。
- `ResearchOrchestrationService` 把 Session 校验、Run 创建和唯一绑定放在同一事务/savepoint 中，并在执行前再次验证项目、Workspace、Session 与 Run 的完整归属链。
- `ResearchRunService` 是真实执行链入口：以 Run 行锁/CAS 防止并发执行，调用 `RuntimeProviderService`、Skill 执行边界与 `AgentTeamService`，再持久化 provider result、终态事件和归档 outbox。
- `RuntimeProviderService` 对 FinGPT 实施 DSH 优先，但只对明确 unavailable/timeout 做 LangGraph 确定性回退；类型化 failed/blocked 保持语义，对 Claw 强制 `agent_team` 并保留原始错误码。生产 DI 提供仅允许 localhost HTTP 的 DSH adapter、严格 JSON 的 Model Gateway Skill/Agent/Supervisor adapter、显式费用估价器与 `AuthorizedResearchToolDispatcher`。每次编译/执行 Skill 都重新调用 registry 校验，工具只有同时存在于 Manifest 与可执行 registry 才能调用；DSH 回传由 `provider_id + provider_result_id + request_id + run_id + request_hash` 幂等和关联约束。
- `AgentTeamService` 只允许 Supervisor 依据当前 Blackboard 动态下发、追加或停止任务，Worker 接收分派时的只读 snapshot，并通过 `BlackboardEntry` 写类型化 assignment/result；步骤、并发、token、费用和 deadline 在调用前预留、调用后按真实 usage 核销。
- `AgentScheduleExecutionService` 是 `agent_schedule` 的唯一生产执行入口：先用 `RuntimeProviderService` 路由 DSH 或内建 Agent Team provider，再把 provider 计划交给同一动态 Supervisor/Blackboard 执行，并用 `domain_event` 结果账本吸收 at-least-once 投递重放。API startup 在默认 `DurableSchedulerRuntime` 启动前显式注册该 handler；handler 使用独立数据库 Session。
- `ResearchWorkspaceService.build_run_runtime_context()` 从 Run 的唯一归属反查 project/workspace/session，只注入最新 20 条 Note、50 条消息和不超过 12,000 个内容字符；超限确定性截断并显式标记。
- `SchedulerCoordinator` 以 `scheduled_job` 的数据库锁、lease owner/expiry 和 attempt/fencing token 实现 single-flight、heartbeat 续租、过期接管及 missed run latest-only；`materialize_due_schedules()` 以 UTC cron 计算下一次执行，手工触发幂等映射由 `domain_event` 持久化。`DurableSchedulerRuntime.register_handler/start/stop/tick` 是 Agent、Market 与 Alert 的统一挂载面。
- `/api/research-runs/{run_id}/events` 从 `domain_event` 按 sequence 投影 SSE，并支持 `Last-Event-ID`；事件负载固定为 `event_id/sequence/status/stage`。planning、collecting、analyzing、validating、publishing 均在独立 checkpoint 提交，因此长时 Provider 调用期间另一事务可以读取已经发生的阶段。

首版仍不把 DSH 作为事实源，也不允许它直连数据库。真实 DSH 进程健康检查、远程 Runtime、生产 PostgreSQL 租约并发压测与桌面打包属于后续环境级验证，不能由 SQLite 单元测试替代。
