# Research Web Tabbit 集成

## 范围

Research Web 在私有 DSH Web Profile 中固定加载 `dsh-tabbit` 0.3.4 和
`research-tabbit-adapter`。供应归档、MIT License、官方源码提交、SHA-256、npm integrity 与文件清单
位于 `vendor/dsh-tabbit/0.3.4/`。Runtime 启动时先校验归档，再复制到私有
`runtime/home/profiles/node_modules/`；不从网络下载、安装或升级 Tabbit。

Profile bundle 顺序固定为 `base`、`web-app`、`dsh-tabbit`、
`research-tabbit-adapter`。`tabbit-installer` 始终禁用，guard 同时拒绝安装/更新工具。
缺少 launcher、浏览器离线、版本低于 1.9.0 或多实例未选择时只返回诊断。包要求运行
Node `^22.19.0 || >=24`；Node 23 不受支持。

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
