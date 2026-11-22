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

## 最终可执行本地结果

源码候选580a7ea9823e13aa3e9499143fdb05e851b4ca7b，tree89c12ef8bd5e443c5309ef45adf317838f9be13e，独立Python复核无已证实P1/P2。最终报告检查点仅修改本文，不改变产品源码。

- 13个Python模块完整收集765，762 PASS、3明确opt-in/platform SKIP，476.24秒；JUnit为logs/g2b-source-integration/python-closure.xml。跳过项：真实Keychain跨进程、owned固定DSH冷恢复、原生Linux私有stdio桥，不认证这些能力。
- 该闭包启动后仅将release.py归档读取循环改为语义等价while以消除新增类型诊断；最终源码SHA另补跑全部发布/维护和相关API：31 PASS、201 deselected，13.06秒，final-sha-targeted.xml。未重复未改动的大套件，来源与定点补跑分别留证。
- JavaScript治理与Docker合同129 PASS；完整changed-set项目约束、文档治理、生成API Atlas/索引通过。变更Python的Ruff/Black/isort通过；mypy 15项与master逐条相同，新增0，整体类型检查保持FAIL。无规则或测试削弱。
- Compose使用合成临时路径只读校验PASS；sh -n通过。没有创建/启动/停止Docker资源，也没有连接PG或真实模型。

源码本地集成完成；当前新镜像构建、stage及晋级/回退演练为BLOCKED（构建内存窗口不足）；CI、Native干净安装、真实DSH/Keychain与Windows/Linux分别NOT_RUN。整体mergeReady=false、releaseReady=false。Hot存在状态目录（包括停止/未知/alias）继续拒绝发布，未来Hot停写/回滚证明不在本次迁移或授权范围。

当前任务不push、不更新/合并PR104，不改g2b-base或任何旧worktree、历史报告、五卷、镜像和封存制品；保留本任务本地分支/worktree以便后续资源窗口验收。正式Git绑定计划/回执保存在logs/g2b-source-integration/，不得把receipt结构有效误称产品通过。
