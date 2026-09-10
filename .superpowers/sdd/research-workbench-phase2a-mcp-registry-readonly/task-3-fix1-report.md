# Task 3 Fix Round 1 Report

## Result

按独立评审修正两项证据契约，未修改产品源码：

- `docs/research-web.md` 与 Phase 2A `.ai` 报告明确区分规范化目录元数据、秘密及原始上游响应：
  缓存/API 保存并返回经 schema 校验、长度限制和纯文本处理的名称、描述、包/远程元数据；Bearer/OAuth
  秘密仅进入 `ResearchWorkbench.MCPRegistry` 系统凭据库；日志不记录凭据、第三方描述或原始上游
  响应体。
- MCP 市场 E2E 直接断言恶意 fixture 描述的完整字面字符串仍可见，并断言卡片未生成 `img`/`script`
  节点；receipt 的 `thirdPartyTextOnly` 由所有 viewport/theme 的实际断言计数计算。

## Verification

本轮提交前实际运行结果记录如下：

- `node tests/e2e/research_web_mcp_marketplace.mjs`：8 个 viewport/theme 组合通过，0 写请求；
  receipt 的 `thirdPartyTextOnly` 为实际检查结果。
- `node --check tests/e2e/research_web_mcp_marketplace.mjs`：通过。
- `node --test tests/javascript/research_web_capabilities_ui.test.mjs tests/javascript/research_web_mcp_marketplace.test.mjs tests/javascript/research_web_architecture.test.mjs`：
  100 passed、0 failed、0 skipped。
- `.venv/bin/python scripts/check_doc_sync.py --project . --base a95532d7`：通过，0 violations；没有本轮需同步的
  产品源码。
- `node scripts/check_research_architecture.mjs --project . --base a95532d7`：通过，0 violations。
- `git diff --check`：通过。

## Scope

未改动 Registry 后端或产品 UI，未访问公网 Registry，未执行安装、Publisher、Registry 写操作、
Phase 2B/2C、桌面/Tauri 或平台验证。
