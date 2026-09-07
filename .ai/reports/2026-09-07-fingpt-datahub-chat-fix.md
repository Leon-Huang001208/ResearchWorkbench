# FinGPT 对话、DataHub 自动查询与异常统计修复

## 结果与边界

- 日期：2026-09-07；目标分支 `codex/web-consolidation`。
- FinGPT/Claw 对话保留原消息、Markdown、流式事件与 HTTP 数据结构；仅改变消息呈现和异常摘要。
- DataHub 只取消原生只读查询的逐次审批。来源配置、凭据启用、来源白名单、参数 Schema、会话隔离、loopback BFF、控制令牌、响应上限、取消与审计日志仍保留。
- 已有会话的失败活动不迁移、不删除。历史 7 条失败继续存在，但横幅改为明确的“7 项活动失败”。
- 工作树同时存在另一项 Report Workflow 工作的改动，本修复未回退、提交或发布这些并行改动。

## 实现

### 对话与异常横幅

- `ui/views.mjs` 为消息保留 `article.message`、角色 class 与 `.markdown`，删除可见头像/署名；用户与助手分别提供“用户消息”和按模式区分的“FinGPT 回复”/“Claw 回复”ARIA 名称。
- `ui/styles.css` 将用户气泡贴右并按内容收缩，桌面最大宽度 78%，760px 以下最大宽度 92%；助手继续左侧正文展示。
- `ui/shell.mjs` 分别统计失败活动与异常 `subagents`，组合输出明确文案；零异常不显示横幅，“查看详情”和原始错误保持可用。

### DataHub 与 Runtime

- `runtime/public-data.mjs` 删除 DataHub 查询的 `approval.request()`，并以必填 `enabledTools` 白名单只注册固定业务工具。输入在发出 HTTP 前严格校验类型、必填字段、额外字段、稀疏数组与原型属性。
- `launch_runtime.py` 在每次 Research Runtime 启动时从离线能力目录计算可调用工具并注入 `enabledTools`；目录读取异常时拒绝启动，避免暴露无来源工具。
- `capabilities/tools.py` 将 DataHub 审批元数据改为 `automatic`；persona、内置研究 Skills 与用户文档同步为自动查询和父任务数据集复用。
- AKShare 与天软同步 SDK 查询截止时间统一为 15 秒。每个 Provider 使用单线程执行器和容量 1 的门闩；超时产生 `failed/deadline` 数据集，未结束的底层同步调用被隔离，后续请求快速返回 `failed/provider_busy`，不会堆积线程或升级成顶层活动异常。

## 验证证据

1. `node --test tests/javascript/*.test.mjs`：168 通过、1 个需要 DSH 源码的条件跳过、0 失败。
2. `DSH_SOURCE_ROOT=/Users/leon/.research-workbench/dsh-source node --test tests/javascript/research_web_public_data.test.mjs tests/javascript/research_web_ui.test.mjs tests/javascript/research_web_appearance.test.mjs`：41 通过、0 跳过、0 失败；包含固定 DSH schema 对齐。
3. `.venv/bin/python -m pytest tests/research_web/test_datahub.py tests/research_web/test_datahub_catalog.py tests/research_web/test_capabilities.py tests/research_web/test_capabilities_native.py -q`：72 通过、2 个条件跳过、0 失败；1 个 Starlette/AnyIO 依赖弃用警告。
4. `.venv/bin/python -m pytest tests/research_web/test_protocol.py tests/research_web/test_api.py tests/research_web/test_event_recovery.py -q`：27 通过、0 失败；HTTP 会话、DataHub 查询、SSE 恢复和消息受理结构保持兼容。
5. Ruff、Black、isort 对本次四个 Python 模块全部通过；`mypy --follow-imports=skip` 对同四个模块通过。常规 mypy 跟随导入时仍命中 `core/observability/{tracer,metrics}.py` 的 13 个既有 logger 类型错误，未在本修复中扩大范围处理。
6. `node --check` 检查桥接与 UI 模块通过；`git diff --check` 通过。
7. Playwright 在 390×844、768×1024、1280×720、1440×900 验证：无横向溢出、用户消息右对齐、可见署名为 0、FinGPT/Claw ARIA 名称正确、历史横幅为“7 项活动失败”、旧含混文案不存在、无 DataHub 审批卡。另在 390×844 深色主题检查背景与文字语义变量生效。
8. Archify 对 02 模块依赖、03 研究序列、04 数据文件流均为 showcase 9/9、0 错误、0 警告；四个桌面视口无溢出。人工查看 1440 浅色/深色与 2048 浅色截图后更新同哈希视觉复核记录，未见穿线、遮挡或裁剪。
9. `.agents/project-constraints.mjs` 对本次源码、测试、文档、图源和复核记录返回 `violations: []`。

## 未执行与保留风险

- 未重启当前共享的 3081 DSH Runtime，也未新发真实“上周A股市场点评”模型任务：验收时存在另一条进行中的 Report Workflow 会话，重启或发送会改变共享运行态。自动审批、工具过滤、超时与参数边界已由桥接、目录、Provider 和 UI 测试覆盖；部署后需重启 Research Runtime 才加载新的 `enabledTools`。
- 将 `DSH_SOURCE_ROOT` 注入 Python 原生能力整套测试时，其中一个与本修复无关的断言仍硬编码“6 个 Skill”，而并行 Report Workflow 工作已使实际目录为 9 个；固定 DSH schema 的 JavaScript 对齐测试已通过。未修改该并行工作的测试预期。
- Python 无法强制终止已进入第三方同步 SDK 的线程；实现将其限制为每 Provider 一个线程，并在真正结束前快速返回 `provider_busy`。
- 取消链路已覆盖原生桥接与直接 HTTP 请求；尚未增加专门模拟“取消已经进入 AKShare/天软同步 SDK 调用”的 Provider 级测试。此类取消只停止等待且不发布快照，底层线程按上一条隔离至自然结束。
- 若第三方同步 SDK 自身永久不返回，对应 Provider 会持续快速返回 `provider_busy`；其非守护执行线程也可能延迟 Python 进程退出。这是同步 SDK 无安全强杀能力的保留风险。
