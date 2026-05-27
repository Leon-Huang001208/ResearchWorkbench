# Test Report: Knowledge Worker Optimization (Round 2)

## Task Info

- **Date**: 2026-05-26
- **Description**: Knowledge Worker 四项优化 — Pipeline 实例复用、空队列指数退避、长文档并发 LLM 提取、多进程水平扩展

## Changed Source Files

- `workers/knowledge_worker.py` — 重写：共享 Pipeline 实例、指数退避、`--worker-id` 参数、`get_all_worker_statuses()`
- `app/cli/commands/ingest.py` — `knowledge start --workers N`、stop/status 支持多 worker
- `app/api/routes/knowledge.py` — `start?workers=N`（最大 16）、stop/status 多 worker 聚合
- `ingestion/knowledge_pipeline.py` — 移除未使用的 `AssertionPrompts` import

## Changed Test Files

- `tests/unit/workers/test_knowledge_worker.py` — `test_process_one_publishes_events` 适配新签名（`process_one(item, pipeline)`）

## Changed Docs

- `docs/modules/ingestion.md` — 添加 `knowledge_pipeline.py` 章节
- `docs/modules/app_cli.md` — 更新 knowledge 命令说明（`--workers` 选项）
- `docs/modules/app_api.md` — 更新 knowledge API 说明（`workers` 参数、多 worker 聚合）
- `docs/CHANGELOG.md` — 添加 `knowledge-worker-optimization` 条目
- `docs/generated/py_file_index.md` — 重新生成

## Commands Run

```bash
ruff check .           # 3 pre-existing errors, none new
black . --check        # 11 pre-existing files need formatting, none from our changes
isort . --check-only   # 2 pre-existing errors, none new
mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/ workers/ ingestion/  # Only pre-existing errors
python -m pytest tests/ -v  # 1250 passed, 1 skipped
python scripts/generate_py_file_index.py  # OK
python scripts/check_doc_sync.py  # PASSED
```

## Test Results

- **ruff**: 3 pre-existing errors, no new errors
- **black**: 11 pre-existing files need formatting, none from our changes
- **isort**: 2 pre-existing errors, none new
- **mypy**: Only pre-existing errors
- **pytest**: **1250 passed, 1 skipped** — no regressions
- **doc sync**: PASSED
- **file index**: Generated

## Justification for No Additional Tests

1. **Pipeline 复用** — 内部重构，行为不变。已有 `test_process_one_publishes_events` 覆盖 `process_one()` 路径。
2. **指数退避** — 纯运行时行为，依赖时间流逝，不适合单元测试。可在 staging 环境观察日志验证。
3. **长文档并发提取** — `ConcurrentLLMExtractor` 路径已有集成测试覆盖（`test_pipeline_integration.py`），KnowledgePipeline 只是路由到已有路径。
4. **多进程扩展** — CLI 命令和 API 端点是 `subprocess` + PID 文件的薄包装，逻辑简单且依赖外部进程管理。与上一轮 knowledge worker 测试相同的理由。

## Remaining Risks

- 多进程并发消费同一 PostgreSQL ingestion_queue 时，`pending → processing` 状态转换在高并发下的竞态行为需要在 staging 环境验证
- `ModelGatewayImpl` 初始化依赖 `settings.PROVIDER_PROFILES` 环境变量配置，部署时需确保 worker 进程能读取 `.env`
