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

## Platform ownership and acceptance (mandatory)

- MacBook Pro（macOS）负责项目功能开发、macOS 适配与真机验收，以及远端 GitHub macOS CI 验收；不承担 Windows/Linux 适配与验收。
- Windows 真机只负责既有功能的 Windows 适配、Windows 真机验收及远端 GitHub Windows CI 验收，不承担功能开发。
- Linux 真机只负责既有功能的 Linux 适配、Linux 真机验收及远端 GitHub Linux CI 验收，不承担功能开发。
- 每次任务先声明宿主平台、任务类型（功能开发或平台适配）及本平台验收范围。Windows/Linux 适配中发现功能缺陷时，记录复现与证据并交回 Mac 开发任务，不在适配任务中扩展功能。
- 当前宿主任务只以本平台本地验收和适用的同平台 GitHub CI 为完成条件。其他平台的适配、真机及 CI 验收必须交接给对应真机，不得作为当前宿主任务的完成前置条件。
- 总体验收计划和跨平台发布就绪状态仍保留所有目标平台证据；任务完成不等于跨平台已验证。按 `docs/AGENT_WORKFLOW.md` 分开记录本平台任务状态与总体验收状态，不得删门、伪造 PASS 或把未验证平台标为支持。
- CI 的 runner 平台决定证据归属：Ubuntu run 属于 Linux，不能因测试是通用合同就计作 macOS CI。现有自动触发不改变职责，其他平台的 run 由对应平台任务处理。

## Web installation contract (mandatory)

- 每次产品迭代都必须保持公开入口 `./setup-web.sh`、`setup-web.cmd` 与
  `python scripts/setup_web.py` 可从干净 checkout 完成安装；不得依赖开发者全局 Python/Node 包。
- 修改 Web Python/Node 依赖、`app/research_web/`、`app/cli/`、固定 DSH、CJPY、启动器或配置流程时，
  必须同步核对 `requirements/web.in`、`requirements/web.lock`、`scripts/setup_web.py`、
  `docs/research-web-installation.md` 和 `.github/workflows/research-web-bootstrap.yml`；无须改变的文件应由
  安装 CI 证明仍兼容，不能仅凭本机已有环境判断。
- Web 交付必须先完成本机 macOS 相关验证，再等待 GitHub `macos-14` 干净安装、固定 DSH 构建、
  3081/8088 健康检查和 `rwb web doctor --json` 通过；本机成功不能替代 GitHub Mac。安装、共享 runtime、
  Windows launcher、路径/编码/进程和本机集成等平台敏感改动会由 Router 标记为需要 GitHub
  `windows-2022`，但 Mac PR/push 不自动触发；必须在 Windows 真机 checkout 待验 commit 后，从该机
  以 exact SHA 执行 `workflow_dispatch`。Windows CI 不能替代 Windows 实机安装、升级、
  Office/Wind 或企业环境验证；未执行的层级必须保留 `NOT_RUN` 或 `MANUAL_REQUIRED`，不得宣称通过。
  Linux 真机任务负责 Linux 适配、实机验收及 GitHub Linux CI；他平台未验证不阻塞 Mac 本平台任务。
  无厂商凭据的 CI 必须把天软显示为“依赖已安装但待配置”，不得伪报可调用。
- 新增用户可配置能力时，Doctor、安装文档、安全清单和一键流程必须同步覆盖；秘密只由本机设置页或
  系统凭据库接收，禁止写入锁文件、安装日志、CI 产物或代码包。

## Safety and delivery

- GitHub 是 Mac、Windows 与 Codex worktree 之间 Git-managed source code 的唯一真相源；不得用云盘、
  Finder/Explorer、U 盘或移动硬盘覆盖同步源码。`master` 是唯一长期集成分支，功能和修复必须从最新
  `master` 建立 `feat/*`、`fix/*`、`refactor/*`、`codex/*`、`platform/windows/*` 或
  `platform/macos/*` 短期分支/worktree，经验证和 PR 合回 `master` 后再清理。
- Windows 默认只 fast-forward 最新 `master` 并做原生验证；只有发现 Windows-only 缺陷时才创建
  `platform/windows/*`。不要长期维护 `windows`、`macos` 或 `develop` 平行分支。仓库当前没有远端
  branch protection，以上是项目契约，不能把它描述成 GitHub 已机械强制。
- 不覆盖或回退无关改动。
- 任何 `git push`、PR merge、tag、`gh run rerun`、`workflow_dispatch` 或受管发布前，必须读取 `docs/actions-budget.md` 并核对当前仓库 visibility。private／billable 状态下，当 Actions included usage 达到 95% 或当前 run 返回 billing-blocked 时，仅允许本地编辑、测试和提交；只有当前 Billing/API 证明额度已重置，或 GitHub API 证明仓库已变为 public 且当前标准 runner run 能启动，才恢复远端操作。旧 billing-blocked 记录不能覆盖更新的公开仓库运行证据。
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

Current phase boundary: product iteration is Web-only until the user explicitly reopens desktop work. Changes limited to `app/web/`, `app/research_web/`, general Web API/runtime code, shared Python/Node dependencies, or Web documentation are not desktop deliverables and must not trigger sidecar, Tauri, installer, or native desktop CI acceptance. The desktop rules below apply only when the task explicitly targets desktop behavior or changes a desktop-owned path such as `src-tauri/`, `desktop/`, `scripts/desktop/`, or `services/desktop_platform/`.

1. Mac local development and tests do not prove Windows support; never claim Windows has been verified without native evidence.
2. Each platform task owns only its native checks and corresponding GitHub CI. The Windows device task must cover dependency installation, Python sidecar build, Tauri Windows installer build, and basic startup/health checks; these are not completion gates for the Mac task.
3. Before releasing a platform build, its device task must complete an installation-level smoke test on that platform. The Windows task owns real Windows smoke tests for Excel/Wind, permissions, upgrade, and installer changes. Missing Windows evidence blocks Windows release readiness, not Mac task completion.
4. Build sidecars natively for each target platform; never reuse a macOS binary on Windows or the reverse.
5. Follow the support matrix and acceptance checklist in `docs/desktop_packaging.md`, and update that document with relevant changes.
