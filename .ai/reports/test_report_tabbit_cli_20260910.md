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
- Windows 路径使用显式 UTF-8、关闭句柄后的原子替换、POSIX 归档成员语义和正斜杠 adapter 配置；POSIX 保留目录 `fsync`，Windows 明确跳过不支持的目录同步。
- DSH waterfall/cancel 交互事件标识在进入 pending map 前逐项验证，非法值稳定返回 `protocol_error`。

## 已执行自动化证据

- 隔离 `.venv` 使用用户已授权的仓库既有 `.[dev]` 依赖；未新增或调整项目依赖。
- Tabbit、Runtime、协议、API、连接中心和本机集成定向测试：99 passed、1 skipped、1 warning。
- `env -u DSH_SOURCE_ROOT ... pytest tests/research_web --confcutdir=tests/research_web`：607 passed、4 skipped、1 warning；跳过项为需要原生 DSH 源码的验证。
- 使用本机 `DSH_SOURCE_ROOT` 运行同一套件：606 passed、1 skipped、2 setup errors；两项均因源码提交 `c389f96bf3a9b6807cb71ed6bdad5849be0df6d8` 与锁定提交 `c919b2a460753859665db3f60143d525fb9140cf` 不一致，未放宽 pin。
- 完整 Research Web Node 测试：220 passed、1 skipped；其中 Tabbit、设置、Runtime guard、Research Web UI 与本机集成定向测试为 58 passed。CI 同构 Tabbit Python/Node 合约分别为 67 passed 和 51 passed；`tabbit-adapter.mjs`、`app.mjs`、`composer.mjs`、`core.mjs` 语法检查通过。
- Ruff 0.16.6、Black 26.5.1 check、isort 9.0.1 check：11 个相关 Python 文件通过；Black 实际限定格式化 8 个 CI 报告文件。
- mypy 2.3.1：6 个相关 Research Web 源文件通过；项目仍以 Python 3.11 为目标，NumPy/Transformers 外部 stub 使用定向 `follow_imports=skip`。
- `node scripts/check_research_architecture.mjs` 与 `scripts/check_doc_sync.py --base origin/master`：无违规。
- `git diff --check` 通过。

## 待执行与阻塞

- PR #73 的修复后原生 macOS/Windows CI 尚待推送执行；此前失败分别暴露 Black 格式、Windows UTF-8、原子替换和路径语义问题，本轮已在本地增加回归并修复。
- 本机检测到 Tabbit `0.30.32` 且没有可用 `tabbit-cli`。因此真实 macOS 状态、授权、动态 DOM、1/8 页 claim、写审批与标签保持打开的冒烟尚未通过。
- 没有真实 Windows Tabbit 环境；新增原生 `macos-14`/`windows-2022` 模拟 Runtime CI 只验证 API、路径语义、staging 和 Node 契约，不替代真实浏览器冒烟。
- 在真实 macOS 与 Windows 冒烟均通过前，本报告不把完整产品验收标记为完成。

## 安全边界与已知限制

- `read_only:true` 是调用方声明，不是对任意 Playwright 代码的静态证明；缺失或为 false 的浏览器操作逐次请求原生审批，系统提示禁止把写操作伪装为只读。
- 标签 claim 结束时保留页面，但 Tabbit 分组可能改变；UI 在发送前明确提示。
- DSH 已受理但结果未知时沿用现有幂等策略，不自动重发可能已执行的消息。
