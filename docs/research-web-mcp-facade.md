# RWB 入站 MCP 私网只读合同

本文件约束供成熟应用调用的入站研究服务。它与 `mcp_runtime/` 的出站第三方工具连接分开，不复用第三方凭据。源码实现、隔离 HTTP、干净安装、实际私网部署、Codex 真机和其他宿主的验收必须分别留证。规划或本地测试不代表部署完成。

## 产品边界

RWB 保留账户与权限、DataHub/Provider、冻结数据、来源证据、档案和质量门；固定 DSH 仍是现有研究入口的执行内核。FinGPT、Claw 的通用聊天和 Agent 执行功能停止扩建，既有入口保持兼容维护；退役需要另一次覆盖、恢复和权限接管验收。

入站 MCP 首版默认关闭，挂载于现有私网 HTTPS 网关 `/mcp`。不开放公网，不增加桌面代理，不通过手填令牌绕开宿主 OAuth。连接、发现和读取不调用 Provider、不发送模型、不创建研究会话，不提交工作流或业务写入。授权存储、审计及必要的既有 RuntimePool 状态记录不算研究执行。

## 规范身份与 OAuth

授权服务与资源服务逻辑分离，共用现有网关进程、账户库与受信配置的 Origin。请求的 Host/Origin、回调和资源不能由转发头或模型参数指定。

| 项目 | 首版合同 |
| --- | --- |
| 资源标识 | 规范 Origin 加 `/mcp` |
| 公开客户端 | `rwb-codex-native`；无客户端密码 |
| 回调 | `http://127.0.0.1/callback`；允许可变有效 loopback 端口；不接受其他主机、路径、用户信息、查询或片段 |
| Scope | 仅 `rwb.read`，同时受本次授权选材限制 |
| 授权方式 | 授权码与 PKCE S256；现有网页登录后显式同意 |
| 时限 | 授权码 60 秒、单次使用；access token 600 秒；refresh token 604800 秒并轮换 |
| 持久化 | 令牌及授权码仅保存摘要；不保存原始值或 PKCE verifier |
| 发现 | 授权服务元数据和 `/mcp` 的受保护资源元数据；不开放动态客户端注册或 CIMD 抓取 |
| 撤权 | 显式撤权、禁用账户和改密立即使相关授权失效；普通浏览器退出不撤销独立应用授权 |

授权响应必须携带规范 issuer。令牌请求若提交 resource，必须在消费授权码或刷新令牌前验证；省略时继承已绑定资源，不能生成无资源约束的令牌。每次调用和返回材料前重新检查账户、授权、scope、对象和外发资格。Cookie 单独存在不能调用 `/mcp`。

授权存储使用现有账户 SQLite 的增量表，不复制用户库。已有浏览器会话和凭据保持原语义。新表的部分损坏不能被误判为旧版本无表而跳过撤权。

存储安全检查、忙碌或 I/O 故障在授权码兑换与刷新轮换阶段返回 HTTP 503 `temporarily_unavailable`；授权请求创建阶段通过 SDK 返回带 `temporarily_unavailable`、state 和规范 issuer 的已验证回调。不能改写为永久 `invalid_grant` 或用户 `access_denied`。事务失败保留回滚后的原授权状态，服务端不自动重试结果未知的兑换或刷新。

## 选材白名单

首批只允许操作员明确批准的 `public` 或 `synthetic` 冻结材料。批准记录绑定账户、上下文、对象种类、对象引用和原件 SHA-256；默认没有批准材料。客户端声明“公开”、拥有会话、可下载或同意 OAuth 均不能自行赋予外发资格。

批准是服务器受信管理操作，不能通过四个 MCP 工具、授权请求或模型文本完成。用户同意只能缩小到该账户当前批准材料的子集。更换摘要、撤销批准、缺失来源、路径越界或原质量门判为 invalid 时拒绝读取；旧 invalid 产物不能通过新入口导出。

首版的严格只读模式进一步拒绝需解析 discovery/scenario/evidence 交接链的上下文，以及 `outputs/` 产物；来源仅接受已登记在 `inputs/` 的冻结 UTF-8 文本。原因是既有 GET 的交接验证和报告 detail 可能写 readiness/delivery 回执或协调子任务。受信只读模式在同一既有 GET 上提前拒绝这些情形，原浏览器行为和原质量门保持。批准记录也不能覆盖此限制；未来输出交接需要独立无副作用的质量读取设计。

## 四项工具

协议使用锁定 `mcp==2.2.0` 的 MCPServer 与标准 OAuth 路由，2025-11-25 Tools 基线、无服务端会话状态的 HTTP。SDK 内部格式和密码学不另写一套。只启用四个只读工具，不启用 Prompts、Tasks、Skills 或 Apps 扩展。

| 工具 | 输入与输出边界 |
| --- | --- |
| `rwb_capabilities_list` | 返回批准的数据能力元信息及本次授权可用上下文引用；发现不分配用户后端 |
| `rwb_datasets_list` | 只列指定授权上下文内的冻结数据集 |
| `rwb_dataset_read` | 原 manifest 或分页行；默认 100 行、最多 500 行；不重新生成摘要 |
| `rwb_source_read` | 未指定来源时列批准来源；指定后只读取已有冻结文本，每次最多 12000 字符 |

HTTP 请求最大 64 KiB，响应最大 256 KiB。分页、截断、coverage、缺失、来源和时点明确返回；空值和未知状态不能补成已覆盖。行数上限不保证字节上限，大行或大 manifest 必须明确拒绝或缩小分页，不能静默丢弃字段。

