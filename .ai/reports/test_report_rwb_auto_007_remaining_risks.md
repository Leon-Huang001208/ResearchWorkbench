# Test Report: rwb-auto-007-remaining-risks

## Task

RWB-AUTO-007 剩余风险修复 — P0/P1/P2 风险处理

## Changed Source Files

- `storage/migrations/env.py` — 启用 Alembic autogenerate (target_metadata = Base.metadata)
- `storage/migrations/versions/009_add_structured_market_data_tables.py` — 手动迁移文件 (8 张结构化表)
- `app/api/routes/assets.py` — `get_asset_service()` 注入 `MarketDataRepository`
- `core/services/asset_analysis_service.py` — 增加 `_has_enough_structured_data` 数据质量防护
- `scripts/check_market_data_schema.py` — 新建: Schema 检查脚本
- `scripts/bootstrap_market_data.py` — 新建: 数据填充脚本

## Changed Test Files

- `tests/unit/test_asset_analysis_service.py` — 适配新的构造函数签名 (移除 use_mock) 和 async 接口

## Changed Docs

- `docs/modules/app_api.md` — 添加 `assets.py` 路由说明和 DI 注入文档
- `docs/modules/core_services.md` — 添加 `asset_analysis_service.py` 数据源优先级说明和 `_has_enough_structured_data` 防护
- `docs/modules/storage.md` — 添加 `env.py` 配置说明 (autogenerate 已启用)
- `docs/DATA_STORAGE.md` — 添加迁移 009 条目
- `docs/FILE_GUIDE.md` — 添加 2 个新脚本
- `docs/CHANGELOG.md` — 添加本次变更

## Commands Run

```bash
black --check .
ruff check .
isort --check-only .
mypy
pytest (relevant tests)
python scripts/generate_py_file_index.py
python scripts/check_doc_sync.py
python scripts/check_task_completion.py
```

## Command Results

| Command | Result | Notes |
|---------|--------|-------|
| black --check . | Passed | All files formatted |
| ruff check . | 228 errors | All pre-existing (timing_engine, etc.) |
| isort --check-only . | Passed | 2 skipped files (pre-existing) |
| mypy | 1181 errors | All pre-existing (246 files with missing annotations) |
| pytest (relevant) | 20 passed | 0 failed |
| generate_py_file_index | Passed | Generated |
| check_doc_sync | Fails on ARCHITECTURE.md, REFERENCE.md | Justified exceptions (see below) |
| check_task_completion | Fails | `.ai/` dir gitignored (known limitation) |

## Skipped Tests

None — all RWB-AUTO-007 related tests pass.

## Doc Sync Justified Exceptions

- **docs/ARCHITECTURE.md**: No architectural change in this session. Changes are incremental fixes (dependency injection, data quality guard, scripts, migration file). Architecture boundaries, data flow, and subsystem responsibilities remain the same.
- **docs/REFERENCE.md**: No API surface changes. `assets.py` change is internal dependency injection; no new endpoints or schema changes.

## Remaining Risk

- Alembic migration requires PostgreSQL to actually run (`alembic upgrade head`). Fails locally because PostgreSQL is not running. Migration file is manually verified.
- `check_task_completion.py` fails due to `.ai/` being in `.gitignore` — test report file not visible in git diff. Known limitation.