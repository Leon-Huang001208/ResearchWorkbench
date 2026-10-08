# 统一集成协调器

macOS 异根 lifecycle reader 只认证标准 OS 用户根中的既有私有 Native pair，不读取厂商
凭据或进程环境，不新增来源探测。消费者仍须目标单写者与就绪条件；Docker/Native 服务
生命周期成功不提升 Office/Wind/Tabbit 的授权或可调用状态，五阶段投影保持原合同。

启动器内部类型与格式整理不改变来源登记、授权、探测或可调用性投影；
质量检查与集成的实际能力验收继续分开记录。

统一集成协调器聚合 DataHub 与本机能力的登记、配置/授权、探测、适配和当前可调用事实。它复用已有 Provider、本机验证器、Tabbit 和 MCP Host，不创建新的数据引擎或守护进程。

从[分层阅读入口](../../../outputs/research-web-architecture/index.html#module-integrations)进入总图、说明、API、源码和测试。

公开来源探测有界并发，本机探测串行，结果原子持久化。Native / Docker 凭据不自动迁移；Doctor 或模型生成成功不提升来源为可调用，容器可见文件也不证明宿主 Office/Wind 可用。

固定 DSH 升级只迁移原生模块解析、preset 注册及子任务活动投影。协调器继续独立判断数据和本机能力，不将模型冷重启或一次公开基金查询的成功传播为所有来源可调用。空实例新默认模型和已有配置兼容，不新增探测器、来源注册或认证中心。
模型配置页的保存、Runtime应用、凭据与真实生成结果来自既有ResearchService，不加入第二套来源注册或五阶段协调器。模型生成成功不改变任何数据来源/本机能力的授权与可调用投影；模型凭据回执未知时阻断模型请求，来源探测仍按原合同独立报告。

installer 同次 auto-start 的创建 scope 不传集成凭据、不改协调器阶段；owned venv 与
实际 root/lease 就绪后进入原启动链，product_ready 仍不证明厂商能力可调用。

Native 控制文件首建先核验既有 MCP/DataHub origin，一致后才补齐缺失记录；协调器消费者
仅在成对配置与实际端点一致后启动，畸形配置失败保留原记录。

消费者启动前还须证明研究数据根单写者；其他 checkout 的产品监听可能通过环境/配置
共享当前根，稳定进程身份不足以放行。归属未知时先拒绝，不读取厂商凭据来推断隔离。

消费者健康失败的 fresh 事务可在精确退出与持续原监听/根/lease 证明下恢复原内部 origin；
失败恢复不会重新启动协调器或读取凭据，未知时主错误保留并附加受控恢复诊断。

macOS生命周期的实际端口记录和成对控制origin重绑只影响内部回调地址；不改变协调器五阶段，
不迁移厂商凭据，不把Docker服务健康当作宿主Office/Wind/Tabbit可调用证据。

内部控制 JSON/回环 URL 的纯 parser 提取至 stdlib helper；DataHub 原 reader 保留原异常和
额外有效字段语义，不改变协调器五阶段、来源授权、探测或凭据迁移边界。

Native 使用宿主 keyring；Docker 在显式配置的私有凭据目录中保存 DataHub 秘密，协调器只读取
DataHub 的安全状态投影，仍以登记、授权、探测、适配、可调用五阶段判定结果。两模式顺序共享
产品数据，但凭据不自动迁移；Docker 容器无法仅凭可见目录证明宿主 Wind、Office、Tabbit
或系统会话可用。Windows Docker 凭据目录 ACL 未能证明时安装失败关闭，不能把来源提升为
`runtime_callable`。

2026-09-29 的启动恢复只影响受管 3081/8088 的进程与页面可访问状态，不改变协调器五阶段状态、
责任桶、来源授权、批次并发、快照或 DataHub 动态选源。Doctor 的 `product_ready` 证明 Web 壳与
Runtime 协议可访问，不证明 Wind、天软、MySQL 或其他来源当前可调用；各来源仍须按现有配置、
授权与真实探测结果单独投影。
未安装环境的顶层 `rwb --help` 不初始化协调器、不恢复快照或发起来源探测；本轮 CI 修复
不改变五阶段状态和责任归因。

一键安装为协调器提供可复现的 Web 依赖与 CJPY 0.5.2，但不把“已安装”当成探测或可调用成功。
没有 `CJ_KEY` 时天软保持待用户配置；保存后的秘密由凭据库在每次探测/查询时动态读取，协调器仍
按既有五阶段模型和责任归因记录结果。
安装器对 Windows DSH checkout 启用命令级长路径，Runtime 首次启动先初始化固定 `web` Profile；
Profile junction containment 与 PowerShell PID 探针仅保证 Windows 3081 安全启动和回收；
这些修复只保证协调器所在 8088/3081 可复现启动，不把任何来源状态提升为可调用。
服务管理器在 spawn 前校验 Doctor 安装事实；安装未就绪时协调器和启动探测都不会创建。
该前置门不把 CJPY 已安装、数据源已登记或历史探测快照误报为当前可调用。
Node 选择与 Runtime build lock 的一致性只决定 3081 是否可安全启动，不改变协调器五阶段状态、
授权或 Provider 可调用结论。
纯 `rwb web status` 的导入不创建协调器，也不加载 Capability、MCP 或 DataHub Runtime 功能图；
Doctor、start 与 8088 Host 仍在各自既有边界内加载并验证这些组件。
安装阶段的 Web import readiness 不运行 lifespan 或协调器启动探测，不读取凭据，也不把任何来源
从已安装提升为已配置、已验证或当前可调用。

## 目标

`IntegrationCoordinator` 是 Research Web Host 内的数据源与本机能力状态编排层。它不替代
DataHub Provider、本机验证器、Tabbit 或 MCP Host，也不创建新的守护进程。它负责把这些既有
边界的登记、授权、探测、适配和 Runtime 可调用事实聚合成一个可恢复、可审计的状态模型。

```text
设置页 / Runtime 状态
        ↓
IntegrationCoordinator
  ├─ DataHub 单来源 probe（公共来源最多并发 4）
  ├─ 本机发现 probe（串行）
  └─ Tabbit 保存配置 + Runtime 应用配置 + 实时诊断
        ↓
原子状态快照 + 批次进度 + 兼容接口
```

## 状态契约

`IntegrationItemStatus` 使用 `schema_version=1`，每项包含：

- `registered` 与 `implementation_state`：区分目录登记、已实现和未交付。
- `configured` 与 `authorized`：配置存在不代表已授权。
- `stages`：固定为登记、授权、探测、适配、可调用五阶段。
- `last_attempt_at`、`last_success_at`、`stale` 与安全 `error_code`。
- `capabilities`：品牌无关业务能力 ID。
- `runtime_callable` 与 `responsibility`：责任限定为 `user/system/vendor/developer`。
- `bucket`：`available/checking/user_action/system_fault/not_delivered` 五类页面汇总。

认证失败和账号权限不足归入 `user_action/user`，因为下一步是用户更换本机凭据或联系供应商开通账号；
依赖缺失、版本错误和凭据库不可用归入 `system_fault/system`；限流、供应商不可达和供应商响应异常归入
`system_fault/vendor`。页面不再把无效 Key 误显示为本机系统故障。

快照仅保存白名单字段，不保存密码、Token、Cookie、MCP 环境变量、用户文件正文或本机绝对路径。
Provider、配置和环境指纹变化时，旧的成功证据保留为历史时间，但当前探测阶段变为过期，不能继续
证明可调用。

## 探测与授权

- 服务启动先读取最后一次原子快照，再异步创建 `trigger=startup` 的全量批次。
- `trigger=manual` 的全量刷新会对全部公共来源和已经取得逐来源授权的来源真实执行探测；未授权的
  账号、终端或可能计费来源明确显示跳过，不以一次“刷新全部”绕过授权。同 scope 同时只保留一个
  活动批次。
- 无凭据公共来源默认允许自动探测；账号、终端或可能计费来源需要逐来源一次性授权。
- 授权撤销后不再自动探测该来源，旧成功证据立即过期。
- DataHub 继续拥有单来源探测语义；本机管理器继续拥有软件发现和真实 Office 验证语义。
- 协调器关闭时取消未完成任务并把批次标为取消，不静默留下“检测中”。

写操作同时要求精确同源 `Origin` 与页面显式用户动作头，用于阻止普通跨站页面驱动本机探测。
当前产品是单用户 Web-only 回环服务，没有可向普通浏览器安全发放且能抵御同用户本机进程的私有
会话凭据；因此同源 XSS 和能直接伪造 HTTP 请求的同用户本机进程属于本批明确保留的威胁边界，
不能把上述头部描述成此类攻击的认证机制。

## API

- `GET /api/research/integrations/status?scope=all|data|local`
- `POST /api/research/integrations/probe-batches`
- `GET /api/research/integrations/probe-batches/{id}`
- `PUT /api/research/integrations/{id}/auto-probe-consent`

原 `/data/sources/{id}/probes`、`/data/probes/{id}`、`/local-integrations/probes` 和本机验证接口继续
保留；本机验证内部的 Workbook timeout 明确受 180 秒总预算减 10 秒协调余量约束，不改变协调器
状态或来源可调用判定。旧页面数据接口允许增加字段，但不删除既有字段。

## Runtime 工具

十五个 `datahub_*` 品牌无关工具常驻 Runtime。可用来源由 DataHub Broker 在每次调用时根据最新
配置、探测、适配和授权状态选择，因此连接状态变化不要求重启 Runtime。没有可调用来源时查询明确
失败；显式 `source` 且 `allow_fallback=false` 时不得静默换源。

Wind binding 只投影已登记且能由现有 `WindAdapter` 证明等价的业务能力、数据集、字段、日期、
复权和单位；不接收公式、表达式、路径或凭据。股票行情要求显式 `asset_type=stock`，指数继续走
独立 points 口径，无法等价映射的宏观利率、基金持仓和大宗交易保持不可调用。自动 Excel 查询使用
容量为 1 的专用 worker 和独立隐藏工作簿；超时或关闭未确认时保持单飞或 poison，不选择、保存或
关闭用户工作簿。

十八个 CPU 有界 Skill 不是新的协调器来源，也不直接持有 Provider 会话；它们只消费会话内已经
物化并带 dataset refs 的相对 JSON 快照，受统一行数、字节、序列、标的和 64 KiB 完整结果预算约束。
不可变能力快照仍由既有会话生命周期发布，清理只处理产品会话目录、调用收据和快照引用，不跟随
链接、不删除 DataHub 原始来源或用户打开的 Excel 文件；真实 Wind/Excel 对照不足时能力保持
disabled。

## 当前批次边界

协调器底座批次已交付协调、持久化、自动探测、统一 API/UI、Tabbit 双状态和 Runtime 工具常驻。
现有 Provider 闭环批次进一步完成 AKShare 轻量真实网络探针、天软/MySQL 安全错误投影，以及
精确 `cjpy==0.5.2` 的离线哈希锁、`PyMySQL>=1.2.0` 依赖契约。AKShare、财联社和东方财富基金已有真实探测、查询、
快照及 Runtime 调用证据；天软和 MySQL 在用户完成逐来源授权并提供真实外部条件前仍保持
`user_action`，不得以依赖可导入或模拟连接替代成功证据。

AKShare 财务摘要的布尔缺失哨兵规范化只发生在 Provider 结果边界，不改变目录登记、五阶段状态、
探测授权、动态选源或 `runtime_callable` 判定；Provider 查询成功仍与单元格是否缺失分开表达。

专业数据源扩展、其他公共/监管来源、文件同步和本地 MCP 真实调用属于后续批次；未交付项必须显示为
`not_delivered/developer`，不能计入用户“需处理”。

连接凭据改为每实例系统服务后，旧全局记录不参与配置/探测/可调用投影；需要在本实例重新录入。协调器仍按当前凭据状态失效和判定，不以其他 data home 的 Key 存在证明本实例可用。

## 设置闭环阶段3：当前能力范围

能力准入只消费现有DataHub当前配置/依赖/允许/探测事实；探测结果绑定非秘密配置身份，配置替换后旧健康证据失效。它不新建协调器；一次来源探测仍不代表全部dataset权限，真实调用持续检查且不能从失效缓存恢复授权。


## 单一兼容模型连接

兼容模型的配置/系统ref/原生生成仍独立于协调器五阶段数据与本机投影；文本生成不提升任何来源/集成为可调用。私有通道的model-connection只返回已验证非秘密配置，不读商业数据凭据，不新建协调器或Vault。

## macOS Office 显式验证诊断

PowerPoint sandbox根使用厂商实际bundle identifier `com.microsoft.Powerpoint`，与应用显示名Microsoft PowerPoint分开；不得由显示名推导容器标识。路径合同修正并不证明此前保存超时已经解决。

Office 验证在调用前将服务端验证ID绑定到本次32位run UUID与合成文件名；完整位置仍由既有Office sandbox根和固定后缀推导，普通API不接受任意路径。现有私有状态文件保留有界的验证run登记，冷启动将未完成任务标为interrupted，不重新执行Office，也不把工作进程退出解释为功能或文件清理成功。

验证结果分别记录last_completed_step、function_outcome、cleanup_outcome。只接收有限步骤/结果和合成文件名，不回传文档正文、账户秘密或任意本机路径。Word使用原生创建、保存、关闭/重开读回，并在save-as后按登记文件名重新绑定文档引用；Excel记录真实应用计算/保存/读回阶段；PowerPoint记录原生演示文稿/幻灯片阶段。库文件生成或编译成功均不是应用真实可用证据。

超时后父进程仅停止已登记的验证工作进程与所属Excel实例，不再重复Office受保护目录I/O。功能结果和清理结果互不替代；清理未确认时保留任务自己的进度目录和文件身份，不按普通老化规则删除，不通过文件名前缀认定未知对象可清理。文件已存在时拒绝验证且保留该未知文件。Word/PowerPoint只关闭所创建/重新打开的测试对象，不退出共享应用。

Wind Excel验证使用既有独立应用/工作簿模式及任务私有元数据目录；它不创建验证文件到Excel Documents。插件心跳成功只证明此次会话调用，不代替具体字段、日期、单位及数据集权限验证。iFinD目录中的旧用户名/密码HTTP网关协议并不是厂商官方refresh/access token协议，普通终端账户不自动证明HTTP接口权限；未完成的接口仍按事实保留未交付或待配置状态。

Office失败理由仅以明确错误号区分：-1743自动化拒绝、-54/-61文件访问拒绝、-1712命令超时、-600未运行、-128用户取消；unknown permission文字不推断授权拒绝。原始错误号只作为有限非秘密整数进入诊断，不回传stderr文档内容。准备阶段10秒、每个原生阶段30秒，记录整秒开始/完成/耗时；原总监督限额不提高。阶段超时仍不证明具体权限拒绝。

文档业务的Excel/PPT原生路径使用任务私有run目录的输入副本，不借用Office容器目录来绕过授权。Excel准入检查全部定义名称与普通公式，仅允许明确的本地函数；数组/数据表公式、外部链接/宏/连接拒绝，工作表与范围在启动前核对。PPT仅支持简单文字对象修改，按OOXML对象身份映射原生对象名称，固定脚本读取私有JSON；保存、关闭、重开后核对文本。原生失败不会转为文件模式。Word原生业务入口及两款真实应用闭环仍需各自验收，不由离线合同或编译通过提升为可调用。
