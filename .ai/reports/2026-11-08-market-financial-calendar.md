# 全市场财经日历（2026-11-08）

宿主 macOS，Web 功能开发。本平台验收覆盖候选 Web、公开排期样本与 macOS Bootstrap；不部署常驻服务。

<!-- architecture-review {"group":"ui","structure":"changed","reason":"全市场概览新增财经日历子页和独立请求生命周期，图13记录与既有行情路径的区别。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"research-api","structure":"changed","reason":"既有账号Host新增财经日历固定GET及有界快照，图13记录公开排期的按需读链。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"从现有财经日历页面经Host复用固定Fed/BLS下载及排期解析，图13新增这一数据分支。","diagrams":["13-market-overview"]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"Host 生命周期管理财经日历读取，不创建自动化任务、调度器或新运行状态。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"只在既有 Checks 和 Bootstrap 步骤注册测试与静态字节，不改变工作流拓扑。","diagrams":[]} -->

参考调查：公开脚本 `FinanceCalendarPage-k5qUt5sj.js` 给出周/月视图、五个分类、同源
`/api/finance-calendar` 和机构专用端点；匿名查询确认逐日统计和多类明细结构。
REA `ev_1bd09f1d802ccf284002ccb24bb5003806f8407e088be0073c1c2220e6b0ccb8`
只观察到匿名登录重定向。随后用户自行登录 Chrome，Agent Reach 的 OpenCLI 通过已连接 Chrome
扩展绑定指定标签，只读确认周历七组、月历单日明细及机构方向／基金集合／市场筛选。取得桌面
周历（1440×900，SHA-256 `3b5ea3e3320213b7e7c4274f9dd3097c61f999d0a61bd7e415c4b0b7a3d08736`）
和窄屏月历（390×844，SHA-256 `93447a469b57dfcd27d2744d262cb2c87223238995ca63a32e11b896de580af4`）
作为视觉基准。已还原原周历与经济数据选中并解除会话绑定；参考图原件留在本机私有临时位置，
不进入源码、CI 或生产服务。

官方源预检使用现有 `event_timeline.sources.fetch/parse`，未读生产或账号缓存：
Fed 成功解析 57 条日程（官方原件 SHA-256 `677be9c4dbc37b1e155cb7024559214bbfabb2c8bece8fa5f431dba6b15feb6d`）；
BLS CPI 与就业日程均为连接超时。三者只声明排期，不推断实际发生或历史 PIT。
本次真实 BLS 取数未通过；离线夹具可验证解析和降级，不能覆盖真实失败。

## 本机门与交付状态

后端定点合同修正测试夹具后 7 项复验通过；分页测试实际跨越上游缓存更新，旧快照仍可翻页。
完整 Router 的 Node/治理组合 238 项通过。Python Router 使用同一登记根保留最初失败证据，
`test_local_integrations.py` 106 通过、1 个原有 Windows 条件跳过，`test_protocol.py` 81 通过，
`test_api.py` 72 通过、141 项无完整证据。第 14 批触及 512 MiB 上限后终止本任务 pytest，
退出 -15，无最终 JUnit；现场和回执保留。已有工具只支持原登记批次以同批 PASS 证据退休，
不能以成功的复验子批替代失败回执，未创建第二根。

因此完整本机验证和远端交付尚未通过。常驻部署、Windows/Linux 原生验证和业务验收未执行。

浏览器夹具初测暴露主内容横向裁切，已限制横向滚动在日历与表格各自容器内。
真实 Chrome 参考对照后调整了分段选择器、周卡、月格、分类下划线及分页，保留 RWB 外壳、
字段缺口和来源。实际候选 UI 用冻结数据在 1440×900 与 390×844 验证导航、切换、逐日分页、
月历滚动、缺口列名及无行情刷新；两种尺寸均通过。候选使用离线数据，不能与参考站数据量做等同宣称。

Web JavaScript 全量首跑发现入口文件突破原体积余量，滚动恢复已复用既有重绘状态模块；
app.mjs 恢复原 260041 字节。固定 Node 24.19.0 最终回归 1382 通过、4 条件跳过；
完整 56 路径约束、文档治理与 Python 索引检查通过。架构图独立通过四种桌面尺寸
与同哈希视觉检查；这些证据不代替本机 Python 完整门及同候选远端 CI。
