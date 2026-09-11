# 研究协议、执行状态与恢复

Phase 2A 的 Registry 读取仍不进入研究执行链。Phase 2B 只把用户已安装、探测、启用且授权的
MCP 工具加入专属 DSH：Host 生成 `mcp__{installation}__{tool}` 声明和 schema 哈希，DSH adapter
经私有 loopback 回调 Host；Host 每次复核安装版本、schema、会话授权、风险等级与人工审批后才由
官方 SDK 调用 MCP Server。安装/启停会等待当前研究归零并仅重启 DSH，失败恢复旧激活清单；Web
进程与既有提交、SSE、恢复和报告状态契约不变。

Phase 2C 的 Automation 只从锁定的 Skill、普通 Workflow 或报告 Workflow 版本创建独立 Claw
会话。APScheduler 仅持有下一次内存触发，原子索引保存任务与 Run 事实；启动时只合并最近一次遗漏，
重叠触发记录 `skipped_overlap`，无法确认的旧会话记录 `interrupted`。研究失败不自动重试，手动
重试生成带 `retry_of` 的新 Run。无人值守 MCP 调用还须通过任务锁定、只读、明确允许和 schema
哈希复核，不能绕过会话授权或高风险人工审批。

## 持久化本地启动边界

`rwb web start|status|stop|restart` 由 `app/research_web/service_manager.py` 管理专属 DSH 3081 与 Web 8088。默认 DSH 源码是 `~/.research-workbench/dsh-source/` 中经过固定提交构建的项目私有副本，避免修改或依赖用户其他 DSH 实例使用的工作树；必要时可用 `RESEARCH_DSH_SOURCE` 显式覆盖。管理器把 PID、进程组、启动命令指纹、最终 Node CLI/overlay 归属签名、项目路径和日志位置写入 `~/.research-workbench/`。新版 Typert Gateway 启动后，管理器从受限日志尾部提取一次性启动令牌，换取 `dsh-auth-*` Cookie，并把 authority、工作目录、固定提交与版本原子写入 `runtime/auth.json`；POSIX 要求文件权限 `0600`，Windows 则拒绝重解析点并核对普通文件、单硬链接、大小及打开前后身份，不把 POSIX mode bit 当作 ACL 证明。健康检查以该 Cookie 调用真实 `session/list`，随后才启动 FastAPI 并检查 `/api/research/runtime`。重复启动是幂等操作；失败回滚只处理本次创建且归属签名匹配的进程，既有 3080 不在其所有权范围内。普通重启发现活动研究时拒绝执行，只有显式 `--force` 才允许中断。备用验收可为管理器指定独立端口，不复用生产状态目录。

`runtime/auth.json` 由客户端和服务管理器通过 `runtime_auth.py` 读取。读取器限制 4 KiB，拒绝非普通文件、硬链接、符号链接、Windows 重解析点及打开前后身份变化；POSIX 要求 group/other 无权限，Windows 不把 `st_mode` 的 POSIX 投影解释为 ACL。

服务管理器创建数据、运行状态和日志目录时采用相同的平台边界：所有平台拒绝非目录、符号链接与 Windows 重解析点，仅 POSIX 使用 group/other mode 位判断目录权限；Windows 不以该投影替代 ACL 结论。

断电或系统重启会结束后台进程，本轮没有安装开机登录项；恢复时重新执行 `rwb web start`。如果状态文件来自先前 checkout 或命令版本，管理器只有在记录的 PID 已确认不存在时才移除该 stale 状态并重建；PID 仍存在、状态损坏或归属无法确认时继续失败关闭，绝不接管或终止未知进程。

研究协议本身仍是下述 DSH RPC、Remote 复用流和 Web SSE 投影。Workbench 兼容桥把既有白名单方法映射到新版斜杠端点与 `{payload:{args}}` 信封；Cookie 只进入 HTTP/WS Header，不进入请求正文、会话记录或浏览器接口。服务管理器只负责本机进程生命周期，不创建第二套研究运行时，也不改变会话、审批或恢复语义。

## Tabbit 实时页面上下文

设置页分别控制浏览器自动化和 Tabbit `web_fetch` 接管。前者默认开启、后者默认关闭；打开 `web_fetch` 必须同时打开浏览器。多实例环境要求选择 16 位实例 ID。配置变更标记 `restart_required=true`，活动研究期间沿用既有重启门禁并保留待应用配置。

Tabbit 配置和 Runtime 锁文件固定按 UTF-8 读写。POSIX 继续使用文件权限位；Windows 在临时文件句柄关闭后执行原子替换并跳过不受支持的目录 `fsync`。供应归档文件名按 tar 的 POSIX 语义比较，adapter 入口在 overlay 中统一为正斜杠。

用户首次展开 `@` 标签菜单时，BFF 才为当前会话申请页面访问授权并读取所选实例的可 claim HTTP(S) 标签页；不会后台预取。消息最多携带 8 个有序 `{tab_id, instance_id}` 引用，且必须带实时接管二次确认。发送前 BFF 重新向 Runtime 读取清单并校验标签、实例、协议及可用状态，不信任浏览器提交的标题或 URL。

