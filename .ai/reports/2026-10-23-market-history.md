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

## 独立审查补充

修复未知交易状态误确认、明确收盘15:00报价被过滤、资金来源日期回退丢新历史及收盘状态/盘中时间矛盾四项；对应RED→GREEN，78项Python与34项JS通过。新增上一完整缓存昨日基线恢复/重启与较新见证优先，避免老版盘前空报价覆盖当前缓存时丢失昨日对账。f987bb7f为首个独立APPROVE检查点，最终产品/操作员组合仍须另绑候选与CI。

## 封闭部署组合

产品检查点96e3cff6181668a91a5117984c160b457b645629，固定旧51f09，新增reviewed-market-history-v1/apply-market-history。原version4锁/空闲/BirthFence/全账号保全/恢复和旧profile不变，市场inflight活动/未知拒绝；只同步固定原锁文件7c631d4f与code_commit，不安装包或启用数据库。操作员868例43.50秒、产品79例、Ruff/Black/isort及3源码mypy通过；独立组合947例通过。初轮扩展1611例中19个冻结恢复子进程因复用测试环境导入旧工作目录而拒绝unsafe_path；显式PYTHONPATH绑定本任务后最小冻结复现通过，整组重跑另证，未修改生产路径校验或恢复保护。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅为Mac Native原version4事务增加固定市场历史profile，旧profile/控制器/恢复及Docker拓扑不变；无新服务或运行节点，同候选Mac与真实保全分开验收。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"原网关/Host/独立用户根和BirthFence拓扑保持，市场历史限定同用户缓存，全账号索引/会话/模型保全及活动拒绝不变，不新增账号权限或共享路径。","diagrams":[]} -->

最终产品检查点更新为4f0a248fc87249d41e1c3f75f700c17c8351ad95：包含96e3的昨日缓存恢复，并将资金覆盖表述改为“快照来源”，避免失败保留旧日线时误称本次请求返回。新profile固定此检查点，旧mode常量与恢复不变。

最终本机组合：1611项Python/84.13秒、983项Web JS通过/3既有跳过；文档同步、完整changed-set约束及Ruff/Black/isort与三生产源码mypy通过。补正PYTHONPATH后完整冻结恢复矩阵通过，原失败日志保留。最终source仅固定payload常量更新4f0a、覆盖文字和夹具UUID修正；profile绑定例再次通过。CI/常驻部署/认证页面仍须实际执行，未执行不预填PASS。
