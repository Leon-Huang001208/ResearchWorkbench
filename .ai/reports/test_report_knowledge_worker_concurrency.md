# Test Report: Knowledge Worker Concurrency & Lifecycle Management

## Task Info

- **Task ID**: N/A (architecture improvement, not task-tracked)
- **Date**: 2026-05-26
- **Description**: Knowledge Worker item-level concurrency, PID/signal lifecycle management, CLI/API commands, cron_jobs deduplication

## Changed Source Files

- `workers/knowledge_worker.py` — 重写：PID管理、信号处理、asyncio.Semaphore并发
- `app/cli/commands/ingest.py` — 添加 `rwb knowledge start|stop|status` 命令组
- `app/cli/main.py` — 注册 knowledge 命令组
- `app/api/routes/knowledge.py` — 新建：Knowledge Worker REST API
- `app/api/main.py` — 注册 knowledge router
- `core/settings/config.py` — 添加 Knowledge Worker 配置项
- `cron_jobs/auto_ingest_service.py` — 移除冗余 `process_ingestion_queue()`

## Changed Test Files

None. No new tests added.

## Justification for No New Tests

1. **`workers/knowledge_worker.py`** — Worker 进程的集成行为（PID文件、信号处理、子进程生命周期）依赖真实操作系统环境，不适合单元测试。核心处理逻辑 `process_one()` 和 `_create_document_v1()` 保持不变，已有集成测试覆盖 KnowledgePipeline 路径。
2. **`app/cli/commands/ingest.py`** — CLI 命令（`knowledge start|stop|status`）是 `subprocess` + PID 文件的薄包装层，逻辑简单且依赖外部进程管理，测试价值低。
3. **`app/api/routes/knowledge.py`** — API 端点与 CLI 命令逻辑相同，是 PID 文件 + subprocess 的薄包装。
4. **`app/cli/main.py`, `app/api/main.py`** — 纯注册/导入变更，无业务逻辑。
5. **`core/settings/config.py`** — 纯配置字段声明，无逻辑。
6. **`cron_jobs/auto_ingest_service.py`** — 仅删除死代码，无新增逻辑。

## Commands Run

```bash
ruff check .           # 1 pre-existing error (crawl_scheduler_worker.py:71 unused import)
black . --check        # 11 pre-existing files need reformatting (not our changes)
isort . --check-only   # Fixed: ingest.py import order
mypy workers/ app/cli/ app/api/ core/settings/  # Only pre-existing errors (missing stubs)
python -m pytest tests/ -v  # 1250 passed, 1 skipped
python scripts/generate_py_file_index.py  # OK
python scripts/check_doc_sync.py  # PASSED
```

## Test Results

- **ruff**: 1 pre-existing error (crawl_scheduler_worker.py:71), no new errors
- **black**: 11 pre-existing files need formatting, none from our changes
- **isort**: Fixed, clean
- **mypy**: Only pre-existing errors (missing stubs for pandas, yaml, akshare, etc.)
- **pytest**: **1250 passed, 1 skipped** — no regressions
- **doc sync**: PASSED
- **file index**: Generated

## Remaining Risks

- Knowledge Worker 并发处理在真实 LLM API 环境下的行为需要在 staging 环境验证
- `asyncio.Semaphore` 并发 + 每个任务独立 DB session 的模式需要在高负载下验证 DB 连接池是否足够
