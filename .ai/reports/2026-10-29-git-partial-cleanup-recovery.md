# Git 部分收尾阻断修复

macOS 功能修复；在新 Developer 主仓派生的隔离 worktree 实现。用户明确授权继续解决
部署及 Git 收尾，并保留全部安全门；原聊天负责维护执行器，本任务不修改其 WIP。

## 实际失败与根因

PR248 的候选834dc02经三 CI、独评及实际 checkout/tree 复核后合并为84b5dab8。
正式 cleanup 已备份实际恢复成功、退休两个工作树和 feature 分支，但本地 integration
分支删除失败，控制器未原子保存最终 cleanup 状态；旧入口只允许 cleaned 状态的恢复，
因此不能对这个 ci_passed/pending 状态执行正规对账。

真实恢复点bbc8f20c-c9f5-4d19-975b-406023ff6c2d保留。新分支先在隔离真实 Git/v2
恢复夹具复现 CLOSEOUT_RECOVERY_NOT_PENDING，再补受控 partial_cleanup 路径。
不改历史 PASS，不手改现场 cleanup 字段，不修改全局 leon-engineering 安装。

## 改动及边界

沿现有 closeout-recover 复用身份、CI/独评/分支保护、备份实际还原、引用保全和资源
再验证。全部工作树必须已退休；本地和远端均按准确 SHA 条件删除。远端 GraphQL
updateRefs 的 beforeOid/零 afterOid/force:false 已经官方文档及在线 schema 核对。
原 proof 不改，新增原 delivery/intent 与恢复 epoch，完成证书绑定实际字节并最后提交。
读控制元数据使用非阻塞打开，FIFO 先拒绝类型，避免检查前挂住。

独评发现并已修补：远端等待期间 worktree 重现、本地引用先删后拒绝、实际 delivery
并发更新被旧对象掩盖、完成态 preview 隐式 fetch/漏 fsck，以及资源复核后的保全
引用丢失。每项均保留真实负控，不能把 fsck 通过当成引用保全。

## 验证及当前状态

最终项目Node24.19.0下Git与资源收尾全套114项通过（184.31秒），Router L4四模块
113项通过（5.86秒），文档治理、Python索引及完整changed-set项目约束通过。
专项原失败与每轮日志保留在 logs/partial-cleanup。独评已检查引用/receipt竞态及资源
完成后证书提交前中断；最终提交还须绑定候选评审和适用CI，再通过正式入口实际恢复。
本任务没有调用模型或供应商，没有部署或修改业务数据。

首候选61f55c42的Project Constraints通过后，应用前审计确认框架验证器隐式fetch
需要继承普通交付的私有Git shim；已补同一进程内固定原生Git/过滤prune/恢复PATH，
真实夹具验证通过；修补后Git/收尾全套115项通过（168.38秒）、L4合同113项通过
（5.50秒），均无跳过。旧任务只读预览确认仅余本地/远端同SHA integration引用。
修补将走同PR249正常repair并重新绑定完整验证/独评/CI，不提升
首候选结果给修补候选；预览仍不创建shim、不fetch。

维护线源 WIP 已由受管同 common 原入口从新 cwd 完成 check/backup/actual restore：
7c2c7997-a47e-4605-941f-fef603da8fb4，HEAD4c72ed43、6161 tracked、70 untracked、
217 refs，fsck PASS。原目录和其他工作树仍保护；该恢复点不等于执行器/现场准入完成。

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"扩展既有Git收尾恢复事务，复用同仓库锁/备份/CI/资源复核，不新增RWB服务、业务API或执行引擎。","diagrams":[]} -->