`runtime/tabbit-adapter.mjs` 只使用官方插件提供的唯一 `ctx.tabbit` 执行器，以 `rwb-mention-<session4>-<request8>` 原子 claim 所选标签，并在一次只读求值中按选择顺序读取当前 DOM。每页最多 60,000 字符、总计 120,000 字符；总量超限时按标签数公平截断并在折叠上下文中标记。无论成功或失败都在 `finally` 调用 `finishTask(..., {keep:true})`，标签保持打开，但分组可能改变。claim、求值或释放任一失败都会阻止消息提交并保留前端草稿。

正文仅写入 DSH 内存 token：绑定当前会话、只能消费一次、10 分钟过期。消息正文只携带短标记，`agent/pre-step` 再将内容注入默认折叠的插件上下文。会话授权后，声明为 `read_only:true` 的浏览器调用可自动执行；缺失或为 `false` 的调用逐次进入原生审批。该声明来自调用方，不能静态证明 Playwright 代码无写操作，系统提示明确禁止把写操作伪装为只读。日志只记录会话 ID、数量、阶段、耗时和稳定错误码，不记录标题、URL、正文或执行代码。

`GET/PUT /api/research/runtime/tabbit` 提供安全状态与配置；`POST .../tabbit-access` 管理本会话授权；`GET .../tabbit-tabs` 提供候选清单。Runtime 状态只允许 `ready | disabled | launcher_missing | browser_offline | unsupported_version | instance_selection_required | error`。安装器显式禁用；缺失、离线或版本过低时只返回诊断和官方手动安装指引。

`ResearchService` 同时持有进程内本机集成诊断管理器，并在服务关闭时取消未完成的发现或验证任务。发现只读取宿主事实；真实验证必须由设置页显式触发，目标限于 Excel、Word、PowerPoint 与 Wind Excel，并在独立进程组及对应 Office 容器的受管临时目录内执行。PowerPoint 保存后按随机文件名重新绑定本轮对象；Wind 运行目录固定落在 Excel 容器，从而不依赖交互式逐文件授权。该管理器只服务设置页的安全主机事实投影，不进入 DSH 会话、工具注册、研究执行或事件恢复链。

`app/research_web/operations.py` 只读取上述原生历史、当前投影和服务管理器状态，生成不含问题正文、审批参数或凭据的监控结果。它不参与提交、恢复或取消；历史事件未提供 usage 时返回未知，不以零替代。研究台通过 `workbench.py` 创建目标 DSH 会话后，后续提交仍完全遵守本页协议。

## 提交与流式

1. `POST /api/research/sessions` 创建真实 DSH 会话和产品归属目录。
2. `POST /api/research/sessions/{sid}/messages` 必须带 `Idempotency-Key`。BFF 先检查连接、运行中任务、附件归属、能力、交付要求和 Tabbit 实时引用；存在标签页时完成再次校验与单次提取后，才由兼容桥调用原生 `session/prompt`，每次请求生成独立 `requestId`。
3. HTTP 202 只表示受理。传输超时不是模型执行超时，且不能自动重发可能已受理的问题。
4. DSH Remote 的 `$events` 与 `session/control` 复用流分别提供 API 事件和控制基线；兼容桥把 `api-session/*`、waterfall 审批／提问及取消事件投影为稳定 BFF 信封。Web 通过 `GET .../{sid}/events` 接收 `snapshot` 或 `runtime_error`，心跳不代表执行进度。
5. 刷新读取同一会话。历史通过 `session/follow` 的 opening snapshot 与 `session/page` 分页恢复，并结合 `session/list` 和 `subagents/list` 恢复真实状态。恢复不另建会话、不重提消息。

会话删除使用 `DELETE /api/research/sessions/{sid}` 做产品内软删除，先写入墓碑并保留 DSH 原生日志与 Workbench 文件；30 天内可通过 `POST /api/research/sessions/{sid}/restore` 恢复。用户主动永久删除，或服务启动／每 6 小时在线任务发现墓碑到期时，BFF 调用 DSH `session/delete`。级联子会话删除由 Session Controller 负责；只有 DSH 明确返回包含根会话 ID 的 `deletedSessionIds`，或明确返回 `session/not-found` 证明原生记录已不存在后，才清理 Workbench 会话目录与索引。其他失败保留墓碑并继续重试，不能把隐藏状态误报为永久删除。所有操作都校验会话归属，不能用于发现、修改或删除其他 DSH 实例的会话。

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

本机 Office/Wind 显式验证证据在 TTL 截止时刻即失效；`verification_ttl_seconds=0` 不允许同一时钟刻度继续复用。POSIX 进程组与 Windows `taskkill /T /F` 由各自平台测试独立覆盖。

## 代码与测试

关键来源：`runtime_auth.py`、`client.py`、`service.py`、`projection.py`、`ui/core.mjs`。协议、认证文件与投影回归位于 `tests/research_web/`，前端幂等、路由竞态、刷新、SSE 清理测试位于 `tests/javascript/research_web_ui.test.mjs`。真实模型验收另记，不以传输模拟代替。

MCP Runtime 与 Automation 默认启用后仍按原有探测、授权、版本锁和风险策略运行；默认启用不等于自动安装 Server、自动授予工具或自动创建任务。显式环境开关关闭时继续失败关闭。
