# 资产观察与 MCP 共用个股日 K 合同

<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"在原DataHub contracts内抽取历史不复权日线构造函数供资产与MCP复用，仍由原query/Broker/仓库/Provider执行，无新节点或存储。","diagrams":[]} -->
<!-- architecture-review {"group":"inbound-mcp-readonly","structure":"unchanged","reason":"MCP仍沿原scope/grant/账号Host提交与status读取，只复用已存在语义的请求构造，不改授权、工具参数、端点或运行拓扑。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"资产观察沿原API和history区块状态读取，仅在截至昨日stock/daily/none分支复用DataHub合同；现有刷新、来源、图表、canonical历史任务及分时链继续原拓扑。","diagrams":[]} -->

平台：macOS Mac mini；功能开发。基线 d8be7c41（PR338合并）。

## 实现

- DataHub contracts.stock_kline_query 统一身份、截至昨日的日期和规范raw日线语义。
- MCP get_stock_kline与资产普通history在stock/daily/none历史窗口共用该构造函数，再沿原DataHub.query执行。
- 资产API保留显式来源、refresh、观察状态与会话快照；raw历史懒加载继承观察来源，不将auto改为tinysoft。
- 复权/周月/非股票/含当日请求、canonical历史任务及分时保持原路径，不跨MCP HTTP。
- 无新依赖、供应商、工具schema、权限或部署改动。安装锁与setup入口无需改动，Mac干净安装CI另验。

## 证据与限制

- 首批12项定点用例通过；涵盖构造等价、显式来源与刷新、旧路径兼容、非法身份零调用及真实DataHub/Broker合成原件/行读回一致。
- 首次临时根准入用 /tmp 被工具以 parent_alias 拒绝；改用真实 /private/tmp 后通过并立即回收，无pytest假通过。
- 首次Black检查发现三文件需格式化，已格式化；最终检查与扩展回归结果随后登记。
- 回归新增raw懒加载来源用例；所有结果以实际退出/JUnit为准。
- 最终相关选择381个case全部执行退出0；第10批20个case包含7个unittest子测试，pytest9的JUnit总数与testcase元素不符，收尾校验失败。保留初轮/重跑日志、实际退出码0和该批failed回收状态；同一根经正式retire函数回收，不伪改为PASS。
- MCP任务合同另以原生unittest执行23项并含subTest检查，退出0；其余19个pytest批次均通过且即时回收。相关资产加载/观察/canonical历史与MCP/OAuth/账号隔离回归完成。
- 230项相关JavaScript检查通过；Ruff、Black、isort通过。文档初查补齐workbench架构决定及模块说明后通过，README已有入口复核为unchanged。
- 独立只读审查发现区块范围优先级和裸代码兼容两项P2，已修复；资产入口规范化代码、MCP仍严格。复核无新增发现。
- 修复后最终资产加载/观察/canonical历史185项通过并即时回收临时根；前批其他MCP/OAuth等回归结果继续有效，不声称最终候选整套重新跑过。
- 项目约束初查提示README复核记录缺失，更新为unchanged后零violations；Python索引和文档同步检查通过。
- 本轮只交付源码与PR，未计划或执行常驻切换；文档中心可先交付文档源码，不能将本任务写作已部署能力。
- 真实供应商、模型、浏览器业务操作、常驻更新、其他平台产品验收均未执行；不把合成原件测试称为厂商实取。

Product-Progress: not-required — 本轮复用后端既有业务合同，未增加页面入口或更改图表交互，常驻产品未更新。
