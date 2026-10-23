# DataHub 披露日期、发布版本与跨源口径专项

平台：macOS，功能开发；新隔离worktree，基线bb531a0。现有服务、PG5432、外盘、账号与模型保持无操作。无需新增依赖或付费服务。用户确认无FRED/ALFRED/Tushare，不再询问。

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"复核02模块及04数据流：新官方档案Parser与Sina利润表仍处于既有Provider节点，历史修订复用原WarehouseBinding和MarketStore可用/入库双时间、原件与冻结表；无新HTTP、服务、存储根或表。股票日历分支仅限bars，不新增宏观日历服务，原图准确。","diagrams":[]} -->

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只在原Research Web Checks同一Python步骤增加两个离线合同模块；完整Router、独立评审、原三CI与同候选Mac安装继续保留，未改变job、runner、门、超时、依赖或平台责任，08流程图准确。","diagrams":[]} -->

## 本批范围

- 新浪利润表明确selector、报告期与日期精度公告日/供应商更新时间、原动态item与原始HTTP；仍first_observed，历史修订/PIT未知。
- 东财SDK/游客资金流来源限定合同，非独立来源；未认证与iFinD的单位/订单分类/净额定义等价，禁止同名替代。
- 原64个来源之外新增bea_archive，仅审核2024Q2初值与第二版官方发布档案；不计作原57来源已修复，不代表完整历史或当前终值。只在已审核cutoff区间允许仓库发布信息回放，非本系统当年知识视图。

## 当前证据和未执行项

已取得三次公开直接HTTP探针：BEA第二版200/61080bytes、初值200/57209bytes；新浪财务200/157425bytes，仅有限8期/总117期。探针body与receipt在logs/pit-feasibility，当前网页公布版本与精确时间分别来自官方档案，原字节以可无损还原的base64进入两份公开fixture。

TDD和独立审查保留原失败：新模块缺失、名义GDP负例最初只误改meta而未改可见正文、BEA误进入股票日历导致StopIteration、并发旧读后同发布写入immutable_revision_conflict，以及目录新增来源后的明确计数/旧错误码兼容。逐项修复，不能删除失败证据。先前源级目标207项及59子测试通过，后续新增接线/并发/selector测试以最终日志为准。

真实完整Host/专用临时PG、重启与独立恢复已由attempt4完成；源码范围独立SPEC与质量复审无P1/P2。最终候选完整门/CI/安装仍待绑定，不引用旧PR196或本任务旧源码的CI作为最终候选通过。Windows/Linux产品原生NOT_RUN；本轮不部署。原任务Docker收尾阻断不通过重启现有服务绕过。

## 真实链路验收

`logs/real-pit-attempt1`因Broker末端未接通bea_archive在网络前失败：0直连/0worker，临时PG完整回收；补路由和回归后继续。attempt2/3保留当时源码证明，不能覆盖后续修改。最终attempt4的11源码hash与当前9个变更模块及service/contracts一致，6.815秒PASS，2次直连BEA HTTPS＋1次Sina财务worker；子进程底层HTTP未独立计数。没有厂商令牌、模型、现有业务数据库或外盘操作。

真实结果：BEA和财务均由完整ResearchService/DataHub内部HTTP写入socket-only专用PG；新会话缓存行/字段一致且零新增上游。BEA三个cutoff依次2.8/2.8/3.0，第一版前与未知第三版日期后拒绝；空仓历史请求零取数。Host与PG都实际重启后复查，五个冻结对象在第二空库恢复，digest/值及原始HTML保持；只恢复初值时第二版cutoff/latest均缺失。Sina选中2026Q2一行，原HTTP8期/总117期，公告2026-08-27仅日期精度，不生成publication_at；金额单位与历史修订资格仍未知。

review-red保存1项P1及2项P2的失败复现：部分恢复错选旧版、上海凌晨被UTC日期误拒、资金流端点attempts在冻结时丢失。全部修复后独立复审无剩余P1/P2；额外全null报告partial/零值有效测试保留red/green。资金流本轮没有实际vendor请求，只验来源合同、拒绝等价及冻结恢复；此前iFinD单cell不因此升级为跨源口径或财务PIT。

完整本机闭包先一轮627 Python/71子测试及264JS通过；全null补测后的最终结果将单独记录。业务验收不等于生产部署或全部57来源可用。

最终本机定点闭包629 passed/71 subtests（15.059秒），Router与市场JS264 passed（5.530秒）；12个改动Python文件Ruff/Black/isort及9源码Mypy正常silent模式通过。Mypy未全面检查未注解函数体。最终真实attempt4 PASS6.815秒、11源码hash匹配；独立SPEC/quality两份working回执均无P1/P2，待提交后绑定最终SHA。

提交前git whitespace检查拒绝官方HTML原件的尾空格，未提交或准备集成；两fixture改为base64 JSON，解码字节与原HTTP完全一致且校验SHA256，保留原数据与门禁，不修剪HTTP字节。运行时代码/真实attempt4证明不变。
