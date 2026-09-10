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

## 预期验证

- 本地静态/单元验证检查 workflow 触发范围、原生 runner、API/探测命令与证据上传契约。
- 推送后以 GitHub Actions 中 `Research Web Windows Verify / Windows local integrations` 的实际结论为最终证据。

## 变更—证据清单

| 变更 | 测试 | 文档 | 证据 / 结果 |
| --- | --- | --- | --- |
| `.github/workflows/research-web-windows-verify.yml`：原生 Windows 测试、回环服务与探测冒烟 | `tests/research_web/test_local_integrations.py` 静态契约及 Windows-only 真实主机检测 | `docs/research-web.md` | 本地相关 Python 107 项通过、1 项因非 Windows 跳过，JavaScript 14 项通过；原生结论等待本次 GitHub Actions |
| Windows-only 主机检测测试：实际调用 `DetectionEnvironment.current()` 与注册信息读取 | 同文件 Windows-only 测试 | 本报告 | macOS 仅确认跳过契约；必须由 `windows-2022` 实际通过后才能验收 |
| Research Web 启动索引、能力种子与 Workflow 目录显式 UTF-8 | 本机集成 API 初始化与 Windows 回环服务启动 | `docs/research-web.md`、`docs/architecture/research-web/07-capabilities.md` | 首轮 Windows CI 发现 CP1252 解码失败；修复后等待原生复验 |
| Windows DataHub 启动控制文件安全回退 | `test_windows_control_fallback_preserves_token_and_rejects_reparse_points` 与 Windows 服务启动 | `docs/ARCHITECTURE.md`、`docs/DEVELOPMENT_MAP.md`、DataHub 文档 | 第二轮 CI 已证明中文能力装载完成，随后发现 POSIX 专属目录标志；修复后等待第三轮原生复验 |

## 本地预检

- `conda run -n base python -m pytest tests/research_web/test_local_integrations.py tests/research_web/test_capabilities.py tests/research_web/test_report_workflows.py tests/research_web/test_api.py --confcutdir=tests/research_web -q`：107 passed、1 skipped。
- 本机集成与设置 JavaScript 契约：14 passed；本次变更文件 Ruff：通过。
- Black 全量检查仍命中仓库既有格式差异，不将其误记为通过；本次没有批量重排无关代码。
- Research Web 架构检查与文档同步检查：通过，0 violation。
