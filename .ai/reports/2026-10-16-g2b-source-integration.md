# G2B 当前主线源码集成

宿主 macOS，任务为功能集成；基线70bb4cba8cd119be9b0564206c9d493d5ecc86e3，来源PR104 a4ddda36464100a9bdbbf4e177603511d564a5a3。
不合并、不发布、不改日常实例、不迁移数据库、不调用真实模型，不停止其他实例。原PR104草稿和历史制品/报告均保留。

29处文件冲突已解；保留resident与G2B双准入、主线Protocol/API和Hot。runtime固定值转canonical JSON及封存副本，Hot依赖/SQL只封存或哈希；发现Hot状态即拒绝晋级。无新依赖。

RED：4 failed/14 passed，复现DSH与Hot发布合同缺口。GREEN：23 passed；双栅栏7 passed；API专项5 passed。初次pytest受父目录SQLAlchemy夹具缺依赖影响；随后使用与现有Web CI相同的confcutdir隔离，不安装包、不放宽Web测试。完整本地闭包及资源回执待记录。

当前源码验收进行中；Docker镜像/真实演练、GitHub CI、跨平台和真实模型均NOT_RUN，不宣称mergeReady或releaseReady。日志：logs/g2b-source-integration/。

<!-- architecture-review {"group": "dual-runtime", "structure": "unchanged", "reason": "复用现有管理员容器、Host、唯一DSH和已有报告/Automation边界，仅增加冻结制品及私有维护契约；保留主线resident与Hot边界，不新增服务、持久库或拓扑节点。当前任务仅本地源码集成，图源和已有视觉回执未被旧分支覆盖，新的运行验收保持未执行。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "复用现有管理员容器、Host、唯一DSH和已有报告/Automation边界，仅增加冻结制品及私有维护契约；保留主线resident与Hot边界，不新增服务、持久库或拓扑节点。当前任务仅本地源码集成，图源和已有视觉回执未被旧分支覆盖，新的运行验收保持未执行。", "diagrams": []} -->

<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "复用现有管理员容器、Host、唯一DSH和已有报告/Automation边界，仅增加冻结制品及私有维护契约；保留主线resident与Hot边界，不新增服务、持久库或拓扑节点。当前任务仅本地源码集成，图源和已有视觉回执未被旧分支覆盖，新的运行验收保持未执行。", "diagrams": []} -->

<!-- architecture-review {"group": "report-workflows", "structure": "unchanged", "reason": "复用现有管理员容器、Host、唯一DSH和已有报告/Automation边界，仅增加冻结制品及私有维护契约；保留主线resident与Hot边界，不新增服务、持久库或拓扑节点。当前任务仅本地源码集成，图源和已有视觉回执未被旧分支覆盖，新的运行验收保持未执行。", "diagrams": []} -->

## 源码检查点

发布/维护专项最终26 PASS（包含独立封存控制器加载与缺失合同拒绝），API专项5 PASS；129项JavaScript治理与Docker合同通过。Ruff/Black/isort全部变更Python文件通过；mypy候选15错误与未修改master逐条相同，新增0，不称类型检查PASS。完整13模块Python闭包仍运行，结果另记日志和报告检查点。

Docker只读预算：VM8319238144 bytes，其他运行实例限额合计3724541952 bytes，所需builder5368709120 bytes，余量不足，当前新镜像/真实演练BLOCKED。没有创建容器、卷或镜像。Compose初次缺少显式安装路径变量，随后仅用合成临时路径完成config --quiet PASS；不使用现有实例数据。

独立Python复核当前树无已证实P1/P2，最终commit绑定复核待源码提交。历史报告文件保留原内容，当前receipt不得复用其PASS。
