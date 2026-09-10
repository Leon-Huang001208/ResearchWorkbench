# Research Web Phase 2B MCP Runtime 交付记录

## 范围

- 仅修改 Research Web、专属 DSH composition、共享 Python 依赖及对应 Web 文档。
- 不修改 Tauri、桌面打包、原生通知、PostgreSQL 或研究引擎。
- Registry 继续只读；不在应用内执行 publisher、构建或上传包。
- 通用 Automation 与外发不属于本批，留待 Phase 2C。

## 已实现

- 新增 `RESEARCH_MCP_RUNTIME_ENABLED` 门控的 MCP Host，使用用户已批准的官方
  `mcp>=2,<3` SDK；旧仓库根 `mcp` 包改名为 `research_workbench_mcp_server`，避免遮蔽官方 SDK。
- 安装严格拆为固定版本解析、完整预览、短期摘要确认、隔离安装、健康探测和启用。npm、PyPI、
  MCPB 分别核验完整依赖与哈希，拒绝 shell 字符串、版本范围、`latest`、安装钩子、隐式环境继承、
  特殊文件和链接越界。
- 远程只接受 HTTPS 或字面 loopback HTTP，关闭自动跨源重定向；OAuth 使用 PKCE、state、受保护
  资源与授权服务器元数据发现、受众校验和系统凭据库，不做 token passthrough。
- Host 保存不可变安装清单、schema SHA-256、风险分级、无人值守许可、会话授权和一次性人工审批。
  DSH 只加载 `mcp__{installation}__{tool}`，每次调用经私有 loopback 回到 Host 重核全部快照。
- 启停先探测候选配置并等待活动研究归零，只重启专属 DSH；健康失败恢复旧激活清单。安装记录保留
  `health_failed`，Web 进程不随 DSH 候选失败退出。
- MCP 市场恢复持久安装状态，分别提供探测、启停、移除、远程 OAuth、工具风险策略、当前研究会话
  授权和不含参数正文的一次性审批。Runtime 关闭时 Registry 浏览与离线缓存继续可用。

## 安全与日志

- 本地秘密与 OAuth token 只进入系统凭据库；安装索引、Runtime 绑定、API 响应、UI 状态及日志均不
  保存秘密值。UI 在提交后立即清空环境值并删除请求对象中的引用。
- 日志只记录固定事件、稳定状态和错误类型；不记录提示、工具参数、收件人、凭据或第三方响应体。
- 外部写入和高风险工具不能无人值守，且每次调用必须有人工作出批准。私有数据工具需要会话级快照。

## 架构证据

- `02-module-dependencies-final.json` 已更新 Registry/Host、不可变清单/策略与外部 MCP 连接职责。
- Archify showcase 校验：9/9，0 errors，0 warnings。
- 交付 HTML SHA-256：`35d40e47192dc574db28125e18e64f6a7a6d78aca39eded28dae8ef23dde95a1`。
- 1440×900、1600×1000、1920×1080、2048×1320 自动包含性通过；1440×900 Light 截图已人工查看，
  未发现遮挡、截断或不可读关系。自动回执中的 `visualReview` 保持原始 `pending`，没有改写为伪通过。

## 已执行验证

- `node --test tests/javascript/research_web_guard.test.mjs tests/javascript/research_web_mcp_adapter.test.mjs tests/javascript/research_web_mcp_marketplace.test.mjs`：34 passed。
- MCP Runtime 聚焦 Python：97 passed，1 个 Starlette 上游弃用警告。
- Registry、Runtime、API 与文档完整性组合回归：275 passed，1 个 Starlette 上游弃用警告。
- 相关 18 个 Python 源文件 `mypy --follow-imports=skip`：0 errors。共享虚拟环境内置的
  mypy typeshed 文件异常为空，直接运行会产生 `Operation timed out`；验证使用缓存的 mypy 2.3.1 wheel
  临时解包运行，没有安装依赖或修改仓库。
- 相关 Python 文件：Ruff 0.16.6、`black --check`、`isort --check-only` 均通过。Ruff 同样从缓存 wheel
  临时解包运行，没有安装依赖或修改仓库。
- `tests/e2e/research_web_mcp_marketplace.mjs`：1440/1280/768/390 的 Light/Dark 共 8 个视口通过，0 次写操作。
- `tests/e2e/research_web_mcp_runtime.mjs`：同样 8 个视口通过，并完成预览、确认、安装、探测、启用、
  风险分级、会话授权、停用、移除及审批拒绝的完整浏览器流程。
- 早期一次禁用插件但漏显式加载 `pytest_asyncio` 的命令产生 26 个异步收集失败；这是验证命令错误，
  修正命令后通过，不计为产品通过证据。
- 远端 CI 状态在发布到默认分支后补充。

## 未验证边界

- 本报告当前不声明 Windows/Linux、桌面包、公网多用户、任意第三方 MCP Server 或真实 OAuth Provider
  已通过。真实外部 Server 的可用性必须在用户明确选择并完成安装、探测和授权后单独判断。
