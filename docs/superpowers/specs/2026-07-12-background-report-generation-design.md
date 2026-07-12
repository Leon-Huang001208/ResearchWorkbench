# 后台报告生成与进度跟踪设计

日期：2026-07-12

## 背景

当前“生成报告”通过一个 `POST /api/report-projects/{slug}/render` 请求同步执行整条链路：证据检索、本地 embedding、rerank、模型写作、Word/PPT 渲染与 run log 落盘。华安 ETF 周报在本地 MPS 重排阶段单批可耗时 75–146 秒，桌面 WebView 会在后端完成前中断 fetch，前端只显示 `Load failed`。

同一轮生成还会由多个 section 线程同时加载本地 embedding/reranker 模型，日志已出现重复加载和 `Cannot copy out of meta tensor` 错误。

## 目标

1. 提交生成后在数秒内返回任务 ID，不再让 WebView 维持长时间 HTTP 请求。
2. 前端轮询任务状态，展示排队、生成段落、渲染输出、成功或真实错误。
3. 同一报告项目在任意时刻最多有一个活动任务，重复点击返回已有任务。
4. 本地 embedding/reranker 模型只加载一次，并串行化不安全的 MPS 推理调用。
5. 保留现有同步 render 接口的核心执行服务，使旧调用方与单元测试不必重写生成业务。

## 方案选择

采用进程内任务管理器和单 worker 执行器。这与当前单机桌面应用的运行方式一致，不引入 Redis、Celery 或新的数据库迁移。全局只运行一个顶层报告任务，避免多份报告竞争 MPS 和内存；报告内部仍可并发调用外部 LLM，本地模型访问由锁保护。

不做运行中任务的跨进程恢复。AlphaFoundry 重启后，内存中的运行任务不会自动续跑；已完成的文档与 run log 仍由现有目录持久保存。这一边界避免为单机工具引入过重的恢复协议。

## 组件设计

### `ReportGenerationJobService`

新建聚焦的任务服务，负责：

- 生成 UUID 任务 ID。
- 保存有界的进程内任务记录。
- 将生成工作提交给 `ThreadPoolExecutor(max_workers=1)`。
- 对同一 project slug 做活动任务去重。
- 将执行结果转换为可序列化的成功数据，将异常转换为可读错误文本。
- 通过回调更新 `phase`/`message`/`completed_sections`/`total_sections`。

任务状态为 `queued | running | completed | failed`。任务记录包含创建、开始、完成时间，project slug，当前阶段，段落进度，结果或错误。

### API

新增：

- `POST /api/report-projects/{slug}/render-jobs`：校验项目后提交任务，返回 HTTP 202 和完整任务状态。如已有同项目活动任务，返回该任务并标记 `deduplicated=true`。
- `GET /api/report-projects/{slug}/render-jobs/{job_id}`：返回最新状态；job 不存在或不属于该项目时返回 404。

现有 `POST /{slug}/render` 暂时保留，用于兼容和直接测试；工作台不再调用它。

### 进度回调

`ReportProjectRunService.execute()` 接受可选回调，不传时行为不变。关键阶段为：

1. `prepare`：读取配置与素材。
2. `generate`：检索证据并生成段落，每完成一个段落更新计数。
3. `render`：替换占位符、图表和表格。
4. `save`：保存文档与 run log。
5. `completed` 或 `failed`。

回调只传递结构化进度，不依赖 FastAPI 或前端类型，便于单元测试。

### 前端轮询

`renderReportProject()` 改为：

1. POST 提交任务。
2. 使用有上限的轮询循环请求 job 状态。
3. 根据 phase 和段落计数更新现有进度卡。
4. `completed` 时返回原 render response，复用已有的预览、下载和刷新逻辑。
5. `failed` 时抛出后端保存的真实错误。

轮询单次请求很短，因此不会触发 WebView 长请求超时。轮询设置足够长的总时间上限，超时只停止前端等待，不取消后端任务；错误文案将明确提示任务仍可能在后台运行。

## 本地模型并发安全

- embedding 和 reranker 缓存各有一个加载锁，采用锁内二次检查，保证同一路径只构建一次模型。
- 模型 encode/predict 调用分别使用推理锁，避免 MPS 对同一模型的并发访问。
- 加载失败保留现有降级行为：embedding 回落到其他检索分数，reranker 回落到已有顺序，不使整份报告因可选重排失败而终止。

## 错误处理与日志

- 任务提交、去重、开始、进度、完成、失败都使用现有结构化 logger，包含 job ID 和 project slug。
- 后台异常通过 `logger.exception` 保留堆栈，API 状态只返回适合用户查错的错误文本。
- 前端不再将网络层 `Load failed` 当作生成结果；短轮询暂时失败时允许有上限的重试，后端明确失败时立即停止。
- 任务历史使用有界缓存，避免长时间运行造成无限内存增长。

## 测试策略

1. 任务服务单元测试：提交立即返回，状态迁移，成功结果，异常保存，同项目去重，项目所属校验。
2. API 测试：POST 返回 202，GET 返回任务，未知任务返回 404，同项目重复提交不重复执行。
3. 进度测试：段落完成后回调数据单调增加，旧的无回调调用保持兼容。
4. 模型单例测试：多线程同时首次请求只构建一个模型；并发推理不重叠。
5. 前端静态行为测试：工作台使用 render-jobs 接口，轮询 completed/failed，展示段落进度，不再直接等待 `/render`。
6. 集成验证：使用可控的慢生成 fixture 确认 POST 快速返回，在后台完成后 GET 得到结果。

## 非目标

- 不引入 Redis、Celery 或独立 worker 部署。
- 不支持运行中任务的暂停、取消或跨进程续跑。
- 不改变 section 配置、Prompt 模板、Word/PPT 文件结构或现有 run log 格式。
- 不在本次修复中替换检索、rerank 或 LLM 供应商。
