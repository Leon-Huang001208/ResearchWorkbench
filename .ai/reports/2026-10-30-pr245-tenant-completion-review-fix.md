# PR245 多用户研究包完成回调修复

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
