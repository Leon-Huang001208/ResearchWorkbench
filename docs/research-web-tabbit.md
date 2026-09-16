# Research Web Tabbit 集成

Web 一键安装固定 Node 支持范围与同一个 DSH 提交/构建闭包，但不下载或升级 Tabbit，也不改变
其 Profile、实时 claim、一次性正文 token、只读声明或写操作审批。Doctor 只报告 Runtime/端口
健康，不读取标签标题、URL、Cookie 或正文。

Goldar 框架解释与深度验证沿用同一个专属 DSH，但其 `framework-explain` / `framework-verify` 预设不装配 Tabbit；框架 Bot 不读取用户浏览器标签，也不改变本页 claim、授权和正文生命周期。

## 范围

Research Web 在私有 DSH Web Profile 中固定加载 `dsh-tabbit` 0.3.4 和
`research-tabbit-adapter`。供应归档、MIT License、官方源码提交、SHA-256、npm integrity 与文件清单
位于 `vendor/dsh-tabbit/0.3.4/`。Runtime 启动时先校验归档，再复制到私有
`runtime/home/profiles/node_modules/`；不从网络下载、安装或升级 Tabbit。

Profile bundle 顺序固定为 `base`、`web-app`、`dsh-tabbit`、
`research-tabbit-adapter`。`tabbit-installer` 始终禁用，guard 同时拒绝安装/更新工具。
缺少 launcher、浏览器离线、版本低于 1.9.0 或多实例未选择时只返回诊断。包要求运行
Node `^22.19.0 || ^24.0.0`；Node 23 和 25+ 不受支持。

DSH 的状态、Profile 和凭据仍由私有 `DSH_HOME` 隔离；启动环境只保留宿主的 `HOME`，并在
Windows 上按存在性保留 `USERPROFILE`、`LOCALAPPDATA`，供官方插件定位浏览器拥有的 launcher
与实例登记。该路径白名单不改变 DSH 数据目录，也不把 Cookie 或页面数据复制进产品目录。

npm 归档成员与供应清单始终按 `PurePosixPath` 比较；通过链接和路径穿越检查后才转换为本机路径。
overlay 中的 adapter 入口始终使用 `/`，避免 Windows 路径分隔符改变 DSH 配置语义。

能力工作区的 `#/skills?kind=tool&view=market` MCP Registry 目录与 Tabbit 只共用 Research Web
路由外壳，不复用 Tabbit 授权、候选或 claim 状态。进入能力工作区时会先清空尚未提交的 Tabbit
菜单请求；Registry 浏览保持只读，也不会改变本节约定的页面访问授权与实时 claim 生命周期。
Phase 2B 启用 MCP Runtime 后，专属 DSH composition 会额外加载经 Host 校验的命名空间 MCP 工具，
但这些工具不进入 `research-tabbit-adapter`，也不复用 Tabbit 的页面访问授权、实例选择、claim 或
一次性正文 token。MCP Runtime 的启停只重建其独立激活清单；Tabbit 仍按本页既有配置和授权状态运行。

## 配置与状态

设置 → 本地集成提供两个独立开关：

- 浏览器自动化默认开启；
- Tabbit 接管 `web_fetch` 默认关闭，开启时浏览器自动化必须同时开启。

配置原子写入 `<RESEARCH_DATA_HOME>/.control/tabbit.json`，权限为当前用户可读写。
文本固定使用 UTF-8；POSIX 以 `fchmod` 收紧临时文件权限，Windows 使用兼容权限处理并在关闭
文件句柄后才原子替换。关闭、清理失败只写入稳定错误类型，不覆盖最初的保存异常。
Windows 启动 Web 时读取的 DSH 认证文件不使用 POSIX mode bit 作为 ACL 证明，而是拒绝重解析点、
非普通文件、硬链接和打开前后身份变化；这不改变 Cookie 格式或 Tabbit 授权生命周期。
更改只影响下一次 Runtime 启动并返回 `restart_required=true`。活动研究期间既有 Runtime
重启门禁仍会拒绝重启，因此配置保持待应用，不会中断任务。多个在线实例时必须选择一个
16 位大写十六进制实例 ID。

