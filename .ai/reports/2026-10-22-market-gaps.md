# 全市场报价、成交额与沪深资金缺口修复

2026-10-22，macOS Mac mini，任务market-gaps-20261022。用户授权修复、必要时采用可靠替代源、常驻部署和真实认证页面验收；保留既有会话、数据和模型。Windows/Linux原生与Docker产品验收交接NOT_RUN。

## 复现与根因

常驻99d3ee34原快照5581条，缺报价10、缺成交额11，总额为空。东财单股API对该11只明确返回0成交额；官网vendor.js明确定义f292状态，7只停牌、4只未上市。旧列表未请求该状态，且把停牌参考价和真实零额当缺失。旧push2his资金接口复现RemoteProtocolError；同参数访客端点200并返回当日真实15列沪深合计。

原始探查与SHA-256在logs/market-gaps/source-probes/；官网脚本https://quote.eastmoney.com/newstatic/build/vendor.js、https://quote.eastmoney.com/center/static/build/index.js，资金合同https://github.com/akfamily/akshare/blob/main/akshare/stock/stock_fund_em.py。另以腾讯qt.gtimg.cn对照停牌参考价、S状态及U未上市状态，新浪只读接口对部分停牌返回0或旧日、北交所样本为空。现有东财接口足够完成同源修复，因此不引入新Provider、登录或依赖。

## 改动与验收

providers_market.py补f292状态、同身份同日的有界明细补取、f301/f59正确缩放和真实零额/零量；原金额与非缺失字段不覆盖。广度停牌/未上市单列，已上市成交额分母明示；未上市保留身份但不构造当日报价。market_service.py的CSV追加状态/价格性质，旧缓存继续兼容。market.mjs显示停牌参考价、未上市状态、六类广度及大盘资金自身元数据。

回归先RED：新停牌详情和访客资金2项失败；实现后provider/service49项、JS31项通过，后续边界及最终候选仍单独记录。完整实采17:29:21：5581条、正常样本5570、上涨535/下跌4999/平盘36/停牌7/未上市4/未知0；成交额1541863946799.9元，已上市5577条覆盖无缺口；11只明细补取成功。沪深大盘当日主力净流入-63251701760元；访客实际只返1个交易日，不能宣称30日历史齐全。原始完整快照logs/market-gaps/live-quotes.json和live-flows.json。

## 交付边界

不改业务index、模型、权限或研究引擎，不虚构未上市报价/停牌成交。最终部署工具另以封闭profile固定旧99d3和不可变产品源码检查点；最终head还须独立评审、最新基线、三CI/同候选Mac安装及正式保全事务。常驻切换与真实认证验收尚待，不以本地完整实采冒充已部署。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"既有Host/MarketService/DataHub/东财请求链内补状态、同源详情及资金元数据；无新运行节点、HTTP端点、权限、依赖或研究数据流，原图准确。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"既有Host/MarketService/DataHub/东财请求链内补状态、同源详情及资金元数据；无新运行节点、HTTP端点、权限、依赖或研究数据流，原图准确。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"既有Host/MarketService/DataHub/东财请求链内补状态、同源详情及资金元数据；无新运行节点、HTTP端点、权限、依赖或研究数据流，原图准确。","diagrams":[]} -->

## 独立审查后的补充

已按独立复现修复普通股缺f169/f170与停牌f43的参考价标记，资金面板继承外层陈旧/错误但保留自己的行数/日期；若本轮板块正常而资金失败，MarketService按同用户/同key保留上次资金，并持久化stale/error，成功后清除。新增100只明细上限、详情阶段取消和资金缓存恢复回归。当前63项Python与32项JS通过；Provider有界mypy无新增错误，MarketService唯一[index]错误在99d3 shadow基线同样存在（490→492行），没有隐藏或取消检查。最终三CI、部署和认证页面仍待最终候选。

## 初始固定部署入口（历史检查点）

产品源码已冻结于b333c51c7508b7d346b3ca0f039e4e746b0fd8b8；后续profile只允许旧99d3和此精确产品祖先，最终同候选独立评审/三CI/最新master仍是前置。新入口apply-market-gaps额外拒绝活动或未知MarketService采集，旧profile和恢复保持。操作员回归先RED的新身份/CLI后，在673项完整矩阵通过/28.10秒；最终新增错误previous拒绝和格式化后的结果另记录。
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"固定旧99d3与不可变产品检查点b333，复用原version4事务和全账号保全，仅补现有MarketService空闲证明；原部署与权限拓扑准确。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"固定旧99d3与不可变产品检查点b333，复用原version4事务和全账号保全，仅补现有MarketService空闲证明；原部署与权限拓扑准确。","diagrams":[]} -->

## 合并主线后的最终范围

已保留PR183合并4dcc88950959102b041df8c441906125ca0de9dc的全部产品、原市场activity_witness/close排空及job类型修复。仅4份文档冲突合并保留双方内容，生产源码自动合并后定点复核。最终固定产品检查点改为9faeeca3003a912ca75799fb27b635ba1bb87a1a（合并已审主线与本市场修复）；b333为初始历史记录。固定旧常驻仍99d3，最终profile与三CI将重新绑定。MarketService原[index]类型错误已由新主线的job:dict修复，不再作为最终候选债务。只验收市场，不触发周报生产、日程、Wind或模型。
