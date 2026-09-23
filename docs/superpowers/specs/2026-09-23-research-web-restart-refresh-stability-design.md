# Research Web restart 与刷新稳定性设计

## 背景与已确认问题

当前 `master` 在干净隔离 worktree 中可以完成公开安装，并在 16.15 秒内启动 3081/8088；Doctor、HTTP 与 DSH health 均通过。浏览器首次打开和刷新最终可用，但存在两个相互关联的稳定性缺陷：

1. `./rwb web restart --no-open` 在没有活动研究时稳定失败，提示“无法核对活动研究”。
2. 浏览器刷新后约 7.5 秒内错误显示“运行时未就绪或离线”，之后才恢复模型和能力目录。

真实反馈环已经确认：

- `/api/research/sessions` 返回 50 个会话，HTTP 200，响应约 2.6–2.8 秒。
- `WebServiceManager._json_request()` 固定 2 秒 timeout，因此同一请求稳定超时。
- `ResearchService.list_sessions()` 先调用一次 `session.list`，再为每个已创建会话串行调用 `subagent.list`；日志可观察到约 50 次重复查询。
- 同一组 50 次 `subagent.list` 查询串行耗时约 1.63 秒；并发上限 8 时约 0.94 秒。
- 专属 DSH 的 `session/list` 可直接返回所有 68 个原生会话及 `running` 状态，当前查询低于 1 秒。

## 目标

1. restart 的活动研究判断不依赖慢速 Web 目录接口，直接使用专属 DSH 的权威运行态。
2. 任何专属 DSH 会话（包括子会话或本地 store 未知会话）仍在运行时，非 `--force` restart 必须失败关闭。
3. Research Web 会话列表保留父会话与子 Agent 的真实运行态判断，但不再串行执行 N 次查询。
4. 前端明确区分“正在连接”与真实“离线”，并在目录分项就绪时渐进更新，不等待最慢目录后才整体刷新。
5. 不通过全局增大 timeout、跳过子 Agent 检查或伪造 ready 状态换取表面通过。

## 选定方案

采用三层协同的方案 A：DSH 直查 restart、安全有界并发目录、渐进加载 UI。

不采用以下替代方案：

- 仅把 2 秒 timeout 调高：会掩盖 N+1，刷新假离线仍存在。
- 新增 Web `active-session` API：让进程管理器再次依赖 Web，增加接口和故障耦合，且 DSH 已提供所需权威数据。
- 跳过已完成会话的子 Agent 查询：可能漏掉父会话状态陈旧但子 Agent 仍运行的情况，不满足安全边界。

## 组件设计

### 1. Service manager 的 DSH 权威查询

在 `app/research_web/service_manager.py` 内提取一个私有 DSH RPC 边界，复用现有 auth record、token/cookie 建立、loopback 限制、2 MiB 响应上限和协议校验。该边界接收 allowlisted method 与 payload，返回验证后的 `result.value` 字典；认证、HTTP、JSON、rpcId、`ok` 或值类型异常均抛出 `ServiceManagerError`。

- `_runtime_healthy()` 调用该边界执行 `session/list`，成功即健康，任何异常返回 `False`。
- `_active_research()` 调用同一 `session/list`，严格校验 `items` 为对象数组，返回所有 `running is True` 的 `sessionId`。
- 任意运行中的专属 DSH 会话都阻止 `restart` 与 `restart-runtime`；`--force` 保持现有显式绕过语义。
- 无 auth、协议异常或无法确认运行态时继续返回“无法核对活动研究”，不回退到慢速 Web `/sessions`，也不假设安全。

这让 restart 的安全判断只依赖其真正要管理的专属 Runtime，而不是目录/UI 层。

### 2. 会话目录的有界并发

在 `app/research_web/service.py` 中保持一次 `session.list` 快照，并将每个已创建父会话的 `subagent.list` 改为有界并发：

- 并发上限固定为 `8`，作为模块级常量。
- 使用一个 `asyncio.Semaphore` 和 `asyncio.gather`；未创建的本地会话直接使用空 entries。
- 查询结果按原始 `rows` 顺序映射，列表排序和响应结构不变。
- 任一子查询失败仍使目录请求失败，保持当前 fail-closed 语义；不以空列表吞掉 Runtime 错误。
- 原生父 session 或任意 child 的 `activity == "running"` 仍把父会话投影为 `running`。

