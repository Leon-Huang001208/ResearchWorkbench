# Task14 scoped P2：Compose创建后失败的回滚

基线 `11cdbcc25`，仅处理 `task-14-scoped-review.md` 唯一残留P2；不重做任务1–12或改Task13三份并发回执。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"修复既有controller失败恢复路径；临时Compose overlay只提供本次创建归属标签，不改变单容器、image接受、进程、挂载或数据/凭据拓扑。","diagrams":["01-deployment"]} -->

## 根因与修复

原 `_call(compose up)` 非零/超时在after枚举前抛出，已创建容器未记录，候选残留会阻挡旧接受image重建。现在up失败也单次有界重枚举，使用启动前空快照、本次随机launch label、候选image及原完整ownership核验记录精确ID，再重验后删除。只有project/image相同不足以证明本次创建，故controller在私有临时目录生成最小Compose overlay传递launch标签；文件不含秘密且调用结束清除。既有停止容器不加新label，统一 `--no-recreate` 防止Compose重建它们。

未知/不可读/不同候选image或不同launch实例不删除：返回原up issue并追加 `docker_rollback_unverified`；删除失败追加 `docker_rollback_failed`，原错误保持首项。清理能力只消费一次，外层安装事务不会悄悄重复失败的删除并覆盖原异常。没有删除image、卷、bind数据或凭据。

## RED → GREEN 与验证

- 新场景首次12 failed / 7 passed / 1.59s：created-then-up非零/timeout、未知或并发实例、离线repair旧image恢复；`/private/tmp/rwb-task14-up-rollback-red.log`。
- 修复后含既有late-failure场景25 passed / 1.97s；`/private/tmp/rwb-task14-up-rollback-green.log`。
- 加入rm自身失败和防重复清理后14场景passed / 0.74s；`/private/tmp/rwb-task14-up-rollback-cleanup-errors.log`。
- 完整目标命令：`.venv/bin/python -m pytest tests/research_web/test_docker_runtime.py tests/research_web/test_setup_web.py --confcutdir=tests/research_web -q`，仅该pytest因真实loopback/ps fixture窄提升，不执行真实Docker或产品服务；最终结果补于下方。
- 最终目标闭包199 passed / 13.18s；`/private/tmp/rwb-task14-up-rollback-final.log`。此前首次完整闭包197 passed / 13.26s；`/private/tmp/rwb-task14-up-rollback-closure.log`。
- `compileall`、`git diff --check`、Python生成索引check通过。base `11cdbcc25` 的architecture与documentation-governance无violations，日志 `/private/tmp/rwb-task14-up-rollback-architecture.log`、`/private/tmp/rwb-task14-up-rollback-documentation.log`。
- 本波只改controller、其测试及直接说明。未改Compose主文件、manifest事务、Native、校验策略、全局设置、依赖、远端或真实用户数据。

## 证据边界

模拟runner证明controller的创建归属、失败传播、回滚与接受image恢复；不冒充真实Docker Engine的完整故障注入或平台验收。先前APT、image/两架构/持久化往返/CI等外部门仍由主代理维护，未在此改写。
