# Mac mini 网关安全升级

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"在原管理平面内补显式空池网关事务和恢复，不新增部署节点、研究引擎或业务数据流，沿原primary锁和网关LaunchAgent。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"保留原primary附接与私有pool拓扑，只在既有边界增加全请求冻结及显式安全更新，不迁移账号、会话或凭据。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅在原Research Web Checks Python步骤增加网关事务回归，不新增job、runner或执行拓扑，其他平台交接不变。","diagrams":[]} -->

宿主 macOS / Web 管理平面功能修复。隔离基线6c4ac79bcf03fb36ffbe9c1c40a647b8e8a34556。用户明确授权修复常驻安全阻断并部署，保留全部数据和会话，活动/未知等待，失败自动回滚；无付费模型或依赖安装。

先补全请求冻结失败回归（GET原返回401而非503）及缺失出生栅栏模块回归。实现SQLite EX +登记inode后no-replace槽位占用、普通SIGTERM完整排空、持久冻结目标启动、匹配当前primary的旧代码回滚和独立不可变恢复agent。旧自动白名单、baseline、controller.pyz及primary wheel保持；当前primary已由另一个常驻更新推进到6c，含Claw修复及删除示例，故不重复切换primary。

离线目标回归覆盖竞争赢家、未知控制、DB sidecar、journal所有权、半释放恢复、artifact复用/篡改、超时无强杀、候选失败恢复及分阶段重入。后续最终测试、独立评审、同树CI和生产结果分开记录；未执行项不称PASS。日志不含问题、回答或模型密钥。Windows/Linux原生NOT_RUN，非本Mac任务前置。

本机最终定点Python及协议224 PASS；架构/治理112 PASS、验证路由117 PASS；ruff/black/isort与完整路径项目约束、文档治理、Python索引检查通过。真实隔离uvicorn子进程证明两次SIGTERM仍等待慢HTTP及线程完整200后退出；实际RuntimePool._record竞争证明零spawn/key/dispose。独立Python源码复审APPROVE、无剩余CRITICAL/HIGH，源码摘要与最终提交另由交付回执绑定。此前lint和README回执长度失败已修正，完整规划保持L4。
