# BaoStock 盈利能力接入与研究仓验证

宿主macOS，功能开发。任务 datahub-baostock-financials-20261023 从0e0022独立worktree开始；不触碰现有服务、5432、正式仓、外盘、账号或模型。复用已批准baostock0.9.4及测试环境，无新安装/依赖/付费。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"复核02模块及04数据流：在既有BaoStock Provider增加封闭单报告期财务数据集，原Broker/公开worker/SnapshotSeries/可选MarketStore路径不变；无新HTTP、服务、存储根、表或引擎。原件和首次观测身份复用既有模型，规范PIT不扩展，原图准确。","diagrams":[]} -->

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只向原Checks同一Python步骤增加季度财务集成模块，原BaoStock模块补合成反例，无新job、runner、依赖或timeout；完整Router、独评与同候选Mac安装保持，08流程图准确。","diagrams":[]} -->

## 范围

- `financials` 明确 `statements=[profitability]`、单个2017年起有效季度末；证券仅既有沪深股票身份。auto只在该数据集选择Bao，不用摘要/利润表替代；实际调用失败也不等价切换Sina。
- 匿名SDK登录/单次query_profit_data/退出复用12秒自有worker，Future真实结束才释放容量。保留固定11字段SDK原值JSON、statDate和日期精度pubDate；不生成publication_at。
- netProfit、MBRevenue的CNY绑定SDK官方文档固定commit e14bd116745d5540c4eca55d8f0a1970e2d13235，SHA256 06369ec88c16977b2efe295f5a0d576c48d80066144b2f22df10cd909795e8fb。已实际读取GitHub contents API并核对Git blob与字节；原raw域连接失败另留记录，不把失败请求改写为成功。比例、股数尺度和累计/单季度口径未校准，不进行百分比/万股换算。
- 单独财务schema/units身份，空/partial/错误或字典/单位不匹配不宣称完整入仓。显示可显式allow_stale读库；严格最新研究重新取数，as_of/backtest拒绝。库命中仍first_observed，不提升正式PIT。
- 旧日线SEMANTICS_REVISION与既有bars/calendar/search合同保持；旧显式快照可读，旧财务schema会话缓存不复用。

## 实际证据及失败保留

父任务第一次匿名SDK发现2026Q2一行，尚无Host财务适配，证据保存在父任务1fc私有归档；它不认证产品接入。

本任务actual attempt1完成一次真实worker、Host入仓与跨会话cache及冻结，但回测拒绝用例误缺必填as_of，HTTP422导致helper断言失败；整轮仍FAILED，不认证重启/恢复。PG与临时HOME已回收，错误与原冻结保留。

修正为合法的backtest+as_of请求后，actual attempt2 8.647秒PASS：1次真实Bao公开worker（底层网络请求次数未独立统计），完整ResearchService/DataHub内部业务API、独立socket-only PostgreSQL capture/cache、合法历史/回测拒绝、Host和PG实际重启后零额外取数命中、第二空库导出恢复摘要相同。货币单位CNY、日期精度、未知比例和formal_backtest_eligible=false均实际核验；模型/RPC0、账号操作0，5432/现有服务/外盘无操作，PG与HOME回收。

attempt2执行在0e0022 HEAD的dirty tree，9个运行文件SHA256前后完全一致；不能用HEAD冒充这些未提交字节。合入新主线、正式候选、本机完整门、独立评审及CI仍须重新绑定。原件与真实数值仅保留ignored本机证据，Git报告不复制金融数值。

## 当前本地检查

适配器先RED后GREEN；共享校验器在Broker source仍auto时调用的集成问题、metadata schema_version及上海日界分别补回归。固定文档哈希、schema、单位、假PIT声明、partial/empty拒入库；旧会话缓存拒复用而显式receipt可读；冻结/恢复及未知比例保留。当前定点27 passed、28 subtests通过；完整闭包/静态/文档/最终SHA评审及CI未由此定点结果替代。

本批不是全历史财报、财务历史PIT、完整利润表或独立上游/跨源等价认证，不改变原剩余57项数量，不启动自动采集或生产部署。

## 同证券、同报告期的实际对照

已合入PR199的真实merge6aec2c5，保留BEA/Sina/资金流全部主线边界；19个冲突主要为文档追加及同一schema/路由分支，双方内容合并并重新生成索引。合流后112项定点/28子测试通过，原始日线与其他来源身份保持。

