# 本机集成 Windows 原生验证

## 范围

- 新增独立的 Research Web Windows 验证作业，不借用桌面打包流程代表 Web-only 能力。
- 在 `windows-2022` 上运行本机集成、API、DataHub 与页面契约回归测试。
- 实际启动 `127.0.0.1:8088`，读取本机集成快照并完成一次幂等探测。
- 上传脱敏证据，只记录平台、服务在线状态、汇总、Wind/iFinD 发现与可调用布尔值及探测结果。

## 证据边界

- 原生 runner 能证明 Windows 代码路径、注册信息读取、回环服务和探测生命周期可运行。
- GitHub runner 不代表真实用户已安装或登录 Office、Wind、iFinD；这些项目不得因 CI 通过而标记可调用。
- 真实厂商登录、COM 自动化和工作簿刷新属于后续实现与专用 Windows 验收范围。

## 预期验证

- 本地静态/单元验证检查 workflow 触发范围、原生 runner、API/探测命令与证据上传契约。
- 推送后以 GitHub Actions 中 `Research Web Windows Verify / Windows local integrations` 的实际结论为最终证据。

## 变更—证据清单

| 变更 | 测试 | 文档 | 证据 / 结果 |
| --- | --- | --- | --- |
| `.github/workflows/research-web-windows-verify.yml`：原生 Windows 测试、回环服务与探测冒烟 | `tests/research_web/test_local_integrations.py` 静态契约及 Windows-only 真实主机检测 | `docs/research-web.md` | 本地 55 项通过、1 项因非 Windows 跳过；原生结论等待本次 GitHub Actions |
| Windows-only 主机检测测试：实际调用 `DetectionEnvironment.current()` 与注册信息读取 | 同文件 Windows-only 测试 | 本报告 | macOS 仅确认跳过契约；必须由 `windows-2022` 实际通过后才能验收 |

## 本地预检

- `conda run -n base python -m pytest tests/research_web/test_local_integrations.py tests/research_web/test_api.py tests/research_web/test_connection_center.py --confcutdir=tests/research_web -q`：55 passed、1 skipped。
- Ruff、Black、isort：通过。
- Research Web 架构检查与文档同步检查：通过，0 violation。
