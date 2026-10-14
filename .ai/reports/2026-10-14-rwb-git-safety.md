# RWB Git 防复发实施报告（2026-10-14）

状态：LOCAL_PASS，待最终合并候选及远端交付。本文记录提交时的本地证据；最终 CI、PR、合并和清理状态以本机受管交付账本及交付回执为准。宿主：macOS arm64；任务类型：开发工具维护。本任务没有产品运行时、服务部署或其他平台宿主启用变更。

## architecture-review

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅在既有 Project Constraints job 增加临时 Git 仓库测试步骤；验证通道、平台归属、runner、发布门与产品运行时结构均保持不变。","diagrams":[]} -->

入口属于项目工程工具，复用受管交付控制器与现有日志目录，不修改全局框架或产品执行引擎。Git common directory 是锁与任务账本的身份边界；提交、快照和工作区恢复证据存于本机独立私有备份根。静态检查和 Ubuntu fixture 不证明其他平台原生启用。

## 基线与边界

- 真实对象丢失原因仍未确定；既有隔离备份不删除、不恢复损坏引用。
- 已从最新 master 创建独立 bootstrap worktree；正式受管交付将在入口完成后接入。
- 已在 `~/.codex/backups/rwb-git-safety/rwb-git-safety-20261014-baseline/` 保存配置原值、引用、worktree、未跟踪文件哈希与服务 listener 基线。
- RWB 仓库本地 `gc.auto=0`、`maintenance.auto=false` 已应用；不修改系统 PATH、全局工程框架或系统调度任务。
- 不安装依赖、不执行 GC／prune／repack、不停止或更新常驻服务。恢复配置仅处理本任务两项值，不能覆盖其他任务的配置。

## 实际验证

- 文档治理、`git diff --check`：PASS。
- L4 通用架构／文档／Actions／仓库平台合同：110 tests PASS（实施中基线检查）。
- Python protocol smoke：54 PASS；使用已经存在的 macOS Python 3.12.13 测试环境，以 `PYTHONDONTWRITEBYTECODE=1`、禁 pytest cache 方式执行，没有安装或修改该环境。
- 现有 Router 的 L4 本地闭包：9 个 validation ID 全部 PASS，没有降低 unknown-boundary 路由。
- Git 安全目标测试：32 PASS；包含真正 bare+worktree 恢复、binary patches、untracked symlink、tree refs、共享配置、锁替换、ignored 数据及备份后新增数据拒绝、日志 hardlink/symlink/race 拒绝、其他仓库拒绝、PR exact-SHA 审查和 origin 变化拒绝。已安装共享控制器在 `type: module` 临时仓库真实 start→commit→prepare 验证 PASS，无 GitHub 调用。
- 独立规格评审、独立 JavaScript 质量评审：PASS。复现的两项规格与两项质量问题均已修复并重新评审；最终实现 SHA-256 为 `37cf6ed7b01da0460c05d8dace50875c396813eb94fdb588e17a80d0d1412a70`，目标测试 SHA-256 为 `1e84b2141e42d86d3632b2a56d7b289579cffc9700498194b479d7c07f380c72`。
- 首次真实 start 因私有 Node Git 转接继承仓库 ESM scope 失败，未创建交付分支或推送；已用 immutable CommonJS marker 修复，补 ESM fixture 与真实控制器临时仓库回归，并完成独立补丁复审。这属于新增入口的接入错误，不能据此归因旧 Git 对象丢失。
- 原仓库入口只读检查：PASS；Git 为 `/usr/bin/git`，完整 fsck PASS，未发现 native/repository lock，共用配置为 `0`／`false`，没有修改其他工作区或常驻服务。
- 最终合并候选、GitHub CI、PR、合并与安全清理：提交本文时 NOT_RUN，由后续实际账本记录；不把本地 PASS 冒充远端或其他宿主启用。Node20 本机 NOT_RUN，通用 CI 中真实执行目标测试。

## 剩余限制

仓库级入口锁不接管 Codex 内部或未使用入口的人工 Git 命令。暂停自动维护可能使对象库增长；维护和备份清理需另行安排。至少保留备份 30 天，不自动删除，既有隔离备份保留至明确授权。
