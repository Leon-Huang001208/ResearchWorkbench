# Local models 安全融合任务

宿主：macOS。任务：功能开发与修复。交付止于 PR，不合并、不自动合并、不升级日常实例。
基线 master：566523a0e0093f113ad12e57c3ef5cd0a8e0a87a。
来源：6ad0b275c86c8af03389af824451a6244759e61e。

## 结果与设计

在独立 worktree 分块融合交互、模型协议与 DataHub；保留 Claw 项目/草稿、研究深度/范围、
原生 Todo、证据笔记、HTML/Word/中文 PDF、准确交付状态与既有权限。
子会话关系修复已在 master，保留其严格 parentSessionId/origin/running 校验，不退回旧字段。
不导入重复 tar/patch/源码副本或机器截图，也不把旧任务验收报告作为本次证据。

四项修复：HTTP 认证入口在读取秘密前拒绝；兼容传输不认证未知模型工具能力；
推理块在正文/工具块前结束；异常、空对象及未知脚本结果失败关闭。
复审另修正文重试资格绕过、JSON/HTML 编码后的凭据反射，并补回归。
保留原 persona 的数据口径、缺失说明、文件重开、Tabbit 审批与四子任务限制。
未经证实的道乐 HTTPS 地址不猜测；原 HTTP 目录明确 blocked。成交量单位未经证实时不换算。
未披露模型容量时使用32768压缩预算，显式配置可覆盖，不把所有模型声称为1M上下文。

## 已执行与限制（提交时快照）

- 四项核心负向先失败后通过；协议闭包40项通过。
- UI专项157项通过；兼容协议19项通过，含真实固定DSH Loader/isolate/pruner/context消费。
- DataHub四模块157项通过；后续external编码反射闭包35项通过，计数重叠不相加。
- Research Web JavaScript最终整套417项、415通过、2项既有跳过；重试草稿保护亦通过真实事件回归。
- 架构/文档/Actions/跨平台仓库合同110项通过；文档治理、改动文件Ruff/Black/isort通过。
- 导入闭包Mypy 58错误，与未修改最新master的诊断逐条完全相同；全Web Ruff6错误，master同样6错误。
  不把相关新模块有限Mypy通过替代完整类型检查，不修改无关债务或放宽规则。
- 完整Python扩大检查：3412通过、7失败、10跳过。两项新增AKShare断言已修正；
  其余五项在未修改master上逐项复现失败（能力目录计数、Native临时HOME状态、框架凭据夹具、
  卖方Skill目录计数及资源脚本）。保留完整套件FAIL，最终影响闭包复跑另行记录，不替代此失败结果。
- 隔离Native安装/健康及GitHub CI仍在执行，最终状态以PR当前检查和后续回执为准。
- Windows/Linux原生验证、真实供应商与真实模型推理未执行；不读取或迁移现有实例秘密。

测试依赖仅在用户授权的任务环境安装，不修改产品锁、全局Python或现有服务。
日志留在任务logs目录；只上传脱敏摘要，不上传运行时认证、供应商秘密或原始请求。

## 结构复核

## 用户实际新任务失败修复

用户报告预览新任务失败。只读该会话原生事件确认：4次市场能力被data_contract_missing拒绝；
6次Python直接/相对字体路径间接触发getcwd拒绝，没有直接network绕过证据。
DataHub27次结果包含5次无可调用绑定HTTP400和7次failed；另发现northbound/money_flow被
当个股资金流返回、指数快照使用股票feed并改错后缀的金融口径缺陷。未自动重跑用户任务。

修复保持安全门：普通任务得到真实admitted与数据可调用性快照；deny摘要含安全missing.code；
非2xx只读4KiB JSON提取稳定code白名单，不泄message/raw/秘密；DataHub failed不投影成功。
新增打包字体绝对路径helper，真实sandbox相对路径红→绝对路径绿，同时cwd/network/未准入资源
负例保持；旧会话提示通过已准入模块__file__兼容，不修改历史资源或用户数据。
AKShare查询支持规则在Broker/SDK/缓存前同源复用；资金流日期先切片再限行，股票身份保持，
不等价北向/资金口径和指数/ETF股票feed快照明确拒绝。semantics revision失效旧cache复用，
原raw/rows保留，新调用可刷新。历史错误数据不能认证为真实北向资金或指数成功。

当前实际回归：相关Python230通过、Research Web JS425通过0skip、固定SDK五组61通过0skip；
Mypy20源码及导入闭包无error，Ruff/格式检查通过。供应商与真实模型未调用；CI、预览更新和
新Git绑定回执在提交后另行核对，既有内置Skill不因提示或目录存在被自动放行。

## 用户授权的继续修复与预览

2026-10-13 用户要求继续修复并查看临时服务。预览在独立安装clone保持已验证的1262b4858，
目录与端口38188/33181独立；product_ready及Doctor通过，不读取日常实例秘密。

