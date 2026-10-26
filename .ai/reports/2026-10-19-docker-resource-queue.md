# Docker 持久构建队列与12GiB维护边界

宿主：Mac mini/macOS；任务：管理员功能开发；交付任务docker-resource-queue-20261019。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"管理员入口复用原builder和操作锁，持久队列由既有心跳恢复，不新增业务节点、生产部署通道或研究引擎，固定提交归档与新管理数据已同步五份模块文档。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅向原Research Web Checks同一Python步骤加入标准库离线队列回归，无新job runner包或平台dispatch，Mac负载和安装仍分别取证。","diagrams":[]} -->

## 实现与合同

新增只读capacity、按任务/worktree/SHA/参数去重的build --wait及resume/--next，保留旧纯Docker命令。
可选入口仅使用已声明Python3.12标准库与Git，无新包；CLI/数据/安全、安装、架构及预算文档同步。
队列原子保存请求/结果，共享锁只用于领取/对账或实际构建；通知去重与等锁分离。
从Git提交归档固定构建输入；legacy持锁重核stage预留及硬额度，身份核验后清理自己的builder。
不操作生产、他任务容器、未知锁或既有DSH候选，不降低5GiB builder/2GiB余量及20GiB缓存上限。

## 当前实际证据

首个RED为模块不存在的ImportError，随后实现；已保存修复前失败记录，不把它们标PASS。
首轮14项、扩展20项离线测试通过；真实capacity显示VM8319238144、运行上限3724541952、
构建+余量7516192768，总需求11240734720。实际开发容器约768KiB，Hot约160MiB，与硬上限分开。
独立Python评审发现可变构建输入、完成结果堵塞FIFO、锁交接清理归属、busy通知和stage预留竞态；均补修并待最终复核。

## 未完成项

Docker Desktop上限尚未调整，维护重启需独立明确授权且等待活动/未知任务退出；不得停止保护资源。
12GiB实际生效、指定候选冷构建/健康、30分钟混合负载及Mac安装CI为NOT_RUN；Windows/Linux原生NOT_RUN。
后续验证/审查/受管交付结果追加本报告，未观察到的步骤不写通过；源码交付与宿主激活分别记录。

## 验证追加

28项队列测试及相邻Docker管理员/协议合同合计146 PASS；相关10文件JavaScript合同247 PASS。
Ruff/Black/isort、单模块mypy、文档治理、Py文件索引及项目约束PASS；Router完整changed set为L4。
独立复审补出锁交接stage启动仍被当永久失败的问题，已映射为stage_active并用真实子进程日志路径覆盖三种准入竞态。
运行镜像与开发镜像均按不可变ID及revision复核，不以可变tag认证完成；构建输入归档不含未跟踪或并发编辑字节。
控制入口脚本也从提交归档执行；上下文准备/清理失败持久记录为blocked，不将已完成构建当作死请求重新执行。
用户已单独明确授权安全维护窗口内调整12GiB及必要恢复；当前两个受保护容器仍运行，窗口未成立，尚未修改设置或重启。
容量/维护方案及原配置备份在本自动化私有evidence/20261019-resource-queue目录，不能把授权当生效证据。

## 2026-10-26 中断续跑修复（本地，待独立评审）

宿主macOS/arm64，任务为既有管理员队列缺陷修复；本轮范围为Python本机离线验证。
原真实冷构建日志`evidence/20261026/original-job-build.log`第6188-6189行记录最终非root导入
`research_workbench_entrypoint.resident.admission`失败；保留的原上下文resident目录实际为0700。
根因是tar data过滤器清空目录mode，提取继承队列umask077；Docker COPY保留该模式。
修复在原data_filter安全检查之后仅将归档目录设0755，执行/普通文件位不变，私有父上下文0700不变。

原队列owner退出不能证明legacy子进程没有完成。缺少持久结果时重建可能重复真实已结束的构建。
持共享操作锁对账时，已退出owner且无结果的running请求改为blocked/build_outcome_unknown，
不再execute；锁仍由legacy持有时只报告operation_busy，live owner仍build_active，
有效failed/completed结果优先对账，源码改变仍invalidated/source_changed。
原真实队列、锁、日志、上下文均未手改；未伪造原构建结果，未启动Docker构建或停止服务。

RED：3失败27通过（2.68s），分别复现dead owner重建和077目录0700。
GREEN：35通过（0.93s）；含实际Git archive、嵌套包读/遍历权限、执行文件保留、私有上下文，
tar逃逸/外部符号链接/设备拒绝，真实短命helper进程及锁/持久结果恢复。
近邻队列+docker_manager合计72通过（0.73s）；Ruff/Black/isort、文档治理和Py索引通过。
检查均用`/opt/homebrew/bin/python3.12`，复用已授权qa-20261014/packages，未装依赖。
初次项目mypy因QA目录缺pydantic插件无法启动；无插件且skip imports的单模块mypy通过，
不以该定点检查替代项目配置门；随后复用主仓现有.venv/lib/python3.12/site-packages的pydantic，
项目配置及插件下`mypy --follow-imports=skip research_workbench_entrypoint/docker_build_queue.py`通过。
不加skip的项目mypy跨模块扫描超过145秒仍无结果，已停止本轮该检查进程，完整import扫描保持INCOMPLETE。
README复核回执更新，说明既有架构节点和图无变化理由。

证据目录：`/Users/leon/.codex/automations/dsh-fork/evidence/20261026-continuation/queue/`。
原主工作区在修复前及修复后tracked/index diff均为空；预存untracked内容未触碰。
本地修复不证明镜像构建、健康或30分钟混合负载通过；GitHub及Windows/Linux仍NOT_RUN。
未提交/push/prepare；独立评审、最新master集成及实际构建恢复由主任务继续。
本轮记录时间：2026-10-26T02:09:15Z。
