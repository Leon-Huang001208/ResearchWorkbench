# Research Bot Radar 批次新鲜度修复

Mac mini Native 验收发现同一个测试 Bot 的手动和定时两条运行都因 `bot_source_unavailable` 终止，均无 DSH 会话或模型提交。

2026-11-15 23:16:41 北京时间直接读取固定 Golddata Radar。HTTP 原始 JSON 摘要为 `98c75fa6b0ddcc37475627a121ccafaeb249aac96aaf74a30dac441fb51e5584`。外层只有 `data`，内层包含 `generated_at`、`industries`、`recent_days`、`stats`。两层均未提供 `cache_stale`，来源批次时间是 `2026-11-15 23:15`，解包保留该字段。之前两轮看到的缓存状态 `not_reported` 与当前响应契约相符。 23:20:45 从在线 Host 读取解包后的 Radar，HTTP 200，四个内层字段和同一批次时间仍在，缓存标志仍缺席。

修复沿 Radar 自身证据准入。真正缺少缓存标志时，仅接受来源明确报告的、可核验且不晚于当前时间的批次生成时点，最大有效期十分钟。使用来源的北京时间格式和 Host 的带时区时钟。明确过期及无效证据继续拒绝。通过校验的依据与冻结原件写入运行历史，去重仍使用定义和原件身份。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"固定 Radar GET 和既有解包保留明确状态，现有同源认证、路由及 Host 关系继续适用。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"在既有 Bot 运行中校验实际来源批次并记录依据，现有 Automation、Store 和 DSH 流程继续使用。","diagrams":[]} -->
<!-- architecture-review {"group":"discovery","structure":"unchanged","reason":"Radar 生成时点进入原资讯 lane 的元数据，资料及读取失败仍沿原 Discovery 边界。","diagrams":[]} -->

定点回归使用真实响应形状的固定夹具，经 Radar 解包、Discovery 投影及 Research Bot 准入。修复前观察到 `bot_source_unavailable`，修复后共享环境 19 项通过。夹具覆盖外层过期、异常标志、旧批次、未来时间、缓存回填及原件去重。正式合并候选和真实运行验收分别取证。

Native 常驻配置 `reviewed-research-bot-v2` 采用原 v4 事务。产品检查点和操作员在同一 PR 内提交，以独立评审及三项 CI 核对最终合并版本。成功及回滚继续验证两入口和原 MCP 状态。真机复测保留原 Bot 及两条失败历史。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Radar 修补沿既有 Native 联合事务冻结版本，角色数、服务启动及回滚拓扑继续沿原流程。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"相同账号 Host 与网关复用现有切换，私网身份和 MCP 配置随现有保全对账。","diagrams":[]} -->

固定产品检查点 `fcc3e8990738d42bcc7a84d1c1ade36c4a05f784`。早期越界日期追加回归先观察到 UTC 转换溢出，再验证拒绝准入。受管操作员定点回归共 42 项通过，覆盖模式分派、真实 Git 祖先及原部署、回滚与 MCP 复核合同。
