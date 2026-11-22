# Wind资产工作区批准实施计划

最后更新：2026-10-22。状态：已批准实施，最终验收进行中。宿主：macOS Mac mini；任务类型：Web功能开发；本平台范围为本机功能、浏览器及同候选macOS安装CI。Windows/Linux原生验收分别交接，未执行保持NOT_RUN。此计划记录用户批准的 Wind v0、完整历史、三种复权与筹码调整；变更证据见 `.ai/reports/test_report_wind_asset_workspace_20261022.md`。

## 目标与保留边界

把当前资产观察改为完整Wind风格连续工作区，保留原全部字段、财务/股东/行业/事件/宏观卡、资金、两融、新闻/公告、自选、笔记、提醒、资料与研究交接。首轮历史支持沪深A股，基金入口独立保留。Host、DataHub Broker、会话快照和唯一DSH引擎复用；不建立第二研究引擎、全局行情数据库或新供应商通道，不改固定ECharts 5.5.0/Chart.js 4.4.7依赖。旧观察、旧冻结材料及个人数据可读。

## 页面与图表验收

- 采用平面布局，48px页头、18px名称/24px价格，桌面占满内容宽度，不留220px自选空栏。资产/查询/研究三个菜单完整承接原操作，自选收进抽屉；主图＋200px筹码＋260px指标侧栏。
- 默认日线，裸K、六条MA各自开关、BOLL以及日/周/月/全部周期保留；分时/多日未支持时明确禁用。默认副图VOL＋MACD，账号内保序保存0至4栏，指标菜单添加、逐栏移除，切证券共用。
- 十字线、滚轮缩放、平移、滑块与读数联动。副图增删不改变已有指标公式；周期覆盖层先聚合再计算，原MA预热、BOLL样本标准差、MACD/KDJ/RSI规则不变。
- 筹码输入为全部已载入日线中截至所选日期的前缀，与可见窗口和周/月聚合独立；同日移动/缩放窗口统计不变。至少5有效OHLCV、180桶，明确估算与真实输入范围，不声称真实持仓成本或未载入全历史。
- 桌面筹码与主图绘图区上下边界误差≤1px，共享价格域；手机可移到下方，仍共享价格域。明暗主题、多个宽度、键盘、菜单、pointerleave、切页/切证券、实例释放和迟到响应分别实测。
- 来源表保留请求/实际来源，数据日、as_of、retrieved_at、报告期、请求/实际/载入范围、单位/币种、限制、旧快照与失败区分。未知值不补造，资金净额不拆成流入流出。

## 历史任务与公开API

