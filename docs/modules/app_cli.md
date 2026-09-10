# Module: app/cli

## Responsibility

`app/cli` provides command-line access to Research Workbench workflows. It wraps service calls into user-facing commands.

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

Research Web commands:

- `rwb web start|stop|restart|status` — manage the owned loopback Web/DSH processes.
- `rwb web tabbit-status` — read-only Tabbit health and pending-restart summary. It deliberately omits paths, cookies, tab titles, URLs and page content; installation and upgrades remain manual.

### `app/cli/commands/*.py`

Purpose:
- Individual command implementations
- Wraps service calls into CLI operations

Update this section when:
- New commands are added
- Command arguments change
- Command output format changes

### `app/cli/commands/ask.py`

Purpose:

- 联网问答命令：`rwb ask`。
- `rwb ask "问题"` — 始终先联网搜索，再综合生成带引用的答案。
- `-n/--max-results N` — 联网搜索最大结果数（默认 5）。
- `--no-fetch-content` — 不抓取网页正文，只用搜索 API 返回的摘要。
- 无搜索 API key 时自动降级为不联网直答，并在答案前标注 `[未联网]`。

Related service:

- `services/ask_factory.py` — `build_ask_service()`
- `services/ask_service.py` — `AskService`
- `services/web_search_service.py`

### `app/cli/commands/data.py`

Purpose:

- 统一数据摄入 CLI（Connector 架构）：`rwb data` 命令组。
- `rwb data list` — 列出所有可用数据源及 datasets。
- `rwb data ingest -s <src> -d <dataset>` — 统一数据摄入入口；CLS 电报数据集为 `telegram`。
- `rwb data backfill -s <src>` — 历史数据回填。
- `rwb data validate -s <src> -d <dataset>` — 数据校验。
- `rwb data status [--source <s>]` — 聚合 connector 健康 + Worker + Scheduler 状态。
- `rwb data file -f <path>` — 摄入单个文件。
- `rwb data schedule start|stop|status` — 采集调度器管理。
- `rwb data workers start|stop|status` — 知识加工 Worker 管理。

Related:
- `core/connectors/registry.py` — `ConnectorRegistry`
- `connectors/` — 具体连接器实现

Update this section when:
- New `rwb data` subcommands are added.
- CLI → Connector integration changes.
- Dataset names or help examples change.

---

### `app/cli/commands/ingest.py`

Purpose:

- 数据摄入和 Worker 管理命令。
- `rwb ingest file` — 摄入文件（PDF/TXT/MD）并提取断言和事件。
- `rwb crawl run|backfill|status|scheduler-start` — 数据采集命令组。
- `rwb knowledge start|stop|status` — Knowledge Worker 进程管理命令。
- `rwb knowledge start --workers N` — 启动 N 个 Worker 进程实现水平扩展。

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
