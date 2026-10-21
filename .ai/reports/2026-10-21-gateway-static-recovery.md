# Mac mini 账号菜单部署与静态网关恢复修复

宿主macOS，功能修复及受控部署；本平台验收，其他平台原生产品保持NOT_RUN。

用户授权部署账号菜单并保全数据/模型/运行研究。实时primary已由既有resident更新到4d011a0，网关仍21d777c。
独立审查发现一次性review callback不能改变旧不可变恢复包的PRODUCT门，属于P1；该脚本apply已硬阻断且从未执行。

正式修复增加显式apply-ui：最新已审核工具C和已验收产品分别qualify；产品必须等于当前primary。
业务只切产品，工具不写入主实例；两段受限Git差异/blob及原所有事务门保持，新version 2包冻结独立恢复代码。

RED：新增7项scope合同先失败；旧事务52项基线通过。新测试保留真实旧recover函数，验证旧helper先拒绝v2；
覆盖六阶段恢复、独立解释器/冻结artifact、篡改、错误helper及apply入口资格/基线/活动/晚到master变更和启动/健康/保全失败。
失败尝试与fixture修正均留日志，不伪报通过。已有测试/格式工具从现存环境读取，未安装新依赖。

独立Python审查未发现P1/P2，94项部署恢复回归通过；Ruff、Black、isort和模块mypy通过。112项治理/架构JS回归通过。
扩大运行的首次4项异步失败源于禁用插件自动加载，随后显式加载现存pytest_asyncio重跑，160项全部通过（1项既有依赖弃用警告）；保留原失败日志。
精确候选CI及真实部署待执行；不因源码或离线测试宣称已部署。
部署前再次核对空闲；活动/未知延后，发信号后异常保留journal并等待正确helper恢复，不强停研究或回写业务数据。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"复用既有网关、准入锁、出生栅栏、排空、journal和独立恢复角色；仅分离工具/产品资格并给既有恢复包增加版本身份，不新增研究循环、数据根或自动兼容范围。","diagrams":[]} -->

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"保留原primary附接、用户池、身份与数据隔离；静态部署只给既有恢复事务增加独立工具和artifact身份，沿用原空闲、排空和保全门，不新增运行时或改变用户请求路由。","diagrams":[]} -->
