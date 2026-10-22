# 沪深北全市场概览实施与验收记录

宿主：macOS；任务：Web功能开发；任务ID：market-overview-20261022。
本轮按用户要求修复东财断连、完成真实行情与正式认证页面验收后再合并PR179；常驻部署未授权。最终候选的本地／真实页面／独立评审／三项CI分别绑定，旧候选通过不能直接沿用。

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

## 连接诊断与真实源

最终本地证据：Web JS 865项中863 PASS／2个既有SKIP（logs/market-all-web-js.log）；L4治理229 PASS（logs/market-l4-js.log）；Python集成326 PASS（logs/market-python-integration.log）、边界112 PASS（logs/market-python-boundary.log）、最终定点43 PASS（logs/market-python-target.log），各范围存在重叠，不相加为独立测试总数。新增3源码文件mypy使用`--follow-imports=skip`通过；9个变更Python文件Black／isort及Ruff通过。曾遇到缺测试工具及Black stdin多进程环境问题，最终使用现有缓存和串行检查解决，无安装或规则降级。

隔离真实浏览器9 PASS／0 FAIL，见logs/market-e2e/result.json；实际app、MarketService与路由核对6001股票、CSV同快照、30秒自动刷新、输入焦点、三市成员、明暗和390px宽度。fixture cookie仅验证同源传递，不是生产认证或真实行情验收；测试无外网／模型／创建会话，退出collector=0。

旧候选216f095的logs/market-real-source.json因三市network_error保持BLOCKED，原三项CI通过未据此合并。继续诊断证实：同主机／同参数／同TLS下，旧报价路径断连，公开访客路径完成读取；指数分时原历史主机也间歇断连，改用固定报价访客路径后12指数各161个真实同日点成功。无IPv4强制、代理变更、TLS降级、凭据或依赖安装。

股票范围取自东财当前官网脚本；旧5925池含退市及非普通股，修正为沪2319／深2908／北354，合计5581，与官网合并范围元数据对齐。13:26:57全量58页无漏页／重复；缺报价11条，含次日上市920285.BJ。保留f26上市日期、unknown及待上市数量，不伪补停牌／平盘／涨跌停或总成交额。源证据和候选源调查见[数据源报告](2026-10-22-market-data-sources.md)。

正式 AccountStore／Gateway／RuntimePool 启动候选Web和固定DSH的首轮真实浏览器取得5581行、5581个CSV唯一ID及逐市对账；行业496／概念516、资金六组合、成分27同快照、30.093秒自动刷新和双账号空缓存隔离通过。首轮13 PASS／3 FAIL保留：一个表格等待条件捕获前次响应、两个过宽进程探针把未知短命实例列为resident；测试修正必须在最终候选重跑，不删除旧失败。沪深大盘日线资金的正式路径断连、访客路径rc100／data=null，保留不可用缺口，不能用板块或盘中资金替代。

正式认证的下一轮27770c9取得14 PASS／1 FAIL，定位为搜索一行后列菜单被卡片overflow:clip裁剪；修复仅让行情卡片菜单可溢出，内层表格继续滚动。独立JS评审另发现旧代刷新finally会误删新代同key登记，行为回归先复现3次POST（应2次），再用generation所有权修复；验收脚本空搜索参数等待也已修正，没有force点击或取消断言。

功能源码检查点 `e62f5cbf63a06ea3ce54fd18a58c01123cac7ade` 的正式认证验收15 PASS／0 FAIL（66.900秒），证据 `logs/market-authenticated/2026-10-22T05-48-14.306Z/result.json`，记录实际commit和九份关键源码／脚本SHA-256。13:48:23沪深北5581行、CSV5581唯一ID及官网合并池5581对齐；12指数报价／同日分时均完整，行业496／概念516及资金六组合完整，27只板块成员同快照。表格筛选排序分页、单条搜索导出、列隐藏恢复、明暗／390px、股票指数跳转通过；自动刷新30.225秒更换5581行快照，浏览sessions=0。第二真实账号缓存为空且根0700，A/B缓存分离。正式resident三组PID／出生时间／源身份hash前后相同，owned pool实例及两个登记子进程已关闭；无pageerror或浏览器外部请求。

该轮两个截图取早（数据绘制前／主题过渡中），不能作稳定视觉证明。只补验收等待、不改生产后，检查点 `988408550f5b9109a7c01790d88c5ee1fccdb6ac` 整轮再获15 PASS／0 FAIL（70.599秒），证据 `logs/market-authenticated/2026-10-22T05-53-51.365Z/result.json`，SHA-256 `b83a840791d626bd886b5f626396d27e28fea8c3dabbaf184ec750e89a155561`。亮／暗截图已有真实内容，但其余逐图复核仍发现成员表取早和窄屏列菜单向左越出屏幕，不能仅凭15项通过认证全部视觉。

