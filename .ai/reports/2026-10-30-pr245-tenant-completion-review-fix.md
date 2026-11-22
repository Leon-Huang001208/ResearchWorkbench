# PR245 多用户研究包完成回调修复

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"只在现有租户内部DataHub鉴权回调清单加入固定pack-completion路径；账号隔离、网关身份、业务路由、证据存储和DSH执行拓扑不变。","diagrams":[]} -->

宿主：macOS；类型：Web 功能组合修复。最终候选基线为已合并专业协作的 `db2ae9a`。

独立总审发现：多用户策略允许已启用内置研究包通过 `skill-preflight`，也允许
`specialist-control`，但漏掉内部 `pack-completion`。研究包与自有方法可开始执行，随后完成
回调在进入原业务路由前被拒绝为 `server_capability_disabled`，无法登记真实结束和保存结果。

仅将固定路径 `/api/research/internal/data/pack-completion` 加入既有内部回调白名单。
`tenant_policy.check_request` 仍先验证 `X-Research-Data-Key`，错误或缺失密钥返回
`tenant_backend_auth_denied`；原路由继续执行会话、对象、证据和幂等校验。未增加公开入口、
凭据种类、模型调用或供应商请求。

定点测试先在未修复源码上运行，研究包与自有方法两例均真实失败；修复后两例及既有
租户鉴权用例共 3 项通过。原始输出：
`logs/pr245-223-final/tenant-completion-red.log` 与
`logs/pr245-223-final/tenant-completion-green.log`。最终组合的其他本地检查、
独立复审、GitHub CI、macOS 干净安装和常驻验收按最终提交重新绑定；旧 `223dd87` 的
333 项 Node、51 项 Catalog、20 项研究包结果不自动认证本次新提交。

第一次独立复审指出以上直接策略用例尚未证明真实完成路由。于是将既有 macOS 原生沙箱正例
限定在完成回调窗口启用租户模式，沿合法预检、`execution_id`／`call_id`、真实脚本结果、
FastAPI 中间件及 `pack_completion` 路由走完整链。研究包 1 项、自有方法 3 项分别验证缺失／
错误 DataHub 密钥为 403，正确密钥为 200，且原有保存状态、执行计数和研究质量断言继续成立。
实测 `logs/pr245-22f-final/tenant-real-pack.log` 为 1 passed，
`logs/pr245-22f-final/tenant-real-owned.log` 为 3 passed。测试使用现有隔离 fixture 和本机
沙箱，没有真实模型或供应商调用；新增测试字节仍须随最终提交重新独立复审。
