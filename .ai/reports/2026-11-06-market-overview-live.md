# 三地市场综合总览接入与 Mac mini 验收

宿主：macOS Mac mini。任务类型：功能开发；本平台范围为 Web、适用 macOS 安装 CI 和
受管常驻部署，不包含 Windows/Linux 原生验收或桌面安装包。

## 已确认范围

- 用户确认原型布局；旧全市场概览作为同页“行情分析”完整保留。
- 新综合总览为普通首页，显式 FinGPT 等旧深链接保留。
- 三地固定九指数、六维资格和事件使用真实来源；缺项不补默认分。
- 用户授权本轮常驻部署；采集日程与入站 MCP 保持关闭。

实现位于独立 worktree，受管任务 `market-overview-live-20261106`，基线
`b192dd1a7d71080a1a4d83ade02102a15cd9f365`。无新增依赖授权，复用已核验共享测试环境。

## 当前证据

后端真实公开源探针已验证腾讯九指数报价及原生日线；Yahoo 两域均 HTTP 403，失败证据保留。
离线回归、前端交互、完整 Router、独立评审、CI、真实常驻切换、用户页面验收和资源收尾
将在执行后分别登记，当前不能将计划记为 PASS。具体后端计数见同日 backend 报告。

产品进展保持验收中；代码存在不等于常驻环境已更新或评分已获准。

## 产品检查点前的实际验证

- 九指数后端20项回归通过，旧目录／服务兼容10项通过；坏JSON单指数失败不丢其余结果。
- 最终前端 Node 套件1366项：1362通过、0失败、4项原有DSH条件跳过。
- Chrome 隔离真实DTO验证三卡、九指数选择、OHLC详情返回、事件抽屉、九类别时间轴、
  星期刻度、月份精度单列、来源目录／公布时间以及390px抽屉，无页面错误／横向溢出。
- 额外2项跨层合同通过：真实前端GET路径经真实FastAPI路由全部200且不写Store；真实
  评分ASC分页／100条上限保持。隔离Host活动上下文不等价为真实认证网关验收。
- 来源真实探针9/9，每指数100根关闭原生日线；Yahoo403保留独立证据，未伪造备用成功。
- 独立评审发现的分页上限、ASC最新选择、真实日历类别、来源字段、同事件旧响应与刷新
  幂等问题均有对应修复和负例。最终候选仍须源字节复审、完整Router及CI和常驻实切换。

本机日志位于 `logs/global-indices-*`、`logs/market-dashboard-*`，成功pytest根均已正式退役。

<!-- architecture-review {"group":"research-api","structure":"changed","reason":"市场首页新增global-v1固定九指数分集，仍由原MarketService及DataHub采集缓存；13图更新来源和首页范围，事件与评分复用原14图领域，没有新增服务或研究引擎。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"原公开来源适配增加腾讯九指数原生OHLCV与独立缓存分集，13图标明三地来源及旧目录并存；固定12指数仓桥、研究仓格式、供应商权限和正式PIT门不变。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks步骤增选九指数离线模块，Mac Bootstrap现有步骤增加四静态资产及Provider导入；原Runner、安装健康、Doctor和CI拓扑保留，未增加平台dispatch或依赖。","diagrams":["08-iteration-docs"]} -->
<!-- architecture-review {"group":"ui","structure":"changed","reason":"综合总览作为默认市场首页读取既有行情、事件与评分领域，原行情分析同页保留；13图更新首页和来源口径，未新增研究执行节点或独立前端运行服务。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"新固定market-live模式只在既有Native操作员内复用事件关闭、三锁、BirthFence及全账号保全恢复，不增加部署节点、不切换Docker、不改双运行时互斥或平台权限。","diagrams":["01-deployment"]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"Mac mini切换沿原primary与gateway独立源身份、全账号业务快照、实际空闲及双健康门，MCP持久False且事件采集关闭；没有新网关、路由授权或用户数据格式。","diagrams":["01-deployment"]} -->
