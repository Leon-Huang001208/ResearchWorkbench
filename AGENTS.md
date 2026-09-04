# Research Workbench Agent Rules

## Start here

- 默认使用中文回答。
- 修改已有文件前，先阅读该文件及其模块文档。
- 修改源代码前，阅读 `docs/ARCHITECTURE.md` 和 `docs/DEVELOPMENT_MAP.md`。
- 用 `docs/AGENT_WORKFLOW.md` 选择本地快环、后台/远程执行通道及所需的 worktree 隔离。

## Engineering requirements

- 新增或修改代码必须使用项目日志设施，并包含明确的错误处理。
- Python 源码变更必须配套相关测试、文档、`.ai/reports` 任务报告和相应的完整性检查。
- 不得把未执行的命令、测试、浏览器验证或平台验证说成已通过。
- 安装 Python 包前必须先获得用户同意，并说明用途。

## Commands and platforms

- 使用当前操作系统环境中的 Python；绝不复制另一操作系统的绝对解释器路径。
- 适用时运行 `python -m pytest`、`ruff check .`、`black . --check`、`isort . --check-only` 及相关 `mypy` 检查。
- 桌面端改动严格遵守 `docs/desktop_packaging.md`；宣称 Windows 支持前，必须有原生 Windows CI 的构建和健康检查证据。
- 发布桌面端版本前，另须在真实 Windows 环境完成安装级冒烟测试。

## Safety and delivery

- 不覆盖或回退无关改动。
- 并行或高风险的仓库改动必须使用独立 Git worktree；worktree 是本地修改隔离，不等同于后台/远程执行通道。
- 长时但只读的研究、CI 日志分析或审查使用后台/远程；后台/远程任务若编辑仓库且存在并行或风险，必须使用独立 worktree 或等效隔离的远端 workspace。
- 未获用户明确授权，不执行破坏性操作、发布、处理秘密或外部协调。
- 交付时陈述变更、实际执行的命令、证据、未验证项和风险。

## Reusable workflows

- UI 迭代：`.agents/skills/ui-iterate/`
- 最小修复：`.agents/skills/bugfix-minimal/`
- 交付检查：`.agents/skills/ship-check/`

## Desktop cross-platform delivery (mandatory)

Applies to `src-tauri/`, `desktop/`, `scripts/desktop/`, desktop configuration and paths, sidecars, installers, updates, Excel/Wind integration, and any change that could affect desktop runtime behavior.

1. Mac local development and tests do not prove Windows support; never claim Windows has been verified without native evidence.
2. Every related change must run on a native Windows CI runner, covering dependency installation, Python sidecar build, Tauri Windows installer build, and basic startup/health checks.
3. Before release, run an installation-level smoke test on a real Windows environment. This is mandatory for Excel/Wind, permissions, upgrade, and installer changes.
4. Build sidecars natively for each target platform; never reuse a macOS binary on Windows or the reverse.
5. Follow the support matrix and acceptance checklist in `docs/desktop_packaging.md`, and update that document with relevant changes.
