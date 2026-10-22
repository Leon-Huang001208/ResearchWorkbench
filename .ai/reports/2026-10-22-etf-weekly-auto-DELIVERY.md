# 华安 ETF 周报自动生产：集成交付证据

任务 `etf-weekly-auto-20261022`；宿主 macOS；任务类型为 Web 功能开发。
源基线 `9b436613aad9136f4959c992c89dd72fc7354ed5`，本记录的初次集成候选
`50294bb8c`。最终候选、Router、评审及 CI 必须由主交付回执绑定；本记录不代替它们。

实现沿已有 Report Workflow → 私有 DataHub → 唯一 DSH → Host 质量门，保留旧
AlphaFoundry 只读。冻结真实底稿 57 序列、明确交易日/收盘口径、同源校准与 API/Excel
逐组切换；规范正文、中文展示投影、原模板图表、版本与定稿证据使用同一冻结输入。
主管理员归属、周五北京时间 15:30、未知受理待处理及先手动定稿后启用日程均在原入口执行。
普通租户权限、现有研究引擎和先前正式稿继续受原边界保护。

集成子任务已记录的实际验证：原 collector、首次 Excel 校准、原规范报告计划、真实 macOS
沙箱模板投影及原 Host 质量门的离线正向达到 `finalized`；同组 **118 passed，76.08 秒**。
数据/API 回归 **99 passed，20.18 秒**；两组存在交集，不能合计为独立用例数。
这两组均注入合成 SDK、底稿及完成事件，没有把模型自评或模拟质量结论当作 Host 通过。
原模板结构检查保留 3 个原生图表、3 份新嵌入 XLSX、18 张表，样式字节一致；结构检查
不等于 Word 逐页版式验收。独立界面夹具验证桌面/窄屏、四种状态分离、日程禁用和迟到响应。
最终源码变化后应由主任务重跑适用闭包，并保留执行 SHA 和日志，不能将旧检查伪记为新执行。

主任务收敛代码 `a9ef684e9` 后实测22个Python模块 **1099 passed，413.03秒**；独立
本机集成模块 **106 passed、1 skipped，10.73秒**；Node UI/协议/架构/治理 **210/210**。
11个核心Python源码mypy通过，全部39个变更Python文件Ruff/isort通过；Black仅剩
`datahub/snapshots.py`既有格式债务，新增解析段已按格式修正，其余38文件通过。
测试结束的旧xlwings atexit清理回调抛出枚举ValueError，pytest退出码仍为0，日志完整保留；
没有据此认证Office刷新。独立Python评审APPROVE（44例通过），JS复审PASS（26例通过）。
本机wheel内34个变更app文件与源码逐字节一致。对应日志为主任务`logs/etf-weekly/`；后续
文档、CI登记和一处空行格式变化不冒充这些测试原始执行SHA，最终集成与CI仍另取证。

最新主线集成候选`19e9890f2`的23模块实际回归 **1205 passed、1 skipped，404.72秒**；
Node合同 **210/210**，验证政策/回执/平台任务合同 **117/117**，完整项目约束及索引通过。
集成评审另外发现市场采集未纳入resident活动判断，已用真实阻塞夹具复现并窄修；该增量的
10项回归通过，源码blob经独立复审确认，完整API/Market运行中的唯一环境失败及正确运行环境
复跑证据见[修复报告](2026-10-22-market-resident-idle-fix.md)。未改动模块按源码blob复核
原结果，不能将前一候选整套回归伪记为在后续提交重新执行。最终CI须绑定最终提交。

本次 CI 登记扩大既有 Checks Python 文件清单，不改变 job、runner、超时或产品依赖；
原锁提取安装步骤同时固定已声明的 openpyxl/et-xmlfile，避免依赖全局或不确定的传递安装。
实时只读 GitHub API 证明 `PUBLIC/private=false`，近期标准 runner 成功记录及预算见
`docs/actions-budget.md`。本候选远端 CI、最终独立评审、受管合并与资源收尾在本记录创建时
均为 **NOT_RUN**，后续以主交付回执实际状态为准。

