# Research Workbench 合并平台 Task 6：FinGPT / Claw 研究运行时

## 范围

本任务实现 Workspace、Session、Message、Research Note、Runtime Provider、声明式 Skill、Supervisor Agent Team、Agent Schedule、Research Run 状态事件与自动归档。未修改市场首页、Research Pack、资产观察、前端视觉或桌面打包。

## 已实现

- Workspace 按 `project_id` 隔离；Session/Message 使用数据库唯一键幂等，临时 Session 以行锁原子升级。
- Note 只接受 Claim 或段落引用，先从持久化 Claim/Run/Session 推导 Workspace 归属；同一 `note_key` 只新增 revision，不覆盖历史。
- completed Run 自动归档关联 Session；归档失败不回滚 Run，而写入持久 `research_run.archive_pending` 事件。
- FinGPT 选择健康 DSH，仅在明确 unavailable/timeout 时从 LangGraph 重新执行；类型化 failed/blocked、关联、安全、tool、预算和 deadline 错误保持语义且不回退。Claw 缺 `agent_team` 或运行失败保留精确 `error_code`，不降级成单 Agent。
- Skill 在保存/编译边界使用平台持有的授权 registry 调用 `validate_tool_registry`；新增可执行 `AuthorizedResearchToolDispatcher`，internal 同时受 `SAFE_INTERNAL_TOOL_IDS`、Manifest 与 callable registry 约束，MCP 必须预注册 callable/config，attachment 只允许声明 ref，controlled-web 只允许预注册 policy 且拒绝任意 URL。工具输出安全校验后回注模型再生成终态；声明但未注册的工具直接阻断。
- Supervisor 是真实执行参与者：每步读取类型化 Shared Blackboard 和剩余预算，依据 Worker 结果动态停止、追加或调整 assignment；Worker 接收分派时的只读 blackboard snapshot，结果写回后供下一轮决策。Supervisor/Worker 都逐步检查 max steps、concurrency、token、cost 和 deadline。
- Agent Schedule 使用 `scheduled_job` 持久租约、single-flight、过期接管和 latest-only coalescing；执行期间的新触发在完成后生成一个 follow-up。
- Agent Schedule 的通用 runtime handler 和手工 `/work` 均改走 `RuntimeProviderService` 的 Claw 路由，再进入动态 Supervisor/Shared Blackboard；不再调用静态 Team 遍历路径。`domain_event` 以 `job_id` 持久化带 expiry 的 reservation/takeover/terminal ledger：活跃 reservation 禁止并发重复，崩溃 reservation 过期且 scheduler fencing 接管后可恢复，complete ack 丢失后的新 attempt 直接重放安全终态，不重复 Provider、模型或工具副作用。手工 `/work` 在独立 Session heartbeat 续租；heartbeat 失败会拒绝旧 attempt complete。
- Research Run 创建、执行、恢复和日程触发接受幂等键；SSE 从 `domain_event` 按 sequence 重放并支持 `Last-Event-ID`，不投影 prompt、secret、附件或 artifact 正文。
- Session→Run 由 `ResearchOrchestrationService` 在同一事务/savepoint 内创建并唯一绑定；所有已绑定 Session、Message、Run、Note 查询都显式验证 project/workspace scope，Run 不能二次绑定到不同 Workspace。
- `ResearchRunService` 已接入 Runtime、Skill 和 Agent Team 真实执行链：FinGPT 的 DSH 失败确定性回退 LangGraph；Claw 缺 Team/能力/Worker 时持久化 `blocked_runtime`；DSH 使用 `provider_result_id` 和类型化终态幂等回传。
- Tool/Agent 调用前预留预算并执行 registry、完整受控 JSON Schema 关键字与敏感输出校验；同步生产 adapter 把 token/cost/deadline 传给底层 sandbox/HTTP/Model Gateway，服务不创建超时后仍继续产生副作用的线程 future。
- Model Gateway 的 `Error`、空响应或非 JSON 不再被当成 completed；Skill/Agent/Supervisor 均使用网关实报 token，并按显式 usage cost 或受控每千 token 估价器核销，正 token 使用不会伪报零费用。
- DSH 生产 adapter 仅接受环境引用的 localhost HTTP endpoint；请求和回传共同携带 `request_id/run_id/request_hash/provider_result_id`，回传会驱动对应 Run 终态及产物落库，不再生成孤立事件。Claw Blackboard 的类型化 Worker 结果合并到 Claim、Artifact 和报告。
- Scheduler 增加通用 `register_materializer/register_handler/enqueue/claim_due/run_due` 与唯一 `DurableSchedulerRuntime`，支持领域周期物化、cron 到期物化、handler 执行期间跨 Session heartbeat、attempt fencing token 和 lease 校验完成任务；Agent Schedule 使用真实生产 Worker adapter，Market/Alert 通过同一 singleton 注册。
- Run Graph 失败先持久化本次 attempt 的失败事件；completed 与自动归档事务语义分离，`research_run.archive_pending` outbox 使用 savepoint 从 PostgreSQL aborted transaction 恢复并可独立重试。
- Run 的 planning/collecting/analyzing/validating/publishing 状态逐阶段提交；慢 DSH 纵切测试已用第二数据库事务证明 POST 返回前可读取前三个运行中阶段。
- `research_session.run_id` 在 ORM 与迁移 017 增加可空唯一约束；服务在绑定前也显式拒绝同一 Run 的第二 Session，数据库约束负责并发兜底。
- 生产 Research Run DI 现注册真实 `internal:asset_snapshot` handler，并只装载启动期预注册且同时在平台授权列表中的 MCP callable；声明存在但无 callable 的 MCP 在模型调用前 fail-closed。
- Skill 多轮执行在每次外部模型调用和每个工具调用前重新检查剩余 token/费用预算；首轮耗尽后不会再调用工具或下一轮模型。
- 研究工作台每次提交创建新 Session，终态或失败后清空本地 Session；Workspace 复用，历史请求固定携带 project/workspace scope 并可打开对应 Run。
- Run 执行输入从唯一归属反查 Workspace，只注入当前 Workspace 最新 20 条 Note、绑定 Session 最新 50 条消息，且内容合计不超过 12,000 字符；其它 Workspace 记忆不可见，超限会确定性截断并显式标记。

