# WGC 月度吨数与研究时点任务

宿主macOS，功能开发；隔离开发与独立研究仓、原三CI和同候选Mac安装。现有服务、生产PG5432、外盘、凭据及模型无操作。

WGC两固定端点只投影四地区月度吨数，284个月的预检各HTTP200；预检不当作Host成功。持仓/流量不同且不与单只SPDR或个股资金流归并。原件、源asOfDate、参考月、单位和完整切片绑定。公开数据更新日程不等于历史公布链；正式PIT/回测仍拒绝。

AK资金流as_of路径离线反例已证明SDK先执行；backtest首轮用例未带必需as_of，构造失败保持原日志，不把它算成产品失败。补齐合法as_of后执行前统一拒绝，43项时点模块通过。WGC修订边界矩阵验证捕获前无数据、t1读旧、t2读更正；宏观/财务/资金流矩阵仅验证合成存储封包，不冒充真实跨源等价。冻结API首轮测试误传位置cutoff造成TypeError，已改关键字as_of；保留失败记录。

真实新进程/PG重启/恢复、独立评审、CI与Mac安装待执行，不宣称完成。

官方定义：[WGC](https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows)：黄金ETF地区聚合，吨数与USD，周/月更新。方法PDF返回403，未引用其未读取内容；Jina阅读超时，官方页面通过浏览工具读取。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"复用既有外部Provider、Broker和个人可选研究仓的原生快照链；WGC既有端点闭合月度投影和AK时点守卫没有新增节点、协议、表或数据流边，现有03/04/09图保持准确。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅向既有Checks同一步新增两个离线模块，沿原三CI及MacBootstrap与Router，不新增runner/job或执行拓扑，既有验证图仍准确。","diagrams":[]} -->


首次完整真实验收在配置校验阶段因临时库名前缀不符rwb_market规则失败，capture进程确认0次供应商执行/HTTP；PG和HOME已清理，代码/helper哈希未变。旧attempt-started及失败回执保留，新尝试须用独立目录且只修临时库名，不修改正式配置规则。
