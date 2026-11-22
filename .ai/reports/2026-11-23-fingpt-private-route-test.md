# FinGPT 私网路由测试契约对齐

Checks `45071638728` 实际选择 FinGPT 来源报告与 Fed 跟踪范围，两个 worker 的 JUnit 共
5363 项：5317 passed、45 skipped、1 failed。唯一失败为
`test_other_profiles_keep_the_original_private_route_gate`；原断言仍把已获准保留精确私网服务的
`FINGPT_MODE` 列为必须拒绝的其他 profile。没有据此推断未运行的 Node、编辑引擎或部署通过。

本次不改生产路由校验。将旧断言明确参数化为未扩展的默认、普通模型升级与市场升级 profile，
继续要求它们拒绝附接路由。原 FinGPT／已审升级的四项正例和三项路由缺失／改写／HTTP
拒绝例全部保留，`/collections` 保全例也保持。

Mac 本机使用原共享 Python，无新依赖、模型或生产调用：原 exact-SHA 单例 RED 复现
`DID NOT RAISE`；修后上述 11 项相关用例通过（0.18s），ruff／black／isort 通过。
RED 保留 failed，GREEN 为 WIP passed，两个受管临时根均已 retired。证据在原任务根的
`fingpt-route-{red,green}.retention.json` 及相应 JUnit／结果文件。最终候选 CI 和真实双入口
回滚／切换仍由原任务接续，不重置累计返修次数。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅对齐既有FinGPT精确私网路由的测试适用profile，未修改生产校验、事务或部署拓扑。","diagrams":[]} -->

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"默认及未扩展profile继续拒绝附接路由，原FinGPT严格正反例与账号保全保持，无权限或接口变化。","diagrams":[]} -->
