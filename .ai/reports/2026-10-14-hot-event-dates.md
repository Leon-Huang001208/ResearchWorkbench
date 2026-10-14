# Hot 事件日期与精度

macOS功能开发，父候选09215bbe9；schema20、原PG与唯一队列不变。正式模型scope仍hot_events_goal_01a11684，累计18calls/77375tokens/10464microUSD，上限20/100000/USD1。本切片新增模型调用0，无新依赖。

现有event.correct新增times，occurred/effective两项必给nullable claim，包含value、day/instant精度、来源timezone及不可变材料id/revision/quote。Node验证当前事件关联及原文title/excerpt字面quote；controller权限、UUID重放、版本/owner、append-only与PIT保持。自动重跑保留日期，活跃依据不能移出；日期撤回只释放日期专属限制，不解除其他人工protected。拆分移出依据前明确清日期；合并保留目标日期，源日期仍在旧版。旧snapshot日期null兼容，无迁移。Python发送前严格shape/日历/时区/引用验证，精确回执不符保留原UUID；稳定错误和日志不包含正文。

页面人工纠错和新简报提供日期与依据，日精度不补午夜、不随显示时区移日；UTC毫秒确切时刻另存。Markdown与Word保留同一冻结事件版本/精度/来源时区/引用。首次真实Word下载因旧time()拒绝day失败，日志保留，新增RED回归后仅事件日期允许day，其他材料/窗口/截止时刻要求时区不放宽；正常HTTP浏览器重试下载38073bytes通过。

PG日期回归1PASS：worker拒绝、旧cutoff未知、审计/重放、自动保护、伪quote拒绝不落盘、撤回后重新自动归组不残留日期锁。TS审查P2指出旧实现将date ref永久加入protected，已改为dateEvidence自身验证，新增撤回释放反例后关闭。Python控制与DOCX限定审查Approve。最终Python闭包67PASS/1anyio warning、TS/JS及治理208PASS、类型/编译/文档/项目约束/索引/Git完整性通过。Python初次默认收集触发legacy SQLAlchemy缺失，沿Research Web既有confcutdir隔离收集；临时目录需resolve通过存储alias守卫，未放宽守卫/安装依赖。

真实组件页已核对官方原文 https://www.federalreserve.gov/newsevents/pressreleases/bcreg20260929a.htm 署名日期及today published陈述，事件为反馈函发布，记录纽约本地2026-09-29日精度。不可变材料affec1f5-963c-4290-b74f-8ed5eb6bcb7c revision1及原题/摘要引用保持，生效未知。不是把发布时间普遍当作事件时间，也不把此核验当独立人工金标准。官方DeepMind URL本轮redirect使Web抓取不可达，不据此补其日期。原事件517a96f2-03ef-5b00-a68d-3a552447dd18新增revision2，旧revision1仍未知；新宏观简报03ba2707-f075-44b0-b3dc-f03f15f2fabf v1引用新事件版本，热度仍0。真实页面/MD/DOCX/PG审计见event-dates-download-receipt.json、event-dates-live-pg-receipt.json和event-dates-real.jpg。HTTP服务正常退出0，原Native generation99 paused，预算未变，旧资料/真实研究报告/镜像/五卷/dev保留。

完整Goal继续：独立真实评价/留出样本、最终最新数据库/原件/选定研究快照联合恢复、整镜像与顺序模式切换、干净Mac安装及当前exact候选CI、受管集成/交付。当前新切片不认证Docker/MacCI/Windows/Linux，不能使用旧CI冒充；Goal INCOMPLETE。

<!-- architecture-review {"group":"hot","structure":"unchanged","reason":"沿现有event.correct、原件/事件版本和controller审计追加人工日期依据，不增加schema、服务或任务后端。","diagrams":[]} -->
<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"复用人工纠错表单和事件/简报详情展示日期精度与依据，无新研究动作。","diagrams":[]} -->
<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"Manager扩展现有纠错参数与签名回执核对，不改变服务启停、凭据或模式归属。","diagrams":[]} -->
<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"已验证冻结简报的Word投影仅扩展事件日期精度及来源依据，复用原report_documents，无研究引擎或外发。","diagrams":[]} -->
