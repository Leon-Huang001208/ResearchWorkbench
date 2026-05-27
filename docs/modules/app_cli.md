# Module: app/cli

## Responsibility

`app/cli` provides command-line access to AlphaFoundry workflows. It wraps service calls into user-facing commands.

---

## Design Rules

- Commands should be discoverable with `--help`
- Use consistent flag naming conventions
- Provide sensible defaults for optional parameters
- Output should be human-readable by default
- Add machine-readable output formats when needed
- Add or update tests when command behavior changes

---

## Files

### `app/cli/main.py`

Purpose:
- Main CLI entry point
- Registers all subcommands
- Sets up logging and configuration

Update this section when:
- New subcommands are added
- Global configuration changes
- Logging setup changes

### `app/cli/commands/*.py`

Purpose:
- Individual command implementations
- Wraps service calls into CLI operations

Update this section when:
- New commands are added
- Command arguments change
- Command output format changes

### `app/cli/commands/ingest.py`

Purpose:

- 数据摄入和 Worker 管理命令。
- `af ingest file` — 摄入文件（PDF/TXT/MD）并提取断言和事件。
- `af crawl run|backfill|status|scheduler-start` — 数据采集命令组。
- `af knowledge start|stop|status` — Knowledge Worker 进程管理命令。
- `af knowledge start --workers N` — 启动 N 个 Worker 进程实现水平扩展。

Related service:

- `services/ingest_service.py`
- `services/crawl_orchestrator.py`
- `workers/crawl_scheduler_worker.py`
- `workers/knowledge_worker.py`

---

## Required Tests

- CLI invocation tests
- Command output verification
- Error case handling tests

---

## Required Documentation Updates

When files in this module change, check:
- `docs/modules/app_cli.md`
- `docs/REFERENCE.md`
- `docs/FILE_GUIDE.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`