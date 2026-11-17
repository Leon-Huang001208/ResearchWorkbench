# 上线验收后的旧工作树退出

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅在原 Native resident 验收持久化后沿既有共享准入调用已登记 Git 源的白名单退役，不新增运行服务、端口、部署角色或 Docker 触发。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"在原 Project Constraints Git safety 步骤加入两组临时仓库回归，作业、runner、依赖和跨平台触发关系保持。","diagrams":[]} -->

2026-11-16。变更范围为 macOS Native 的交付管理入口。源码验收只记录合并及工作树待退出，
旧工作树由正式 Native 上线验收触发复核。退役流程与既有部署共享准入锁，不改变运行服务。
部署身份取自既有安装、验收、回滚包、受管 PID 和实际运行提交；源码已合并无法单独触发。

临时独立 Git 检出验证跟踪内容、权限、索引、工作树管理目录及可能持有独有提交的引用。
未跟踪内容、未处理的 ignored 文件、在用引用、iCloud 或作用域不明确的目录继续保留。
写入私有退役证明后仅移除本任务的已验证工作树，保留交付、必要验收和回滚材料以及 Git
历史。保护原先的完整备份恢复路径，退役不触发备份轮转。

历史预览以旧仓库中 37 项 CI 已通过且两棵旧工作树仍登记待清的交付为范围。37 个 PR 均已合并，
74 条路径记录中有 62 棵现存旧 iCloud 工作树。没有一项同时具备可绑定的上线验收及完整的
旧树恢复证明。本轮未清除历史工作树，未启用或改动现场常驻服务，Docker 上线接口保持待接入。

隔离验证覆盖真实 Git 工作树移除、忽略文件和未归并 reflog 拒绝、当前 Native 版本与回滚
材料复核，以及失败退役和上线回执隔离。平台、CI 与正式环境验收按各自的运行记录判定。