目标是消除串行 N+1 延迟，而不减少检查范围。

### 3. 前端连接中与渐进目录加载

在 `app/research_web/ui/app.mjs` 的 catalog 中增加请求中的名字集合：

- `loadCatalog(names)` 在发请求前把名字标记为 pending，并先渲染一次。
- 每个请求独立完成或失败后立即清除对应 pending 并渲染；最终仍执行连接/集成状态合并和收尾渲染。
- Runtime 请求 pending 时，顶部状态显示“DSH 连接中”。
- Runtime 尚未返回时，composer 保持草稿可编辑、发送禁用，提示“正在连接运行时”；只有 Runtime 请求已经失败或返回未连接时才显示“未就绪或离线”。
- Runtime、模型或能力目录各自完成后即可更新对应控件，不等待 sessions 等最慢目录。

`app/research_web/ui/composer.mjs` 增加显式 `runtimePending` 输入。`runtimeReady` 继续只表示真实可发送状态，两者不能互相推断。

## 错误处理与安全边界

- DSH session 响应缺少 `items`、item 非对象、`running` 非布尔值或 `sessionId` 无效时，restart 关闭失败。
- 并发目录查询不自动重试、不降级为空数据，也不改变 DSH allowlist。
- UI pending 只表示请求尚未结束；请求失败必须进入现有 error/offline 投影，不能无限保持 loading。
- 不修改端口、PID ownership、Runtime auth 文件格式、外部 API、依赖或 Windows 自动验证政策。
- 服务异常恢复、外部端口占用和“不误杀未知进程”规则保持现状。

## 测试与验收

### 自动化回归

1. `tests/research_web/test_service_manager.py`
   - 无运行会话时 DSH 直查返回空列表，restart 可继续。
   - 父会话、子会话或未知会话任一 `running=true` 时均拒绝非 force restart。
   - auth、HTTP、rpcId、协议形状和 item 字段异常均失败关闭。
   - `_runtime_healthy` 与 active 查询复用同一协议边界。
2. Research Web API/service 测试
   - 50 个父会话仍全部调用 `subagent.list`，最大观察并发不超过 8 且大于 1。
   - 输出顺序、running 投影和查询失败传播保持正确。
3. JavaScript 测试
   - composer 的 pending 文案与 offline 文案互斥；两种状态都禁用发送但保留草稿编辑。
   - `loadCatalog` 在分项完成时渐进渲染，Runtime 完成不等待 sessions。
   - Runtime 真失败后不再显示“连接中”。

### 真实 macOS 验收

1. 公开安装、Doctor 和首次 start 通过。
2. 50 个历史会话下 `/api/research/sessions` 本机响应小于 2 秒。
3. 无活动任务时普通 restart 成功并更换 3081/8088 PID。
4. 幂等 start 保持 PID；Runtime SIGTERM 后 start 只恢复 3081 并保留 8088；stop → start 通过；最终 stop 后状态为 stopped。
5. 浏览器首次打开与刷新期间不出现假“离线”；先显示连接中，Runtime/模型就绪后可发送，Skill 目录随后渐进出现。
6. `status` 和 `doctor --json` 的真实进程、端口、HTTP、DSH health 保持一致。

### 增量与远端验收

- 使用项目 `incremental-validation` 由真实 changed set 计算 L0–L4，不手工压低级别。
- 运行规划器选出的全部本地测试、文档治理、Project Constraints 和 receipt 校验。
- 发布后必须通过 Project Constraints、Research Web Checks 与 GitHub `macos-14` Bootstrap。
- Windows 自动验证继续暂停，不运行也不声明通过。

## 文档与回执

同步 Research Web 安装/安全或架构文档中与 restart 活动判断、会话目录性能和加载态相关的说明；任务报告记录诊断时间、50 会话基线、并发测量、浏览器刷新以及最终 lifecycle 结果。预发布 receipt 对外部门保持 `not_run/blocked`，只有实际 GitHub 结果通过后才转为 `passed`。

## 非目标

- 不清理或迁移用户历史会话。
- 不改变 DSH 源码或协议。
- 不新增依赖或公开 API。
- 不恢复 Windows 自动验证。
- 不重构与本缺陷无关的 Research Web 页面、会话详情或研究执行链。
