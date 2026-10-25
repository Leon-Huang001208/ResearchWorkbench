# SDK 原端点与宏观、财务证据扩围

macOS Web 功能开发，独立 worktree 和 owned socket-only 临时 PostgreSQL；现有服务、正式库5432、系统代理、外盘及真实凭据不操作，无新增依赖或付费。源码检查、实际取数/入仓/重启/恢复、独评、通用CI和同候选Mac安装分别记录，未运行项不标通过。

## 原端点诊断

只读核对当前官方AKShare main与已装1.18.94的stock_fund_em.py原字节SHA相同，未发现可直接套用的上游修复。继上一轮四案之后，本轮只做两个未执行的交叉路由：82.push2原/api路径在响应头前RemoteProtocolError；push2his加/webguest路径返回404空正文。随后原端点仅添加固定公开Referer仍在响应头前RemoteProtocolError，3次请求无重试。失败没有被归因账号或模型，SDK原端点仍未修复；真实后备成功也不代表原端点或独立上游成功。

## 月度宏观v4

保存三份东财页面及页面真实引用的JS原字节和SHA。CPI六项同比/环比、PMI两项同比、货币供应量六项同比/环比明确为percent；CPI当月/累计指数基期仍未知，PMI水平不是百分比变化或百分点。M2/M1/M0数量为亿元，不按BASIC_CURRENCY英文名错称基础货币。

央行原件明确M1自2025-01调整、回溯2024年可比月末余额；保留该定义修订证据，供应商采用的vintage未证实。统计局2025-09 CPI页声称2025-10-15 09:30公布，时区和当时原始字节未独立证明，不将其赋给当前供应商序列。所有当前捕获仍first_observed、非历史PIT/正式回测不可用，跨源及跨版本等价未认证。

## Bao盈利能力v2

从既有归档校验恢复600000.SH/2026H1半年报PDF及两页图像，重新目视核对集团/本行、当期/上期四列、半年累计和人民币百万元。仅netProfit/MBRevenue原始字符串精确哈希匹配时附限定参考，原金额不改；集团净利不冒充归母，其他股票/期间/修订值不外推。供应商8月28日与发行人列表8月27日的旧声称分别保存，列表原字节未证明，不能回填精确可得时间。

生产与入仓共享原件投影，严格重建行、字段、固定元数据和引用地址，伪造行/证据/原件拒入仓且保留此前好快照。旧schema缓存跳过，旧显式冻结保留原义。宏观及财务均沿现有Host/DataHub/可选研究仓，无新服务、表、HTTP或依赖；数值冻结保存供应商原件和引用元数据，外部定义/PDF随独立证据归档，不声称嵌入每份数值冻结包。

## 当前阶段

新宏观合同先6失败再79通过/59子测试；财务新模块缺失RED后70通过/28子测试（含cashflow）。这些局部结果不替代真实验收或最终候选资格。完整实际与最终交付信息由后续精确SHA回执补充。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"只扩展既有宏观字段字典及限定财务引用，强化原件重建与缓存版本，没有新节点、HTTP、表、依赖或执行引擎，原拓扑仍准确。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只向原Checks同一步追加一个离线模块，保持原三CI及同候选Mac安装，无新job/runner/timeout或验证节点。","diagrams":[]} -->

## 已执行真实仓库验收

源码执行HEAD b83b15ce69c263c4b1378b438e502d83c2f6ea9f，8.937秒PASS；377份源码/helper、依赖包和PG二进制前后校验一致。7个实际public worker与7次受观测HTTP提交（Bao原生socket底层次数仍unknown），宏观四类GDP1/CPI3/PMI3/M2 3，资金流1，Bao与Sina同600000/2026H1各1行。两格原始字符串Decimal哈希相等，集团累计和单位参考独立保留，provider scope/dataset不合并。

默认ResearchService/ResearchWarehouse及原postgres factory，owned PG18.3仅Unix65478、TCP空、fsync开启；22313/22568/22590三个独立进程，postmaster真实重启、新Host业务读回及同actor/scope/dataset第二空库恢复通过。后两阶段SDK/HTTP均0，行/字段/原件/引用/冻结摘要相同；临时PG已停并移除。原SDK自然连接失败+guest后备仍分别记账。回执SHA256 be10518e2e014789301704b60dccc169b32ef027088f554ea6a9f59c360381dd。

本机源候选完整10组56.799秒通过，Python1282/101子测试；最终集成评审、CI与同候选Mac安装仍由精确SHA外部回执认证。新增报告只包含摘要与哈希，真实数值及定义/PDF字节保留私有证据。
