# 2026-10-23：档案与机会预警结构审阅

本轮以组合阅读检查点 `96657c68f925ec73f0ee5be41f3fdf27e96ea5c4` 及档案／扫描／小创合同核对模块边界，仅追加中央文档说明。源码、API inventory、CI清单与02模块／04资料图由主任务更新。个人SQLite仅保存元数据、引用和pin，原文保留原Store；Prompt-only交接继续进入唯一DSH；A股跟踪默认关闭且当前只重查冻结材料，不自动采集。

小创候选真实Registry身份未核验，保持unsupported；54子弹仅公开单价估算，真实价格核对、凭据、收费与常驻部署均未执行。归档和信号不提升原报告quality。Doctor／配置状态沿既有插件status，无合法安装不开放个人凭据配置。

最终候选的独立评审、相关离线验收、原通用仓库／同候选Mac CI及图源/HTML/收据由主任务绑定；本文只记录本轮结构判断，不宣称这些门通过。Windows／Linux与实际部署分别交接，不以文档更新代替设备或运行证据。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"新增资产档案和情报信号二级视图、独立档案控制器及Prompt发送前的冻结草稿状态，模块依赖需体现档案服务及来源读取边。","diagrams":["02-module-dependencies"]} -->

<!-- architecture-review {"group":"research-api","structure":"changed","reason":"新增账户绑定档案API及实际Prompt的结构化receipt字段，Host路由连接档案事务与原DSH读取分支，更新模块关系而不新增服务。","diagrams":["02-module-dependencies"]} -->

<!-- architecture-review {"group":"mcp-runtime","structure":"changed","reason":"受管插件新增固定候选凭据、18项预算状态及原件快照适配，transport token回显检查与辅助方法拒绝进入现有Host模块边界。","diagrams":["02-module-dependencies"]} -->

<!-- architecture-review {"group":"automations","structure":"changed","reason":"新增默认关闭的dossier_scan原生分支，锁定规则hash并确定性重查A股档案冻结资料，复用Automation而不增加调度进程。","diagrams":["02-module-dependencies"]} -->

<!-- architecture-review {"group":"files","structure":"changed","reason":"新增档案引用和pin的同事务保全及源永久删除栅栏，普通文件读取不得绕过dataset授权，源字节仍在既有文件和快照根。","diagrams":["02-module-dependencies","04-data-file-flow"]} -->

<!-- architecture-review {"group":"runtime","structure":"changed","reason":"新增仅实际Prompt可绑定的档案交接receipt与research_read_source句柄分支，沿既有Host鉴权和唯一DSH执行并保持原报告质量门。","diagrams":["02-module-dependencies"]} -->

<!-- architecture-review {"group":"datahub","structure":"changed","reason":"新增档案对既有冻结快照的引用、逐次授权和完整性读取，MCP原件亦复用Snapshots，扫描不采集且不把未准入结果当作数值事实。","diagrams":["02-module-dependencies","04-data-file-flow"]} -->

<!-- architecture-review {"group":"dossiers","structure":"changed","reason":"新增个人SQLite元数据、不可变修订、证据引用pin、成果关联和冻结交接，以及确定性扫描与跟踪意图状态；原文不进入新库。","diagrams":["02-module-dependencies"]} -->

<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"六类研究方法仅扩展现有能力中心说明并复用原版本、工具与发布流程，不新增能力执行器或改变发布发现拓扑，数据和MCP权限仍独立审批。","diagrams":[]} -->

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"新增个人SQLite及pin只扩展原业务根保全清单，Native与Docker仍是原单一写入部署选择，无新服务节点、容器角色、端口或数据库服务。","diagrams":[]} -->

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"档案和MCP凭据仍由原账户Store根及RuntimePool隔离，新增的是各账号元数据和引用保全覆盖，不新增网关、共享正文库或跨租户访问流。","diagrams":[]} -->

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Project Constraints和Research Web Checks及同候选Mac Bootstrap追加定点测试与静态资源，不新增workflow/job/runner或减少质量门，跨平台仍交对应设备。","diagrams":[]} -->
