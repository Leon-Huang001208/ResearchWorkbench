# 资产周期与副图 v8 固定部署

- macOS Web/Native操作员任务；产品PR213已合并1780064b，实际三个驻留身份一致5343e18d。
- 新增固定v8而非改写v7；沿原version4/64MiB严格索引/维护锁/BirthFence/全账号保全与恢复，市场inflight必须为空。
- 新mode不存在的RED已观察，日志logs/asset-v8/red.log。后续完整矩阵、Router、独评、原三CI、Mac安装、实际部署/认证UI分别留证。
- 无新依赖、凭据、DB迁移、Office、模型或新HTTP；旧reader/controller和全部旧profile保留。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"仅新增原Native操作员固定v8身份和CLI分派，原主实例/网关/DSH、维护锁、version4保全恢复拓扑保持；没有新节点或数据流，既有部署图准确。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"v8复用全账号索引冻结、64MiB严格读取与BirthFence，不新增账号/权限/数据根；额外市场inflight空闲分派沿既有能力，原私网与多用户图准确。","diagrams":[]} -->
