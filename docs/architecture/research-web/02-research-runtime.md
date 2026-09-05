# 研究协议、执行状态与恢复

## 持久化本地启动边界

`rwb web start|status|stop|restart` 由 `app/research_web/service_manager.py` 管理专属 DSH 3081 与 Web 8088。默认 DSH 源码是 `~/.research-workbench/dsh-source/` 中经过固定提交构建的项目私有副本，避免修改或依赖用户其他 DSH 实例使用的工作树；必要时可用 `RESEARCH_DSH_SOURCE` 显式覆盖。管理器把 PID、进程组、启动命令指纹、最终 Node CLI/overlay 归属签名、项目路径和日志位置写入 `~/.research-workbench/`，先等待 `host.describe`，再启动 FastAPI 并检查 `/api/research/runtime`。重复启动是幂等操作；失败回滚只处理本次创建且归属签名匹配的进程，既有 3080 不在其所有权范围内。普通重启发现活动研究时拒绝执行，只有显式 `--force` 才允许中断。

研究协议本身仍是下述 DSH RPC、双事件通道和 Web SSE 投影。服务管理器只负责本机进程生命周期，不创建第二套研究运行时，也不改变会话、审批或恢复语义。

`app/research_web/operations.py` 只读取上述原生历史、当前投影和服务管理器状态，生成不含问题正文、审批参数或凭据的监控结果。它不参与提交、恢复或取消；历史事件未提供 usage 时返回未知，不以零替代。研究台通过 `workbench.py` 创建目标 DSH 会话后，后续提交仍完全遵守本页协议。

## 提交与流式

1. `POST /api/research/sessions` 创建真实 DSH 会话和产品归属目录。
2. `POST /api/research/sessions/{sid}/messages` 必须带 `Idempotency-Key`。BFF 先检查连接、运行中任务、附件归属、能力和交付要求，再调用原生 `session.prompt`。
3. HTTP 202 只表示受理。传输超时不是模型执行超时，且不能自动重发可能已受理的问题。
4. DSH `events.mux` 与 `events.host` 同时连接，事件按原生 seq 归一。Web 通过 `GET .../{sid}/events` 接收 `snapshot` 或 `runtime_error`，心跳不代表执行进度。
5. 刷新读取同一会话。必要时分页读取 `session.history`，结合 `session.list` 和 `subagent.list/history` 恢复真实状态。恢复不另建会话、不重提消息。

相同键与相同内容返回原受理收据；同键换内容拒绝。受理结果未知时先查历史中的本任务标记，不能以 UI 重试按钮无限重复执行。

## 运行状态（不是 Workflow 节点状态）

| 状态 | 来源或条件 | 用户可理解的含义 |
|---|---|---|
| `idle` | 原生日志未出现当前执行 | 可准备新问题 |
| `running` | 父回合或真实子 Agent 运行 | 研究仍在进行 |
| `awaiting_approval` | 当前归属内存在原生审批请求 | 等待用户允许或拒绝 |
| `completed` | 原生 `turn/end` completed 且无子任务运行 | 回合结束，文件另行检查 |
| `cancelled` | 原生 aborted | 已记录取消结果，不等于发送取消请求时即结束 |
| `failed` | 原生 error 或受理/执行错误 | 错误必须展示 |
| `interrupted` | interrupted 或历史运行但原生已不运行 | 无正常完成证据；交付仍pending时不能直接发送 |
| `blocked` | 原生 blocked | 原生执行阻塞 |
| `incomplete` | 原生 max-tokens | 本轮未完整执行 |
| `disconnected` | 任一下行通道断开 | 当前状态未知，不能伪报完成 |

`can_cancel` 根据父/子 Agent 的真实运行状态计算。工具失败保留活动级错误，并不必然将整轮改为 failed。子任务历史当前读取最近 100 条；若截断则明确标记，用量和耗时不冒充全量。

## 审批、问题与停止

原生审批通过 `POST .../{sid}/approvals/{aid}` 响应 approve/deny，校验待审批 ID 与会话归属。批准允许原工具继续；拒绝不得发起相应外部请求。原生问题经 `questions/{qid}` 回答，保留单选/多选语义。

停止调用父 `session.cancel` 与本会话真实子 Agent 的 `subagent.interrupt`。请求受理后仍等待原生状态确认。脚本取消需终止实际子进程，不能仅改变前端标签。

已受理且非运行、交付仍pending时，`can_recheck_stop` 提供「重新核对停止」。停止意图绑定当前任务与幂等键；真实受理后，完整历史精确当前标记、唯一空闲父任务、全部空闲子任务及可用父连接、双事件通道和无待处理审批/提问缺一不可。若仅缺原生终止事件，显示failed/结果未确认，独立交付verification_failed；不补造turn/end、不运行解析器。同键不重发，新键可继续，持久化后可冷恢复。证据不全保持等待，普通原生aborted仍正常显示cancelled。

DSH 不可用时明确报错，无 LangGraph、固定答案或第二 Supervisor 回退。已有资料和能力目录的只读可用性与运行能力分开。

## 代码与测试

关键来源：`client.py`、`service.py`、`projection.py`、`ui/core.mjs`。协议与投影回归位于 `tests/research_web/`，前端幂等、路由竞态、刷新、SSE 清理测试位于 `tests/javascript/research_web_ui.test.mjs`。真实模型验收另记，不以传输模拟代替。
