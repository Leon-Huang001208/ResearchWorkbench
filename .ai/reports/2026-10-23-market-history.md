# 全市场限价、昨日成交额与沪深资金历史

2026-10-23，macOS Mac mini，market-history-20261023。用户授权补齐可靠数据、明确缺口、部署及真实认证验收，保留会话/数据/模型。Windows/Linux原生与Docker产品层NOT_RUN。

## 证据与口径

旧版51f09fa7无涨跌停、昨日金额或资金历史表。东财官网vendor.js明确f292=5已收盘；完整clist同批f350/f351真实返回逐股涨停/跌停价，沪深北样本与stock/get限价和腾讯报价交叉对照。仅比较同日有效现价及正数限价，不套固定涨跌幅；新股无限价但来源未明确语义时仍未知。专题涨停池存在范围排除，不替代完整股票池。

历史探查：原push2his日线资金RemoteProtocolError；访客lmt=0/30/100均实际只返2026-10-22一日，其他报表配置不存在，不声明30日已补齐。官网大盘JS合同 https://data.eastmoney.com/newstatic/js/zjlx/dapan.js；原AKShare字段合同 https://github.com/akfamily/akshare/blob/main/akshare/stock/stock_fund_em.py。盘前来源切换到23日时现价/成交额和资金data暂为空，不能填0；交易时段真实验收另证。

昨晚完整快照c16c25c2-dd26-4a93-a532-6935a6a324d9来源日22日，已上市5577只时间均15:33:42以后、采集22:17:01。今晨股票池新增920285.BJ/移出000016.SZ，不能只比数量；以旧快照逐股实际金额重算，含旧未上市来源明确的0，覆盖本次5577只，得到1541863946799.9元。此为缓存只读推演，不冒充部署后页面证明。

## 实现与验证

Provider新增两限价、状态与覆盖、收盘见证；Service在原当前/上一缓存中保留逐股昨日基线，日历/日期/收盘/金额/身份缺口拒绝，公开投影不泄露内部逐股基线。资金按同账号同key同定义保留最多30条有来源和采集时间的实际日线，本次返回数与留存数分开。UI显示确认涨跌停/未知、昨日同池金额或原因及五类资金历史表，CSV追加限价字段。无新依赖/HTTP路径/业务index迁移或模型调用。

新增四项Python先RED（缺字段/方法）；实现后Provider/Service75例通过，JS新增两项先RED后通过。最初全局/生产Python缺pytest，旧测试环境缺SQLAlchemy，用户明确允许隔离安装既有测试依赖；任务.venv复用现有测试工具并仅补声明的SQLAlchemy和已锁定psycopg[binary]，不修改常驻环境。完整Router、本机质量/回归、独立评审、同候选三CI、部署与认证页面仍待最终候选，不能以当前定点结果替代。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"既有市场页面/Host/Provider/用户缓存链内补限价和历史投影，无新服务或HTTP路径；原图拓扑准确，缓存/API字段文档同步。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"既有市场页面/Host/Provider/用户缓存链内补限价和历史投影，无新服务或HTTP路径；原图拓扑准确，缓存/API字段文档同步。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"既有市场页面/Host/Provider/用户缓存链内补限价和历史投影，无新服务或HTTP路径；原图拓扑准确，缓存/API字段文档同步。","diagrams":[]} -->