最终源码与验收脚本检查点 `d130a294208669b09daa2ba2c61fcdd11bde2bfb` 修复窄屏菜单锚点，并统一等待页面／表格绘制完成；成员图等待DOM总数与真实API的27匹配，窄屏正常点击PB列且检查菜单几何。正式认证整轮15 PASS／0 FAIL（70.261秒），证据 `logs/market-authenticated/2026-10-22T06-00-19.240Z/result.json`，SHA-256 `4cd6f614d0c8db431db0a7b53ee1d3117515b2e721e3cff5a4e27bf11e748f9a`。七图逐一复核均有真实内容、无加载早帧；主代理另直接复核成员27和窄屏菜单。菜单x201／宽160／右缘361在390px内，表格client356／scroll1080；亮暗文字对比度14.863／13.447。全池5581、12条同日分时、六资金、27成员及CSV同快照全部通过，自动刷新30.235秒；sessions=0、A/B缓存独立，owned池与子进程全部关闭，三个正式resident身份不变。

资金可用性按本轮实况修正：行业today首次沪深日线资金成功返回30行，后续五种分类／周期仍各有market_flow缺口。它是间歇可用，不能说永久不可用或已稳定；每区保留本次missing／原时间，不混用盘中频率或另一供应商。

Provider／Service回归47 PASS、市场JS31 PASS（含路径／范围／未来上市及旧代竞态），Python和JS分别独立Approve。d130检查点API／资产／市场Python306 PASS（267.93秒，一条既有Starlette/anyio弃用警告）、协议81 PASS，Web及治理基础JS共1019 PASS／2个既有SKIP。最终仅文档检查点更新报告和架构源码链接，按Git blob与九个SHA-256复核生产及测试字节不变，不改写实际执行SHA。最后文档／完整changed-set约束与L4治理在文档提交后执行；同候选三项GitHub门仍待发布后完成，结果保存在私有logs的精确SHA／实际checkout／runner回执，本文件不提前把待执行门写成PASS。真实Sina交易日历覆盖至2026-12-31。

Windows/Linux原生和Docker实机保持NOT_RUN交接，不能由Mac或Ubuntu通用检查替代。本任务未切换常驻服务、读取生产秘密或运行模型；正式认证只使用新的0700临时用户根和内存随机测试密码。

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

源码检查点：`8043d028242fa4687be260ae151a8333ceaa6af6`；架构阅读器的源码链接固定至该真实提交，后续图文检查点不自指。

集成主线基线：`a0ff3ae2e2ab92bad10ba8547e45027687ec7cc1`；合并源码检查点：`3b59f586b23b4dc8a5988c5443790b32ca396b5f`。保留PR177资产历史、目录／测试修复及原取消行为，市场路由仅取消自己的订阅。合并候选重新验收，不将旧日志直接认证为最终SHA结果。

继续集成基线：`08aacb6d1723961a2846727627d569fd97a481f2`，保留主线Wind v3固定部署profile，README回执按两者合并。最终源码与验收脚本检查点为上述d130a294；架构阅读器链接更新至该不可变提交，不自指文档提交。后续固定路径、范围、菜单及竞态修复不改变图13的数据流拓扑。

主线再次前进至 `9b436613aad9136f4959c992c89dd72fc7354ed5`（PR180 Store启动默认键保全），已原位合入且保留全部主线代码；市场与验收脚本字节保持。最新合并源码检查点 `fda1e0da3031fe4c882adc0cfbd718b7863de907` 独立Python复核通过，集成API／资产／市场／Store／历史344 PASS（292.64秒，同一既有弃用警告）、协议81 PASS、Web基础JS1019 PASS／2既有SKIP。该真实启动链再跑原15项与七图，15 PASS／0 FAIL（72.667秒），证据 `logs/market-authenticated/2026-10-22T06-13-04.014Z/result.json`，SHA-256 `88e5fae7a607297888bf5798ae71c84c28485762dad305c92522d89770e76a70`。全池／12分时／27成员／列控制／主题／七图／零会话／双账号与保全均通过，实际自动刷新30.264秒；本轮资金前五组合日线缺口、概念10日成功，继续标间歇可用。最后架构链接固定至fda1e0da，文档检查点与上述代码测试按不变Git blob映射，CI必须绑定最新文档候选，不沿用旧a7abc候选结果。
