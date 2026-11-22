# 市场联合 Native V2 切换完成时限

宿主：macOS Mac mini；任务类型：功能修复及已授权Native部署。Mac本机、原三CI及macos-15安装为本轮门；
其他原生设备不冒充通过。初次实际部署PR280合并9a97168e，原操作员退出2／378.386秒，
`git switch --detach` 30秒超时。两仓库HEAD均在13:25:31写入目标，13:26:19恢复a76ecfdf；
原回滚返回preserved=true，双事务journal已清，私网ready/a76、MCP严格false及两个账号采集日程关闭。
旧目标隔离文件和原运行日志保留，不同SHA须正常源交付。隔离网关同common、原hook未改，
复测checkout 0.236秒正常，未重现现场尾部耗时；具体hook原因未知。已按身份退休该临时工作树。

V2目标及恢复切换独立120秒，仍走原Git与hook；切后核验真实HEAD和干净状态，再进入安装wheel。
失败记录角色、方向、耗时及稳定错误码，沿原事务回滚，不吞错误；其他profile、通用30秒命令门、
三锁、BirthFence、所有账号保全、资格、采集/MCP关闭和历史恢复身份保持。P3产品cd09与已接受a76均不变。
实际30秒失败证据与定点模拟分开：模拟45秒两个HEAD已写时旧install拒绝；新事务测试覆盖45秒通过、
121秒仍回滚并保全。最终本地、独评、同候选三CI及实际私网验收另证，不能用回归模拟宣称已上线。

Product-Progress: not-required — 仅修复既有常驻部署中的有界等待及诊断，不新增用户页面、数据来源、配置或功能。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"同一Native事务及两代码仓库，V2只改切换命令时限和切后检查，保全和恢复拓扑不变。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原测试夹具与原三CI追加两例，不增加作业、执行节点、依赖或权限。","diagrams":["08-iteration-docs"]} -->

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"原账号网关的Git切换在同一个Native事务内延长有界完成等待，权限、保全、同源、MCP与日程校验不变。","diagrams":["01-deployment"]} -->
