# AlphaFoundry 资源监控第二期设计

## 目标

在既有实时资源看板上补足两项能力：

1. 将资源使用归因到 AlphaFoundry 管理的 Worker、任务类型和数据源；
2. 将异常和错误作为可确认、可恢复、可追溯的持久化事件展示在监控页，而不是只保留短期图表数据。

监控范围始终只限 AlphaFoundry。系统不得枚举、展示或持久化其他应用的进程信息。

## 已确认范围

- 归因范围采用“独立进程 + API 进程内任务”模式。
  - 独立 Worker（知识处理、抓取调度器等）按受控 PID 做精确进程资源归因。
  - Wind、PDF 转换、报告渲染和手动抓取等 API 进程内并发任务登记运行上下文；它们展示为共享 API 进程资源的估算，不宣称线程级 CPU 的精确值。
- 异常首先在系统监控页记录和置顶；本期不发送桌面原生通知。
- 实时资源图保留近 5 分钟；异常事件是独立的持久化历史，默认查询近 90 天，未恢复事件不受时间窗口影响。

## 设计选择

### 受控进程发现

`ResourceMonitoringService` 将保留 API 根进程及递归子进程采集，并额外接入**明确登记**的 AlphaFoundry Worker PID：

- `logs/scheduler.pid`：抓取调度器；
- `logs/knowledge_worker*.pid`：知识处理 Worker；
- 已有状态函数返回的 PID 会先验证进程仍存在；失效 PID 只记受控警告，不扩展到系统扫描。

采样器按 `(pid, create_time)` 去重，因此 PID 被操作系统复用时不会沿用旧进程的 CPU 或 I/O 基线。进程样本新增 `role`、`attribution_kind`、`source_key` 和 `confidence`：

- API/其子进程与已登记的独立 Worker：`confidence=exact_process`；
- API 进程内的活跃任务：`confidence=shared_process_estimate`，只列出共享的 API 资源，不拆分为虚构的任务 CPU 值。

### 任务上下文登记

新增 `services/resource_task_registry.py`，提供同步与异步安全的 `resource_task(...)` 上下文管理器。

每个任务记录：稳定 `task_id`、`task_kind`、可选 `source_key`、用户可读标签、PID、线程/协程标识、开始时间、当前状态和已净化的错误摘要。任务类型限定为 `crawl`、`pdf_conversion`、`knowledge_processing`、`wind`、`report_render`。

同一进程的活动任务写入运行目录下以 PID 隔离的 JSON 快照，采用“临时文件 + 原子替换”。API 只读取该受控目录，合并仍存活的 Worker 快照。这使独立进程不必向 API 开放新端口，也避免跨进程共享内存失效。

集成点：

- `CrawlScheduler` 为单源抓取、补数和 PDF 批次包裹任务上下文；
- Knowledge Worker 为每个队列项目包裹 `knowledge_processing` 上下文；
- Wind 工作簿准备/读取、报告渲染和手动抓取入口包裹对应上下文；
- 任务正常结束时从活动清单移除；异常会记录失败状态并触发持久化告警。

任务标签和数据源键只来自已有 `SourceSpec`、任务 ID 和受控字符串；不得记录请求参数、令牌、文档正文或命令行参数。

### 异常事件与生命周期

复用既有 `alert_payload` 与 `incident_record` 表，不新增第二套告警数据库。新增监控子系统枚举值 `resource_monitoring`，资源事件在 `metadata` 中携带规范化归因：`event_kind`、`task_id`、`task_kind`、`source_key`、`pid`、`attribution_kind`、`confidence` 和最近安全资源快照。

事件类型：

| 事件 | 严重度 | 触发条件 | 自动恢复 |
| --- | --- | --- | --- |
| `task_failed` | critical | 已登记任务抛出未处理异常 | 否，需人工确认后解决 |
| `managed_process_unavailable` | warning | 已登记 PID 在任务仍活跃时消失 | 是，受控进程重新可用后 |
| `resource_pressure` | warning | 同一受控进程连续 3 次采样 CPU ≥ 90% 或 RSS ≥ 1 GiB | 是，连续 3 次回落到阈值以下后 |
| `monitor_sampling_failed` | warning | API 根进程采集失败 | 是，后续采样成功后 |