统一集成状态同时保留 Tabbit 的“已保存配置”和当前 Runtime “已应用配置”，并单独展示
`restart_required`。重新检测只刷新诊断事实，不把待应用配置冒充已生效；旧快照恢复时只接受
白名单状态与版本格式，发现遗留敏感字段会先原子清洗再向 DataHub 恢复其他状态。

只读命令 `rwb web tabbit-status` 输出状态、版本、开关、在线实例数量和是否需要重启；它不输出
路径、Cookie、标签标题、URL 或正文。状态枚举为 `ready`、`disabled`、`launcher_missing`、
`browser_offline`、`unsupported_version`、`instance_selection_required`、`error`。

## API

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| `GET` | `/api/research/runtime/tabbit` | 返回安全状态、版本、CLI/launcher 可用性、实例数量、选中实例和重启标记 |
| `PUT` | `/api/research/runtime/tabbit` | 保存 `browser_enabled`、`web_fetch_enabled` 和可选 `instance_id` |
| `POST` | `/api/research/sessions/{sid}/tabbit-access` | 对当前会话和当前 BFF/Runtime 生命周期批准或拒绝页面访问 |
| `GET` | `/api/research/sessions/{sid}/tabbit-tabs?q=&limit=50` | 授权后列出所选实例内可 claim 的 HTTP(S) 标签页 |

消息请求可包含按用户选择顺序排列的
`tabbit_tabs: [{tab_id, instance_id}]`，最多 8 个且不可重复，并必须包含
`tabbit_live_confirmed: true`。缺少二次确认返回
`409 tabbit_claim_confirmation_required`。发送前后端重新读取 Runtime 标签清单并核对
tab ID、实例、协议和 `available` 状态；标题和 URL 不作为浏览器提交字段。

## 实时 claim 与上下文

输入框只有在用户键入 `@` 展开菜单时才请求候选，不在后台预取。首次展开先请求当前会话授权；
可按标题或 URL 过滤 50 项，支持上下键、Enter、Escape、加载/不可用状态和最多 8 个可移除 chip，
并与 `/` 能力菜单和附件共存。发送前二次确认会说明标签临时移入代理任务且分组可能改变；授权、
claim 或提取失败都会阻止发送并保留正文与 chips。

适配器只复用官方插件注入的唯一 `ctx.tabbit` 执行器，不创建第二套 Playwright 或 CLI 链路。
任务名为 `rwb-mention-<session4>-<request8>`；选中标签原子 claim 后在一次只读 evaluate 中依序
读取实时标题、URL 和 DOM 正文。官方 `pages()` 不保证返回 claim 顺序，因此适配器用发送前的
可信清单把结果恢复为用户选择顺序；标题与 URL 均相同而无法唯一映射时在 claim 前失败关闭。
每页最多 60,000 字符、全部标签合计最多 120,000 字符；公平
上限为 `min(60000, floor(120000 / 标签数))`，截断内容显式标记。

无论提取成功或失败，适配器都会在 `finally` 调用 `finishTask(task, {keep:true})`。标签页保持打开，
但不保证恢复原分组。claim、提取或 finish 任一步失败都不会提交消息；若 DSH 是否受理未知，沿用
现有幂等策略且不自动重试。

正文只存在适配器进程内存。消息仅携带绑定会话、单次消费、10 分钟过期的短 token；
`agent/pre-step` 消费 token 后将正文注入为默认折叠的插件上下文。跨会话、过期、重复或已消费 token
均拒绝。日志只记录会话 ID、数量、阶段、耗时和稳定错误码，不记录标题、URL、正文或执行代码。

## 只读与审批边界

会话页面访问获批后，Research Workbench 发起的实时 DOM 提取自动带 `read_only:true`。其他
`tabbit_browser` 调用缺少该字段或字段为 false 时触发原生逐次审批。系统提示禁止把写操作伪装为
只读；但官方工具可以执行任意 Playwright 代码，因此 `read_only` 是调用方声明，不是静态强制证明。
用户批准只读调用前仍应核对任务意图；写入页面、账号或外部系统的操作必须走逐次审批。

## 验证边界

Python/API、Node adapter、前端交互和 Runtime staging 可用模拟 Runtime 在原生 macOS/Windows CI
验证，但这不证明真实浏览器可用。当前 Web-only 功能的合并门禁为：真实 macOS 覆盖状态诊断、
首次授权、1/8 页实时 DOM、动态表单内容、二次确认、标签保持打开、失败保留草稿、只读自动执行、
写操作审批、`web_fetch` 开关和缺失/旧版指引，同时原生 macOS/Windows CI 均通过。