五项失败的最小根因：工具/Skill目录旧计数遗漏已注册项；Native读探测用例检查了其他实例
默认端口而不是显式配置端口；框架夹具缺合成credential describe，且默认内置数据合同确实
不完整（继续409、无prompt）；研报脚本未显式准入锁版本资源。测试保留真实失败关闭，
以正规创建/发布/编辑/再发布的合成web-only v2覆盖框架成功路径，不授予默认内置数据权限。

类型修复采用精确Protocol/TypedDict/Callable和已验证类型收窄，保留锁、PID、alias、
manifest、清理、超时及回滚边界；结构化日志改用项目logger，fallback显式exc_info=False
不打印原异常，默认True保持。Wind11项公式、三复权参数及naiveUTC表示由离线回归认证，
不改变市场口径。Mypy完整导入闭包58项诊断及全Web6项Ruff已清零，新增检查不加ignore/noqa。

本轮完整Research Web Python复跑3439通过、10既有跳过、9警告、9 subtests通过，耗时1261.63秒，
没有失败；随后最新日志/Wind122项专项补验通过。已观察的专项：框架10、能力/研报61、非runtime340、
运行时1063（首次有两失败，时限例及端口例随后定点通过）、日志/Wind122通过。
JS/治理510项中508通过、2既有跳过。计数有重叠，不相加成总验收。
共享Wind路径触发额外桌面门，未执行门保留NOT_RUN，不削弱规则或擅自开启桌面工作；
新源码CI不能复用1262b4858的run。预览先固定旧提交，最终更新须确认无用户活动任务。

<!-- architecture-review {"group":"dual-runtime","structure":"unchanged","reason":"类型收窄保留已有根与PID证明、manifest、pipe清理和模式回滚，不增加控制器、端口或运行模式。","diagrams":[]} -->
<!-- architecture-review {"group":"mcp-registry","structure":"unchanged","reason":"RegistryValidationError继续是ValueError，认证与Pydantic拒绝语义保持，日志只增加稳定错误类事件。","diagrams":[]} -->
<!-- architecture-review {"group":"mcp-runtime","structure":"unchanged","reason":"安装Plan与Manifest的显式收窄沿既有安装生命周期，环境names和artifact完整性边界不扩张。","diagrams":[]} -->
<!-- architecture-review {"group":"report-workflows","structure":"unchanged","reason":"报告迁移仅补精确需求字典与Service Protocol，CLI原SimpleNamespace路径不改变执行和资源授权。","diagrams":[]} -->
<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"Asset类型默认值及空数据行声明保留资产观察API和现有权威口径，不新增DataHub查询或研究循环。","diagrams":[]} -->
<!-- architecture-review {"group":"local-integrations","structure":"unchanged","reason":"已验证native_error再查消息映射，原Office/Wind权限、poisoned状态和清理合同保持。","diagrams":[]} -->

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"共用原生renderer/controller融合停止超时和重试资格，不新增框架，Claw、深研和报告路径保持。","diagrams":[]} -->
<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"既有FastAPI Host继续负责会话和DataHub桥接，新增投影字段不创建研究循环，原准确失败语义保留。","diagrams":[]} -->
<!-- architecture-review {"group":"datahub","structure":"unchanged","reason":"外部Provider扩展既有Broker和会话快照，HTTPS及反射检查留在Provider边界，不新增数据库或调度器。","diagrams":[]} -->
<!-- architecture-review {"group":"automations","structure":"unchanged","reason":"共享service只保留精确工具验证，日程草稿、锁版本确认和原Automation监控合同完全保持。","diagrams":[]} -->
<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"固定DSH内注册兼容协议和隔离压缩组，安装器、唯一执行循环、Tabbit审批及进程所有权未扩展。","diagrams":[]} -->
<!-- architecture-review {"group":"capabilities","structure":"unchanged","reason":"external_data工具复用已登记准入和版本目录，未知endpoint/model不获得深入研究或MCP权限。","diagrams":[]} -->

<!-- architecture-review {"group":"files","structure":"unchanged","reason":"字体helper沿已准入资源模块定位只读打包字体，不新增文件仓库或扩大脚本cwd及网络权限，历史资源不覆盖。","diagrams":[]} -->

现场修复收尾时master更新至0cf38ff23（PR101 Docker凭据、PR102历史模式读取）。
以普通merge保留全部主线更新，文档冲突合并双方内容；DockerModelStore仅补backend类型声明，
不修改加密、锁或权限行为。对最新主线的凭据/启动/平台/协议/API重新回归，结果另见日志。

最新master融合专项JavaScript42通过0skip，Mypy22源码及导入闭包无error；
独立合并快审未发现P1/P2，精确选模、准入快照、历史字体回退与Docker桥均保留。
项目约束、文档治理、生成索引通过。首次pytest误加载根conftest因未授权的legacy SQLAlchemy
依赖失败；改用既有Web-only confcutdir，不安装无关依赖，实际结果见专项日志。

最新主线专项首次265通过、5失败、2跳过；5失败为Linux专属Docker后端在Mac直接运行。
修正测试平台路由，仅Linux执行这5项；新增非Linux构造拒绝且不创建凭据目录测试，
产品sys.platform硬门保持，Linux原生桥依然NOT_RUN，不把Mac跳过记为Linux通过。
