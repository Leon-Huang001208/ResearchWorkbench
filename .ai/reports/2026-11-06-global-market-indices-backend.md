# 三市场指数后端切片

- 宿主：macOS；任务：隔离 Web 功能开发；本切片不部署，不作 Windows/Linux 原生认证。
- API：沿原 GET overview 与 POST refresh，新增 global-v1，独立 indices:global-v1 缓存身份。
- 源：DataHub既有腾讯history注册合同的固定9符号有界适配；原生 OHLCV、按市场时区本地日、当日部分bar分离。Yahoo独立离线parser保留，不作线上重试。
- 安全：不改评分、生产准入、日程、入站MCP、凭据、数据库或旧12/24集合语义。
- 首次真实9符号探针：可用报价0/9、关闭日线0/9，全部 source_unavailable；
  摘要在 logs/global-indices-live-summary.json，不将已接入声称为源真实可用。
- 后续HTTP诊断：query1 SP500和query2固定9symbol均HTTP403，无代理环境变量；logs/global-indices-query2-summary.json。未改系统代理。
- 腾讯真实最终Provider：9/9报价，每指数100根关闭日线；CN/HK报价日11-06且今日partial单列，US报价日11-05，无gap，complete=true。证据logs/global-indices-provider-live-summary.json（只有元数据、计数和摘要，无报价原文）。首次来源失败证据均保留。
- TDD red：缺新模块的预期 ModuleNotFoundError，logs/global-indices-red.*；主任务审阅恢复后原node真实1 PASS并通过原retire_root回收同一根，失败原件外存保留。
- 离线完整17具体节点 PASS、0 fail/skip；logs/global-indices-full.json/xml/result.json/stdout/stderr，同批正式run已retired。WIP验收不冒充最终提交exact-SHA。
- 最终补充source元数据后同17节点复验PASS、0 fail/skip，logs/global-indices-final.*，正式run已retired。另5项旧指数合同和5项读缓存/取消/幂等/部分失败恢复回归共10 PASS，logs/global-indices-compat.*，正式run已retired。没有新活动测试根。
- 来源单位：指数点；本币和时区来自冻结指数身份/已核供应商市场合同；原生volume保持source_reported_volume且volume_unit_verified=false，不换算股份/手数/金额。日线timestamp显式为源日期在市场本地午夜的桶坐标。
- 静态验证：定点 ruff、black、isort 通过；完整CI、认证页面、部署另由主任务取得。
- 独评P2补修：实证null/数组顶层造成AttributeError；改为严格dict类型门及invalid_tencent_schema。新增null/数组/字符串三项one-bad-eight-good真实HTTP Mock回归，完整20具体节点PASS、0 fail/skip；logs/global-indices-p2.*，正式run已retired。未加宽泛catch，原取消传播保持。
- Python/Node依赖无变化；安装入口与现有bootstrap兼容性由主任务同候选CI验证，当前未认证。

模块合同见 docs/research-web-global-indices.md；最终集成交付和原生部署由主任务绑定精确候选。
