# Agent 任务路由指南

多用户常驻附接的离线绑定、保全及 kernel boot 恢复测试复用既有 Research Web Checks 同一 Python 步骤；精确源码交付之后另做 Mac mini 私有部署与真实双账号隔离验收，不把 CI 或登录成功等同模型生成。

AI资讯自主化本轮在隔离实例接入原版API/worker与独立库，保持DSH研究执行及当前常驻内容。零调用和后续切换边界见[自主资讯合同](research-web-ai-news.md)。

私网多用户的账号、网关、运行池和CLI安全合同加入既有Research Web Checks四个定点测试文件；
只增加当前安全边界的回归，不扩大为全目录pytest，也不增加runner或平台dispatch。
变更前五次成功运行与新增时间预算记录在actions-budget；Mac仍承担本地Native和macOS安装CI，
Windows/Linux任务交接保持独立。真实模型、管理员初始化、用户迁移与常驻部署不由这些fixture授权。

FinGPT 单引擎质量门变更使用离线来源/数值/续研与原生工具回归；macOS 安装沿既有 Bootstrap。无真实模型调用，未获预算不做付费对比；Windows/Linux 验收交接保持 NOT_RUN，不从 Mac dispatch。

固定 DSH 搜索升级的 macOS Bootstrap 沿用既有空搜索 HTTP 冒烟，并核对 unavailable_count=0；部分覆盖、原生不可见范围与真实工具/文件由本机独立候选验证，不新增平台 dispatch。

macOS迭代若供resident自动部署，仍须完成受管delivery和独立review，确保最新master与
Project Constraints/Research Web Checks/macOS Bootstrap实际checkout树匹配。缺失Mac门时补齐同候选证据；
不因部署紧迫跳过CI、不从本机dispatch其他平台。未知/依赖/迁移变化交给明确授权的专项升级。


Hot 安装变更沿既有 Mac Bootstrap 验收：公开安装器运行后，在 Node 24.19.0 下
验证 Hot 生产依赖导入。此步骤不连接 PG/模型，不替代真实 worker、模式切换或付费
研究证据；Windows/Linux 产品 dispatch 仍由对应真机执行。CI 的受管停止错误保留
非零结果，不用 `|| true` 省略。源检查点与仅记录结果的报告检查点须分别标明。

持久文本验收预算精确匹配专属ledger与launcher测试和guard测试，按L4安全边界保留完整Docker/Windows及macOS计划；历史时钟测试不表示当前政策或模型授权有效。平台任务与总发布就绪继续分开记录。

