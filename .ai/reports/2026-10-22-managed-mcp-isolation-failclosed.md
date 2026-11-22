# 受管本地 MCP 进程隔离缺口：失败关闭

宿主 macOS，Web 安全功能修复；在既有插件任务 worktree 实现，检查基线 `3334dfa`。
不提交/push/部署，不安装依赖、不访问秘密、网络、模型或供应商；主任务负责后续独立评审及最终交付。

## 根因与决定

受管安装的字节和 schema 审核没有限制 SDK stdio 子进程的 OS 权限。
SDKHost._official_target 构造 StdioServerParameters，官方 SDK 在握手/list_tools 前启动 launcher。
合法安装内可执行文件仍可读取/写入绝对路径，最小 cwd/HOME 无法隔离其他用户资料。

当前没有经过验收的 MCP OS 沙箱合同，采用已授权的最小失败关闭：受管本地包的插件原生预览、
安装、直接 target 解析、probe、startup、cached target 和 call 一律拒绝
`mcp_managed_local_process_isolation_required`（403）。tenant 原生安装也在 manifest/installer
副作用前拒绝。本地组件 limited/ready=false，UI 禁用执行按钮并说明缺口。固定远程端点与
非受管 Native 保持原合同。此修复关闭漏洞路径，**不是完整本地 MCP 支持或 OS 沙箱交付**。

## 实测

使用父任务批准的既有 `.venv-tests/bin/python`（datahub-warehouse-20261022），无安装。

- Red：`python -m pytest --confcutdir=tests/research_web tests/research_web/test_plugins_mcp_security.py -k real_sdk -q`，2 FAILED / 5 deselected。官方 SDK 实际启动自有 launcher，可读/改写自有兄弟 sentinel；managed probe 未拒绝。日志 `logs/managed-mcp-isolation-before.log`。
- Green：`python -m pytest --confcutdir=tests/research_web tests/research_web/test_plugins_mcp_security.py tests/research_web/test_plugins.py tests/research_web/test_plugins_runtime_restart.py tests/research_web/test_mcp_runtime_routes.py tests/research_web/test_mcp_transport.py tests/research_web/test_mcp_runtime_integration.py -q`，最终源码复跑83 PASS，1 条既有 Starlette 弃用 warning，24.75 秒；`logs/managed-mcp-isolation-final.log`。
- 实际 SDK 回归先证明非受管可执行 fixture 的 sentinel 读写，再对 tenant 与 Native managed marker 两类身份确认 probe/start/call/direct resolve 及缓存 target 拒绝，sentinel 未改变，installer 未调用；没有模拟 Host/SDK/transport。
- 精确 argv 覆盖 Python inline、shell、Node script、直接 launcher，在任何目标解析前拒绝；额外覆盖旧 token 插件安装与 tenant manifest 创建前拒绝。
- `node --test tests/javascript/research_web_plugins_ui.test.mjs tests/javascript/research_web_plugins.test.mjs`：5 PASS，0 skip；`logs/managed-mcp-isolation-js.log`，本地按钮禁用、远程按钮保留。
- changed Python Ruff/isort/Black PASS，mypy `--follow-imports=silent` 3 个源码 PASS。文档治理、架构检查、`check_doc_sync.py --base 3334dfa` PASS。Python 索引检查初次 stale，已按正式生成器更新并 `--check` PASS；`logs/managed-mcp-isolation-{docs,architecture,index,sync}-final.log` 和 `-mypy.log` 保存结果。主任务仍需按最终交付候选复核。
- 首次 pytest 未指定 confcutdir，legacy conftest 缺 SQLAlchemy 导致收集失败；一次扩展命令误写不存在 test_plugins_runtime.py，退出 4，无测试执行。均纠正后运行上述实际目标，不安装依赖。

## 尚未验证与风险

最终候选 Mac Bootstrap、通用 CI、真实外部 MCP/OAuth、常驻部署、Windows/Linux 原生：NOT_RUN。
本地 MCP：BLOCKED，后续须交付 OS 进程/文件/网络边界及独立真实验证。现有包、manifest、审批与
旧会话没有删除或迁移；旧 active 本地条目遇到启动/调用拒绝，不应据旧缓存声称可用。

## 架构判断

<!-- architecture-review {"group":"ui","structure":"unchanged","reason":"仅在既有插件组件状态与按钮内显示操作系统隔离缺口并禁用本地执行；无新增页面、服务、执行引擎或框架节点。","diagrams":[]} -->

<!-- architecture-review {"group":"mcp-runtime","structure":"unchanged","reason":"在既有Host target与managed准入前增加本地进程失败关闭门；官方SDK、固定远程端点、唯一DSH和存储拓扑均保持，不新增沙箱实现或服务节点。","diagrams":[]} -->
