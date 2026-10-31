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

## Current Research Web delivery phase (authoritative)

机器阶段权威为 `.agents/research-web-stage.json`，依据用户 2026-10-07 明确授权：阶段二、三及 Windows/Linux 平台交接已重新开启。当前 Mac 任务执行功能开发、macOS Native 与 Mac Docker Desktop 验收；Windows/Linux 原生适配、真机及同平台 CI 由对应设备执行，缺设备保持 NOT_RUN，不冒充支持或阻断独立完成的 Mac 任务。

`.agents/verification-policy.json` 保留完整目标计划与风险；Windows/Docker 条件门恢复选取。Docker workflow 仍仅由 Linux 真机对 exact SHA 手动 dispatch；Mac 不发送 Windows/Linux 产品 dispatch。Ubuntu Project Constraints/Research Web Checks 保持通用仓库门。平台能力状态与实际验收分别见 `docs/research-web-platform-support.md`。

## Platform ownership and acceptance (mandatory)

- 24GB Mac mini（macOS）承担主开发、Docker 构建/测试与常驻服务；MacBook Pro 是受控远程操作与浏览器入口，不再承担主要开发计算。Mac mini 负责 macOS/Docker Desktop 真机及适用 GitHub macOS CI，不承担 Windows/Linux 原生验收。
- Windows 真机只负责既有功能的 Windows 适配、Windows 真机验收及远端 GitHub Windows CI 验收，不承担功能开发。
- Linux 真机只负责既有功能的 Linux 适配、Linux 真机验收及远端 GitHub Linux CI 验收，不承担功能开发。
- 每次任务先声明宿主平台、任务类型（功能开发或平台适配）及本平台验收范围。Windows/Linux 适配中发现功能缺陷时，记录复现与证据并交回 Mac 开发任务，不在适配任务中扩展功能。
- 当前宿主任务只以本平台本地验收和适用的同平台 GitHub CI 为完成条件。其他平台的适配、真机及 CI 验收必须交接给对应真机，不得作为当前宿主任务的完成前置条件。
- 总体验收计划和跨平台发布就绪状态仍保留所有目标平台证据；任务完成不等于跨平台已验证。按 `docs/AGENT_WORKFLOW.md` 分开记录本平台任务状态与总体验收状态，不得删门、伪造 PASS 或把未验证平台标为支持。
- CI runner决定原生证据归属：Ubuntu不冒充macOS原生证据；本任务仍保留Project Constraints/Research Web Checks通用仓库门，不表示交付Linux产品。其他平台产品执行由对应设备任务接手。

## Web installation contract (mandatory)

- 每次产品迭代都必须保持公开入口 `./setup-web.sh`、`setup-web.cmd` 与
  `python scripts/setup_web.py` 可从干净 checkout 完成安装；不得依赖开发者全局 Python/Node 包。
- 修改 Web Python/Node 依赖、`app/research_web/`、`app/cli/`、固定 DSH、CJPY、启动器或配置流程时，
  必须同步核对 `requirements/web.in`、`requirements/web.lock`、`scripts/setup_web.py`、
  `docs/research-web-installation.md` 和 `.github/workflows/research-web-bootstrap.yml`；无须改变的文件应由
  安装 CI 证明仍兼容，不能仅凭本机已有环境判断。
- Web 交付必须先完成本机 macOS 相关验证，再等待 GitHub `macos-14` 干净安装、固定 DSH 构建、
  3081/8088 健康检查和 `rwb web doctor --json` 通过；本机成功不能替代 GitHub Mac。安装、共享 runtime、
  Windows launcher、路径/编码/进程和本机集成等平台敏感改动由 Router 标记为需要 GitHub
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
  `platform/windows/*`。不要长期维护 `windows`、`macos` 或 `develop` 平行分支。2026-10-07 已启用 `master`
  branch protection：必须 PR、最新基线、GitHub Actions 的 `check`、管理员受约束、禁止强推/删主线、解决讨论。平台条件门仍由任务回执校验，不能宣称全部被 GitHub 无条件强制。
- 不覆盖或回退无关改动。
- 任何 `git push`、PR merge、tag、`gh run rerun`、`workflow_dispatch` 或受管发布前，必须读取 `docs/actions-budget.md` 并核对当前仓库 visibility。private／billable 状态下，当 Actions included usage 达到 95% 或当前 run 返回 billing-blocked 时，仅允许本地编辑、测试和提交；只有当前 Billing/API 证明额度已重置，或 GitHub API 证明仓库已变为 public 且当前标准 runner run 能启动，才恢复远端操作。旧 billing-blocked 记录不能覆盖更新的公开仓库运行证据。
- 并行或高风险的仓库改动必须使用独立 Git worktree；worktree 是本地修改隔离，不等同于后台/远程执行通道。
- 长时但只读的研究、CI 日志分析或审查使用后台/远程；后台/远程任务若编辑仓库且存在并行或风险，必须使用独立 worktree 或等效隔离的远端 workspace。
- 未获用户明确授权，不执行破坏性操作、发布、处理秘密或外部协调。
- 交付时陈述变更、实际执行的命令、证据、未验证项和风险。

