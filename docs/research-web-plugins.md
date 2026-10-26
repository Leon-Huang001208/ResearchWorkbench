# Research Web 插件契约

插件是现有能力与 MCP 的受审分发单元，DSH 仍是唯一执行引擎。入口是能力中心的
`#/skills?kind=plugin`。导入不启动进程、不安装依赖、不读取 Codex/Claude 配置或凭据。

## 包格式和支持边界

接受包根的 `plugin.json`（包括 `extensions.com.openai`）、旧
`.codex-plugin/plugin.json`、`.claude-plugin/plugin.json`，以及没有 manifest 的标准布局。
多个 vendor manifest 同时出现拒绝，不自动猜根目录或移动文件。版本是固定语义版本；无
manifest 时以内容摘要生成包名、固定 `0.0.0`。相同名称和版本的不同字节不能覆盖旧包。

| 组件 | 真实适配 | 明确限制 |
| --- | --- | --- |
| Skill | 通过 `CapabilityCatalog.create/check/publish/transition` 发布不可变原生版本，保留模板、沙箱 Python 资源、原生元数据和业务数据声明 | 原生静态检查、依赖存在性、脚本摘要和数据预检继续生效；不安装包中声明的依赖 |
| Workflow | 标准 `workflows/<name>/SKILL.md`、`capability.json`、`workflow.json` 交给同一原生目录编译 | 既有 Skill 绑定必须通过原生检查，不按名称猜业务等价关系或自动改写未知步骤 |
| Commands | `commands/*.md` 发布原生指令，`/包名:命令 参数` 使用本会话固定模板替换 `$ARGUMENTS` | shell 插值、宿主权限、model/tools/context fork 等未适配语义拒绝；不执行 Markdown 中的 shell |
| Agents | 原生 Skill 指令表示；`rwb_plugin_agent` 经当前 `ctx.tools.execute` 的完整守卫链调用已有 `subagent` | 另需明确 `agents:delegate` 权限；继承当前 Agent/model/取消/深度/原生审批与预算，不接受宿主 model/tool/permission override |
| MCP | 显式固定 Registry 选择复用原生 preview、confirmation、installer、probe、OAuth、工具策略和 session grant | Claude/Codex 任意 `command/args` 不直接执行；需要映射原生选择。服务器 OAuth 回调未适配，保持未就绪；Native 既有 OAuth 未改写 |
| Hooks | `before_message` 的有序声明式 allow/deny/cancel；明确批准的 macOS Seatbelt `/bin/sh` builtin 子集 | 不是任意 shell。无外部进程/fork、网络、Mach/Keychain、宿主资料或继承的环境秘密；HTTP/prompt/agent Hooks、其他事件及宿主 UI/cloud API 不支持 |

标准 Skills/Commands/Agents 接受纯指令 frontmatter 的 `name`、`description`、
`argument-hint`；影响执行、权限或路由的未知 frontmatter 会显示为不支持。原件仍可下载审查。
资源中 Python 脚本的具体 SHA-256、声明的工具和依赖逐项列入审批权限；只有完全批准本摘要
对应权限后，才向原生目录传入相同脚本摘要。原生代码分析、沙箱和质量门没有绕过。

组件逐项返回 `supported/limited/unsupported`、原因、`ready`、原生绑定和校验问题。
发布目录投影不等于 DSH 实际发现，`ready` 只有实际原生列表确认后才可成立；服务器还核对
启动时精确 guard 白名单。MCP 安装/探测/启用也不等于对任一会话可调用，更不等于 DataHub
某个规范数据集语义已核实。缺失数据不会因插件而变成 callable。

## 安全导入和审核

ZIP 上限 10 MiB，单文件 1 MiB，展开总量 20 MiB，最多 256 条；仅接受 stored/deflate。
路径必须是包内相对路径，拒绝 traversal、绝对路径、反斜线、控制字符、大小写/Unicode
归一化碰撞、文件/目录冲突、symlink 和特殊文件。没有 `extractall` 或安装时脚本。
摘要由排序后的路径及每个文件 SHA-256 组成，与 ZIP 时间戳、压缩元数据无关。