本次治理实际执行：生成 API Atlas（310 个声明、307 个唯一操作、15 类）及 Python 文件索引；
完整基线至候选的架构检查 95 个路径、0 违规；文档、架构、额度 Node 合同 **109/109** 通过。
日志保存在本治理 worktree 的 `logs/weekly-docs/`，仅认证本次实际候选文档与生成物。

真实 Wind Client API/本机权限、精确跨市场日历与经济日历合同、实际 Excel/API 等价性、真实模型
成稿与盲评、Word 逐页检查、至少三个真实周周期、常驻部署均 **NOT_RUN**。缺 SDK、来源合同、
数据或质量证据时保留阻断/未完成，首个真实完整定稿前不启用日程。本机源码和离线验证不认证
这些运营门，也不认证 Windows/Linux 原生支持；其他平台交由对应设备对精确候选验收。

用户随后明确授权独立环境安装官方SDK及一次只读对照预检，并补充可能只有Wind账户、未开通
Client API。实际预检发现Wind.app 26.5.3已运行，但Python无WindPy；[官方Client API页面](https://www.wind.com.cn/portal/zh/ClientApi/index.html)、
[下载中心](https://www.wind.com.cn/download.htm)及只读终端帮助菜单均未找到可直接安装的SDK包。
本次因此停在SDK获取/依赖层 **BLOCKED**，未安装第三方同名包，未调用SDK连接、行情、
`w.start/stop`或Office刷新。API权益仍为 **UNKNOWN**，API/Excel对照 **NOT_RUN**，不能写成
账户已被拒绝授权。原始来源、哈希和本机证据保存在主任务`logs/etf-weekly/wind-precheck/`。

PR183首轮候选`8e55a9d16`：Project Constraints通过；macOS Bootstrap通过（job543秒、
含排队run1147秒）；Research Web Checks失败（13 failed、2510 passed、28 skipped、22 errors，
job647秒）。三门实际checkout均为`93546a2ae850636b9b23ac664b224c148a4a2813`，父提交
为基线`99d3ee349`和候选`8e55a9d16`。完整日志和元数据保存在`logs/etf-weekly/ci-evidence/`。

已按实证只修三份测试：缺xlwings用例明确模拟受支持宿主，另测不支持平台的严格拒绝；报告
集成测试使用独立内存钥匙串并保留真实系统后端不可用的拒绝回归；旧resident桩显式声明市场
空闲前置条件并新增缺失见证仍未知的回归。生产源码和质量/权限/空闲硬门未改。实际本机报告
两模块84通过、resident53通过、API边界11通过；Mac受控Linux/无钥匙串模拟下原22集成业务
和新2凭据边界24通过，此模拟不认证Ubuntu。修补后的精确候选CI仍须重新运行并独立记录，
不能继承首轮Mac通过为新候选通过。

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"在既有能力中心和Claw详情投影周报状态与入口，保留原单页导航及Host请求链","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"新增周报准备路由仍由原FastAPI和ResearchService处理，不增加独立API服务或执行引擎","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"封闭Client API适配与取数仍通过原私有DataHub及快照交接，不新增跨租户通道或数据服务","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"周五生产继续复用原Workflow日程及后台资格复查，不引入第二调度器或额外常驻进程","diagrams":[]} -->
<!-- architecture-review {"group":"files","structure":"changed","reason":"规范正文经Host投影原模板并核对图表和产物哈希，冻结输入及正式稿档案链增加显式证据","diagrams":["09-report-workflow-sequence","10-excel-report-dataflow"]} -->
<!-- architecture-review {"group":"report-workflows","structure":"changed","reason":"原工作流加入冻结数据、原Host质量门、一次有界修订及独立定稿状态，保留唯一DSH执行链","diagrams":["09-report-workflow-sequence","10-excel-report-dataflow"]} -->
<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"仅复用主管理员既有Native绑定并在后台重新核验所有者，网关与普通租户隔离拓扑不变","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"模板脚本只使用Host注入的绝对会话根路径，保留原DSH执行及沙箱文件浏览器授权边界","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"回归登记复用原Checks步骤及Mac安装门，不增加验证引擎、模型调用或平台任务拓扑","diagrams":[]} -->