### 开发任务持续交付授权（2026-10-14）

- 用户已明确持续授权：今后本项目开发任务完成后，自动提交本任务改动、push 本任务开发分支、创建目标为 `master` 的 PR；项目规定的必需检查和评审通过、讨论已解决且满足最新基线与分支保护后，直接合并到 `master`，不在这些环节重复询问授权。用户在具体任务中要求仅本地修改、不发布或不合并时，以该任务指令为准。
- 合并后安全更新本地 `master`，确认本任务提交已进入远端 `master`、本任务 worktree 干净且没有进程占用后，清理本任务已归并的短期分支和 worktree。不得清理其他任务资源、丢弃未提交修改、删除未归并提交或强制移除脏 worktree。
- 此授权不免除现有验证、评审、平台归属、Actions 额度和分支保护要求；不得强推、绕过检查或伪造通过。检查失败或冲突应在本任务范围内修复并重新验证；无法解决或必需证据缺失时，保留真实阻断状态并报告。
- 部署、更新常驻服务、引入或安装新依赖、处理秘密，以及上述安全清理以外的破坏性操作，仍需单独明确授权。此授权不扩展到 tag／版本发布、系统配置、数据库迁移或其他外部协调。

### 每轮迭代资源收尾（2026-10-15 明确持续授权）

- 验收和合并后自动执行“证据归档 → 本任务资源回收 → Git安全清理 → 空间复查”，不再为同一范围重复请求授权；`status`只有收尾成功才返回`cleaned`。失败记录`blocked`、对象、大小或大小不可用原因，不能用验收通过代替收尾完成。
- 本项目明确受管的`desktop-linux`与`rwb-dev-builder`构建缓存**合计上限20 GiB**。通过BuildKit引用/租约保护和LRU GC回收，使用与`rwb-docker`相同的操作锁；不手删snapshot/blob或Docker.raw，不中断运行服务。维护只临时调整已停止、身份已验证构建器的内存限额，完成后恢复原限额和停止状态；预算、身份或并发检查不通过就保留并报告。
- 自动回收本任务已退休的临时容器、经归档恢复校验的测试卷、可再生依赖、多余镜像和已归并worktree。运行服务、业务数据、凭据、必要报告、恢复归档、当前及上一通过镜像、未知归属/其他进行中任务/未归并提交继续保护；Git安全备份保留规则不变。
- 创建临时Docker资源时设置`RWB_DELIVERY_TASK_ID=<本任务ID>`或显式传入`ResourceSession(..., delivery_task=...)`；生命周期标签和精确归属随资源保存。Git入口在start/prepare/publish登记目录身份，不从名称、时间或“已停止”推断退休。
- 只清理已登记且复查身份、引用、占用和Git跟踪状态的依赖；证据校验归档后才能移出worktree，不重复保存node_modules、.venv。未知ignored路径仍阻止Git清理，禁止强删脏worktree或伪改回执。

### RWB Git 完整性与安全交付

- macOS 受管交付通过 `node scripts/git_safety.mjs delivery --project <RWB绝对路径> --task-id <任务ID> <动作参数>` 执行，使用 `/usr/bin/git`，不直接修改全局 `leon-engineering` 安装或系统 PATH。开始任务先运行该入口的 `check`；具体流程见 `docs/AGENT_WORKFLOW.md`。
- RWB 共用 Git 目录的本地 `gc.auto=0`、`maintenance.auto=false` 由 `configure` 备份原值后设置。维护与并行开发分开；禁止在有并发写入时执行立即 prune、repack 或直接删除 `.git` 内容。入口不执行对象维护，也不因遇到锁而自动删锁或终止进程。
- 清理前必须验证任务提交、未提交修改、未跟踪文件及相关 Git 快照的可恢复备份，再复查归并状态、worktree 归属、工作区干净和进程占用。仅安全清理本任务资源，禁止直接删除 worktree 目录、强删未归并分支或整体覆盖旧 `.git` 元数据。
- Git 安全备份保存在 `~/.codex/backups/rwb-git-safety/`。依据用户2026-10-31事件清理方案，新登记且完成交付的普通恢复点不再等待7天，满足全部保护检查后轮转，并始终保留最新2个验证通过的恢复点；未登记历史存量先核对并逐类批准。使用v2独立共享对象/文件存储，相同现场复用已验证恢复点。轮转经正式入口预览、持备份锁、完整恢复验证；未提交、未归并、活动、未知归属及独有保护锚点继续保留。2026-10-14对象修复隔离备份不迁移、不删除，仍须另行明确授权；对象丢失原因仍未确定。交付与清理状态分开，欠账后续事件补清；完整协议见`docs/resource-lifecycle.md`。
- 该入口的仓库级锁只约束采用入口的操作；Codex 内部 Git 操作和直接执行的人工命令不因此被完全接管。仓库迁移、全局工具配置和常驻服务更新仍须单独授权。

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
