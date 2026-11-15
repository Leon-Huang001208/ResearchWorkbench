# Research Bot Native 受管升级

- 范围为 Mac mini 现有 Native 主实例和附着网关。产品载荷为 PR #302 合并提交 `88bec0ec04cbe2eb6979e6ebde695b992ed27336`，产品树 `cc3148cb806bf5a7b55e9a222580aceb3b782af8`。该产品的三项 CI 均已通过。
- 当前登记前版为 `1315d11a`。操作员复用原联合事务和回滚机制，校验已合并产品、运行条件、账号索引及 MCP 状态。
- 操作员候选、GitHub CI、实际常驻激活及入口验证分别记录。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"新入口在现有 Native 联合操作员绑定固定产品，不新增部署进程、容器或数据流。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"相同主实例和网关沿既有事务切换，账号身份和私网入口保留。","diagrams":[]} -->
