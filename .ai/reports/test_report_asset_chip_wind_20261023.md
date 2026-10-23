# 资产筹码、精炼布局与单位显示验收记录

任务 `asset-chip-wind-20261023`；macOS Mac mini，Web功能开发。Windows/Linux原生验收由对应设备接手；本报告不宣称跨平台通过。

## 范围与结果边界

已批准v0正式化：去嵌套卡片/重复说明/空概览；宽屏工具与历史读数跨整行，右侧指标与价格绘图区顶部对齐。图表直接操作、页签局部更新、搜索、复权与账号偏好保留。来源/计算集中到更多。万/亿显示按原始单位还原基数再格式化，两位小数；原快照和计算不变。

筹码增加封闭换手输入、同复权VWAP、衰减三角/平均分布、统计/龄/设置/历史叠加，明确自有估算。Wind观察用于结构与样本对照，不声称已取得其私有公式。均龄按已取得日线期数，原始数量、价格与未知缺口保留。

## 已执行证据

- 真实冷启动：隔离Store经 AssetWorkspace → HistoryJobs → DataHub/Broker → CJPY。单A股固定天软，全部2262条，2016-08-18至2026-10-22；完整逐日换手和VWAP，71个至多32日期批次，约82.174秒。记录位于 `logs/asset-chips/live-contract/result.json`，绑定三份后端源码SHA-256与不可变输入manifest。只读当前账号连接namespace，未复制秘密、修改生产业务或调用模型。
- Python定点：`python -m pytest tests/research_web/test_asset_chip_inputs.py tests/research_web/test_asset_history.py tests/research_web/test_cjpy_asset_data.py --confcutdir=tests/research_web -q`，117 PASS；另Router选定local_integrations/protocol/asset_workspace，244 PASS、1 SKIP，跳过原因保留原日志。
- 资产JS：`node --test tests/javascript/research_web_asset*.test.mjs tests/javascript/research_web_chip_distribution.test.mjs`，178 PASS（后续完整候选重新执行并由交付回执绑定）。MA/BOLL/MACD/KDJ/RSI原金值保留；旧无换手OHLCV分布不作为新模型的正确性oracle。
- 独立评审修复：共享桶边界防止平价原子双计（精确反例质量1.875→1）；重试读取frozen的include旗标；偏好签名纳入chip_settings。对应回归覆盖不同桶数质量/年龄守恒、重试body和同面板偏好加载/回滚。
- 正式隔离浏览器：使用产品组件和冻结输入，没有v0注入脚本。1575px宽屏读数31.19px高、横跨1460px；指标与图表上沿同为174.69px（实际高度随视区变化）。日期/周线/BOLL与筹码操作、明暗可见结果分别留图；最终宽窄/交互回执另存 `logs/asset-chips/`。

## 必需后续资格

完整changed-set Router为L4，未知边界风险保留。本地闭包、文档/索引/约束、最终独立评审和同候选Project Constraints/Research Web Checks/macOS Bootstrap必须绑定真实候选；不能用上面的局部结果冒充最终通过。安装清单增加四个静态资源，不新增依赖或削弱原门。

外部CI、合并、固定profile、驻留实际版本、空闲/账号与业务数据保全和认证浏览器结果，由受管交付及部署回执记录；本文不预先标记部署成功。当前任务不得因旧profile或旧常驻51f记录而覆盖最新实际版本。没有正式库启用/迁移、外盘修改、模型或周报生产。

## 结构判断

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"本轮是已批准资产页内部排布和数值格式化，延续原生UI、账号搜索、局部专题和图表生命周期；无新页面服务或研究引擎，现有02/03模块与交互层级仍准确。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"固定chip_turnover扩展原CJPY market_activity适配器，复用原Broker授权、串行SDK Future和冻结快照路径；未增加Provider进程、共享仓库或对外任意公式，现有数据流与集成图仍准确。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"历史任务与偏好仍使用既有观察和GET/PUT/POST路径，可选字段与前端纯函数分解不增加运行时节点；同版本换手派生与原子发布位于原快照链，旧模块/数据文件图仍准确。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"沿原Checks追加一个定点模块，Mac同一步增加本地静态资源名单；job、runner、依赖、时限与既有平台/恢复门未改，08迭代验收图仍对应原流程。","diagrams":[]} -->