## 已执行证据

RED：

- 新增五组测试首次执行在收集阶段因目标 Repository、Service 和 route 尚不存在而失败。
- 新增 SSE/自动归档测试首次执行为 2 failed、1 passed，失败分别为事件 route 404 和 `ResearchRunService` 尚无 Workspace 集成。
- 新增执行中 missed-run 测试首次执行失败：完成后 pending run 为 0；实现 follow-up 后转绿。
- 新增 Worker 返回后 deadline 复检测试首次执行失败：未抛 `deadline_exceeded`；补充逐步复检后转绿。
- 复审修复第一组测试首次收集失败：缺少 `ProviderExecutionResult`；补齐类型化 DSH 终态契约与持久化后转绿。
- Session→Run API 纵切测试首次收集失败：缺少 `ResearchOrchestrationService`；补齐原子创建/绑定服务与路由后转绿。
- DSH 回传 API 首次返回 404；补齐 `/{provider_id}/results` 类型化幂等入口后转绿。
- 通用调度 handler 测试首次失败：`SchedulerCoordinator` 无 `register_handler`；补齐 handler registry、generic enqueue/claim/run 后转绿。
- 单一 Runtime 领域物化扩展测试首次失败：`DurableSchedulerRuntime` 无 `register_materializer`；补齐幂等注册、claim 前调用和失败回滚/跳过 claim 后转绿。
- 动态租约攻击测试首次失败：heartbeat 已失败并把测试 clock 推过 lease 后，旧 worker 仍成功 complete；将固定时点仅用于 materialize/claim、renew/complete 改读动态 clock 后，旧 attempt 被 fencing 拒绝且新 worker 可接管。
- 复审攻击测试依次出现并保留 RED：Session execute 将 `RuntimeBlockedError` 转成 `HTTPException` 导致终态回滚；生产 DSH 永远回退；callback 不驱动 Run；Claw Blackboard 不进入产物；Skill schema/deadline/预算未传递；history 未按 Workspace 过滤；cron 未物化；handler 无 heartbeat；archive 数据库异常使事务 aborted；运行中 SSE 阶段不可见。上述测试均在对应实现后转绿。
- 最终独立复审新增测试首次收集即 RED：缺少 `AuthorizedResearchToolDispatcher` 与 `RuntimeFailedError`。实现后首轮为 1 failed/37 passed，失败是 attachment 越界错误信息不符合稳定契约；修正后转绿。随后补充类型化 failed/blocked 不回退、网关 Error/非 JSON、实际 token/cost、MCP 真实调用与结果回注、任意 URL/Shell/attachment 拒绝、动态 Supervisor 第二步、Worker blackboard snapshot 和 Workspace 上下文隔离/截断测试。
- 最终 API 语义攻击测试首次为 1 failed：direct 与 Session execute 虽已提交 failed Run，但响应把 provider 的 `provider_crashed` 覆盖为通用错误码。两个 route 增加 `RuntimeFailedError` 专用 JSON 终态响应后转绿，blocked/failed 均保留稳定原始 code。
- 最后四项复审的 RED 证据：Skill 预算攻击测试首次失败，首轮已耗尽仍调用第二轮模型；Run 第二 Session 绑定与迁移测试为 3 failed；生产工具接线测试首次缺少可观测授权 registry；Agent Schedule 测试首次因 `AgentScheduleExecutionService` 不存在而收集失败，随后 startup 与 API 依赖测试为 2 failed。实现预算前置 guard、唯一约束、真实工具 registry、Runtime/Supervisor 调度服务和持久执行账本后均转绿。
- Agent Schedule 租约复核新增三项 RED：长执行与 heartbeat-failure 测试因执行服务没有独立 heartbeat factory 均抛构造参数错误，reservation crash 恢复测试因 repository 不支持 expiry 而失败。实现独立 Session renew、heartbeat failure fencing、reservation expiry/takeover 后，长执行跨越初始一秒租约仍成功、失败 heartbeat 的旧 worker 不能 complete 且新 attempt 可接管、reservation-only crash 可恢复；另保留 ACK 丢失重放零重复与活跃 reservation 禁止并发测试。
- 最终 terminal fencing 攻击测试首次 `2 failed`：attempt2 takeover 后旧 attempt 的 terminal API 尚无 writer token，且同 attempt 对过期 reservation 再 reserve 暴露数据库 `IntegrityError`。终态写入现锁定 job 并同时校验 `writer_attempt == scheduled_job.attempt == latest reservation_attempt`；takeover 强制 attempt 严格递增，同 attempt 返回稳定 `ValueError`。攻击测试确认旧 writer 不生成任何 terminal，ACK 丢失安全重放不受影响。