当前交付平台以 [AGENTS.md 的 Current Research Web delivery phase](../AGENTS.md#current-research-web-delivery-phase-authoritative) 为准：用户已开启阶段二、三，Mac 任务验收 macOS Native 与 Docker Desktop；Windows/Linux 由对应设备执行，缺设备保留交接。Ubuntu 通用 CI 不代替平台真机验收。


本指南用于在开始工作前选择合适的执行方式，并定义可复核的交付证据。共享规则以仓库根目录的 `AGENTS.md` 为准；`.agents/skills/` 中存放已跟踪的项目 skills。`.claude/` 仅是本机可选配置，不能作为共享规则来源。

数据能力仅在对应任务中按需加载：`wind-find-finance-skill` 负责金融能力发现，`wind-mcp-skill` 负责受支持的 Wind 查询；`cls`、`cnstock` 和 `data-connector-development` 只维护 legacy crawler/Connector 层，不能把代码存在误报为当前 Research Web DataHub Provider 可调用。全局目录不再承载这些项目专属 Skill。

## Git、设备与 Worktree 契约

GitHub 是 Mac、Windows 和 Codex worktree 之间 Git-managed source code 的唯一真相源。不得使用云盘文件夹、Finder/Explorer 覆盖、U 盘、移动硬盘或同步工具复制源码；移动介质只可保存 data、database、model、cache 或 artifact。

远端长期只保留 `master`。日常流程固定为：

```text
master
  → short-lived branch/worktree
  → local platform-aware minimal acceptance
  → PR
  → routed CI
  → merge master
  → preserve evidence and reclaim task resources/cache within aggregate20GiB
  → restore-verified safe Git cleanup and disk receipt
```

短期分支使用 `feat/*`、`fix/*`、`refactor/*`、`codex/*`、`platform/windows/*` 或 `platform/macos/*`。Mac 是主要开发机，负责功能、架构、重构和 macOS 本地验证；Windows 默认运行 `git switch master` 与 `git pull --ff-only` 后验证最新集成版本，验证成功不创建分支。只有 Windows-only 缺陷才从最新 `master` 建立 `platform/windows/*`，并通过 PR 回到 `master`。需要 GitHub Windows CI 时，Windows 真机先 checkout 待验 ref、读取 `git rev-parse HEAD`，再从该机 dispatch workflow 并传入 `expected_sha`；Mac 不发送 Windows dispatch。禁止长期维护 `windows`、`macos`、`develop` 或设备专属代码线。

一个并行任务对应一个明确 branch，原则上对应一个独立 worktree。合并后仅在确认提交已进入 `master`、worktree 没有未归并修改且没有进程占用时，才移除该 worktree 和失效短期分支。2026-10-07已启用master保护：PR、最新基线和Actions check（app15368）强制通过，管理员也受约束；平台条件门继续由任务回执校验。禁止强推/删除主线及未解决讨论由远端保护执行；各平台条件 CI 与真机证据仍是项目任务合同，不能宣称全部被远端无条件强制。

## RWB Git 安全入口（macOS）

本入口只管理 RWB 的受管 Git 交付，不改变产品运行时。写入操作要求 `--project` 与脚本所在 RWB checkout 共用同一个 Git common directory，不接受其他仓库或 CLI 身份绕过参数。macOS 固定使用系统 `/usr/bin/git`，控制器子进程使用任务私有 PATH 转接；不修改全局框架、系统 PATH 或其他项目。转接禁止对象维护，fetch 不带 `--prune`。`check` 只读，不写日志或修复引用；其余操作在 `logs/git-safety.jsonl` 记录结果、Git 版本、SHA、耗时及备份引用，不记录凭据、环境变量或完整命令输出。

在已有 RWB checkout 中使用以下流程；`--project` 指向任务交付账本所属的主 checkout，不随意切换到其他仓库：

```bash
node scripts/git_safety.mjs check --project /absolute/RWB
node scripts/git_safety.mjs configure --project /absolute/RWB
node scripts/git_safety.mjs delivery --project /absolute/RWB --task-id TASK --start --slug SLUG
```

`configure` 先保存仓库本地 `gc.auto` 和 `maintenance.auto` 的原值（含原先不存在），再设置为 `0` 和 `false`；配置只留在本机 Git common directory，不进入代码包。回滚仅恢复这两个配置项，并确认它们没有被其他任务改动，禁止整体覆盖旧 `.git/config`。自动维护暂停期间对象库可能增长；本阶段不自动删除备份或执行 GC，后续维护需在停止并发写入、完成备份与完整性检查后另行安排。

实现、提交和本地验收后，仍按完整 changed set 的 Router 结果执行所有必需检查：

```bash
node scripts/git_safety.mjs delivery --project /absolute/RWB --task-id TASK --prepare
node scripts/git_safety.mjs delivery --project /absolute/RWB --task-id TASK --publish \
  --verification-command 'ACTUALLY_EXECUTED_COMMANDS' \
  --verification-status passed --verification-duration-seconds INTEGER_SECONDS
node scripts/git_safety.mjs delivery --project /absolute/RWB --task-id TASK --status \
  --reviewed-commit EXACT_REVIEWED_PR_HEAD_SHA
node scripts/git_safety.mjs delivery --project /absolute/RWB --task-id TASK --cleanup
```

发布必须走 PR；检查、评审和分支保护通过后才合并。`--reviewed-commit` 是操作者对独立评审候选的明确声明，必须绑定当前 PR head，不能用旧 SHA 或仅看测试通过代替评审。入口在 common directory 的私有任务记录中持久保存该声明；已被外部合并的 PR 也不能在缺少 matching 声明时认证完成，清理前必须再次核对。仓库未开启 GitHub Auto-merge 时，由入口在后续 `status` 检查中执行普通 Merge；不启用仓库设置、不使用管理员绕过。private／billable 仓库没有当前额度证明时停止远端操作，不能从历史 public 状态推导权限。

本任务因 `master` 前进进入 `remote_moved` 时，先在原集成工作树合入
最新 `origin/master`、解决冲突并提交，再运行原 `--prepare`。入口仅认证已提交候选：
当前候选必须包含旧候选、新基线和已登记feature；仓库、工作树/分支、原PR、GitHub实时
master及PR head须匹配，并在写入前再次核对。脏目录、未提交合并、改动中的回执、未知PR
head或既有锁均拒绝。支持旧prepared尚未发布时主线再次前进；只接受明确登记的已发布tip，
不接受任意祖先。成功发布后会把该tip推进到实际发布候选，禁止沿用更老的tip。
首次发布前恢复要求 `mode`、`pullRequest`、`remoteCommit` 三项明确为 null；不查询不存在的 PR。已发布任务继续验证原 PR 身份，不接受部分发布字段或未知远端 tip。
恢复将旧完整回执以0600存于Git common dir的 `leon-engineering/git-safety/base-refresh/TASK/`，
保留原PR、原工作树、所有引用和修补计数；不调用共享控制器的删除/重建分支，也不执行push。
新回执回到prepared并清空verification/CI，旧评审因候选SHA不同而失效；须重新完成本地验证、
对应候选的CI与独立评审，再用正常 `--publish` 更新同一PR。`--replace-prepared` 及已完成交付的
重建仍拒绝。全局运行时、系统PATH、分支保护和资源/Git恢复备份硬门保持。

`backup` 也可独立创建当前 checkout 的恢复证据；清理时捕获本任务受管 worktree 和调用 checkout，其他任务的工作区文件不被读取或导出，历史失效注册不被删除。备份位于 `~/.codex/backups/rwb-git-safety/`，目录 `0700`、普通文件 `0600`，包含提交 bundle、分开保存的暂存／未暂存二进制补丁、tracked 普通文件的原始工作副本字节、未被忽略的未跟踪文件、快照引用及其对象闭包。在自己的临时仓库中实际恢复并校验对象链、文件哈希和普通文件权限：Git 只记录 executable 位，还可能按属性转换换行，不能用 checkout 的默认字节或 `0644` 替代原本的 LF／CRLF 工作副本及 `0600` 等权限。恢复字节和权限只作用于临时恢复仓库中的已验证普通文件，不跟随符号链接或修改源文件。恢复前保存未认证的 draft metadata；失败备份保留诊断状态，不产生成功认证。发现备份期间目标变化、缺失对象、明确敏感文件或失败时停止，不能静默省略后继续清理。不读取凭据库或忽略的运行时秘密文件；合法报告名出现 token 不视为凭据文件。

清理前必须确认所有拟处理的分支均已归并、worktree 共用同一 Git 目录且匹配任务账本、工作区干净、没有进程占用，并完成可恢复备份。ignored 文件不会因为 Git status 干净就变成可删除数据：只要拟删除工作区仍有 ignored 路径，入口就拒绝清理，且不读取或导出它们。操作者可将明确由本任务产生的验证日志保留到私有证据目录，其他缓存、数据和秘密必须保留并单独处理。清理后检查对象完整性和其他任务资源保留情况。遇到 Git 锁或仓库级入口锁时停止，不自动删除遗留锁。只允许移除本任务已归并资源，不接受任意 shell 命令，也不提供 GC／prune 接口。

锁仅串行化采用本入口的操作；Codex 内部和人工直接执行的 Git 命令仍可能并发。Ubuntu 临时仓库测试属于通用算法证据，不代表 Linux／Windows 宿主启用已验证。现有隔离备份永久保留至另行授权；原始对象删除者仍未确定。

备份的全仓引用与其他 worktree 注册是捕获时的快照，不表示其他任务被冻结。导出并在临时仓库校验所捕获 SHA 的完整对象闭包后，其他聊天可继续新增或更新 Codex tree 引用；本任务目标 worktree 的 HEAD、分支、索引、补丁和文件仍必须在备份前后完全一致。清理保留性检查记录其他任务的合法提交快进；Codex 快照指针更新仅在旧对象已保存于认证备份、新对象仍完整时记录，不回退当前指针、不执行过期清理。其他非任务引用消失或非快进变化仍停止验收。

## 任务路由（Routing rules）

### 自动资源收尾

项目规则固定`.agents/resource-closeout.json`的两个受管构建器合计20 GiB。Git入口在start/prepare/publish登记任务目录身份；publish修补只允许把已完整包含在候选中的干净feature tip更新到受管记录，保留CI计数和基线，不接受未提交或其他分支身份。资源登记/回执保存在Git common directory的`leon-engineering/resource-closeout/<task-id>/`，不放在将删除的worktree中。

`status`确认已审查候选实际合并且CI通过后，释放仓库锁再进入既有`cleanup`流程。它自动移除已登记的再生依赖，将日志证据逐文件校验保存到私有证据目录，复用`docker_resources`归档/恢复/删除当前任务退休对象，再经原Git备份和安全条件移除已归并worktree。未知ignored数据、进程占用和未归并提交仍拒绝，不能用清理授权绕过。

临时测试资源用`RWB_DELIVERY_TASK_ID`或`ResourceSession(delivery_task=...)`关联交付；没有关联的历史资源保留。缓存维护与`rwb-docker`共用操作锁，验证Buildx节点、context、容器/卷和本机内存门，仅对已停止构建器临时使用2 GiB限额，完成后恢复原容器限额和停止状态。BuildKit自行保护in-use记录并LRU回收；总量仍超20 GiB或恢复失败，回执为blocked。

每次验收在回执列出reclaimed/retained/blocked、缓存前后总量和宿主df实测；逻辑镜像容量或du累计不能冒充宿主实际释放。`cleaned`必须同时代表资源及Git收尾成功。重复status对已cleaned交付复核，不重新删除。原有Git安全备份至少30天保留。

先按下列优先级路由，而不是只凭任务大小选择。后台/远程是执行通道，worktree 是本地仓库修改隔离；二者可以组合，长时本身不要求 worktree。选择最小但足够的方式，不因任务看似复杂而跳过验证。

### 路由优先级与决策顺序

1. **先应用桌面端例外。** 只要改动影响桌面端，就必须先满足“桌面端例外”中的原生平台验证和发版前烟测要求；执行方式仍按后续规则选择。
2. **再判断是否必须使用独立 worktree。** 任何并发改动、已有无关工作区改动、涉及公开接口、数据库、安装流程，或无法局部回滚的高风险变更，必须使用独立 worktree。高风险指影响公开契约、数据迁移、桌面安装/更新、跨平台行为，或无法快速还原的变更；此隔离要求可与后台/远程执行通道同时适用。
3. **再判断是否适合后台/远程。** 验收稳定且确定、但执行耗时的工作，使用后台/远程；例如只读仓库研究、CI 日志分析、审查或有界实现。后台/远程任务若编辑仓库且有并发或风险，必须在独立 worktree 或等效隔离的远端 workspace 中执行。
4. **最后才使用本地快环。** 仅当变更单一、局部、可快速验证且无冲突时，才使用本地快环。

多文件本身不是自动进入独立 worktree 的条件；只有存在冲突、风险、并行需求或需要干净比较时，才需要隔离 worktree。

| 路由 | 适用条件 | 交付证据 | 不适用场景 |
|---|---|---|---|
| 本地快环 | 变更窄、需立即判断、不与活跃修改冲突 | 目标命令或浏览器结果 + 简洁 diff | 长任务、并发公共区域、或需要探索替代方案 |
| 独立 worktree | 并发、已有无关工作区改动、高风险或需干净比较分支 | 路径、分支、针对验证、明确集成计划 | 只读或一行确认；仅因多文件而隔离 |
| 后台/远程 | 验收稳定且确定但耗时，如只读仓库探索、CI 日志分析、审查或有界实现；若编辑且有并发/风险则与独立 worktree 或等效远端隔离组合 | 任务范围、diff/报告、命令、未验证约束 | 交互秘密、破坏操作、发版决定、持续设计判断 |

选择后仍应先阅读相关规则、目标文件及其直接依赖；任务范围、所有权或验收不明确时，先同步并拆分，而不是扩大执行范围。

## 平台职责与任务完成范围

| 宿主真机 | 允许的工作 | 本任务验收责任 |
| --- | --- | --- |
| 24GB Mac mini / macOS | Docker 主开发、构建、测试、常驻服务；MacBook Pro 远程操作 | macOS / Docker Desktop 本地验收 + 适用的 GitHub macOS CI |
| Windows | 已有功能的 Windows 适配；不承担功能开发 | Windows 本地验收 + 适用的 GitHub Windows CI |
| Linux | 已有功能的 Linux 适配；不承担功能开发 | Linux 本地验收 + 适用的 GitHub Linux CI |

开始任务时记录宿主平台、功能开发/平台适配类型、代码提交、验收范围。Windows/Linux 适配只能修复本平台的路径、权限、依赖发现、启动和构建等兼容问题；发现平台无关的功能缺陷时，提供复现并交回 Mac 开发任务。

当前宿主不执行、不修复、不等待其他平台的适配或验收来完成本任务。GitHub runner 的操作系统决定 CI 归属，不能把 Ubuntu 的通用测试算作 macOS 验收。Docker CI 不从 Mac PR/push 自动触发。Linux 真机完成本机验收后，以 checkout 的 exact SHA 发起 `research-web-docker.yml` 的 `workflow_dispatch`，传入 `expected_sha`；该工作流先校验 checkout/dispatch SHA，再执行原有双架构构建、健康、重启、持久化与清理。其他 workflow 的自动触发仍按配置运行；其他平台 CI 结果由对应真机任务负责。

### 总体验收与本平台任务分开记录

`plan_verification.mjs` 保留原 changed-files 模式；显式 `--base` 与 `--task-context` 启用 Git 绑定 plan v4，`validate_verification_receipt.mjs` 对应验证 receipt v3。完整影响与所有总门禁仍保留，机械校验另推导本宿主任务与其他平台交接，不裁剪总计划。未提供 task 的历史 plan v3 / receipt v2 继续保持原语义，不能从旧回执推断新的本宿主验收 PASS。执行代理必须：

1. 保留完整 changed set、风险等级、总计划和所有平台门。
2. 执行当前宿主可运行的通用检查、本平台检查及适用的同平台 GitHub CI；若总计划没有本平台 CI，按已存在的本平台 workflow 核对适用检查，缺少入口时如实记录本平台 CI 待配置，不凭其他平台 run 替代。
3. task context 记录 `hostPlatform`、`taskKind`、`objective`、`acceptanceScope`、`candidateCommit`、`candidateBaseCommit` 与 `supplementalGateIds`。RWB 薄入口要求声明宿主与实际执行宿主相同，功能开发仅允许 macOS，Windows/Linux 只接受已有功能的平台适配。receipt v3 与报告记录 `hostAcceptance`（PASS/FAIL/BLOCKED/NOT_RUN）、完整 `platformHandoffs` 和 `aggregateAcceptance`（READY/NOT_READY）。同平台 CI 尚未取得时，本平台验收不能为 PASS；若路径规则未选中适用的本平台门，可在 task 中补选策略 catalog 已登记的 gate ID，不能传入任意命令。
4. 总回执里他平台未执行的门仍保留 NOT_RUN/BLOCKED 和未覆盖风险；总体验收或跨平台发布可能未就绪，但不得据此把已完成验收的本平台任务标为失败或继续在本机适配其他平台。
5. 当前宿主任务可在本平台验收 PASS 且交接完整后完成；`mergeReady`/`releaseReady` 继续表示总体验收，不得从本平台 PASS 推导跨平台发布就绪。发布授权和仓库分支保护仍须独立满足。

新模式按真实 runner/machine 平台归属证据：多平台 local gate 的一次 macOS 执行不复用为 Windows/Linux PASS；`generic` 不推断所有原生平台，`cross-platform` 未覆盖的目标仍保留 NOT_RUN 交接。CI PASS 必须绑定 workflow、run、候选、预期及实际 checkout；merge preview 还须由本地真实 Git commit 的父提交证明关联 base/head，未知对象失败关闭且 validator 不自行 fetch。候选、说明源码、图源/生成物与报告提交分别记录，避免报告或生成物自指提交。报告仍记录验收范围和证据来源；机械结构有效不代表任务已全部完成。

## 最小验收规划（Verification planning）

Claw正文搜索的快速HTTP/私有RPC边界使用`test_session_search.py`，与既有协议合同一起进入Research Web Checks；查询须走JSON POST，浏览器验收另检查模式/归属、错误重试与迟到响应。新增只读搜索不替代完整本地API回归、Native候选与exact-SHA Mac安装CI，也不扩大Windows/Linux dispatch授权。

双运行时 Web 改动仍使用下方同一 changed-file 规划器：Dockerfile/Compose、bootstrap、runtime contract、凭据后端与 Docker CI 命中各自策略规则；不因 Web Docker 部署自动引入 Tauri/sidecar/桌面门。`--runtime` 无参数默认 Native，真实 Docker 构建/健康与 Native 安装分别保留证据；没有镜像或平台回执时必须写 `not_run`/`blocked`，不能用模拟测试替代。模式切换需确认旧模式所有权并顺序停用，共享产品数据不能被两个模式同时写入。安装/依赖操作仍按原审批边界执行。

在决定具体测试和交付范围前，用项目内只读规划器为全部改动路径生成机器可读计划：

```bash
node scripts/plan_verification.mjs --project . \
  --changed-file <changed-file> \
  --changed-file <another-changed-file>
```

需要平台任务回执时，使用项目相对 JSON 作为 task context，固定当前候选 HEAD 与 Git 基线：

```bash
node scripts/plan_verification.mjs --project . --base <base-sha> \
  --task-context <task-context.json>
```

此模式自动发现完整 committed/staged/unstaged/untracked changed set；如另传 `--changed-file`，必须与实际完整集合相等。task JSON 不接收秘密；候选未提交的字节不能借已提交候选的 CI PASS 认证，提交后重新绑定。原 changed-files 模式仍支持显式路径与 signal。

验收回执固定后，用只读摘要入口同时呈现任务与交付身份：

```bash
node scripts/summarize_verification_delivery.mjs --project . \
  --plan <project-relative-plan.json> --receipt <project-relative-receipt.json> \
  --delivery <project-relative-delivery.json>
```

摘要要求 plan v4 / receipt v3，并调用正式 validator；旧回执或未绑定回执不能涂改为本宿主 PASS。delivery metadata 必须记录同一 `candidateCommit`、`branch` 和显式 `runtimeUpdated`，可记录 `pr`、`mergeCommit`、`sourceRevision`、`reportCommit` 与 `diagramIdentities`（ID、图源/HTML SHA-256）。未知字段拒绝，不能通过 metadata 改写验收结果或执行命令。CI checkout 身份直接来自受验证 receipt。摘要的 `deliveryMetadataVerified=false` 明确这些交付记录未由摘要独立查询 GitHub、运行实例或图形产物；本宿主 PASS 与总体验收 NOT_READY 可同时保留。命令只向 stdout 输出 JSON，不落盘、不发布；报告另由任务保存。

`.agents/verification-policy.json` 是唯一政策真源；规划器只输出计划，不运行测试、构建、CI、发布或策略中的命令。Git 绑定模式只读 Git 发现与身份，不修改 Git 或工作区。`.agents/project-constraints.json` 保持独立架构门，不拥有或复制路由表。

规划与回执算法来自 `.agents/runtime/leon-engineering/` 的受管最小运行时；
`manifest.json` 固定框架版本、source commit、协议版本和每个受管文件哈希。
`scripts/plan_verification.mjs` 与 `scripts/validate_verification_receipt.mjs`
只保留项目兼容 CLI 和导出接口。项目策略、业务映射和平台支持仍由本仓拥有，
不得从开发者 home 或浮动 `main` 导入。

所有聚焦 `tests/research_web/` 的 Python catalog 必须带 `--confcutdir=tests/research_web`，与 GitHub
Research Web Checks 使用同一测试边界。这样本机 `.env`、根 `tests/conftest.py` 的兼容平台数据库
fixture 和旧平台依赖不会污染 Research Web 验收；根 conftest 与非 Research Web 测试本身保持不变。

### L0-L4 分层

| 等级 | 最小验收语义 | 典型证据 |
| --- | --- | --- |
| L0 | 静态合法性 | syntax、format/lint、JSON/config、文档治理、生成索引 |
| L1 | 修改模块局部单元 | 与变更组件直接映射的测试 |
| L2 | 上下游依赖闭包 | 架构约束、直接接口与依赖链测试 |
| L3 | 相关关键路径 smoke | 跨越本次边界的最短 API/runtime/user 路径 |
| L4 | 完整相关验收 | full relevant suite/build、交付与必需平台/CI 门 |

`requiredLevel` 是完整 changed set 的最高必要等级；`validationsByLevel` 是实际执行真源。等级是累积责任，但不会凭空加入不相关平台门。Web-only 的 L4 仍不能伪称已执行桌面 Windows 验收；只有规划器实际输出的外部门才进入回执。

### Component × Risk × Platform

每次迭代必须读取并保留：

- `changeSummary` 与 `changedFiles`：改了什么；
- `components`、`impact` 与 `reasons`：影响组件、耦合和边界；
- `platforms`：`generic`、`linux`、`macos`、`windows`、`cross-platform` 或 `real-machine-required`；
- `validationsByLevel`：最能证明影响的最小测试、文档和外部门；
- `escalations` 与 `uncoveredRisks`：为何扩大、仍未覆盖什么。

多个高耦合模块由策略自动提升到至少 L3。公开契约、schema/config、核心抽象/共享工具、数据模型/迁移、依赖、CI、安全、桌面、发布和未知边界保持 L4/fail-closed；parser、workflow 和 agent orchestration 等已知关键链至少 L3。具体路径与命令只在策略中维护，本文不复制。

### 执行、升级与回执

按 L0→`requiredLevel` 执行输出项，并为每个实际检查记录状态、耗时和证据路径。局部失败后用 `--signal validation_failure` 重新规划；非预期行为用 `--signal unexpected_behavior`。两种 signal 均逐级扩大范围并保留升级原因。

Planner schema v3 将验证投影为三个 lane：`local` 是执行者本地运行的 merge validation，`ci` 是 GitHub runner merge gate，`realMachine` 是真实设备 release gate。macOS 本地通过不能替代 macOS CI，Windows CI 也不能替代 Windows 实机。

最终 receipt schema v2 必须包含变更摘要、精确 changed set、组件/平台、计划/实际等级、影响判断、`executed`、`external`、`realMachine`、`mergeReady`、`releaseReady`、`uncoveredRisks` 与升级决定，然后运行：

```bash
node scripts/validate_verification_receipt.mjs --project . \
  --plan <plan-json> \
  --receipt <receipt-json>
```

总回执校验失败就不是总体验收完成。已选中的 merge gate 不得写成 `NOT_REQUIRED`；未运行时必须以 `NOT_RUN` 和对应未覆盖风险保留。旧 plan3/receipt2 的总结果为 `BLOCKED`；新 plan4/receipt3 按宿主判定 `result`/`hostAcceptance`，可同时为 `PASS` 与 `aggregateAcceptance=NOT_READY`、`mergeReady=false`。不能用本机检查冒充 CI/平台证据，也不能从宿主 PASS 推导跨平台发布。

规范状态只有：`PASS`、`FAIL`、`SKIPPED`、`NOT_REQUIRED`、`NOT_RUN`、`BLOCKED`、`MANUAL_REQUIRED`。选中的必需 gate 只有 `PASS` 是正向证明；`NOT_REQUIRED` 只能描述未选择的范围，不能用于已选 gate。Windows CI 为 `NOT_RUN` 时 `mergeReady=false`；Windows CI 为 `PASS` 而真实 Windows 安装为 `MANUAL_REQUIRED` 时，可以保持 merge-ready，但 `releaseReady=false`，两层证据不得合并为单一 “Windows PASS”。

计划必须覆盖完整 changed set，并按最高风险合并。未知路径不能降级；非法策略、符号链接或越界路径必须先失败，不能退回猜测计划。

普通 `app/research_web/` 与 `app/web/` Web-only 改动只选择相关 Web、文档与轻量 CI 门，desktop、Windows、Tauri、sidecar 和 installer 门数量必须为 0。共享安装/runtime、Windows launcher、本机集成和路径/编码/进程边界会让 Router 选择 Windows Web CI gate；该 gate 仅由 Windows 真机对 exact SHA 手动 dispatch，Mac PR/push 不自动执行。只有桌面专属路径才附加原生 macOS/Windows Desktop gate 与 [`desktop_packaging.md`](desktop_packaging.md) 的发布前实机门。

Research Web 框架的 backend、renderer 与已登记测试按组件影响合并；单个 renderer 可停在局部闭包，backend+renderer 等高耦合跨模块集合自动扩大到依赖和 smoke 闭包。其他未登记测试继续 fail closed，不能用通用测试目录规则批量降级。

`app/research_web/datahub/` subtree 由全局 delegated namespace 机制交给 namespace owners：只有策略显式 allowlist 的公共 Provider 才能使用 L1-L3 专项闭包。多个 delegated prefixes 同时命中时只采用最长 prefix；owner 只能由该 namespace 内的正向 `match.files` 或 `match.prefixes` 建立，`segments`、`suffixes` 和 namespace 外的父 prefix 都不算 owner。命中 delegated namespace 后只有这些 owner rules 参与匹配；没有 owner 接住时必须回到 L4 fallback。Broker、contracts、security、snapshots、专业 Provider 和未来新增路径都不能被通用目录、segment 或 suffix 规则降级。

Asset Workbench UI 与 backend 使用彼此独立的专项规则。公共 Provider 与 UI 同时变化会形成两个 high-coupling impacts，自动提升到 L3，并执行覆盖 API、快照与呈现的资产观察 smoke；这不会扩大到桌面平台门。

## 桌面端例外（Desktop exception）

worktree 只隔离文件冲突，绝不取代桌面端原生 Windows CI，也不能取代真实 Windows 安装级烟测。凡影响 `src-tauri/`、`desktop/`、`scripts/desktop/`、sidecar、桌面配置或路径、安装包、自动更新、Excel/Wind 集成的改动，都必须以 [`desktop_packaging.md`](desktop_packaging.md) 的跨平台开发与发布验证流程为准。

当前产品迭代阶段为 **Web-only**。仅修改 `app/web/`、`app/research_web/`、通用 Web API/Runtime、共享 Python/Node 依赖或 Web 文档时，不进入桌面端例外，也不运行 sidecar、Tauri、安装包或原生桌面 CI。只有用户明确重新开启桌面工作，或任务直接修改 `src-tauri/`、`desktop/`、`scripts/desktop/`、`services/desktop_platform/` 等桌面专属路径时，才恢复下列桌面验收。

交付时按平台任务分配以下不可省略的验收范围；Mac 任务不等待 Windows 任务：

1. Windows 真机任务负责的原生 Windows CI 至少覆盖依赖安装、Python sidecar（`.exe`）构建、Tauri Windows 安装包构建、真实 PostgreSQL + pgvector 的 `ready` `/health` 检查，以及数据库不可达时的 `setup_required` `/health` 检查。
2. MacBook Pro 任务负责的原生 macOS CI 必须完成对应平台的 sidecar 与桌面包构建，并验证 `ready` 和 `setup_required` 的 `/health` 契约。
3. Windows 平台发版前，由 Windows 真机任务在真实 Windows 设备上验证 CI 产物的安装、卸载、升级、主窗口、sidecar、`/health`、用户数据目录和日志；涉及 Excel/Wind、系统权限或自动更新时，还须验证相应功能。

macOS 本地运行或隔离 worktree 都不能证明 Windows 可用。

## 证据与交接（Evidence and handoff）

Docker 构建与验收任务的完成检查必须包含资源收尾：临时资源使用
`research_workbench_entrypoint.docker_resources.ResourceSession`；成功、失败及正常中断均验证无遗留。
正式资源保持持久身份与数据；遗留清理先预览、逐项核对证据并保护有效安装及上一接受镜像。
涉及数据卷时必须归档、校验并实际恢复验证。回执记录已删除、已缺席、失败及剩余对象，
同时记录前后实际 Docker 占用；共享层大小不相加，未知归属资源与构建缓存保留。

交接应让接手者无需猜测即可复核结果，至少包含：

- 任务范围和未触及的边界；
- 修改文件、简洁 diff 摘要，以及 worktree 时的路径和分支；
- 实际运行的验证命令和结果，或浏览器检查结果；
- 未运行的验证、环境限制和风险；
- 后续集成步骤、依赖的 CI 或人工验收责任人。

不得将未运行的检查写成已验证。后台或远程任务必须报告可审阅的 diff 或结论，并保留未验证约束；涉及秘密、破坏性操作、发版决定或需要持续设计判断时，必须回到可交互的人工决策流程。

## 示例（Examples）

- 修正文档中的单个链接并立即确认渲染：使用本地快环，交付检查命令与简洁 diff。
- 为独立功能修改多份配置和测试：使用独立 worktree，交付 worktree 路径、分支、针对性测试和合并计划。
- 分析失败的 Windows CI 日志并提出有界修复：可用后台/远程执行，交付日志范围、分析报告、修复 diff、运行命令及未在真实 Windows 复测的限制。
- 修改 Tauri sidecar 或 Wind/Excel 集成：Mac 任务完成 macOS 验收后交接 Windows 真机任务；Windows 任务负责原生 Windows CI 和 Windows 发版前的安装级烟测，不阻塞 Mac 任务完成。
- 只修改 Research Web 页面、Web API 或 Runtime：按 Web 测试与项目约束交付，不运行 Desktop Verify。
