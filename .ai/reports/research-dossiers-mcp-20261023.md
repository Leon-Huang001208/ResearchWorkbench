# 长期研究档案：MCP 候选与证据分支

- 宿主：macOS；类型：Web 功能开发；本分支范围：阶段 3 离线适配、受管凭据 UI、固定评估费用状态与原始响应快照。
- 工作树：`/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/research-dossiers-mcp-20261023-409a6f13`。
- 不修改主 checkout、常驻服务、真实凭据、供应商账户、数据库或依赖；没有真实模型、供应商或收费调用。
- 总体架构/Router/CI/部署文档及源码接线由主任务集成；本报告不是总体验收或发布回执。

## 变更

1. `authorizations.json` 增加固定预算/调用记录，跨进程锁、锁内重读及原子保存覆盖所有授权读写。18 个固定单元、参数与版本/schema 绑定；未知/取消不重发、不退款；确定未发才可释放。
2. 受管安装的静态 Bearer 限定小创真实 endpoint 与专用 slot，经既有个人/租户插件身份、包审批和 native/schema/session 审批。原安全边界与 secret 后端复用。
3. 插件详情新增凭据状态/录入/删除、清单预览、明确授权、逐项执行。密码只存在单次表单请求内，不进入 state/日志/响应。单项执行派生稳定 call_id，返回有界回执，原件在既有 datasets。
4. call_tool 链自动冻结原始 SDK JSON 到现有 Snapshots，保留工具/schema/参数/hash/时间/费用状态，结果始终 clue。发布中断保留 pending 原件并恢复；响应期间撤权不暴露结果，原件仍可保全。
5. 提供同步离线 `assert_frozen_result_authorized` 与 async `read_frozen_result` 供档案和普通文件路径复用。软删除只保留只读资料，撤权依然拒绝。
6. 一方候选包及下载入口可沿现有导入流程预览。没有猜测 Registry 身份或 schema；导入演练明确 `unsupported/native_registry_selection_required`。

## 实际验证

解释器为既有测试环境：`/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/datahub-warehouse-20261022/.venv-tests/bin/python`，未安装依赖。

- pytest：`test_mcp_authorization.py test_mcp_runtime_routes.py test_mcp_runtime_integration.py test_mcp_transport.py test_mcp_installation.py test_plugins.py test_plugins_mcp_security.py test_mcp_seek_alpha.py --confcutdir=tests/research_web`：**151 passed，1 warning，121.13s**。最后一次全闭包受同机并发影响比前一次 16.25s 慢，但完整结束。
- 新专项：**19 passed，1 warning，1.39s**。覆盖跨进程争抢、陈旧管理器读回、固定成本/工具/schema、预算不足不发、未知/取消、原件恢复/损坏、跨账户、撤权/软删除、secret 回显拒绝及候选导入阻断。
- JS 六个近处模块：**41 passed，1 既有 skip，0 failed**。新增凭据测试验证当前用户路径、清除 DOM、无 secret state/log，以及明确预算 UI。
- Ruff / Black --check / isort --check-only：修改 Python 文件均通过。
- mypy `--follow-imports=skip`：5 个变更源文件通过。
- `git diff --check`：通过。
- 本地 Hatch wheel 构建成功；7 个新增代码/UI/候选资源与 checkout 逐字节一致。wheel SHA-256：`5a9214abf5b5e2796f4c04b6570cb27fb0328044e50104e25131136bd6e0cc66`。

完整测试日志保留在 `/tmp/rwb-mcp-regression.log`、`/tmp/rwb-mcp-seek-alpha-test.log`、`/tmp/rwb-mcp-js.log`；本地 wheel 位于 `/tmp/rwb-mcp-candidate-wheel/`。它们属于本任务，未混入源码提交。

## 阻断与未验证

- 小创真实 Registry ID/server/version/remote index 尚未验证，当前候选只可导入预览、不可安装或调用。公开 Registry 查询超时不能证明存在或不存在。需要供应商可验证身份，不能伪造条目。
- 18/54 按本轮公开目录单价 3 估算；本地限制是调度预算，不是供应商保证扣费上限。真实试跑前须另核当时报价并单独确认。
- 真实凭据、握手、付费评估、内容来源质量、浏览器实际效果、干净安装 CI 与常驻部署：**NOT_RUN**。其他平台原生验收由对应设备承担。
- 普通 DataHub/会话文件读取与复制入口的 MCP guard 由主任务核心分支接线；集成后必须回归，不得仅凭此分支认为撤权链已全部闭合。