相同“事件类型 + 任务或 PID”同时只保留一个未恢复告警，防止每两秒重复置顶。告警状态沿用项目既有语义：`open → acknowledged → resolved`。确认只表示已阅；资源恢复或人工解决会写入 `resolved_at`，历史事件和其归因永远可查询。

默认列表取近 90 天，但未恢复事件始终并入结果；数据库不在本期自动删除历史。保留策略将作为独立的运维配置工作项，而非悄悄丢弃异常证据。

### API 与前端

保留现有实时接口，并新增资源监控专用接口：

- `GET /api/system/resource-usage`：实时摘要、受控进程、任务归因和当前未恢复事件计数；
- `GET /api/system/resource-usage/history`：近 5 分钟的轻量资源序列；
- `GET /api/system/resource-events`：按状态、严重度、任务类型、数据源和时间查询持久化事件；
- `POST /api/system/resource-events/{alert_id}/acknowledge`：确认事件；
- `POST /api/system/resource-events/{alert_id}/resolve`：人工解决事件并记录可选说明。

系统监控页新增：

1. 顶部“待处理异常”固定区：critical 优先，显示任务/来源、发生时间、确认和解决操作；
2. “活跃归因”区：独立 Worker 显示精确 CPU/RSS，API 内任务显示共享估算标识；
3. “异常历史”区：默认 90 天，支持状态、严重度、任务类型和数据源筛选；
4. 既有 5 分钟曲线维持实时诊断用途，并清晰标注其不是长期错误记录。

轮询失败时保留上一帧数据，并把前端错误以受控状态显示；不得清空图表或把网络错误伪装为零资源占用。

## 数据流

```text
Worker/API 任务开始
  → resource_task 写入本进程活动任务快照
  → 资源采样读取 API 树 + 受控 PID + 活动快照
  → 生成进程/任务归因视图
  → 检测失败、消失与持续资源压力
  → MonitoringRepository 保存/更新资源告警与事件
  → 系统监控 API
  → 页面置顶未恢复事件、显示实时图和历史
```

## 错误处理与安全边界

- PID 文件、JSON 快照、psutil 和数据库访问全部捕获预期 I/O/权限/进程异常并写结构化日志；单个 Worker 快照损坏不会中断总采样。
- 任务快照损坏或过期会被忽略并生成受控诊断日志，不会解析任意路径。
- 所有命令参数继续完全脱敏；事件元数据不包含秘密、请求体或文档内容。
- 仅通过 API 根进程、既有 AlphaFoundry PID 文件和本功能专用目录发现进程；不调用系统全量进程枚举。

## 验收标准

1. 在受控 PID 的独立 Worker 上，实时表显示精确进程资源与正确角色；无关 PID 永不出现。
2. API 进程内任务显示任务类型、数据源和共享估算置信度，且不会显示伪造的任务 CPU。
3. 模拟任务失败后生成一个置顶 critical 事件；刷新或重启 API 后仍可查询并可确认/解决。
4. 连续资源压力只产生一个未恢复事件，回落后自动恢复并保留历史。
5. 实时图仍只保留 5 分钟，异常历史可检索近 90 天，且未恢复事件始终可见。
6. 任务快照、psutil 读取或数据库失败时返回明确的降级状态，前端保留上一帧数据。
7. 覆盖服务、API、任务注册与前端静态契约的单元测试；在 macOS 本地验证 API 与浏览器页面。Windows 桌面运行不在本期本地验证范围内。

## 明确不在本期范围

- Tauri/操作系统原生桌面通知、通知权限管理和通知去重；
- 对任意系统进程、浏览器或其他应用的监控；
- 持久化全部原始资源采样点或将任务级 CPU 伪装成精确测量；
- 自动重启、自动终止任务或自动执行修复动作；
- 自动删除告警历史的保留策略。
