# 财经日历切换保留既有 MCP（2026-11-08）

macOS Native，部署操作员开发。产品固定于已通过 CI 的 `79102a95`，现有主实例和网关均为
`1315d11a`。配置与本机／私网健康观测均为 MCP 启用；主实例活动读数为明确 False。
用户授权保留原 MCP 状态、授权和凭据的前进与回滚合同，并授权合格后直接部署。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅在既有 macOS Native 主实例与私网网关 v4 事务登记固定产品和回滚保全；无新进程、接口、依赖或容器拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"沿原双健康和账户库哈希检查，新增特定模式的保留现有 MCP 值与明确失败边界；原认证、运行节点和数据路径不变。","diagrams":[]} -->

新 profile 复用 market-daily 的原路径并集冻结、关闭事件日程、空闲/真实 Native 检查、三锁和
恢复事务。旧 profile 的 MCP 关闭门保持。新 profile 对配置和本地／私网健康严格比较原布尔值；
账户数据库的已有保全哈希包括 MCP 授权和令牌摘要，存在未结 SQLite sidecar 时拒绝认证。

首批无夹具 RED 已复现：新 profile 和 health 合同在实现前缺失。最终独立评审、同候选 CI、
Mac mini 切换及业务验收分别取证；本报告不作为生产切换成功的证明。

独立评审发现前版网关复核与 SQLite 锁后的账户保全复核需前移。已在
`preparing` 恢复解除围栏前和初次执行信号前，分别于 BirthFence 的排他锁内复验。
复审确认健康探测无 Cookie、不会进入账户数据库事务；状态不符时保留网关 journal。
44 个新 profile 离线用例及新增的 3 个边界用例实际通过，含两种 MCP 原值和回滚、
OAuth 数据漂移及未结 sidecar 的拒绝反例。首次用两个未展开节点选择器得到三个通过结果，
回执拒绝绑定；保留原件，改用三项完整节点身份重新验证并回收成功批次。