干净e4b45b3实际cross-source attempt3，5.351秒PASS：600000.SH/2026-06-30，Bao与AK-Sina各恰好1次worker，两个来源各自入仓、跨会话cache、Host/PG重启后零新增上游、第二空库恢复均通过。scope、dataset及冻结摘要分别不同，不拼接行或覆盖来源。SDK底层网络次数未独立统计。源原件只在ignored本地证据保存。

- 两源的供应商公告日均2026-08-28，只有日期精度；issuer官网定期报告列表经web实际读取为2026-08-27，直接原HTML抓取ConnectError原样保留。它们是不同渠道日期，不能把早一天覆盖回供应商字段，或制造精确发布时间。
- 对巨潮公开披露的浦发银行2026半年报PDF做原件归档（4,553,498字节；SHA256 01f41e69ad9dc1b348204b3aa0acf615b2343d402ac00a0ae3895f56e7010f66），原报告PDF第111/112页的表头及四列已渲染目视核对；另提取公司/股票代码确认600000。
- 报表明确集团合并、1月1日至6月30日、人民币百万元。按明示比例转元后，Bao netProfit/Sina NETPROFIT及Bao MBRevenue/Sina BIZINCO这两个具体cell与集团当期列相同；与本行列不同。因此本样本是半年累计，不是4–6月单季流量。
- Bao netProfit与Sina归属于母公司净利润字段不相同，不能标作归母利润；只对本股本期两格确认金额尺度及报告期间，不升级全部Sina字段单位、其他公司/期间或供应商全局等价。API原行/金额/供应商日期未改写，来源仍分开保存。
- 财务修订链与精确历史可得瞬时没有证明，正式backtest/as_of继续拒绝。接口描述改为“季度末/单报告期”而非暗示单季金额，保留累计口径与归母归属警示。

参考：[官方SDK固定字典](https://github.com/zxygithub/baostock/blob/e14bd116745d5540c4eca55d8f0a1970e2d13235/docs/pythonAPI.md)、[发行人报告列表](https://news.spdb.com.cn/investor_relation/periodic_report/)、[发行人公开半年报](https://static.cninfo.com.cn/finalpage/2026-08-28/1225521898.PDF)。这些是单样本核对，不构成全历史/正式PIT或整源独立性认证。

最终运行代码c98c7752在干净Git候选完成actual attempt4，4.956秒PASS，Bao/Sina各1次真实worker；报告/原字段保留、库命中、Host/PG重启及双scope独立恢复再次通过。原件重算issuer对照仍两格匹配集团半年累计，供应商8月28日与issuer列表8月27日差异保留。10运行源码hash前后一致；其后仅文档/台账更新，不把旧dirty-tree或失败回执改写为最终证明。

## PR203 CI依赖隔离修复

840b候选Project Constraints与同候选Mac Bootstrap已PASS；通用Checks run39913230426实际失败：3724 passed、69 skipped、115 subtests、1 failed。新缓存兼容测试mock了fetch却未声明SDK可用，本机已装Bao而通用CI只安装dev依赖，导致Broker正确按blocked_dependency拒绝；失败原日志保留，不改生产readiness或安装依赖来绕过。

在本机强制find_spec返回None复现原缓存测试失败（red2，首个helper启动命令失败另保留）；仅该合成测试显式mock依赖可用，并新增显式/auto缺SDK仍503/data_capability_unavailable的反例。相同缺依赖环境下缓存测试green通过，独立缺SDK拒绝与整个模块11项通过。生产app字节、实际厂商执行与源合同不变；新候选完整门、独评及Mac安装须重绑，旧840b Mac结果不转写新候选。

## PR203第二次CI：模拟子进程端口生命周期

ed30候选同SHA Mac与Constraints已PASS，Checks run39916718351实际3906 passed、69 skipped、115 subtests、1 failed；Bao缺SDK相关测试已通过。失败为既有test_multiuser_runtime四用户容量用例，四个fake backend只有三个URL。真实RuntimePool关闭预留socket后等待实际子进程监听；原fake_processes既不启动进程也不持有端口，ready立即成功，OS可把已关闭的临时端口再分给后续fake用户。

新增确定性反例证明fake backend活着时同端口仍可bind（RED），不靠随机循环碰撞复现。仅测试fixture在fake Popen时绑定命令里的loopback端口并listen，fake stop释放，fixture finally清理；原四用户URL唯一、容量拒绝、既有用户不驱逐、停止后再准入断言不减。补测假子进程活跃时拒绝占用、停止后可重绑，模块26项通过。只开有界测试socket，没有启动服务/DSH、访问模型或修改生产runtime代码；旧失败保留，不手工rerun或降低门。新候选原三CI及Mac须再次取得。
