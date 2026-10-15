# macOS resident 自动部署任务

宿主：Mac mini/macOS；任务：功能开发；范围：Native登录后常驻、exact-tree交付准入、空闲切换、回滚。
用户明确保留FileVault，登录后自动运行；不新增依赖、不重启、不迁移数据、不调用模型。

实现：固定stdlib控制器artifact、LaunchAgent60秒轮询；GitHub与受管review/delivery共同准入。
累计兼容清单限制自动升级；准入共享锁覆盖HTTP/研究/Automation，更新独占锁先于原lifecycle锁。
固定生产checkout/venv/8088/3081，新旧wheel来源绑定；journal先于停机且fsync目录。
候选失败恢复旧源码/wheel/manifest，data/Keychain不恢复覆盖；失败SHA独立隔离，网络失败不清除。

本地离线故障注入：候选启动失败回滚、排队/原生活动延后、崩溃恢复与恢复失败保留栅栏、
跨进程锁、失效review及其他CI树拒绝。真实运行/CI/激活证据在本任务私有logs和Git受管回执归档。
本报告是实现检查点，不把未取得的CI、launchd或真实重启验收标为PASS。
Windows/Linux/Docker resident未启用；真实重启登录、真实模型生成为NOT_RUN。

<!-- architecture-review {"group": "dual-runtime", "structure": "unchanged", "reason": "同一Mac Native部署节点与原Web/DSH进程不变；新增短时登录管理程序细化既有管理入口，Docker图节点与模式互斥边界不变。", "diagrams": []} -->

<!-- architecture-review {"group": "research-api", "structure": "unchanged", "reason": "现有Host增加只读管理投影和维护503；仍在同一API节点、精确Host/Origin及DSH边界内，没有新增服务或数据通道。", "diagrams": []} -->

<!-- architecture-review {"group": "runtime", "structure": "unchanged", "reason": "研究协议与唯一DSH执行循环不变；复用现有同根生命周期lease并在管理入口补准入锁，数据与凭据原位保留。", "diagrams": []} -->

<!-- architecture-review {"group": "automations", "structure": "unchanged", "reason": "沿既有scheduler和ResearchService增加共享准入，不创建新队列或调度节点；维护期间等待，恢复及执行归属不变。", "diagrams": []} -->

<!-- architecture-review {"group": "verification-workflow", "structure": "unchanged", "reason": "原受管PR交付和三个工作流不变，新增只读消费精确树证据和同job离线回归；未创建独立CI或发布通道。", "diagrams": []} -->

已使用真实PR117只读核对GitHub三工作流和实际checkout tree，准入结果匹配bbb110c；此证据只验证验证器，不认证本任务候选。

本地组合回归初跑1207 PASS/1 FAIL（511.44秒）；唯一失败在未改master同样复现，为缺endpoint的测试漏计默认常驻端口。测试现同时识别原指定pair与默认pair上的真实产品writer，保留unknown时拒绝及无写入断言，不改运行时安全门。复测与最终组合证据分别保存。
