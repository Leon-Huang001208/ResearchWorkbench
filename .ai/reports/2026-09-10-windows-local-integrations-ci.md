# 本机集成 Windows 原生验证

## 范围

- 新增独立的 Research Web Windows 验证作业，不借用桌面打包流程代表 Web-only 能力。
- 在 `windows-2022` 上运行本机集成 API、探测生命周期与页面契约测试。
- 实际启动 `127.0.0.1:8088`，读取本机集成快照并完成一次幂等探测。
- 上传脱敏证据，只记录平台、服务在线状态、汇总、Wind/iFinD 发现与可调用布尔值及探测结果。

## 证据边界

- 原生 runner 能证明 Windows 代码路径、注册信息读取、回环服务和探测生命周期可运行。
- GitHub runner 不代表真实用户已安装或登录 Office、Wind、iFinD；这些项目不得因 CI 通过而标记可调用。
- 真实厂商登录、COM 自动化和工作簿刷新属于后续实现与专用 Windows 验收范围。
- DataHub 全量 Windows 兼容性不由该专项作业代替；第二轮执行暴露的启动控制文件 `os.O_DIRECTORY` 兼容问题已按固定路径安全回退修复，会话快照与连接写入仍不在本专项结论内。
- 专项冒烟使用一次性、无厂商权限的回环 DSH 认证元数据启动应用生命周期；它不证明 `127.0.0.1:3081` 上存在 DSH 服务，也不会把 DSH 或厂商集成标记为可用。

## 预期验证

- 本地静态/单元验证检查 workflow 触发范围、原生 runner、API/探测命令与证据上传契约。
- 推送后以 GitHub Actions 中 `Research Web Windows Verify / Windows local integrations` 的实际结论为最终证据。

## 最终结果

- 原生 Windows 作业 `34452526217` 在提交 `1e8aeba17db9a3a9402b4e7dce96de8bed819b2a` 上通过；项目约束作业 `34452526224` 同步通过。
- Windows 回环证据为 `service_online=true`、`probe_status=completed`；hosted runner 投影出 1 项可用、12 项需处理。
- runner 未发现 Wind 与 iFinD，二者 `callable=false`。这符合无厂商软件主机的预期，不代表厂商软件不支持 Windows，也不构成真实安装、登录或工作簿刷新验收。
- 脱敏 JSON 仅含约定的九个状态字段；未包含本机路径、Cookie、Token、密码或厂商秘密。随附服务日志同样通过这些敏感模式检查。

## 变更—证据清单

| 变更 | 测试 | 文档 | 证据 / 结果 |
| --- | --- | --- | --- |
| `.github/workflows/research-web-windows-verify.yml`：原生 Windows 测试、回环服务与探测冒烟 | 本机集成、运行时认证、协议和服务管理器的 Windows 契约 | `docs/research-web.md` | 本地相关 Python 117 项通过、1 项因非 Windows 跳过，JavaScript 14 项通过；原生作业 `34452526217` 通过 |
| Windows-only 主机检测测试：实际调用 `DetectionEnvironment.current()` 与注册信息读取 | 同文件 Windows-only 测试 | 本报告 | macOS 仅确认跳过契约；必须由 `windows-2022` 实际通过后才能验收 |
| Research Web 启动索引、能力种子与 Workflow 目录显式 UTF-8 | 本机集成 API 初始化与 Windows 回环服务启动 | `docs/research-web.md`、`docs/architecture/research-web/07-capabilities.md` | 首轮 Windows CI 发现 CP1252 解码失败；修复后等待原生复验 |
| Windows DataHub 启动控制文件安全回退 | `test_windows_control_fallback_preserves_token_and_rejects_reparse_points` 与 Windows 服务启动 | `docs/ARCHITECTURE.md`、`docs/DEVELOPMENT_MAP.md`、DataHub 文档 | 第二轮 CI 已证明中文能力装载完成，随后发现 POSIX 专属目录标志；修复后等待第三轮原生复验 |
| Windows CI 回环认证元数据 | 静态契约检查文件位置、占位令牌与私有权限；真实启动仍由 `windows-2022` 冒烟验证 | `docs/research-web.md` | 第三轮 CI `34444138805` 缺少 DSH 认证控制文件；第四轮 `34445221544` 进一步定位为 POSIX mode 在 Windows 上被误用 |
| DSH 认证控制文件跨平台安全读取 | Windows/POSIX mode、别名、文件类型、大小、打开前后身份、客户端与服务管理器回归 | 架构、开发地图、安全边界与本报告 | 第四轮 CI `34445221544` 的 Python 和 JavaScript 契约通过，服务启动暴露 Windows `st_mode` 误判；共享读取器修正后等待原生复验 |
| Research Web 私有运行目录跨平台校验 | Windows 不把 POSIX mode 投影当作 ACL；POSIX 仍拒绝 group/other 权限 | 本报告 | 第五轮 CI `34450837466` 证明认证控制文件回归已通过，随后暴露目录准备仍沿用 POSIX mode；修复后原生作业 `34452526217` 全绿 |

## 本地预检

- 本机集成、运行时认证、协议、服务管理器、DataHub 与 API 相关回归：117 passed、1 skipped。
- 本机集成与设置 JavaScript 契约：14 passed；本次变更文件 Ruff：通过。
- 本次变更 Python 文件的 Black 与 isort 检查：通过。
- Research Web 架构检查与文档同步检查：通过，0 violation。