2026-09-10 的真实 macOS 验收使用 Apple Silicon、官方签名并公证的 Tabbit 1.13.24.0、可用
`tabbit-cli` 和一个在线实例，以上旅程均已通过。Windows 交付以原生 CI 的 Runtime staging、路径
语义、服务启动和健康探测为准；真实 Windows Tabbit 浏览器尚未验证，但不再阻止本 Web-only 功能
合并。该调整不改变通用桌面 Windows 发布前仍需真实安装级冒烟的门禁。Research Workbench 本身
仍不下载或升级 Tabbit。

设置页与 Office/Wind 本机诊断共存时，Tabbit 仍只读取自身 Runtime 状态与配置；本机软件发现或真实验证的忙碌态不会改变 Tabbit 开关、实例选择或重启标记，Tabbit 的健康结果也不会参与 Office/Wind 的可调用结论。Office/Wind 验证副本迁入对应 Office 容器只改变本机文件访问边界，不改变 Tabbit 的页面授权、claim、一次性 token 或浏览器数据生命周期。

Phase 2C Automation 通过独立 Claw 会话复用同一 Research Service，但不自动申请 Tabbit 页面访问、
不保存标签正文或页面授权，也不改变实时 claim、一次性 token 与写操作审批契约。

Office/Wind 显式验证证据在 TTL 截止时刻即失效，零 TTL 不会留下可调用状态；该修复不改变 Tabbit 的独立授权、会话或浏览器运行时边界。

2026-09-11 本机集成 Wind 改为复用已登录 Excel 并只操作独占空白工作簿执行最小公式心跳，不再以某份报告工作簿代表插件状态。该变化只收紧 Wind 验证与进程所有权边界，不改变 Tabbit 的页面授权、claim、一次性 token、标签保持、实时正文或浏览器数据生命周期。

MCP Runtime 与 Automation 默认启用不自动授权 Tabbit，也不把浏览器工具加入无人值守 allowlist；Tabbit 的实时页面授权、一次性 token 与写操作审批继续独立生效。

研究框架的“解释”预设固定无工具；“深度验证”虽可使用已授权的只读研究工具，但不会自动申请 Tabbit 页面访问、读取当前标签或复用一次性页面 token。框架 slug、章节、缺口与 snapshot revision 的绑定不改变 Tabbit 的独立授权和实时 claim 边界。

2026-09-11 的本机集成格式基线维护不改变 Tabbit 的授权、claim、token 或浏览器运行时边界。

`rwb` 在 Codex Desktop 中固定 bundled Node 后，Tabbit 仍沿用同一受审归档、overlay、授权和一次性 token 边界；该选择仅防止原生 Node 模块 ABI 漂移。

Method 选择不授予 Tabbit 权限，也不会自动添加页面引用、消费一次性正文 token 或改变浏览器 Tool
审批。即使某个 Method 与使用 Tabbit 的业务 Skill 同时采用，页面授权、实时 claim、只读声明和写
操作审批仍分别按原协议核对；方法记录不接收标题、URL、正文或浏览器参数。
2026-09-14 研究脚本 Host 增加全局 FIFO 单执行队列和 Python 3.12/科学计算包 readiness 门禁。
这只收紧 `research_run_script` 的本机 CPU 执行；Tabbit 的页面 claim、一次性正文 token、写审批与
浏览器生命周期不变。脚本槽仅在 child close 后释放；强杀无法确认关闭时 Runtime 保持 busy，避免
后续脚本与残留进程重叠，child `error` 事件也不能替代 close 或解除该状态。
浏览器实例选择保持独立，排队或 `runtime_not_ready` 不会扩大页面访问权限。readiness 对非对象
JSON 等无效探针响应失败关闭，不读取或改变 Tabbit 配置。

同阶段 DataHub Runtime 的 `market_bars` 与 `market_snapshot` 工具增加显式 `asset_type` 上下文；Wind binding 仅接受
`stock`，指数和 ETF 不会按代码形态猜测或改走股票行情。该工具契约不进入 Tabbit 页面请求、claim
或正文 token，Tabbit 也不能提供缺失的资产类型来绕过 Provider 的失败关闭。

