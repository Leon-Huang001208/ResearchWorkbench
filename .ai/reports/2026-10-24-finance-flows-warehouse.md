# 现金流财务与个股资金流研究仓

macOS Web 功能开发，使用独立 worktree 和隔离临时库。现有服务、正式数据库、外盘、凭据和模型不操作，不引入新依赖。真实来源验收、候选代码、独立评审、原三 CI、同候选 Mac 安装与收尾分别记录，未执行项不标通过。

新增 BaoStock 单证券、单报告期 `cash_flow`，与既有盈利能力分开注册。七项比例保存供应商原值和空缺，不推定百分数尺度、累计或单季、集团或母公司口径，不换算为现金金额或证券交易资金流。字典来源为已锁定官方文档及 SHA256；研究仓重新解析 SDK 原件并核对完整投影、字段、身份、计数和证据，避免修改后发布。`as_of` 和正式回测在 worker 前拒绝；自然日 pubDate 不是历史当时可得证明。

已有 BaoStock／新浪盈利两格核对属于 PR203，不重复计为新增来源或真实验收。当前 A 股资金流仅匿名访客有界预检成功，HTTP200/rc0、1 条记录；尚待默认 Host、持久化、重启和恢复。AKShare SDK 与访客是同一 Eastmoney 上游，未知单位和完整历史不能提升。

合成验证先失败后修复：新增投影和路由先出现五个失败；主仓库测试首次错误地把冻结包当供应商原件，改为解析包内原件核验，未修改生产封包合同。顶层 pytest 因非 Web 的 sqlalchemy 缺依赖拒绝，使用原 Web `--confcutdir` 范围，无新安装。详细日志在本任务 logs 及完成后的私有归档。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"仅扩展既有BaoStock公开worker财务数据集及原生仓准入；Host、Broker、Provider、可选研究仓节点和边不变，没有新HTTP、数据库表、服务或依赖。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"原Checks同一Python步骤增加两离线模块，保留既有三CI和同候选MacBootstrap，不新增job、runner或验收拓扑。","diagrams":[]} -->


## 实际现金流验收

源码`0ae2c55a4c043b14c20c38f157b04e9f1a5c8c79`，4.746秒PASS：一次真实Bao公开worker，三个独立Python进程，默认Host/ResearchWarehouse/真实psycopg和独立socket-only PG18.3。600600.SH、2026-06-30，1行七项财务比例，其中6个有数值、1个来源空值；pubDate自然日精度保留，不冒充可得时刻。真实停启PG后新进程零供应商执行读回；另一空库恢复并核对rows/fields/原件哈希。287份源码/helper哈希前后一致，SDK/PG二进制另绑定。底层SDK网络次数未测量，不把一个worker写成一次网络请求。临时PG及HOME已清理；5432、现有服务、外盘不动。回执SHA256=2e6a9dc4bfbe5ac63f20670a99188cd9a8518a551ba2e516f72fd608eb07af2a。
