# 专业 Agent 原生执行适配

本模块为现有 DSH 配置增加受控工具，不新增研究循环、模型提供方、数据库或独立调度器。
业务 DAG、版本、预算和准入事实由 Host 私有账本拥有；DSH 拥有子会话、inbox、模型请求、
运行历史及中断。普通研究保持原执行配置，只有 Host 明确识别的协作任务应用以下约束。

## 配置与受控接口

`app/research_web/runtime/research.cordis.yml` 的 `research-specialists` 使用本机生成的
`__SPECIALISTS_MODULE__` 与 `__NATIVE_LLM_MODULE__`。两者由 `launch_runtime.prepare`
解析到当前安装树和固定 DSH 的模块，不接受模型路径。安全启动与 Docker 继续沿原安装链。

- `specialist_plan({nodes, expected_version})`：提交或修订业务计划，Host 校验版本、
  图、角色、能力及修订额度。返回的 `cancel_attempt_ids` 只触发原生中断请求。
- `specialist_run({node_id, expected_version})`：先持久预留身份，再创建一个新的原生
  continuable 子会话。共享当前模型与工具授权，深度上限 1，输出上限 4096。
- `specialist_status({})`：读取账本，不能恢复模型执行。
- `specialist_cancel({attempt_id})`：登记取消并请求原生中断，不把回执当作终态。

模型参数不能提供 session、child、prompt、模型、工具覆盖或工具执行身份。
`trustedDirectory()` 从真实 Agent 及祖先会话确定账号工作区；`privateControl()`
核验现有私有控制文件权限与回环 origin。所有调用沿固定
`POST /api/research/internal/data/specialist-control`，使用现有
`X-Research-Data-Key`。该路径复用租户 callback 边界，不开放任意 URL。

协作控制回执使用固定 4 MiB 有界读取，与 Host 账本及提交前回执投影检查一致，支持
合法的完整计划修订历史；普通 DataHub 仍默认 1 MiB。超限明确拒绝，不截断或自动重发。
当前交付参与账本校验、对账、取消和质量投影时还须匹配 Host 回执的
`specialist_run_id`；完成后切入普通交付不会让普通取消改写历史协作。只改界面模式不能
解除仍绑定交付的协作质量门，未解决协作仍禁止普通发送。

## 提交与真实终态

Host `reserve` 在原生调用前写入 attempt、child UUID 和冻结 prompt。只有 Host 返回的
parent 与当前真实 DSH Agent 一致时才能启动。重复的 reserve 回执绝不再次启动子会话。
原生启动前还必须持久登记独立 `dispatch` 意图；该回执缺失或重放时不调用 DSH。
因此没有 dispatch 记录的预留与可能已经进入原生启动的尝试可以在恢复时分别核对，
不能仅凭 child 暂未出现就断定请求未发送。
受理后登记 message ID；响应丢失或调用异常记为 `submission_unknown`，不自动重发。

模块仅消费已预留 child 对应的原生 `subagent/start`／`subagent/end`，匹配真实 run ID。
模型声称完成、其他 child 或不匹配的 run 不能登记成果。原生 `completed` 的最终正文
必须是仅含 `conclusion`、`evidence_ids`、`as_of_date`、`limitations`、`artifact_ids`
的 JSON 对象；解析失败记 `invalid_output`，引用有效性仍由 Host 独立检查。
`aborted`、`error`、`max-tokens`、`refusal` 保留原生状态。取消未确认不释放身份或并发。

原生 continuation 自行向父 Agent 发布带来源的结束通知并唤醒其执行，不建立 Host
轮询调度器。进程重启丢失内存中的观察映射后，Host 只从原生历史对账，不凭内存缺失重发。
运行事件回调写账本失败记录稳定日志，并保留待对账状态；回调失败不改变 DSH 的真实终态。

## 预算与取消边界

`specialist_run` 与原生 `subagent` 共用原守卫每回合四个子 Agent 的预算。
协作模式禁止原始 `subagent`、`rwb_plugin_agent` 及父 Agent 直接 `send_message` 唤醒旧子会话，
防止绕过图和新尝试要求；子 Agent 仍可通过原生消息向父 Agent 返回成果。

每次原生 `agent/request` 先核对 Host 协作准入，再在 SDK 冻结请求前将输出上限限制为
4096，并核对实际原生 provider/model 等于 Host 冻结路由；未知或不匹配立即拒绝。
`llm/stream` 验证 SDK 原生标记、真实 owner、session 和 signal，持久预留每个
实际请求后才进入模型提供方；重复请求不再次执行。输入只支持有界文本，预留量按
序列化 UTF-8 字节、消息／工具数量的固定开销和输出上限保守计数。
这是准入估计单位，**不是通用 tokenizer 或人民币费用硬上限**；未识别的多模态输入拒绝。
只有正常结束且收到真实 input/output usage 的请求才用实际用量结算；缺失、失败、取消
或结算回执不明时保留未结算预留，不视为零消耗。
每个请求另绑定原生 turn／step，重启后可由 Host 用真实 assistant/message 用量记录
对账；随机请求 ID 自身不能证明任何历史计费，也不能代替这层绑定。
协作请求的 `agent/request-error` 不委托给提供方自动重试策略；失败回合结束并留待明确
处理。普通研究仍沿原重试策略，不修改全局 provider 配置。

离线代表性测算：仅加载 28 个现有研究／DataHub／协作适配器工具声明及现有研究 persona，
加入一条半导体问题，序列化输入为 38,501 字节，按当前规则预留 48,613 单位。
这还未包含原生 Skill／Todo／subagent 工具、Host 研究合同和真实会话历史，因此不能用
40,000 默认额度宣称完整研究可执行，更不能从此数值推算费用。实际首次验收应展示完整
冻结请求的预留需求，由用户选择额度；不自动提高或降低原预算，不打印或留存请求内容。

模型流与工具执行使用 Host 持久截止点的剩余时限。超时对确切原生 owner 发出取消，
待确认的 provider 调用保持未知；不伪造已停止或自动重放。日志使用项目运行时 logger，
只记录稳定事件、工具 ID 和终态，不记录 prompt、原始回复、控制凭据或预算请求正文。

## 离线验证与限制

`node --test tests/javascript/research_web_specialist_runtime.test.mjs` 覆盖持久预留先于
调用、重复准入、受理回执丢失、原生事件绑定、输出合同、取消延迟、原守卫配额、
每个模型请求准入／用量未知、普通研究兼容及在途流超时。邻近原生 guard 与 public-data
测试继续执行。所有场景用可控执行器，不调用模型或商业来源。

这些测试不能证明真实提供方的取消、实际计费、DSH 重启或 Native／Docker 产品行为。
这些层级须在费用确认后的隔离真实验收分别取证，未执行时保持 `NOT_RUN`。
