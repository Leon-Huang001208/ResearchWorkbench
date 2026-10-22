# 全市场数据源连接诊断与替代调查

日期：2026-10-22；宿主：macOS；范围：公开文档、维护源码及无凭据小样本。未安装依赖、读取供应商秘密、修改代理或部署常驻服务。新浪、腾讯的小样本成功不等于完整股票池已验收，也不构成自动混源回填授权。

## 东财根因证据与修复

同一 `82.push2.eastmoney.com` 主机、参数、httpx及TLS设置下，旧 `/api/qt/` 断连，`/webguest/api/qt/` 完成报价、指数和板块采集。原 `push2his.eastmoney.com/api/qt/` 指数分时先有成功，后续整轮12次均断连；同参数固定报价访客路径取得12指数各161个同日真实分时点，24次报价／分时HTTP均200，因此指数分时也采用访客路径。对照保存在任务私有 logs/market-route-comparison.json 等文件，不把结果推断为IPv6故障或厂商正式弃用公告。无代理、证书、DNS或系统变更。

沪深大盘日线资金单独保留缺口：原主机连接中断，访客路径HTTP200但rc100／data=null。小范围字段和lmt参数对照未取得有效数据，不能把200或空数组认证为资金可用。行业／概念的today／5d／10d板块资金六组合已在真实租户完整读取；它们不替代沪深大盘合计。

旧范围完整读到5925行但有355条缺报价，包含历史退市及北交非普通股。采用[东财行情中心生产脚本](https://quote.eastmoney.com/center/static/build/index.js)当前三个A股范围后，沪2319、深2908、北354，合计5581，与官网合并范围元数据一致。官网脚本HTTP200、673734字节，SHA-256为 `1224df21d3aa5cef8659acd9293b1f44047e0398080e6bce72fe881d755dc59b`；未复制其实现或数据库。北交范围从旧 `s:2048` 改为官网 `s:262144`，三市均保留官网 `f:!2`，不猜测其位语义。

13:26:57上海时区的完整实测为5581行、58页、无重复或漏页；11条缺报价中含上市日期2026-10-23的920285.BJ。原始 `f26` 保留为上市日期，未来上市不参加有效涨跌及排行，缺报价不当作停牌或平盘。此批全市场成交额为缺口，未用零值补齐。证据 logs/market-current-universe-live.json，SHA-256为 `01cf1d59a2f6c29d11c47a900ce2fd4abe6273ef485f68b251d13b7445f028c1`。独立交易所目录本轮未完成核验（沪超时、北HTTP错误、深旧目录接口空Excel），不能将官网池完整性升级为独立三市名册认证。

## 独立上游候选

| 来源 | 当前能力与实际证据 | 接入边界 |
| --- | --- | --- |
| 新浪公开行情 | 全A count HTTP200，5576；1条列表为bj920000，北交快照bj920799含2026-10-22 13:12:36。AKShare实现按symbol分页80条，字段含价格、涨跌、量额、PE/PB及市值 | 优先免费候选；列表只有ticktime，需同源完整日期及全量核验。实现明确警告频繁调用可能临时封IP，不能按用户每30秒反复全扫 |
| 腾讯公开行情 | rank HTTP200，total5577；沪深北三只qt快照均200，带20261022131033/34完整时间。当前AKShare按total及offset+=200完整分页 | 优先独立核对／备用候选；rank缺行情时间，量额单位、批量容量与完整目录待验；不能用单页200只冒充全市场 |
| 同花顺公开板块 | 官方AKShare目录有行业行情、行业／概念资金即时及3／5／10／20日接口 | 文档候选，未实探。分类与资金定义不同，净额不能静默映射为东财主力／超大／大／中／小单 |
| Tushare Pro | rt_k支持.SH/.SZ/.BJ及通配符，最多6000行；rt_min为1～60分钟、最多1000行，另有rt_idx_k与rt_sw_k | 各实时接口单独权限，本轮无Token调用。rt_k不覆盖全部估值；部分资金为盘后，DC系列仍复用东财 |
| BaoStock | 官方介绍日线17:30、分钟20:00入库，指数无分钟线 | 适合历史／盘后；新VIP API_KEY不证明30秒盘中全市场能力 |
| mootdx／TDX | 股票、指数和分钟能力，原仓库北交所／920识别问题仍有未关闭issue | 暂不作为完整沪深北兜底；未安装 |
| Wind Client API／iFinD HTTP | 正式实时、日内、指数及多品种接口 | 需确认许可、并发、批量及北交覆盖，不能借此恢复租户禁止的宿主Wind／Office权限 |
| 既有CJPY／天软 | 项目已固定0.5.2；订阅接口存在多标的形式 | 无冻结的全A容量、首帧完整性及三市覆盖公开合同，未调用既有凭据 |
| 东财EMT正式API | 正式股票／指数订阅，有北交所股转交易所枚举 | 与公开push2不同；需账户及服务授权，不是无凭据替代 |

腾讯5577、新浪5576与东财5581存在范围差异，原因未逐证券核实；不推定哪一家漏股。建议主路径继续采用本次完整验收的东财官网范围，后续将新浪目录＋同源快照、腾讯带日期快照分别做受控完整性验收，再决定备用策略。首版不新增自动切换或混源统计。

## 一手资料

- [AKShare新浪实现](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/stock/stock_zh_a_sina.py)、[腾讯实现](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/stock/stock_zh_a_tx.py)、[股票／板块接口目录](https://akshare.akfamily.xyz/data/stock/stock.html)。维护源码是这些适配的来源证据，不代表供应商SLA。
- Tushare [rt_k](https://tushare.pro/wctapi/documents/372.md)、[rt_min](https://tushare.pro/wctapi/documents/374.md)、[交易所指数实时](https://tushare.pro/wctapi/documents/403.md)、[申万实时](https://tushare.pro/wctapi/documents/417.md)。
- [BaoStock官方知识库](https://www.baostock.com/mainContent)、mootdx北交问题[#79](https://github.com/mootdx/mootdx/issues/79)及[#103](https://github.com/mootdx/mootdx/issues/103)。
- [Wind Client API](https://www.wind.com.cn/portal/zh/ClientApi/index.html)、[iFinD官方接口](https://quantapi.51ifind.cn/gwstatic/static/ds_web/quantapi-web/)、[EMT订阅文档](https://emt.eastmoneysec.com/api/help/classEMQ_1_1API_1_1QuoteApi.html)。
