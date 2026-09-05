# FinGPT DSH Web 壳实施记录

## 交付范围

- 新增 FinGPT 顶级页面，嵌入 loopback DSH Web iframe，并在 Host 不可用时显示启动诊断。
- 新增可治理但不复制聊天正文的任务、会话索引、同步事件、证据引用与 Artifact 关联模型，以及 016 迁移。
- 每日市场点评作为完整的 AlphaFoundry Workflow；其余四张卡明确启动通用 DSH Agent 任务。
- DSH Bundle 新增一次性 `launch_id` 接收端、严格 UI Origin 检查和脱敏会话事件同步。

## 运行边界

- DSH：完整会话与对话轨迹。
- AlphaFoundry：市场/数据库 Tool、Workflow、Evidence、Evaluator、Artifact 和会话治理索引。
- DSH 原生 Web 搜索索引为 `external_uningested`，未经证据管线捕获不可作为权威证据。

## 验证证据

- `npm run typecheck --prefix runtimes/dsh/plugin`
- `npm run build --prefix runtimes/dsh/plugin`
- `.venv/bin/python -m pytest tests/unit/test_fingpt_service.py tests/unit/test_alembic_migration_graph.py tests/unit/test_runtime_kernel.py tests/unit/test_dsh_adapter.py tests/unit/test_dsh_bundle.py -q`
- `.venv/bin/ruff check …`、`.venv/bin/black --check …`、`node --check app/web/static/js/fingpt.js`、`git diff --check`

## 架构与依赖资产（2026-08-28 同步）

- Archify：`outputs/fingpt-dsh-shell.architecture.json` 与对应 HTML 已完成结构校验、交付和 1440×900 至 2048×1320 的视觉检查；图中明确了 `AlphaFoundry UI → DSH Web Shell → DSH Agent → AlphaFoundry Tool/Workflow`，以及 DSH 完整会话与 AlphaFoundry 治理索引的边界。
- Graphify：既有根图谱含多个历史/并行目录，无法安全增量去重。因此以当前工作区重新执行 code-only 提取并输出到 `outputs/fingpt-code-graph/`，而未覆盖旧图谱。结果为 19,492 个节点、46,882 条边；报告位于 `outputs/fingpt-code-graph/GRAPH_REPORT.md`。
- 依赖方向检查：在 `core/`、`services/`、FinGPT API 和 DSH 插件范围内，仅 `services/runtime_workflow_service.py` 导入 `runtimes.dsh.adapter.DSHAdapter`；没有发现 `core/` 导入 Runtime 的反向依赖。

## 本地预览（2026-08-28）

- 已以 `ALPHAFOUNDRY_PREVIEW=1`、`ALPHAFOUNDRY_DESKTOP=1` 启动隔离 API 预览并在浏览器打开 `http://127.0.0.1:8770/`，切换至 FinGPT 页面。
- 当前页面正确呈现 DSH Host 未连接诊断，而非空白 iframe：现有 3280 Host 是未加载 AlphaFoundry Bundle 的旧 Profile。未因此将实际对话、模型执行或 iframe 消息端到端标记为已验证。

## 嵌入式启动握手修复（2026-08-28）

- 修复通用预置任务在 iframe 初始加载尚未完成时可能只创建 AlphaFoundry 任务、却没有投递给 DSH 的竞态。
- AlphaFoundry Web 现在等待来自精确 DSH Origin 的 `alphafoundry.fingpt.ready`；DSH frame 同时支持无凭据 `alphafoundry.fingpt.ping` 回应。任务 `postMessage` 仅在握手完成后发送，保留既有 Origin 校验与一次性 `launch_id` 约束。
- 真实浏览器复现显示 iframe 的 HTTP 请求 Origin 为 DSH 自身（而不是父页面）。Bridge 现校验请求 Origin 必须等于本机 DSH frame origin，而 DSH frame 继续在接收 `postMessage` 时严格校验 AlphaFoundry UI origin；同一 launch 路由的 403 复现已在修复后变为 202。
- 纠正 DSH `session/event` 的双参数回调映射，并在 AlphaFoundry 已配置 PostgreSQL 上执行 014→015→016 迁移。成功启动的任务和 DSH 事件 POST 均有本地 API 202 日志；完整模型回合及 Artifact 仍未在本次预览中声明为完成。
