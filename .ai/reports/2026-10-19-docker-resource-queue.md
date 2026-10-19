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