GREEN：

```text
python -m pytest \
  tests/unit/test_agent_team_service.py tests/unit/test_runtime_provider_service.py \
  tests/unit/test_scheduler_coordinator.py tests/unit/test_research_workspace_service.py \
  tests/unit/test_research_workspace_api.py tests/unit/test_research_run_service.py \
  tests/unit/test_research_runs_api.py tests/unit/test_research_workbench_frontend.py \
  tests/unit/test_merged_platform_contracts.py \
  tests/unit/test_merged_platform_frontend_contract.py \
  tests/unit/test_merged_platform_migration.py -q
172 passed, 5 warnings

python -m pytest \
  tests/unit/test_runtime_provider_service.py tests/unit/test_agent_team_service.py \
  tests/unit/test_research_workspace_service.py tests/unit/test_research_workspace_api.py \
  tests/unit/test_agent_schedule_runtime.py tests/unit/test_scheduler_coordinator.py \
  tests/unit/test_research_run_service.py tests/unit/test_merged_platform_migration.py -q
96 passed, 5 warnings

python -m pytest \
  tests/unit/test_agent_schedule_runtime.py tests/unit/test_runtime_provider_service.py \
  tests/unit/test_agent_team_service.py tests/unit/test_scheduler_coordinator.py -q
54 passed, 4 warnings
```

最终验证使用已存在的兼容项目虚拟环境，未安装新依赖。warnings 为既有 FastAPI `on_event` 弃用提示和攻击性 savepoint 测试有意制造主键冲突时的 SQLAlchemy identity warning。

聚焦 owned Python 文件的 `ruff check`、`black --check`、`isort --check-only`、`py_compile` 均通过，`research-workbench.js` 的 `node --check` 通过。Mypy 以仓库固定 Python 3.11 配置运行时被已安装 NumPy stub 的 PEP 695 `type` 语句阻断；显式 `--python-version 3.12` 后可进入项目检查，但暴露 71 项既有/SQLAlchemy legacy typing 与 Task 6 注解债务，因此不记录为通过。

## 未验证与发布门禁

- 已在本地 PostgreSQL 18.3 + pgvector 0.8.5 从空库执行 `001 → 018`，并验证通用 `SKIP LOCKED`、租约接管/fencing、Workspace 幂等隔离和 Run→Session 唯一约束；尚未对 Agent reservation 崩溃窗口做长时多进程 soak。
- 尚未连接真实 DSH 产品侧车或真实白名单 MCP；已通过真实 localhost HTTP server 验证生产 DSH adapter、请求关联、回调落库、回退和运行中阶段可见性。
- 本任务不改桌面端；未运行原生 Windows/macOS 桌面 CI，也未执行真实 Windows 安装级冒烟。
- SSE 长连接已验证有限重放响应，尚未进行长时断线/并发客户端负载测试。
- 未增加迁移 019；Run 唯一归属约束随迁移 017 additive 增补，空库完整迁移链与真实 PostgreSQL 约束查询均已通过。
