# Phase 2A Final Documentation Fix Report

## Result

在后端 `c6c3697b` / `f87d8f2c` 与 UI `50d7b067` 提交完成后同步最终契约：

- 认证 Registry 仅允许 HTTPS；无认证 HTTP 只允许精确 loopback；OAuth 端点始终要求 HTTPS。
- normalize/cache/API 保存有界 Unicode plain text，拒绝 control/surrogate，不做 entity escape；UI
  只在最终 HTML sink 转义一次。
- 包目录拆分 `package_type_supported` 与 `immutable_reference`，Phase 2A 不承诺可安装。
- 搜索、Registry 切换等结果集替换作废 pending detail，收敛 loading 并保留当前上下文焦点。

本轮不改变 API 路由、模块拓扑、持久目录或 Runtime 依赖，因此不重绘 Archify 图；API Atlas 将重新
生成核对，预期操作清单不变。

## Verification

- `.venv/bin/python scripts/check_doc_sync.py --project . --base a95532d7`：通过，0 violations。
- `node scripts/check_research_architecture.mjs --project . --base a95532d7`：通过，0 violations。
- `node scripts/build_research_web_api_atlas.mjs .`：137 declarations、135 unique operations、9
  categories，生成物无变化。
- `node --test tests/javascript/research_web_mcp_marketplace.test.mjs tests/javascript/research_web_architecture.test.mjs`：
  70 passed、0 failed、0 skipped。
- `PYTHONPATH=/tmp/rwb-pytest-shim .venv/bin/python -m pytest tests/research_web/test_mcp_registry.py tests/research_web/test_api.py --confcutdir=tests/research_web -q -o addopts='' --tb=short --show-capture=no`：
  108 passed。
- `node tests/e2e/research_web_mcp_marketplace.mjs`：8 个 viewport/theme 组合通过、0 写请求；精确第三方
  文本、迟到详情抑制和上下文焦点保留均由 receipt 确认为 `true`。
- `git diff --check`：通过。
- Archify：不适用；现有图 02 已覆盖未改变的 Browser → FastAPI → Registry service → cache/Keyring
  → official/private Registry 拓扑。

## Boundary

未修改产品源码或 E2E，未访问公网 Registry，未执行安装、Publisher、Phase 2B/2C、桌面/Tauri 或
平台验证。