`/mcp` 仅通过 POST 执行协议消息，不提供持久 GET SSE 流。GET 先经过 SDK bearer/scope 认证及 Host/Origin 边界，合法请求及时返回 405 和 `Allow: POST`；缺少令牌、Cookie 单独认证或无效令牌仍返回 SDK 401 challenge，scope 不足返回 SDK 403。SDK 的 ASGI 路由登记为 `methods=null`，仅表示交由处理器判断方法，不声明全部动词可用。

账户由服务器验证令牌确定，客户端参数不能选择账户。只调用固定的既有后端 GET 路径；禁止任意路径、URL、SQL 或命令代理。内部实例控制 key、Cookie、浏览器 Authorization 和用户自选租户头不交给外部宿主。后端选择遵守现有 RuntimePool 容量，超限返回明确忙碌，不扩大运行池。

首版只选择原生命周期中**已运行**的账户后端。MCP 请求不冷启动 Web/DSH pair：现有冷启动会恢复框架采集、发现及报告 scheduler，可能触发取数或研究。缺少存活后端、维护冻结、旧后端缺少只读协议时明确拒绝，不回退到普通 `backend_for` 或关闭已有用户任务。连接、发现和列表不分配实例；批准元数据的可见性也不等于原件已现场核验。取消这一限制需要后续独立、无业务恢复副作用的读取服务设计。

## 安装与操作示例（未执行）

公开安装入口 `./setup-web.sh`、`setup-web.cmd`、`python scripts/setup_web.py` 继续使用已有 Web 锁；本次未引入依赖。已核对 `mcp==2.2.0`、`python-multipart==0.0.32`、`starlette==1.6.0` 与安装器；兼容性仍需同候选 Mac Bootstrap 干净安装证明，当前 `NOT_RUN`。

只有网关进程环境中的 `RWB_MCP_READONLY_ENABLED=1` 开启入口；缺省、`0` 或其他值均关闭。既有服务须在独立授权部署后按原受管方式更新，不能因修改当前 shell 自动认定常驻已开启。以下配置例子未执行：

公开 `./rwb server` dispatcher 在既有最小环境上仅传递规范 `0`／`1` 字符串；不传递其他 RWB 开关或模型／供应商秘密。Doctor 也走该实际交接，因此能如实检查显式开关，仍不初始化 SDK 服务或创建账号根。

```bash
RWB_MCP_READONLY_ENABLED=1 ./rwb server doctor --json
codex mcp add rwb --url https://research.tailXXXX.ts.net/mcp --oauth-client-id rwb-codex-native --oauth-resource https://research.tailXXXX.ts.net/mcp
codex mcp login rwb
```

Origin 和 resource 必须换成同一个已批准私网规范地址。GUI 原生 MCP 配置填同一 URL、公开 client ID 与 resource，客户端密码留空；由宿主完成 loopback callback 和 PKCE，不能手填 bearer 或改用代理绕过 OAuth。上述 CLI 语法仅由本机 help 核对，尚未修改真实 Codex 配置或执行登录。

服务器登录后在同意页核对账户、应用和逐项材料；在“已授权应用”撤销。材料批准只能由受信操作员调用 `AuthorizationStore.approve_material(user_id=..., context_id=..., kind=..., object_id=..., sha256=..., classification=...)`，classification 仅 `public` 或 `synthetic`；没有批准 HTTP 端点。批准必须先核实原件和来源许可，不从文件名、客户端声明或可下载性推断公开。

`rwb_dataset_read` 的 `view="manifest"` 返回原 manifest，`view="rows"` 读取已冻结 rows；manifest 原件摘要与 rows 文件摘要各自校验。`rwb_source_read` 省略 `file_id` 时仅列该上下文批准来源；片段摘要不替代来源原件摘要。两项列表基于批准元数据，不表示底层原件现场通过。

`server doctor --json` 中 `mcp_readonly` 只读环境开关和分发包元数据：`disabled` 或 `configuration_pending`，授权／连接 `not_checked`，原生 Codex／DSH／WorkBuddy／私网 TLS 均 `NOT_RUN`。安装包存在或版本匹配不等于连接成功；即使启用也不初始化 SDK、授权表、后端或模型，不读取凭据和历史正文。

## 验收与回滚

隔离验证使用临时账户根、公开/合成冻结材料、真实 HTTP 认证边界和可计数的模拟后端。覆盖无令牌、Cookie 冒充、错误 issuer/resource/scope、过期和重放、PKCE、恶意回调、读取中撤权、四用户隔离、十客户端并发、容量忙碌、摘要与来源质量门、零研究副作用及账户升级兼容。

Codex 真机链必须由用户网页登录并同意，通过原生 OAuth 读取批准公开材料并完成一次报告，独立复核；失败不自动重发。官方 DSH 与 WorkBuddy 的原生 OAuth 单列结果。文档支持、模拟 HTTP 和一个宿主成功均不能替代其他宿主实测。未运行的层级保持 `NOT_RUN` 或 `MANUAL_REQUIRED`。

回滚先关闭入口并撤销应用授权，保留新增授权表供恢复，不删除历史、不回退业务数据、不替换 DSH。常驻更新、真实账户授权及生产迁移不由本地源码实现自动授权。日志只记录主体、授权标识、操作、对象引用、状态和稳定错误码；不记录密码、Cookie、授权码、令牌、verifier 或无界正文。
