# FinGPT 原生 WeKnora 工作台

首批仅替换 FinGPT。RWB 保留名称、主导航及账号系统，知识库、聊天、智能体、Skills、MCP、沙箱和工具结果界面直接使用固定 WeKnora 完整应用；Claw 仍沿原执行链。界面可用与模型、供应商和金融质量分别验收，不能把未配置的 rerank 或未验证的子 Agent 写成可用。

## 登录与入口

网关账号根的私有 `fingpt.json` 配置 `origin`、`client_secret` 和布尔 `cookie_isolated`，文件须为当前用户所有、0600。没有该配置时安装和原有独立 Web 行为保持兼容。`rwb server doctor --json` 的 `fingpt_workspace` 只报告配置状态，不读取用户密码或冒充真实登录。

已绑定账号通过知识库原生 `/auth/me` 核验后保存 `sso_email`，不会用 RWB 用户名、浏览器传入邮箱、共享管理员或 API Key 代替原 WeKnora 身份。旧绑定由操作员用已有凭据库 JWT 核对并补该字段；JWT 和密码不交给前端或登录桥。没有绑定的 RWB 用户不能继承主账号的空间。

RWB 的 `/api/server/fingpt/authorize`、`token` 和 `userinfo` 只服务一个固定 client 和精确回调。60 秒一次性码绑定原 RWB 浏览器会话，token 仅用于这次用户信息交换；退出、禁用、过期或绑定变化后拒绝交换。固定上游原生 OIDC 客户端支持经认证的 userinfo 模式，不引入通用身份提供商或新 Python 依赖。发现文档位于 `/.well-known/openid-configuration`。

FinGPT 入口从网关取得 `/rwb-fingpt.html`，由 WeKnora 原生 OIDC 回调完成本地登录；原生前端继续管理自身 token 和会话。每次重新进入先清除旧的原生认证缓存，避免直接显示上次登录的账号；RWB 壳刷新不移除 iframe，不重开登录或中断原生流。RWB 退出会撤销交换凭据；已经独立打开的 WeKnora 标签仍遵循上游自身的退出和 token 生命周期，不宣称实现了上游尚未提供的全站单点退出。

## 原生前端代理

沿已有 nginx、frontend 和 app，不新增代理服务或镜像。`integrations/weknora/workspace_proxy.py` 生成精确的 RWB `frame-ancestors`，并仅放行 WeKnora 原生 `weknora_oidc_nonce` Cookie；浏览器传来的 RWB Cookie 不送到 WeKnora，响应的其他 Set-Cookie 被丢弃。保留原 WebSocket、SSE、上传、Bearer、原生 nonce 校验及密封的向量化 relay。`.mjs` 必须以 JavaScript MIME 提供。

同 HTTPS 主机不同端口本来共享 Cookie，不能裸用。仅已部署并实测上述双向边界的 FinGPT 配置可设 `cookie_isolated=true`；MCP 常驻配置还须显式登记 `weknora_cookie_isolated=true` 和 `weknora_oauth_origin`。默认同主机拒绝保持。身份登录不授予 DataHub 权限，原 `rwb.read` / `rwb.data.query` 仍走逐用户原生 OAuth 同意及撤权。

## 旧历史删除与部署

用户明确要求直接删除旧 FinGPT 会话、专属附件及生成文件，不备份、不迁移。原 `apply-reviewed` 增加显式 `--discard-fingpt-history`，只在已停止网关和 Host 后、安装候选前执行。Claw、知识库、DataHub、正式报告及实际共享材料保持；数据集保留原目录和 data-only context，不显示为旧聊天。DataHub OAuth 创建的数据上下文不属于聊天删除集合。

删除后重新冻结同一事务的保全基线，业务索引中除 sessions、receipts、operation_audit 外的内容必须保持一致；代码回滚沿删除后的基线，不恢复已删除聊天。没有本次显式参数的升级行为不变。

本机验收覆盖真实原生登录、用户/空间一致、iframe 不重载、双向 Cookie 和删除反例；同候选必要 CI、macOS 干净安装、实际生产切换与金融业务结果分别记录。Windows/Linux 原生验收不由本机替代。
