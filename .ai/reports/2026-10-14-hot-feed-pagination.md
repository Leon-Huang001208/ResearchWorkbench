# Hot 同源 feed 有界补抓

宿主macOS，功能开发，父候选abcb5c600。正式模型预算保持20calls/100000tokens/USD1，原账本18/77375/10464microUSD；本切片新增付费调用0，无依赖/迁移。

采集只请求固定来源明确声明的RSS/Atom next；同origin HTTPS、拒绝凭据/fragment/循环/多next/重定向。最多三页、每页4MiB、共享25秒。backfillDays=0不翻下一页；全部可信发布时间早于下界时停止，但不假设全feed有序或范围完整。无next仍为latest_snapshot。原件/页序/run/URL/边界与inbox同owner+claim事务保存；后页失败保留早页，成功水位不前移。解析按来源取得顺序排空，既存页复核hash后不再次发布采集成功、清错误或回退水位。材料取得时间与修订不可变合同保持。

新增测试初次缺少acquireFeedPages的RED日志pagination-red.log。单位闭包58PASS；真实PG新分页+来源权限2PASS，含第二页503、早页原件/hash/inbox、错误与水位保留、重跑排空/版本复用、事务中断整批回滚。TS类型PASS，独立TS只读审查无阻断，治理111PASS，文档/项目约束/文件索引PASS。项目约束首次缺UI模块说明，补覆盖/gap说明后通过，未降级路由。未执行取消压力/外部TLS/本候选MacCI，不把单测HTTP替身算作真实网络分页。

正常Native manager+原逻辑PG的四源各两轮真实HTTP通过；测试频率恢复原值、worker受管停止，最终Native generation95 paused。pagination-live-receipt.json及pagination-live-pg-receipt.json保存来源结果/页metadata/账本。四个当前feed全部stop=no_next_link，故实采证据只证明真实最新快照，不证明供应商实际多页历史。真实PG替身请求证明next请求与部分失败持久化机制，范围能力如实区分。首次验收driver误调不存在manager.rpc，finally已停止；修正后回执通过，错误日志保留。

最终Docker整镜像、最新资料联合恢复、已知事件日期、独立评价、干净安装与exact候选MacCI及受管交付继续，完整Goal仍INCOMPLETE；旧镜像/五个stage卷/dev资源保留，不增加预算。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"在既有hot.collect/parse、raw_pages/inbox和owner/claim事务中扩展有限next请求，不增加服务、schema或队列；原水位由采集唯一发布，现存页解析只处理材料。","diagrams":[]} -->