2026-09-14 新增的六个 CPU 资讯/事件 Skill 仍只经既有 `research_run_script` 读取会话内相对路径
JSON，并受同一 FIFO、readiness、预算与沙箱限制；它们不调用 Tabbit、不获得浏览器标签正文，也不
改变页面授权、claim、一次性 token、写操作审批或浏览器生命周期。包内计算脚本、schema、映射、
provenance 和 synthetic golden 进入能力不可变版本，不构成新的 Runtime 或浏览器执行节点。
后续严格输入契约、未来数据拒绝和初始 disabled/receipt 启用门禁同样只收紧能力选择与
`research_run_script` 输入；`YYYY-MM-DD`、CNY、无换行分隔符的规范来源哈希 key/value 验证及 psutil 测试采样都不进入浏览器
交互，disabled 六项也不会成为原生 provider candidates，不让 Tabbit 取得新的页面、网络、文件或执行权限。
Stage 2 后续增加的 evidence artifact 派生 receipt、失败关闭旧版迁移、POSIX 逐组件 openat/Windows
final-handle loader 和完整 64 KiB UTF-8 envelope 只作用于六个 CPU Skill 的能力或 sandbox 边界；不改变 Tabbit 的页面
授权、claim、一次性 token、写审批、标签生命周期或浏览器 Runtime。
receipt 对 packaged golden 与 comparison run actual 分别验摘要并做业务 JSON 比较，六 CLI 成功 stdout
也不附加换行；artifact v2 还由宿主登记器 HMAC 绑定 synthetic/actual 输入和固定执行器，登记密钥不
进入 research sandbox。这些收紧仍不读取 Tabbit 标签或复用浏览器证据。

2026-09-15 新增的七个 Stage 3 基金/组合/行业 CPU Skill 继续只通过既有能力目录和
`research_run_script` 工作。它们复用安全相对 JSON、预算、64 KiB 完整输出和 comparison receipt
门禁，全部可发现但默认 disabled；未核验 DataHub 映射为 `callable=false`，单一快照/非杠杆权重、
基准偏离逐条报告期/行业映射等价、景气嵌套投影与拥挤度统一日历总额及至少两个滚动观测约束均只
处理调用方已提供 JSON。基金穿透的层级/cycle 校验和只吃预聚合数据的行业计算不会请求
Tabbit 页面、正文 token 或浏览器证据，也不会扩大 claim、写审批、网络、文件或执行权限。catalog
启动时对 enabled receipt 的重新审计及选择前复核也只会撤下不再可信的能力投影，不读取或改变
Tabbit 的授权、claim、标签、正文 token 与浏览器 Runtime 状态。

2026-09-16 新增的五个 Stage 4 CPU 量化研究 Skill（利率均线、股权风险溢价、风格轮动、平台突破、
缠论确认分型与笔）仍只消费调用方提供的会话内 JSON，并复用既有 `research_run_script`、预算、
不可变版本和 comparison receipt 门禁。它们不调用 Tabbit，不读取页面正文或浏览器证据，也不改变
页面授权、claim、一次性 token、写操作审批或标签生命周期；真实对照证据不足时保持 disabled。

Stage 4 复审增加的 provider-aware series descriptor role/identity/version/tenor 契约、风格独立
golden 和缠论歧义结构负测只收紧计算器已提供 JSON 的等价性判断；官方 JSON Schema 元数据 URI
也不触发远程加载。它们不访问 Tabbit、页面正文、浏览器网络或一次性 token，也不
改变 claim、写操作审批和标签生命周期。

Stage 4 质量复验进一步要求 comparison receipt 的 synthetic/actual 输入不仅路径分离，内容摘要也
必须不同；测试证据同时绑定相同业务记录及 source artifact 摘要，避免用无关文件满足独立性门禁。
缠论结果顶层回传唯一 `asset_id`，混合标的继续失败关闭。这些变化仍只作用于能力证据与离线计算
结果，不读取 Tabbit 页面或扩大其授权、claim、token、网络和写操作边界。

Stage 2 输出 schema 严格化与 event-review 共同交易日收益配对修正仍只处理调用方已提供的离线 JSON；
不读取 Tabbit 标签、页面正文或浏览器证据，也不改变授权、claim、一次性 token 和写操作审批。
