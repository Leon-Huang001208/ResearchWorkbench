# Test Report: Unified Research Center and Template Registry

## Task Info

- Task ID: `af-rrc-7f3c8a1d`
- Date: 2026-08-11
- Branch: `codex/research-run-agent`
- Scope: 将 A 股独立入口收敛为跨资产研究中心，并打通资产观察、模板注册表、通用 subject 契约和 Research Run 验收闭环。

## Delivered

- 一级导航统一为“研究中心”；股票、宏观、商品、指数和行业以 Research Template 展示，不再各建页面。
- `a_share_deep_research` 为首个可执行模板；宏观、商品、指数/ETF 和行业模板注册为规划中，前后端均拒绝执行。
- 新增框架无关的模板注册表；Research Run 服务按 `template_key` 解析执行器、对象类型、证据分类和质量门禁。
- 新增通用 `ResearchSubject`，保留旧 `target_id` 的读取、恢复和导出兼容；新增 Alembic 014 迁移。
- 资产观察新增“启动深度研究”，把对象类型、代码、名称、时点、建议模板和默认问题带入研究中心。
- 用户页面移除原始证据 JSON；阻塞态改为结构化补证表单，详情内保留进度、门禁、证据、决策卡、报告和返回资产观察入口。
- 修复验收中发现的资产搜索失败态未定义变量，并将含阻塞数据源的搜索路由交给 FastAPI 线程池，避免拖住模板与 Research Run 请求。

## Automated Verification

| Command | Result |
| --- | --- |
| `python -m pytest tests/unit/test_research_run_service.py tests/unit/test_research_runs_api.py tests/unit/test_research_workbench_frontend.py tests/unit/test_search_route_concurrency.py tests/unit/test_asset_kline_interaction.py tests/unit/test_desktop_shell_scaffold.py -q` | 64 passed, 4 existing FastAPI deprecation warnings |
| `python -m pytest tests/unit/test_alembic_migration_graph.py -q` | 1 passed |
| `ruff check <changed Python files>` | passed |
| `black --check <changed Python files>` | passed; the pre-existing whole-file formatting drift in `test_desktop_shell_scaffold.py` was intentionally not rewritten |
| `isort --check-only <changed Python files>` | passed |
| `node --check app/web/static/js/research-workbench.js` | passed |
| `node --check app/web/static/js/asset.js` | passed |
| `node --check app/web/static/js/app.js` | passed |
| `python scripts/generate_py_file_index.py` | passed |
| `python scripts/check_doc_sync.py` | passed |
| `(cd storage/migrations && alembic heads)` | `014 (head)` |
| `python /Users/leon/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/a-share-deep-research` | passed |
| `git diff --check` | passed |

## Browser and Desktop Verification

- 启动命令：`npm run desktop:preview -- --port 8766 --use-stable-data`。
- macOS Tauri 分支窗口启动成功，后端使用 `127.0.0.1:8766`，后台 Worker 保持关闭。
- Playwright 实测一个贵州茅台 Run：无证据执行进入 `blocked`，Markdown/Word 不显示；补齐五类证据并恢复后进入 `completed`。
- 完成态包含 5 条 Claim、5 个通过的质量门禁、决策卡和 Markdown 报告；Markdown 下载返回 200/693 bytes，Word 下载返回 200/36917 bytes 且识别为 Microsoft OOXML。
- 资产观察输入 `600519.SH 贵州茅台` 后，研究中心正确预填 `security`、代码、名称、2026-08-11、A 股模板和默认问题；搜索请求未阻塞研究模板加载。
- 模板卡正确显示 1 个可用和 4 个规划中；ETF/指数等规划中模板不可提交。
- 最终浏览器控制台为 0 error / 0 warning（除正常 SSE connected 日志）。
- 验收 Run：`research_run_a15245d2ba644fe1a9db8ba1116a7649`。

## Database Note

稳定桌面数据库的 `alembic_version` 原记录为 011，但 Alembic 012 的表、列、唯一约束和索引已全部存在。只读比对确认结构等价后，将版本标记校正到 012，再顺序应用 013 和 014；未删除或覆盖业务数据。

## Known Boundaries

- 首版仍只有 A 股公司深研可执行；宏观、商品、指数/ETF 和行业只有注册元数据。
- 当前页面的证据补充是规范化输入闭环；Wind/iFinD、交易所和公开连接器尚未作为图节点直接拉取数据。
- 现有 AgentWorkflow、认知黑板和完整报告编译器尚未接入实际图节点，仍沿用 Research Run MVP 执行器。
- 本次只完成 macOS 桌面预览与浏览器验收；未运行原生 Windows CI 或真实 Windows 安装冒烟，不能据此声明 Windows 已验证。