预览返回 manifest、文件清单/大小/哈希、组件状态和完整权限。界面初始不勾选权限，原件以
attachment/octet-stream 下载。审核必须精确匹配全部权限和包摘要；升级、新字节、新脚本、
新依赖声明或新增权利不能沿用旧版本审批。`.env`、宿主凭据文件、内嵌 MCP 秘密拒绝导入；
环境变量引用可保留，秘密仅通过原生 MCP 凭据入口提交，不进入包索引/原件/日志。

## 生命周期与旧会话

`preview → reviewed → enabled`；新版本改变后续新会话的默认选择。旧版本变为
`superseded` 后仍保留有效审批，已有会话继续使用其固定指令、Hook、原生 Skill 和资源字节。
不会将升级误当撤权，也不会把旧快照静默替换成新版。原生 Skill 准入根据当前会话固定的
包摘要复验，新会话不能通过旧原生名称偷选旧包。明确停用某版本才撤销该版本的后续调用；
包括已经登记到 receipt 的 Skill 数据/工具范围也重新核对当前审批。

切换、停用、回滚和删除要求明确空闲。回滚是选择一个已审的旧摘要，不重写历史。
已被会话固定的版本暂不删除，返回 `plugin_version_pinned`；原生不可变历史由其目录继续
保管，卸载只删除本任务安装目录内可证明拥有的副本，不修改上传源或用户其他目录。

MCP 暂不自动完成包版本并存切换：旧 MCP 仍活跃，或 launcher 没有生命周期证据时，更新
记录为 `deferred_updates`。旧会话保持原版本，新会话返回 `plugin_version_activation_deferred`；
不停止旧 MCP、不封掉仍批准的旧版、不把旧 grants 静默换到新 installation。明确通过原生
生命周期停用旧 MCP 后，才可应用新默认版本和新的固定安装/工具授权。

## 服务器共享、个人与个人凭据

`/api/server/plugins/{shared|personal}` 由真实 AccountStore cookie 身份授权：管理员导入、
审核、分发或撤权；用户只能读取共享仓和自己的个人审批仓。管理员可通过受验证的用户 UUID
管理目标个人审批仓，普通用户不能指定另一个 owner。界面隐藏按钮只是 UX，后端独立拒绝。

RuntimePool 只通过 manager 选定的 `RWB_SHARED_PLUGINS_ROOT` 和
`RWB_PERSONAL_PLUGINS_ROOT` 投影批准包到逐用户 `CapabilityCatalog`。同名跨作用域冲突失败
关闭。共享的是字节和审批，不共享安装 ID、OAuth token、环境秘密、session grant 或工具风险
策略。每位用户通过专用固定插件 MCP 路由配置自己的原生凭据。

专用路由跨 loopback 使用 method/path/body hash/actor/role/短过期时间和一次性 nonce 的
HMAC。角色来自网关登录状态，浏览器 header 不获得授权；nonce 消耗持久保存。安装确认 token
还受原生单次消费约束，未知安装结果不自动重试。全 `/mcp` 管理边界保持封闭，仅批准插件的
固定动作开放。唯一 MCP 内部 callback 仍先验证该后端自己的私有 MCP control key，再走
包/实际字节/配置/schema/会话授权和风险审批，不接受另一用户的 key。

## MCP 实际审核与两阶段重启

macOS 受管本地 MCP 仅开放离线 Python：PyPI 的固定 `python -m module` 或 MCPB 内固定
`python server.py` 入口，由 Host 自己固定的 Python 以 `-I -S -B` 启动；不使用包提供的
shell、env launcher、宿主 site-packages 或 `.pth`。npm/Node、供应商环境凭据及非 macOS
本地执行保持拒绝。固定远程 HTTP 端点与非受管 Native MCP 保持原合同。

