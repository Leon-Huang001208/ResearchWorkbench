# 沪深北全市场概览实施与验收记录

宿主：macOS；任务：Web功能开发；基线：5495e64c0be08c9db58e336705db90584f8ba8b5。
任务ID：market-overview-20261022。当前状态：代码及离线验收完成，真实行情验收BLOCKED；同候选CI待执行。未合并、未部署。

## 实施范围

- 一级市场入口和总览／完整行情／板块资金三页签；搜索、筛选、排序、分页、列设置、CSV及资产观察跳转。
- 固定公开源，沪深北独立有界分页，12指数和同日分时，行业／概念与三种资金周期。
- 无会话MarketService、用户有界缓存、共享采集与精确取消；GET不触发上游取数。
- 无新依赖、凭据配置、研究引擎、数据库迁移或常驻切换。

## 已执行验证

- `node --test tests/javascript/research_web_market*.test.mjs tests/javascript/research_web_navigation*.test.mjs`：首轮51 PASS；前端修补后目标测试另复跑。
- 通过现有缓存加载pytest9.1.1与pytest-asyncio1.4.0，无包安装。Provider19项、Service24项通过；包括5004／6001行、跨日报价、漏页／重复／总数变化、取消排空、raw成员按目标快照求交和损坏current恢复previous。
- Python与JS分别独立评审。原P1/P2均先复现再回归修复；评审不替代浏览器或真实数据验收。
- 新市场数据流图使用Archify showcase验证9/9，自动四视口包含性通过；最终截图与哈希复核另记。

## 真实源与剩余门

最终本地证据：Web JS 865项中863 PASS／2个既有SKIP（logs/market-all-web-js.log）；L4治理229 PASS（logs/market-l4-js.log）；Python集成326 PASS（logs/market-python-integration.log）、边界112 PASS（logs/market-python-boundary.log）、最终定点43 PASS（logs/market-python-target.log），各范围存在重叠，不相加为独立测试总数。新增3源码文件mypy使用`--follow-imports=skip`通过；9个变更Python文件Black／isort及Ruff通过。曾遇到缺测试工具及Black stdin多进程环境问题，最终使用现有缓存和串行检查解决，无安装或规则降级。

隔离真实浏览器9 PASS／0 FAIL，见logs/market-e2e/result.json；实际app、MarketService与路由核对6001股票、CSV同快照、30秒自动刷新、输入焦点、三市成员、明暗和390px宽度。fixture cookie仅验证同源传递，不是生产认证或真实行情验收；测试无外网／模型／创建会话，退出collector=0。

最终Provider字节的真实只读采集见logs/market-real-source.json：股票池0行、complete=false、三市network_error，日历8796日成功。真实市场验收保持BLOCKED，不能凭离线或安装门改为PASS。

- 真实Sina交易日历成功读取，覆盖至2026-12-31；北证50单点身份已核对。
- 当前全市场、指数及行业完整采集遇到RemoteProtocolError，原因未知。早先小样本HTTP成功不算完整市场验收；代码明确保留partial、缺口与旧快照，未降低TLS或放开环境代理。
- 生产认证页面和同候选GitHub三门尚待完成；本地Router闭包已执行，最终Git绑定回执另留logs。Windows/Linux原生和Docker实机保持NOT_RUN交接，不能由Mac或Ubuntu通用检查替代。
- 常驻服务部署未授权，本任务未变更运行服务、会话、模型配置或业务数据。

## 变更与证据映射

| 子系统 | 定点测试 | 文档与证据 |
| --- | --- | --- |
| 固定源与完整性 | test_market_provider.py | DataHub合同；logs/market-python-integration.log |
| 缓存与HTTP | test_market_service.py | API、文件、安全及生命周期合同 |
| 页面与导航 | research_web_market*.test.mjs | UI／外观文档；logs/market-js.log |
| 架构 | check_research_architecture.mjs | 13-market-overview图、规范和同哈希截图 |

<!-- architecture-review {"group":"ui","structure":"changed","reason":"新增市场三个页签及无会话刷新消费路径，独立市场数据流图给出页面、缓存和来源关系。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"Host新增MarketService和固定market路由，新增缓存生命周期而不增加研究引擎或部署进程。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"DataHub目录新增固定市场适配，数据进入无会话用户缓存，区别于原会话物化路径并用新图表达。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"共用浏览器API只增加市场页面调用入口；市场刷新不注册Automation，不改变研究日程、运行状态或交付渠道拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"既有Checks同一步骤增加两个离线测试模块，原任务、runner、检查流程和平台边界保持，不新增验证节点。","diagrams":[]} -->
<!-- architecture-review {"group":"documentation","structure":"unchanged","reason":"文档阅读器仅新增固定市场图名称白名单，原安全读取、隔离CSP、HTTP端点和阅读流程保持。","diagrams":[]} -->