新增观察子资源的创建、列表、状态和取消4端点，以及账号图表偏好GET/PUT两端点，均沿现有认证/账号Store。准确字段见[API合同](../architecture/research-web/04-api.md#资产历史任务与图表偏好)。

- 创建为202＋Idempotency-Key，正文仅scope（recent/older/all）、adjustment（none/qfq/hfq）、可选retry_of；同键同参返回原任务，改参冲突。
- 近期取2自然年，更早向前4年，全部从近到远至已证明上市日；无上市日证明只声明1990-01-01扫描下界。每请求≤4自然年、≤5000行、15秒，边界日重叠检查，串行使用同来源真实Future。
- 公开job给state/status、progress、coverage、current_dataset、failure、request_key及显式重试信息。queued/running/cancelling/draining保持活动；completed/failed/cancelled/interrupted为终态。HTTP受理或旧数据不得伪报任务完整。
- 前端按规范snapshot全部row_count分页读取，不能在5000行上截断；保留实际覆盖与扫描范围、空响应和不完整状态，失败保留旧规范快照。

## 因子验证、缓存与规范发布

天软 `factor_macro` 只开放adjustment_metadata、listing_date、adjustment_factors三种封闭series；单证券，逐日日期列表≤500。不得开放任意repo、formula、宏观全集或额外参数。只用批准的SDK/授权路径，不安装新依赖、不复制秘密。

产品规范前复权为 `P(t)*A(t)/A(as_of)`、后复权为 `P(t)*A(t)/A(listing_date)`。复权前验证真实上市日行情和上市因子1、定义hash、每个交易日的精确正因子及固定截止锚点；更早历史续取保留原锚点。三模式保留量额原值，缺因子/IPO/anchor、重叠冲突、因子或来源配置版本变化全部失败关闭，不前向填充、不回退原价。OHLC币种/单位未声明，volume股/amount元只引用供应商目录。

定义版本tinysoft-adjustment-v1，SHA-256 `76fb444109d027db7657b8baea96a4299b5d8ddb826aac7edc31dfb09df82fc5`。实际授权预检为两只股票676交易日加上市日，共18次调用，原报告hash `85fc23ae55255cdaec3e693753d4202c972a56ba29b9bd41b93750c273849cf3`，独立gate PASS；原始行情/因子/wire只存私有logs，不提交。有限预检不认证全市场/全历史，厂商原生前复权的全局尺度和精确锚点未确定，不宣称vendor按as_of SDK保证。

原始块/因子不可变，账号缓存绑定会话/观察/证券、授权配置摘要、定义与因子版本；重试先复验哈希、授权及因子。每次新规范snapshot原子发布全部累计行＋同版本metadata，比较代次和原dataset指针后切换，不能把不同锚点复权块直接拼接。交接复制规范/raw/factors/metadata自包含证据，旧冻结材料不重写。无数据库迁移，仅兼容添加Store键。

## 取消、恢复与常驻安全

取消联动子DataHub call_id，真实SDK Future自然退出前保持draining与单通道占用；不发布迟到结果、不启动重叠来源调用。会话cancel/purge、service close和重启恢复覆盖任务，清理前核验归属与hash，未知对象保留。无owner任务标interrupted，不自动重试。

`/api/research/resident.active` 同时反映真实CJPY Future及历史非终态，异常witness为未知。操作员asset_queries_idle覆盖旧索引、历史queued/running/cancelling/draining/unknown/malformed；接受completed/failed/cancelled/interrupted和已取消DataHub查询终态，但真实Future仍阻止切换。旧数据、会话、报告、模型和凭据保全。

## 实施顺序与验证

1. 留存批准范围和独立真实复权预检，冻结定义，不再追加未经授权的厂商/模型调用。
2. 封闭Provider参数与metadata，校验Future容量、取消与超时，补纯复权及Provider边界回归。
3. 持久任务、账号缓存、代次CAS规范发布、全行读取、自包含交接、清理/恢复/空闲证明；不改变旧材料。
4. 平面UI、动态副图偏好、历史进度、完整日线前缀筹码、像素及移动例外验收，保留全部原功能。
5. 同步UI/DataHub/API/存储/开发地图、生成Python索引、API Atlas及既有02模块/04数据流图；执行文档治理和完整性检查。
6. 本机目标Python/JS、静态格式与完整性通过后执行同候选必需CI及macos-14干净安装、固定DSH构建、3081/8088、doctor；Ubuntu通用仓库门保留，不冒充Linux产品证据。Windows/Linux产品CI仅对应设备exact SHA触发。
7. 真实浏览器验证原功能、全历史>5000行、三复权与锚点、失败/取消/重试/恢复/交接/账号隔离；离线夹具和有限预检分别记录，不替代本条。
8. 独立评审、最新基线及分支保护通过后按持续授权提交/push/PR/合并；常驻部署另按明确授权与精确版本事务执行，真实页面、版本、数据保全另证。当前常驻5495基线不能被开发态结果替代。
9. 证据归档、任务资源回收、Git安全清理、空间复查；未知或活动资源保留，不能提前标cleaned。

## 证据状态与限制

预检、Provider154例、图表52例、UI136例、空闲相关359例仅为各实现阶段checkpoint，由主任务复核最终源码与日志；不是同一最终SHA全量验收。最终CI/浏览器/完整历史/部署没有实际证据前保持NOT_RUN或待验。无新增job/runner/超时/依赖，新增Python回归只加入现有Research Web Checks；Actions预算与当前visibility另存[预算说明](../actions-budget.md)。
