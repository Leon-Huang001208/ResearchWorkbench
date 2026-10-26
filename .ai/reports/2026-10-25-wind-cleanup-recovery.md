# Wind 清理未确认恢复：证据与安全构件

## 范围与现场

macOS Mac mini，Web/Native 恢复能力修复。原真实周报在 Wind Excel 清理失败后进入保护状态；原 `verify_primary` 返回 `research_active_or_unknown`，Host `active=null`，Native 活动研究为零。普通维护必须继续拒绝此状态。

用户已授权同版重启及一次新历史验收，随后要求执行恢复缺口的下一步修复。这不授权强杀、清除保护标记、修改 Excel/Wind 工作簿、重放未知模型请求或开启定时。

源码 worktree 基线：`7408e1d3aa33e4b7dc4ed1bb74e1f3e9d1a790b4`。受管 Git 检查实际通过；本任务 Harness 已开始。生产仍独立保留，未运行本任务服务命令。

## 根因与边界

`worker_activity.source_futures` 在 Wind poisoned 时先抛异常，Host 只有归约后的未知值，无法区分 Future 仍运行和 Future 已结束但外部清理未确认。Native 空列表不能补成全部 Host 工作已结束。

原 `_stop_owned_probe` 超时后会升级为 SIGKILL；正常关闭钩子还会取消后台工作。因此普通 restart 不能被描述为无强杀、无业务副作用的恢复事务。

旧常驻的不可变 `controller.pyz` 不认识新的恢复 journal。只改新源码 controller guard 不足以约束旧 artifact；不得伪造旧 transaction 或暗换控制器及其哈希。

## 本轮实施状态

已完成本机源码验证及两阶段独立评审：逐项活动见证、严格只读维护 preflight、无信号升级的私有停止构件。普通活动/部署/recover 门保持；旧 Host 缺见证必须拒绝。没有 apply 入口，preflight 不能证明可执行恢复。

完整有 journal/BirthFence 的同版恢复事务、控制器兼容迁移和旧现场恢复仍未完成，不得以本轮源码/测试/CI替代。

## 验证账本

- 真实原维护拒绝已保留于私有操作日志：`same-version-readonly-gate-result.json`；它是原流程失败证据，不是新源码通过证据。
- 旧运行工作区 58 文件和旧 Native 输入 59 文件重新核对，全部字节相同。仅认证该范围，不认证恢复执行。
- 新源码 RED/GREEN 保留缺字段、只读锁创建、晚到状态、WAL sidecar、FIFO 及类型错误的原失败；最终八模块 592 passed（8.78 秒），研究协议 81 passed（0.37 秒），最终旧保全/gateway/固定 profile 四模块 2838 passed（261.49 秒）。用例有重叠，不能相加为独立覆盖数。
- 最终 12 个 Python 文件的 Ruff、Black、isort 通过；七个源码文件 Mypy 无错误。Router JavaScript 230 passed；文档治理、完整源变更约束与生成索引检查通过。最终候选的 Git 绑定 Router/回执及远端 CI 仍由交付日志另行认证，本报告不提前将待运行 CI 标为通过。
- 独立规格、Python 质量评审均 APPROVED；修复并复审了缺 active、档案隐式创建锁、SQLite 只读仍创建 sidecar、FIFO 阻塞和活动归约不一致。严格档案路径只接收可安全读取的 rollback 格式，在内存中保留原账户/版本/完整性检查，普通默认路径保持。
- 最终矩阵第一次重跑的自有测试进程 PID 56805 退出 139，未有完整 JUnit，不计通过。macOS 崩溃报告匹配该 PID，故障栈在辅助器定时 faulthandler 转储线程；原脚本、完整失败输出及崩溃原件保留。移除仅用于导入排查的 25 秒定时转储后，相同四模块完整通过；没有删除用例、断言或改变产品代码来回避该失败。
- 实际运行入口为任务 `logs/wind-recovery/run_offline_tests.py`（Office 构造失败哨兵），pytest 使用 `--confcutdir=tests/research_web -q -o addopts= -p pytest_asyncio.plugin`，各模块与 JUnit 分别保存在 `final-local.*`、`protocol.*`、`final-preservation-profiles-retry.*`。完整环境和命令保存在任务日志，不安装或修改生产依赖。
- 实际新只读预检对旧 b800 返回 `blocked/wind_cleanup_activity_unverified`；这验证缺证拒绝，不认证恢复或同版重启成功。
- 生产取数、新 DSH 请求、Word/认证下载、正式定稿及日程启用：未执行。
- Windows/Linux 原生验收：NOT_RUN；通用 Ubuntu 仓库检查不表示 Linux 产品验证。

## 后续硬门

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"只向原resident状态增加无秘密分项观察，不增加HTTP路由或执行恢复；原Host与Native节点及未知拒绝边界保持。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"原SDK worker内部区分Future与清理状态，不新增采集、来源、数据根或快照格式；原DataHub和唯一DSH的数据边保持。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"离线测试和受管交付补证不会执行服务、供应商或模型，原CI节点与平台归属不变，现场恢复仍独立阻断。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"只读预检复用原账号集合和完整保全比较，严格读取不得创建锁或SQLite文件，不新增租户执行权限或控制器事务。","diagrams":[]} -->
<!-- architecture-review {"group":"dossiers","structure":"unchanged","reason":"仅为原档案保全增加显式禁止创建的读取方式，旧调用默认行为与档案授权删除保护保持，不新增档案存储或扫描执行。","diagrams":[]} -->

完整事务须证明精确同版本和安装身份、真实全部分项见证、Native 与全账号后台无活动，并在三锁/BirthFence 下再次验证；旧进程缺证仍拒绝。仅向精确 owned PID 发送一次单 PID SIGTERM，不重复、不升级，不走旧强杀/回滚路径。失败保留可恢复记录与阻断；保全或身份不符不启动。新增控制器及具体部署版本须重新评审、CI并取得相应授权。
