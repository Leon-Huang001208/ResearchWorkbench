# 已审升级的启动暂态核验

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"原Native联合事务在启动后最终核验内等待实际活动暂态消退，仍复用原Operations.verify和finish、三锁、BirthFence、安装lease与保全，不新增服务或恢复模式。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"保留原账号出生围栏、真实健康、权限和保全校验，仅在原reviewed模式最终verify_target/verify_previous遇MaintenanceBusy时有界等待，不新增账号或权限入口。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"正式GitSafety CLI将显式备份根交给原恢复点执行器，跨盘仍沿原校验流和v2去重；原Constraints完整GitSafety模块与Checks原维护分支覆盖确切改动，不新增作业或运行服务。","diagrams":[]} -->

用户随后明确授权优化备份并使用WorkDisk。正式GitSafety CLI新增`--backup-root`并向原执行
接口传递，WorkDisk在写入前按既有UUID/APFS/挂载点核验。跨设备直接走原校验流复制，
避免逐文件派生不可能成功的APFS克隆。保留原容量、源竞态、hash、独立恢复与v2去重。
旧内盘恢复点另按真实用途和引用退休，不移动历史未知材料。没有改HOME、凭据或resident路径。
CLI参数和跨设备复制的两个RED回归先失败、修复后通过。原Constraints完整GitSafety/容量
模块覆盖此变更；Checks沿原reviewed_upgrade_only补确切文件，未知/业务混入仍全量，三CI不变。

平台为macOS Mac mini；本次修复Native部署期间实际暴露的启动暂态。

现象：7a3e5c43部署启动两端后，Host短暂active=true，Native任务为空；稍后自行转false。
原最终核验立即返回recovery_required，下一次不可变监督器按原中断恢复回退primary，
造成待恢复的双端版本不同。现网已正式回滚到63a24daa，账号/业务保全通过且围栏已解除。
此前927f0999文档运行版与Native accepted/config63a24daa的记录差异也已通过真实代码恢复消除，
没有把未验版本写为accepted。7a3e5c43源码仍已合并，本次失败不记为上线成功。

修改仅在Operations.action的最终核验分支：reviewed-full-upgrade-v1遇MaintenanceBusy
最多30秒、每0.5秒重跑原完整verify。真正的忙/未知到期保持原异常和恢复语义；其他完整性
错误立即传播，其他profile、stop/install/finish、原锁、保全、依赖和固定DSH均不变。

RED：新增两个启动暂态回归在原实现均因MaintenanceBusy失败。GREEN：这两项及deadline、
旧profile、完整性拒绝、原排空与journal顺序共7项通过。首次GREEN以函数级node记录参数化
用例，实际7项通过但证据数量不一致；保留行政失败原件并按真实失败结果回收临时根，
随后明确列出7个完整node重跑通过，未改写原exitCode或PASS。

独立审查指出睡眠可能跨越deadline后仍启动核验，已修复剩余时间与唤醒后期限检查；
新增跨期限回归后8项定点通过，原真实Operations部署/失败恢复8项通过。
Ruff、Black、isort、架构与文档完整性、Python结构索引检查通过。

Web lock/runtime/安装入口不变；仍需原三CI及同候选Mac干净安装证明兼容。
真实重部署另证；Windows/Linux原生NOT_RUN，不调用供应商、模型或安装新依赖。
