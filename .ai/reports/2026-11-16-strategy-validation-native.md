# 策略验证 Mac mini 常驻升级

## 范围

用户授权合并 PR #308 并更新 Mac mini 常驻 RWB，随后通过正式入口用原冻结行情验证四条研究规则。PR #308 已经通过 GitHub 普通受保护合并，产品提交为 `4983949df4aac654dd95415be1d5d6a654170ff5`。此次操作员以现场已接受的 `3be8a17b48ca5c57a71837bdc806efaf386a68b8` 为前版。

## 实现

复用既有 Native 联合事务及精确产品检查，新增固定模式 `reviewed-strategy-validation-v1`。保持空闲、主实例与网关身份、账号保全及原 MCP 设置的切换和回滚校验。当前操作员不改安装依赖、后台任务配置、策略默认条件和跨平台验收政策。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"策略验证只增加固定 Native 续版，主实例、DSH 和网关仍用既有联合切换及恢复，无新增进程或运行拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"策略结果经原账号网关访问，固定升级复用双入口身份与全部账户保全，网关账号路由和准入合同延续。","diagrams":[]} -->

## 验收记录

Mac mini 正式入口基线健康已确认，冻结行情包摘要为 `10877827ea5dc42f24eebea2e9d4eae6cce61a75809de1baffb6abfe22c98113`。候选测试、三项 CI、正式切换和认证页面跑数使用各自的验收回执。随代码提交的本说明不认证尚未执行的候选上线或生产运行。
