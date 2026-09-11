# Research Web Phase 2 默认启用交付记录

## 范围

- 在 Phase 2A、2B、2C 远端门禁通过后，将 MCP Registry、MCP Runtime 与 Automation 的缺省状态改为开启。
- 仅修改 Research Web 功能门控、契约测试和同步文档；不新增接口、依赖、桌面代码、安装、授权、任务或外发。

## 契约

- 未设置环境变量时，`RESEARCH_MCP_REGISTRY_ENABLED`、`RESEARCH_MCP_RUNTIME_ENABLED` 与 `RESEARCH_AUTOMATIONS_ENABLED` 均按开启处理。
- 任一变量显式为 `0` 时继续关闭对应功能；既有 `false`、`no`、`off` 也继续按关闭处理。
- Research Web Host 和 `launch_runtime.py` 使用相同的 MCP Runtime 默认值，避免 API 与 DSH 工具绑定状态分叉。
- 默认开启不自动安装 MCP Server、不授予工具、不迁移报告日程、不创建 Automation，也不发送外部消息。

## 验证

- `python -m pytest` 对 Registry、Runtime、Automation 与启动层相关模块执行 154 项测试，全部通过；Starlette `TestClient` 有 1 条上游弃用警告。
- `node --test tests/javascript/*.test.mjs` 执行 270 项 Research Web JavaScript 测试，269 项通过、1 项既有 DSH schema 依赖测试跳过。
- `ruff check`、`black --check`、`isort --check-only` 覆盖 4 个源文件和 4 个测试文件并通过；`mypy --follow-imports=skip` 覆盖 4 个源文件并通过。
- 架构图文门禁、文档同步门禁、项目约束和 `git diff --check` 均通过。
- MCP 市场、MCP Runtime 和 Automation 三组浏览器回归各通过 8 个 viewport/theme 组合，共 24 项；覆盖 1440/1280/768/390、Light/Dark 与 reduced-motion。
- 浏览器回归使用本地固定 fixture，不声明真实第三方 Registry、OAuth、MCP Server、邮件或机器人渠道已联通；本次不涉及桌面端。
- 远端 CI 与清理结果由受管交付 receipt 记录。
