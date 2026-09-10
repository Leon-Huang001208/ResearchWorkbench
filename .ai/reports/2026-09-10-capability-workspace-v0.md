# 能力工作区 v0 任务记录

## 范围

- 仅修改 Research Web 前端、对应 JavaScript 测试与文档。
- 将 `#/skills` 组织为 Skill、Tool、Workflow、数据四个互斥主标签，并在类型内提供适用的二级视图。
- 删除“全部类型”混合流和类型下拉；使用现有真实目录与安全状态投影，没有新增 Automation、MCP Registry、依赖或后端接口。
- 快览只选择能力进入研究草稿，不自动发送。

## 变更

- 新增 `app/research_web/ui/capability-workspace.mjs`：四类主导航、类型内二级视图、严格类型过滤、计划/连接摘要与快览 dialog。
- `core.mjs` 归一 kind/view 参数；旧 kind 深链保持有效，无 kind 的 plans/connections 分别映射到 Workflow/Tool。
- `app.mjs` 接入工作区、专用管理跳转、Escape／遮罩关闭、焦点锁定与焦点恢复。
- `appearance.css` 增加四／三／二／一列响应式布局、Light/Dark 语义变量复用与手机全屏弹层。

## 已执行验证

- `node --check app/research_web/ui/core.mjs app/research_web/ui/capability-workspace.mjs app/research_web/ui/data-catalog.mjs app/research_web/ui/app.mjs`（逐文件执行）
- `node --check tests/e2e/research_web_appearance.mjs`
- `node --test tests/javascript/research_web_capabilities_ui.test.mjs tests/javascript/research_web_report_workflow_v0.test.mjs tests/javascript/research_web_appearance.test.mjs`：51 项通过。
- `node tests/e2e/research_web_appearance.mjs`：Light/Dark 下覆盖 1440、1280、768、390，四类主标签、键盘切换、Skill/Tool/Workflow/数据快览、弹窗焦点锁定、Escape、焦点恢复和移动端全屏均通过；0 个浏览器错误，0 个写请求。
- `/Users/leon/opt/anaconda3/bin/python -m pytest tests/research_web/test_capabilities.py -q`：20 项通过。
- `/Users/leon/opt/anaconda3/bin/python -m ruff check app/research_web`：通过。
- `/Users/leon/opt/anaconda3/bin/python -m isort app/research_web --check-only`：通过。

测试使用现有 Conda Python 的临时、未跟踪 `.venv/bin/python` 链接运行，完成后已删除；未安装任何依赖。

## 已知基线门禁

- `black app/research_web --check` 报告 25 个既有 Python 文件需格式化；本任务没有修改 Python 源码，也没有批量改写这些无关文件。
- `mypy app/research_web` 在多个内置能力包都使用 `scripts/workflow.py` 时报告重复模块名，检查在分析本次变更前中止。
- `test_report_workflow_integration.py` 的 21 个测试主体通过；其中 `test_delivery_retry_consumes_late_payload_without_starting_another_claw_session` 在 TestClient teardown 时因已关闭的 asyncio event loop 报错。单独重跑仍为 1 项主体通过、1 个 teardown error；本次未改报告 Workflow 后端。

## 当前检查点

用户已确认 web-design-engineer 的可浏览 v0 视觉与四类信息架构。阶段二通用调度、MCP Registry、安装／授权／Runtime 代理和交付渠道尚未实现，也不属于本次交付。
