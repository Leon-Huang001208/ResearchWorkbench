# WGC 月度吨数与研究时点任务

宿主macOS，功能开发；隔离开发与独立研究仓、原三CI和同候选Mac安装。现有服务、生产PG5432、外盘、凭据及模型无操作。

WGC两固定端点只投影四地区月度吨数，284个月的预检各HTTP200；预检不当作Host成功。持仓/流量不同且不与单只SPDR或个股资金流归并。原件、源asOfDate、参考月、单位和完整切片绑定。公开数据更新日程不等于历史公布链；正式PIT/回测仍拒绝。

AK资金流as_of路径离线反例已证明SDK先执行；backtest首轮用例未带必需as_of，构造失败保持原日志，不把它算成产品失败。补齐合法as_of后执行前统一拒绝，43项时点模块通过。WGC修订边界矩阵验证捕获前无数据、t1读旧、t2读更正；宏观/财务/资金流矩阵仅验证合成存储封包，不冒充真实跨源等价。冻结API首轮测试误传位置cutoff造成TypeError，已改关键字as_of；保留失败记录。

真实新进程/PG重启/恢复已执行，详见后续证据；最终候选独立评审、CI与Mac安装待精确绑定，不提前认证。

官方定义：[WGC](https://www.gold.org/goldhub/data/gold-etfs-holdings-and-flows)：黄金ETF地区聚合，吨数与USD，周/月更新。方法PDF返回403，未引用其未读取内容；Jina通道未取得可用正文，官方页面通过浏览工具读取。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"复用既有外部Provider、Broker和个人可选研究仓的原生快照链；WGC既有端点闭合月度投影和AK时点守卫没有新增节点、协议、表或数据流边，现有03/04/09图保持准确。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"仅向既有Checks同一步新增两个离线模块，沿原三CI及MacBootstrap与Router，不新增runner/job或执行拓扑，既有验证图仍准确。","diagrams":[]} -->


首次完整真实验收在配置校验阶段因临时库名前缀不符rwb_market规则失败，capture进程确认0次供应商执行/HTTP；PG和HOME已清理，代码/helper哈希未变。旧attempt-started及失败回执保留，新尝试须用独立目录且只修临时库名，不修改正式配置规则。


## 实际入仓与进程重启验收

干净源码5574af8aa9aa8e6458778814ba5378c12cdf8804，受审helper第二尝试9.404秒PASS。capture/reopen/restore分别使用PID70208/70415/70465，首次进程已退出后实际停止/重启owned PG，再由不同OS进程重建默认Host读回；第三进程将两冻结包分别恢复到同一owned实例的第二空库并读回。两端点各一次真实HTTPS GET、各284行；后两进程HTTP均0，行/字段/原件摘要一致，两个dataset身份不同。默认仓库工厂未替换，真实psycopg只允许owned Unix socket/65473/库白名单/空密码，PG TCP禁用/fsync=on，5432未接触。临时PG/数据目录/HOME/Host均清理；全部281项源码/隔离夹具/helper哈希前后相同。

真实回执SHA256=810d3e97a4b191aa893c51f5ec3e881e5f25fbcc9fecf1b7ef58fd53fe80c569。仅证明本次四地区月度吨数投影，不认证全API、历史公布版本或跨源等价。原始数值只保存于ignored私有证据，Git仅记录合同、计数、时间和哈希。合法历史与正式回测请求拒绝，日期不伪装披露时间。方法PDF403、首尝试0HTTP、先前语法/用例/格式失败均保留。

本地1094 Python/99子测试、397 JS及六源码静态检查已通过；补齐README相对本基线unchanged回执及两项架构结构说明后10项本地闭包PASS。所有原计划门保持L4，新的最终评审、CI/Mac及部署依旧分别记录，认证页面/常驻部署NOT_RUN。