管理员须显式审核新增 `mcp:offline-sandbox:<policy SHA256>` 权限；旧审批不自动启用。
显式重导入相同包可显示新权限，但清空旧权限与 schema 审核。实际安装复审另绑定当前政策、
Python/runtime/精确链接库和安装树摘要；启动、探测、工具调用与缓存恢复均重新验证。
改变任一绑定即拒绝，必须重新审核当前版本。SDK 运行仅拥有安装树及固定 runtime 的只读权限，
每次连接生成独立可写 HOME/TMP/XDG scratch。禁止网络 IPv4/IPv6/Unix socket、fork、
非固定解释器 exec、Mach lookup/register、POSIX IPC、signal 和进程信息访问；不传供应商
凭据或环境秘密。官方 MCP SDK Client/Session 管理协议；Host 受管专用 transport 在官方 JSON-RPC adapter 解析前限制单行 1 MiB、连接总输出 8 MiB（固定 64 KiB 分块），请求单帧 1 MiB、连接时限 35 秒。Host 拥有唯一新会话子进程，在独立任务内有界关闭/terminate/kill/wait并确认reap及句柄关闭；反复原生 asyncio 取消也须等待出生/回收结束后再传播取消。随后验证 scratch 身份并回收；未知进程、身份变化或清理失败保留scratch与runtime.operations出生/容量栅栏及明确错误。只读元数据和固定系统 runtime 文件可见，
不宣称抵抗可信 Host 同 UID 管理员在检查与启动之间的恶意竞争。

这些边界的 Native fixture 验证与真实 Host/DSH/浏览器产品验收分开记录；Doctor 的
`mcp_managed_local_sandbox.available` 仅表示平台具备入口，`acceptance=NOT_RUN`
不认证任一已安装包。没有相应原生能力的平台不会降级成普通 stdio 执行。

包审批以后仍保留原生安装确认。原生安装结果与实际安装树摘要绑定；探测后由管理员确认
固定 manifest/config/artifact/schema 快照。工具 schema 漂移、安装字节变更、源审批撤销会
使后续启动/探测/调用失败关闭。遗留非受管 active 清单不能因此自动获准启动。

插件页提供单独的待审工具调用队列：选择当前用户会话后，通过当前插件/组件的
`approvals` 与 `decide` 刷新、批准或拒绝，服务器不依赖已封闭的普通MCP管理接口。
参数正文不在页面显示，批准仍绑定单次调用、会话、安装、版本、schema和输入摘要。
切换范围、插件版本、组件、自动更换选中项或导入新包均清除旧确认/快照/调用队列；
异步MCP回包还核对原上下文，不能把旧组件响应回填到新的选择。

服务器启停采用 `stage → freeze → replace owned DSH → commit → unfreeze`：stage 保存候选
active 清单，但当前 Host 的 `_active` 与 grants 不提前变成成功；回包并释放 gateway 请求
出生租约后，Pool 才冻结此用户的新请求。后端先落原生 guard birth fence，再核实 HTTP
inflight、原生研究与子 Agent、交付/receipt、日程、资产历史、DataHub/probe、SDK 与插件 Hook
全部明确空闲。活动或未知返回 deferred/unknown，不发任何信号。

manager/generation/私有控制 key/owner record/旧 PID 与新 guard PID 都核对；只替换 Pool
拥有的 DSH child，Web child、用户 root、模型、会话和凭据留存。失败先恢复原 active 配置，
再尝试恢复已知的自有 DSH；恢复无法证明则保留 fence 与 `plugin-restart.json` 的 unknown。
freeze 响应丢失也视为可能已生效，使用相同 freeze 身份恢复；没有核验到 rollback/unfreeze
成功就不会声称恢复完成。附接的原常驻实例或旧版缺少这套能力时保持 unknown，不接管旧进程。

