# DataHub 研究仓实施进度

任务：datahub-warehouse-20261022；平台 macOS；功能开发。状态：IMPLEMENTING，尚未交付/部署。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"研究仓复用数据设置与能力中心数据目录现有入口，增加内部状态面板及显式验证表单，不改变全局导航、框架或主题拓扑。真实仓库数据边界已在04图更新。","diagrams":[]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"本批仅在原租户边界补拒绝新仓配置路径，网关身份、账号隔离和资讯服务拓扑保持；未绕过租户权限或发布新共享仓。","diagrams":[]} -->

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"ResearchService仅增加可选可信存储桥注入及resident真实占用证明，原Host/DSH部署和HTTP端点拓扑保持，不启动新业务实例。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"changed","reason":"DataHub新增可选研究仓、原始日线内部缺口补数、实际失败切换及独立历史时点/冻结合同，图04同步存储与排空边界。","diagrams":["04-data-file-flow"]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"service构造注入不改变Automation触发器、版本、队列或预算；原日程执行仍走同一DSH，新增仓库不授予采集或模型权限。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"public-data只扩展既有工具请求策略和白名单结果/错误投影，不增加DSH执行器、进程协议、插件或模型权限；真实存储在Host内。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"既有Research Web Checks的同一步骤增加定点离线测试，未增加workflow/job/runner/timeout，Mac安装及跨平台交接规则保持。","diagrams":[]} -->

## 已验证

- MarketStore 内核完成两轮独立评审并修复历史重放、累计容量限制和时区等价幂等问题；42 项测试包含 15 项自有临时 PostgreSQL 真实测试通过。TCP 禁用、临时私有 Unix socket，无现有业务库操作。
- DataHub 新增范围仓读写、每次授权、历史时点失败关闭、取消后真实 SDK/数据库操作排空、多源实际尝试及熔断。当前可选桥依赖可信宿主绑定，尚未接入正式数据根。
- 扩大 DataHub 回归 243 项通过（一次 Starlette 弃用警告），在 BaoStock 最终接线前运行。BaoStock 接线后定点 69 项通过。以上不能替代最终完整变更集合验收。
- AKShare 原始新浪日线的换手率与成交额分开；东方财富成交量手转股，频率白名单与超时参数补齐。隔离 SDK 免费历史查询各得到 7 行；该结果不是认证页面验收。
- BaoStock 0.9.4 官方包已获授权并在隔离环境安装；原始沪深股票日线、股票目录、交易日历适配及单位/证券/复权校验实现。首次请求12.01秒超时；后查实官方SDK无EOF/recv时限，在自有子进程补有限socket/EOF边界后，免费重验2行/1.39秒、active_futures=0。保留首次失败事实。
- 真实Host API及临时PG完成3行→7行缺口补库、重启后禁止网络仍命中7行，零模型调用；近期同候选回归再次通过。财务摘要1行、指数日线2行实际取数，经默认ResearchWarehouse接入追加原生快照，PG重启后逐字节冻结原件与rows一致，1项真实测试通过（2.01秒）。原生快照仍正式回测不合格。
- 真实浏览器使用独立18994 Host/临时Unix socket PG：配置保存保持停用→显式初始化→AKShare免费2行及第二次仓命中→BaoStock免费2行及第二次仓命中；页面均展示冻结摘要。现有5432、常驻服务及外盘未改变。DSH传输fixture拒绝模型生成；这不等同认证私网部署验收。
- 原生快照修订使用固定逻辑键，超过10,000个捕获后仍投影单一截止版本，无永久累计查询上限；17项离线测试通过。新增独立评审发现未知单位被提升和同时刻并发歧义，已移除天软规范桥、加逐字段单位核验，并在内存/PG提交事务内拒绝同排序不同值；35项仓/真实PG回归通过，真实厂商门本轮默认跳过2项。

## 正在完成

最新本地分层结果（不是合并候选或CI总PASS）：DataHub/仓库/真实临时PG等394通过、2个LIVE_DATA条件跳过；Host/API/服务管理/本机集成738通过、1个Windows条件跳过、5个既有弃用警告（279.30秒）；架构/文档/额度/跨平台合同Node112通过。连接中心39通过；官方数值/token反射43通过；原生桥新增类型守卫定点通过。17个仓/新DataHub模块mypy通过，已修改Python的Ruff/Black/isort通过。独立Python修复本地目录误报和JSON转义令牌反射后限定PASS；JS过期状态定时清理修复后限定PASS。后续最新主线整合仍须重新绑定完整候选。

- 最终依赖锁、公开 worker 协议/容量边界、实际增量补库、仓库配置与 Doctor、来源修复清单和安装/架构文档。
- 插件另一受管worktree已形成本地检查点3334dfa576f55e53fb6c776fc6d46a611d8ab658，完成Host/DSH/MCP/双身份网关及浏览器验收；尚未与本研究仓分支整合、远端交付或部署，旧分支测试不得当整合候选通过。
- 最终 Python/JavaScript 独立评审、完整 Router、本机必需门、适用 Docker、同候选 GitHub Mac 安装、提交/PR/合并及资源归档均未完成。

## 权限与外部条件

正式库/服务部署、外盘迁移/格式化、全量采集未执行。付费账号、Windows/Linux 设备验收和认证私网页面为独立状态；缺账号只引导本机设置，不在聊天/日志收取密码。

中间命令日志目前位于 `/tmp/rwb-datahub-warehouse-*.log`，最终交付前须归档并记录哈希。报告后续按真实执行更新，不将中间计数拼成最终 PASS。
