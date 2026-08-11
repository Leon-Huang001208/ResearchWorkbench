# Test Report: Evidence-first A-share Research Run

## Task Info

- Task ID: `research-run-019feac5`
- Date: 2026-08-10
- Scope: 单证券、单一 `as_of` 的 A 股公司深研闭环。

## Delivered

- PostgreSQL/Alembic 013 持久化 `ResearchRun`、任务快照、证据输入、不可变 Artifact、当前 Claim 与质量门禁投影。
- LangGraph 纯执行图：来源规划、证据归一、研究笔记、观点综合、Challenge、质量门禁、决策卡和 Markdown 报告；运行状态仍以数据库为唯一权威。
- A 股五类证据、数值完整性、冲突、引用和覆盖门禁；阻塞后可以补证恢复，完成前不能导出。
- FastAPI 运行、执行、补证、恢复、产物读取及 Markdown/Word 下载接口；工作台包含创建、门禁、观点证据、决策卡和报告预览。
- `a-share-deep-research` Skill、引用证据契约和使用说明。

## Commands Run

| Command | Result |
| --- | --- |
| `python -m pytest tests/unit/test_research_run_service.py tests/unit/test_research_runs_api.py tests/unit/test_research_workbench_frontend.py -q` | 7 passed |
| `ruff check <changed Python files>` | passed |
| `black --check <changed Python files>` | passed |
| `isort --check-only <changed Python files>` | passed |
| `node --check app/web/static/js/research-workbench.js` | passed |
| `node --check app/web/static/js/app.js` | passed |
| `python scripts/generate_py_file_index.py` | passed |
| `python scripts/check_doc_sync.py` | passed |
| `(cd storage/migrations && alembic heads)` | `013 (head)` |
| `python /Users/leon/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/a-share-deep-research` | passed |
| `git diff --check` | passed |

## Browser Verification

未完成真实浏览器流程：工作树的 API 预览启动被本地 PostgreSQL readiness 阻塞；终端启动的临时静态服务器在命令会话退出后不可访问。已用前端静态契约和 JavaScript 语法检查覆盖导航、DOM、API 调用与完成态下载链接，但这不替代真实浏览器验收。

## Known Boundaries

- 首版接收规范化证据输入并记录授权→官方→公开→用户的降级路径；尚未直接调度 Wind/iFinD、交易所或公开连接器取数。
- Graph 产物目前是确定性 MVP 投影；现有 AgentWorkflow、Thesis Review 和报告编译器仍是后续节点适配工作，不在本次替换范围内。
- Word 导出为内存内 Markdown 投影的基础 DOCX；尚未套用报告项目模板。
