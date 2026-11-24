# 私网架构文档打不开：网关文档 Cookie 与沙箱导航修复

宿主 macOS（Mac mini），任务为功能修复。现象来自用户实际使用：在
`https://mac-mini-1.tail947973.ts.net/api/research/documentation/15-inbound-mcp.html`
打开失败，且设置页「架构文档」中的技术细节链接点不进。

## 根因（已复现，不是猜测）

1. 会话过期。用户的 Chrome 里 `能力中心` 标签页已跳回登录页，匿名请求返回
   `401 login_required`，这是本次直接原因。
2. 即使会话有效，文档之间仍打不开。文档响应带
   `sandbox allow-scripts`，属于 opaque origin；从一张文档点链接到另一张时，
   浏览器标记 `Sec-Fetch-Site: cross-site` 且不发送 `SameSite=Strict` 的
   `rwb_session`。网关原来只对 OAuth 导航留例外，于是返回
   `server_origin_denied`（403）。

第 2 点在浏览器中实测确认：使用 `SameSite=Strict` Cookie 从 sandbox 文档跳转，
目标页收到的 Cookie 为空、`site=cross-site`；改用限定路径的 `SameSite=Lax`
Cookie 后 Cookie 正常送达。

## 修复

- `app/research_web/multiuser/gateway.py`：成功读取固定架构文档时，额外签发
  `rwb_documentation`，即同一可撤销令牌、HttpOnly、Secure、SameSite=Lax，
  path 仅限 `/api/research/documentation/`。
- 该 Cookie 只在文档白名单路径被接受；其他路由仍必须使用原 `rwb_session`，
  不是新会话，也不延长 12 小时有效期。
- 网关放行固定文档名的顶层 GET/HEAD 导航；其他跨站请求继续返回
  `server_origin_denied`。
- 退出登录同时删除两个 Cookie；账号停用沿用原令牌撤销。

## 验证

- `pytest tests/research_web/test_multiuser_gateway.py`：28 passed。
- `pytest tests/research_web/test_documentation.py`：27 passed。
- 新增用例覆盖：Cookie 属性与路径范围、文档间跨站导航可读、
  文档 Cookie 不能打开业务路由、退出后文档 Cookie 失效。
- `ruff check` 与 `ruff format --check` 通过。

<!-- architecture-review {"group":"private-multiuser","structure":"unchanged","reason":"修复只在既有账号网关内增加文档路径限定的 Cookie 与固定白名单导航例外，不新增服务、进程或执行器。","diagrams":[]} -->
