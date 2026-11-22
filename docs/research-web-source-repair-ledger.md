# DataHub 来源修复与实际验收账本

2026-10-22，macOS隔离功能开发。完整64来源的静态适配/能力清单与逐来源实际状态见[机器账本](../.ai/reports/2026-10-22-datahub-source-audit.json)。登记、依赖发现、目录和静态callable均不等于真实取数通过；没有账号或设备的项目保留NOT_RUN。

| 来源 | 本次实际结果 | 已修复或剩余边界 |
| --- | --- | --- |
| AKShare | 原始股票日线、交易日历、指数日线和财务摘要有界取数通过；股票增量补库及重启读仓、财务/指数原生快照重启通过 | 新浪换手率不冒充成交额；东方财富手转股；raw失败后才走另一上游；行数截断明确partial；财务报告期过滤，完整报表不冒充摘要 |
| BaoStock | 首次12秒超时；修复后2行/1.39秒；真实页面二次数据库命中通过 | SDK EOF及socket等候仅在自有子进程修复；实际完成前不释放容量；证券目录/日历单项真实验收仍待补，不把日线成功泛化 |
| 东方财富基金 | 原有NAV端点实际取得510050两行历史记录 | 未核币种、未复权总回报、缺基准明确保留；含这些missing的原生入仓仍待补，不宣称全基金研究仓已完成 |
| 财联社 | 原有电报端点实际取得两条 | 新闻不进入数值研究快照；不冒充历史全量或授权再分发 |
| 世界银行 | 官方接口实际取得2023–2024两期全球通胀观测，写仓及PG重启后同版本读取通过 | 分页头不算观测；未完成分页拒绝完整发布；今天下载的修订值不伪装过去公开版本 |
| Wind、天软 | 适配与授权/取消回归通过，当前隔离环境未做账户真实取数 | 天软未知单位仅保留原生快照；Mac/Windows SDK与Office各依赖真实设备及账户，不能用模拟替代 |
| iFinD | 用户确认Windows SDK权限；Mac官方HTTP授权页已提供，尚待录入现有refresh_token | token换取不取行情、不轮换token；授权成功不代表数据指标权限；历史time/table错位失败关闭；真实账户取数NOT_RUN |
| Tushare及其他账户来源 | 按目录登记，未新增付费订阅或假报可用 | 原旧适配有隐式前复权、全局token和吞异常问题，不直接接回统一数值查询；待逐项按账户/权限验证 |

官方接口结构依据：[世界银行API](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures)、[BLS v2](https://www.bls.gov/developers/api_signature_v2.htm)、[iFinD示例](https://quantapi.51ifind.com/gwstatic/static/ds_web/quantapi-web/example.html)。iFinD [FAQ](https://quantapi.51ifind.com/gwstatic/static/ds_web/quantapi-web/help-center/faq.html)将Mac入口指向HTTP；按[部署说明](https://quantapi.51ifind.com/gwstatic/static/ds_web/quantapi-web/help-center/deploy.html)使用现有refresh_token，不能为了探测而更新并使其他环境令牌失效。

原始字节、供应商字段与首次观测时间保留。原生快照正式回测不合格；覆盖、单位、历史可得性和修订链满足专门合同后才能提升。新增付费服务、稀缺额度探测、真实模型、正式部署及外盘调整仍分别确认；本账本没有触发自动批量采集或每日定时巡检。
