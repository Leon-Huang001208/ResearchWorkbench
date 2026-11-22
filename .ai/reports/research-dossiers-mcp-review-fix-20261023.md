# MCP 独立评审 HIGH 修复

宿主为 macOS，范围为 Web MCP 安全修复。仅在原隔离 MCP 工作树修改所属文件；无真实凭据、网络、模型或收费调用，无 push/部署。

## 已确认的问题与修复

- 原服务端在返回后读取“当前 token”，并在 JSON 序列化字节中找原文。派发中删除/轮换、引号/反斜杠转义会绕过。现 SDK 在创建本次 remote transport 时局部绑定真实使用的 Bearer；工具、能力发现都在解析后的 JSON 键和字符串叶子检查。MCP 文本中有界 JSON 也解码检查。字段截断前检查 server/protocol，避免先投影再漏检。
- 服务端预派发绑定只作注入 Host 的附加防护；实际 transport token 检查由 SDK 独立完成。任何回显均在公开/冻结前拒绝；已发送预算保持 unknown，不宣称未发送或退款。
- 当前小创候选没有 resource/prompt 费用或内容合同。现 service 与 SDK 两层在 target/能力探测和 transport 创建前拒绝这两种方法；发现结果不再宣称辅助方法可用。普通 OAuth MCP 的资源/提示词能力及既有 HTTPS、audience、redirect 等约束保持。

## 实际验证

解释器使用既有 `/Users/leon/Desktop/Projects/ResearchWorkbench-worktrees/datahub-warehouse-20261022/.venv-tests/bin/python`，不安装依赖。

- pytest：`test_mcp_seek_alpha.py test_mcp_transport.py test_mcp_runtime_routes.py test_mcp_authorization.py test_mcp_installation.py test_plugins_mcp_security.py --confcutdir=tests/research_web -q`：**152 passed，1 warning，2.86s**。
- 精确新增复现：派发中 delete/rotate × 普通字符串、JSON key、嵌套 leaf、文本内 JSON；capabilities tools/resources/prompts/server/protocol 回显；无预算 prompt 私有参数与 read_resource 零派发；SDK URL 规范别名同样拒绝；候选不宣称 resource/prompt 可用。
- 已发送拒绝回显时记录 unknown、保留费用占用且没有原件快照；原 OAuth get_prompt/read_resource 回归通过。
- Ruff、Black --check、isort --check-only、mypy（2 源文件）与 `git diff --check` 通过。
- 完整输出：`/tmp/rwb-mcp-echo-fix-final.log`，失败/中间证据保留在 `/tmp/rwb-mcp-echo-fix.log`；只使用 memory Keychain 和离线 client/transport fixtures。

组合分支、Root 全量回归、干净安装 CI 与浏览器/常驻仍由主任务验证。本报告不替代这些门。