## API 入口

Native `/api/research/plugins` 提供列表、ZIP preview、按 digest 的文件原件、review、
enable/disable/delete。服务器 `/api/server/plugins/{scope}` 对应共享或个人审批分发；
`POST /api/server/plugins/runtime/refresh` 只请求本用户空闲实例应用。

固定组件的 MCP 动作为 preview/install/probe/status/review/enable/disable/classify/
authorize/approvals/decide。Native 前缀 `/api/research/plugins/{digest}/mcp/{key}/`，服务器
前缀 `/api/server/plugins/mcp/{digest}/{key}/`。服务器探测产生服务端锁定 owner/安装的待审 ID，
管理员从 `/api/server/plugins/reviews/pending` 读取原快照，再按待审 ID 批准，审批 body 不选择
owner 或任意上游。每次 schema 确认还复验预览时的实际 fingerprint。

## 验证与安装边界

离线用例覆盖恶意包、不可变审批/版本、实际 CapabilityCatalog 升级/回滚、旧会话继续与显式
撤权、MCP 字节/schema 失效、固定 proof、旧 active 拒绝、Seatbelt/超时/取消、出生租约和仅
自有 fixture 进程的两阶段重启。固定 DSH `7ecf564f2e09b829240c5553687223bdd1e2df73` 的真实
ToolRuntime 离线注册与嵌套 subagent fixture 证明执行管线契约；没有真实模型调用。

受管本地隔离回归使用官方MCP SDK和自有离线Python包，实际完成握手、发现、会话授权和工具调用；兄弟哨兵、安装写入、外部链接、继承FD、网络和子进程访问被拒绝。解析前单行/连接总量和时限有界，连续取消在真实reap后清理scratch；回收未知保留栅栏。早期无沙箱的失败关闭回归仍覆盖不支持的平台与目标，不把旧拒绝测试替代新进程执行证明。Mach/Keychain仅静态拒绝核查，动态验证未执行。

浏览器 fixture 使用实际能力中心与真实 Web/Plugin/Capability/MCP API，DSH 和外部 MCP Host
是明确的离线 fixture；另有真实临时 AccountStore/gateway 的 admin/reader cookie 登录验证
共享/个人权限。它们不代替真实外部服务器/OAuth、厂商账号、付费运行或常驻部署验收。

本轮没有新依赖，公开 setup-web 入口和 Web 锁保持。需最终候选 Mac 干净安装/固定 DSH/
3081、8088/Doctor CI 才能证明安装兼容；本机已有环境、fixture 和离线契约不能替代该门。
Windows/Linux 原生及 CI 为对应设备任务，未执行保持 NOT_RUN。无 OS sandbox 的脚本 Hook
保持关闭；没有任意 shell、HTTP、prompt 或 agent Hook 的降级执行路径。


2026-10-23 真实Host验收使用实际ConfirmationTokenManager、InstallationStore、PackageInstaller、SDKHost和AuthorizationManager；仅注册目录/字节下载为离线夹具，模型传输明确NoModels。原生审核HTTP契约接受远程三项和受管四项固定指纹，未知字段422且不改变审核记录。可见页面覆盖至会话授权，真实工具调用/人工批准由独立HTTP验收证明；不冒充完整DSH模型回合。

## 2026-10-23：长期研究档案与机会预警

新增一方小创候选包可下载并沿原流程导入预览；未核验真实 Registry ID／server／version／remote index，当前明确 unsupported／不可安装，不伪造条目或未知 schema。只有合法受管安装及审批后才显示个人固定 resource／slot 凭据控件，Doctor／status 继续沿原插件状态；实际 token 在 transport 绑定并检查所有回显，候选 resource/prompt 禁用。18项／54 子弹是本轮公开单价估算，真实当时报价、凭据、付费授权和部署均未执行；费用未知不重发，原件冻结为 clue，详见[候选合同](research-web-seek-alpha.md)。
