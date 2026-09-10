# Research Web Tabbit CLI 接入交付报告

- 任务 ID：`01k50tabbit9f7h2r6c4y8n3pqa`
- 日期：2026-09-10
- 范围：Research Web、产品私有 DSH Profile、Web API/UI 与跨平台模拟 CI；不涉及 Tauri、sidecar 或桌面安装包
- 分支：`codex/01k50tabbit9f7h2r6c4y8n3pqa-01k50tabbit9f7h2r6c4y8n3pqa`

## 交付内容

- 固定供应官方 `dsh-tabbit@0.3.4` GitHub 提交 `361ef61f4d42ae51d657ca1351acacd6b5db5d44`；归档、MIT License、来源、SHA-256 和完整文件清单均随仓库保存并在 Runtime staging 前校验。
- 产品私有 Profile 按 `base → web-app → dsh-tabbit → research-tabbit-adapter` 加载；禁止 `tabbit_browser_install`，不执行运行时下载或自动升级。
- 浏览器自动化默认开启，Tabbit `web_fetch` 接管默认关闭；配置原子写入 Research Web 数据目录并标记需要重启。
- BFF 增加 Tabbit 状态/配置、会话授权和标签候选接口；消息契约支持最多 8 个同实例、有序且不重复的实时标签引用和二次确认。
- Runtime 适配层只复用唯一 `ctx.tabbit` 执行器；发送前再次验证、原子 claim、一次求值读取实时 DOM，并在所有路径执行 `finishTask(..., {keep:true})`。
- 页面正文仅进入会话绑定、单次消费、10 分钟过期的 DSH 内存 token；日志不记录标题、URL、正文或执行代码。
- 输入框增加按需 `@` 搜索、键盘交互和可移除 chip；设置页增加独立开关、实例选择、健康状态和官方手动安装说明。
- 新增只读 `rwb web tabbit-status`，输出不含路径、Cookie、标签标题、URL 或正文。

## 已执行自动化证据

- `node --test tests/javascript/research_web_tabbit_adapter.test.mjs tests/javascript/research_web_tabbit_ui.test.mjs tests/javascript/research_web_guard.test.mjs tests/javascript/research_web_settings_ui.test.mjs`：23 passed。
- `node --test tests/javascript/research_web*.test.mjs`：Tabbit 与其余不依赖 Python 的测试通过；总计 206 passed、1 skipped，3 项因 worktree 尚无获授权安装的 Python 开发环境而失败，失败均为找不到 `.venv/bin/python`，不是断言失败。
- `node --check`：`tabbit-adapter.mjs`、`app.mjs`、`composer.mjs`、`core.mjs` 通过。
- `/opt/homebrew/bin/python3.12 -m py_compile`：所有本轮变更 Python 源码与 Python 测试通过。
- `node scripts/check_research_architecture.mjs`：模块文档、架构评审、API 清单和源码证据映射已通过；三张更新图的生成回执与同哈希人工截图审阅仍在本任务后续步骤生成。
- `git diff --check` 与 `architecture-map.json` JSON 解析通过。

## 待执行与阻塞

- 未执行 Python `pytest`、Ruff、Black、isort、mypy、`check_doc_sync.py` 与 `check_task_completion.py`：当前 worktree 没有 Python 开发依赖；按项目规则，只有用户明确同意后才能由 `uv` 安装已声明依赖。
- 本机检测到 Tabbit `0.30.32` 且没有可用 `tabbit-cli`。因此真实 macOS 状态、授权、动态 DOM、1/8 页 claim、写审批与标签保持打开的冒烟尚未通过。
- 没有真实 Windows Tabbit 环境；新增原生 `macos-14`/`windows-2022` 模拟 Runtime CI 只验证 API、路径语义、staging 和 Node 契约，不替代真实浏览器冒烟。
- 在真实 macOS 与 Windows 冒烟均通过前，本报告不把完整产品验收标记为完成。

## 安全边界与已知限制

- `read_only:true` 是调用方声明，不是对任意 Playwright 代码的静态证明；缺失或为 false 的浏览器操作逐次请求原生审批，系统提示禁止把写操作伪装为只读。
- 标签 claim 结束时保留页面，但 Tabbit 分组可能改变；UI 在发送前明确提示。
- DSH 已受理但结果未知时沿用现有幂等策略，不自动重发可能已执行的消息。
