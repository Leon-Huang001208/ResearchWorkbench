# 首批场景 CI：MCP Marketplace DOM 夹具补齐

- 宿主：macOS；类型：Web JavaScript 测试夹具修复。
- 执行基线：`5a2d81816081d362028c44024fa40baa13e1994f` 加本报告对应测试补丁。
- 范围仅 `tests/javascript/research_web_mcp_marketplace.test.mjs` 和本报告。未改产品源码、Python、依赖、CI、skip 或既有断言；未调用真实 MCP、供应商、模型或常驻服务，fetch 继续使用本地假响应。

## RED 与根因

CI Checks `40440907774` 的 JavaScript 通配符发现 10 项 Marketplace 失败。本机先执行固定 Node 的 `--test tests/javascript/research_web_mcp_marketplace.test.mjs`，得到 27 项、17 passed、10 failed、0 skipped；`logs/mcp-fixture-red.log` 保留原失败。

这两个根夹具的 `querySelector` 总返回 null；产品 `app.mjs` 的 render 模板真实包含 `.app-shell`，场景模态层随后设置其 `inert`。因此测试在渲染时抛出 `Cannot set properties of null (setting 'inert')`，尚未进入原 MCP 行为断言。修复沿已有 capabilities UI 夹具提供 shell 节点，不在产品中添加 null guard。

两个夹具现在返回各自的 `appShell`。原 MCP 对话框的焦点循环、backdrop、Escape 与焦点恢复断言全部保留，并新增 shell 非 inert 断言；独立场景回归通过实际 app click/keydown 处理器，检查初始 false、场景面板打开 true、Escape 关闭 false，且检查真实渲染的模态 DOM。

## 实际验证

Node 固定 `/Users/leon/.research-workbench/toolchain/node-v24.19.0-darwin-arm64/bin/node`。相邻及全量测试复用 controller 已有环境：`PYTHONDONTWRITEBYTECODE=1`、`RWB_TEST_PYTHON=/Users/leon/.local/share/research-workbench/releases/d744029a5/.venv/bin/python`，`PYTHONPATH` 为 `run-local-validation.py` 中五个既有 uv archive 路径；没有安装依赖或修改该脚本。

| 验证 | 实际结果 | 日志 |
| --- | --- | --- |
| Git safety check | PASS | `logs/mcp-fixture-git-check.log` |
| 目标文件 RED | 17 passed / 10 failed / 0 skipped | `logs/mcp-fixture-red.log` |
| 目标文件 GREEN | 28 passed / 0 failed / 0 skipped | `logs/mcp-fixture-green.log` |
| `node --test` Marketplace、capabilities UI、scenarios、asset*、workbench | 360 passed / 0 failed / 0 skipped | `logs/mcp-fixture-adjacent.log` |
| `node --test tests/javascript/research_web*.test.mjs`，与 Checks 同通配符 | 1228 total / 1225 passed / 0 failed / 3 skipped | `logs/mcp-fixture-full-research-web.log` |
| `git diff --check` | PASS | 本地命令 |

全量中的 3 项既有跳过均因未设置 `DSH_SOURCE_ROOT`：compatible model 的固定 Loader、plugins native 的 ToolRuntime、public data 的业务工具 schema。此次未增加、删除或改变 skip 条件；不将这三项报告为已通过。目标文件从 27 增至 28 项是新增场景 inert 回归。

日志 SHA-256：

- RED：`eb6663e54a3bf0433dea859b08318a01775f68f96030023e4263f427661428e2`
- GREEN：`221be17e38697fbf63b4964debe2528ba6e3d4a95eb909ab583790fed34e7769`
- 相邻：`eb0f2518804a32a76b4b3424caf888378d27eaa8b0c6960191df4197354859a1`
- 全量：`8387c9de5384f09fac0714d6b1ed866fcf82c5b5fe82239c1b62d7499b39d7ff`

## 交接边界

本次仅证明本机离线 DOM 夹具与既有 Research Web JavaScript 全通配符兼容；没有重跑 Python、远端 CI、真实浏览器或平台产品验收。最终候选的独立评审、完整 Router、文档检查、源码等价证明和远端交付由 controller 统一绑定。没有以旧局部 339 项结果代替本次完整 JavaScript 执行。
