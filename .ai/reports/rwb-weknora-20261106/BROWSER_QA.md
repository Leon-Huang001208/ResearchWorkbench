# WeKnora 设置组件浏览器验证

- Date: 2026-11-06 / macOS；仅隔离组件 fixture，不是完整 RWB 或 WeKnora 业务验收。
- Browser: 现有 Playwright MCP，新建 isolatedContext=`weknora-qa-20261106`；未安装浏览器或依赖，未操作既有页签/原生应用。
- Fixture: `http://127.0.0.1:49447/`，标题 `WeKnora isolated settings QA`。实际加载当前 `knowledge-settings.mjs`、`core.mjs/createAPI`、`styles.css` 与 `appearance.css`，只连接合成 HTTP API。
- Source fixture: `/private/tmp/rwb-weknora-ui-zhxa24tq/server.py`；自有 PID 13755 / exec session 56591（验证后已按精确命令身份终止）。

## 观察结果

| 检查 | 实际结果 |
| --- | --- |
| 初态身份、非空白 | PASS；可见未绑定卡片，自动请求只有 1 次状态 GET，列库 0 次 |
| 绑定 | PASS；表单提交同步清空 JWT，忙碌期按钮禁用；服务收到字符串空间 ID `101` 和明确用户动作头；成功显示绑定用户/空间 |
| 显式列库及 XSS | PASS；点击后只有 1 次列库 GET；恶意 `<img ...>` 库名按纯文本呈现，无 img 节点或执行 |
| 失败恢复 | PASS；主动注入 HTTP 500 后显示“绑定结果尚未确认”，隐藏远端正文，输入为空；显式刷新后 POST 仍为 2 次，未观察到自动重发 |
| 浏览器存储 | PASS；localStorage/sessionStorage 均空 |
| 桌面和窄屏 | PASS；1440×900 与 390×844 均无横向溢出；窄屏全部输入/按钮位于视口内，截图已实际查看 |
| Console | 1 条预期的合成 HTTP 500 资源错误，0 warning；未观察到 JS 异常或框架错误覆盖层 |

## 证据及限制

使用 `browser_tabs(new isolatedContext)` → `browser_resize` → DOM snapshot/evaluate → submit/click → 截图 → console 检查。条件等待使用 MutationObserver，不使用固定浏览器 sleep。截图工具不能直接写 visualizations，故先生成本次精确工具产物、校验 SHA 后复制到任务可视化目录，再删除原临时截图。

未执行：真实 WeKnora 登录、服务撤权、原件/解析/向量化、WeKnora 管理界面上传/重解析、完整 RWB 设置页、真实周报及部署。以上均 NOT_RUN；本 fixture 不认证这些层级。

- `/Users/leon/.codex/visualizations/2026/11/06/01a1afd5-70bd-78b3-a760-5586b347c7bf/weknora-qa-desktop-unbound.png` — SHA256 `df7cefe61d0bc9eecab12c3de5db8453ea11492c58d7e44bb58f3fad2a1ac6f0`，87533 bytes
- `/Users/leon/.codex/visualizations/2026/11/06/01a1afd5-70bd-78b3-a760-5586b347c7bf/weknora-qa-desktop-bound.png` — SHA256 `0a4687098f7717c3c0c85ee8f20f4c041439d513a07275beae350627a80c7602`，109561 bytes
- `/Users/leon/.codex/visualizations/2026/11/06/01a1afd5-70bd-78b3-a760-5586b347c7bf/weknora-qa-mobile-failure.png` — SHA256 `fd5653d940801c0ed874c21b70160265cc8fc112d420501a5647fd03d59b0a28`，102190 bytes
