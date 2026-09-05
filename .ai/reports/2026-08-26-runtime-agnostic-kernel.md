# Runtime-agnostic 投研能力内核实施报告

## 已完成

- 新增 Runtime-neutral Core contracts，Core 未导入任何 DSH/Codex/Claude SDK。
- 每日市场点评以 `WorkflowSpec` 编排 5 个原生 Tools、4 个 Runtime Skills、原生 Evaluator 和 Renderer；报告叙事必须在质量门禁通过后才能执行。
- 新增 v2 PostgreSQL 账本模型、015 Alembic 迁移、`/api/v2` 工作流与可恢复 SSE 路由。
- DSHAdapter 使用 HTTP/SSE Bridge Transport；独立 TypeScript Bundle 以 `@deepseek-ai/dsh-tools@0.1.1-rc.2` 和 Cordis 作为 peer dependencies。Bundle 强制回环、双向独立 Token、allowlist、幂等键、超时、稳定 session identity 和 `alphafoundry_submit_skill_result` 双重 Schema 校验。`npm run dsh:bootstrap` / `npm run dsh:web` 参考蒸研的 vendor checkout + 隔离 Profile 模式，项目管理固定 DSH Host，但不将 DSH SDK 写入根依赖或锁文件。
- Archify 已交付架构图和时序图；两图结构 showcase 验证为 9/9。

## 验证证据

- `python3 -m py_compile ...`：通过。
- `git diff --check`：通过。
- `.venv/bin/python -m pytest tests/unit/test_dsh_deploy.py tests/unit/test_dsh_bundle.py tests/unit/test_runtime_kernel.py tests/unit/test_dsh_adapter.py tests/unit/test_alembic_migration_graph.py -q`：13 passed。
- Ruff、Black、isort：通过；`mypy --follow-imports=skip` 对 7 个新增/修改源文件通过。完整 mypy 仍暴露 `core/observability` 既有 13 个 Logger 类型错误。
- Graphify 根图 `--update --code-only` 已执行 AST 提取，但历史图包含多个独立 scan root，合并阶段被 Graphify fail-closed 拒绝（跨项目去重禁止）。已对 `runtimes/dsh` 单独生成代码图谱：159 节点、235 边、11 社区，无 import cycle。`core/contracts/runtime.py` 未导入 Runtime SDK，`runtimes/dsh/{adapter,deploy}.py` 仅单向导入 Core；以 `rg` 复核未发现 Adapter 反向导入，符合 Adapter → Core 方向。
- 官方 DSH `dsh-v0.1.1-rc.2` 源码 checkout 的 `pnpm install --frozen-lockfile` 与 `pnpm run build` 已完成；独立 Bundle 的 `pnpm install`、`pnpm run build`（含 declaration bundle）和 `pnpm run typecheck` 均通过。项目托管 Host 成功以 `127.0.0.1:3290` 启动；认证 health 返回 5 Tools / 4 Skills，未认证请求为 403，创建 session、有限 SSE replay 和 cancel 路由均已真实冒烟。
- 已审阅 `zhengyan`：它 vendoring 上游 DSH 源码、应用补丁并由项目脚本启动隔离 Profile；AlphaFoundry 已采用其项目托管、隔离 Home 的运行方式，同时保留本项目的 Bridge、双向 Token 与 Runtime-neutral Core 边界。
- Archify：两张图均已 `validate` / `deliver` 通过 9/9 showcase 检查，`visual-check` 在 1440×900、1600×1000、1920×1080、2048×1320 均无水平或垂直滚动；已人工查看 1440×900 截图。

## 未验证项

- 未配置模型 Provider 凭据，因此没有执行真实模型 Skill 回复或 AlphaFoundry API 方向的原生 Tool 回调；Host、Bridge、Bundle、Skill discovery 与路由合约已验证。
