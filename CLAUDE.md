# Claude Code additions

@AGENTS.md

This file retains project context not covered by AGENTS.md and Claude-specific workflow guidance needed for Claude sessions.

## 架构速览

Research Workbench 是本地优先、模块化单体的 AI-native Investment Operating System：PostgreSQL + pgvector 是事实源，跨层数据通过 `core/contracts/` 中的 Pydantic v2 契约交换。

```text
外部数据 → connectors / data_layer → ingestion_queue → knowledge_layer
         → reasoning → cognitive_agents → timing_engine → signal_lab
         → memory_learning → reporting → app (FastAPI / Click / Web)
                              ↕
                     storage (PostgreSQL + Alembic)
```

- 所有模型调用只能经 `core/model_gateway/`；业务代码不得直接调用模型 API。
- Agents 只能通过 `CognitiveBlackboard` 交换 `AgentView`；不得直接互聊。
- 未经 Signal Lab 验证的信号必须保留为 `research_only`，不得提升为交易候选。
- Connector lifecycle 固定为：`discover → fetch → save_raw → parse → normalize → validate → persist`。
- 新数据源在 `data_sources/` 用 `register(SourceSpec(...))` 注册，由 `ConnectorRegistry` 发现；Connector 负责摄入，LLM 提取属于 KnowledgePipeline。

## Runtime selection

使用当前操作系统中满足 Python >=3.11 的项目环境。Windows 上先激活文档说明的 `research_workbench` 环境；这是本机环境约定，不是跨平台硬路径。macOS/Linux 同样使用当前系统中满足版本要求的项目环境。跨平台命令中绝不可复制特定机器或系统的绝对解释器路径。

## 开发命令

当前可验证的开发调用为 `python -m app.cli.main`。`pyproject.toml` 中的 `af` console-script 入口是既有问题，不在本次文档工作流改造范围，不能作为已验证命令示例。

```bash
# 启动 FastAPI（自动重载）
python -m uvicorn app.api.main:app --reload
# http://127.0.0.1:8000 | Swagger: /docs | 健康检查: /health

# 初始化数据库
python scripts/bootstrap_db.py

# 测试
python -m pytest tests/ -v
python -m pytest tests/test_<module>.py -v
python -m pytest tests/test_<module>.py::test_<name> -v

# 静态检查与类型检查
python -m ruff check .
python -m black . --check
python -m isort . --check-only
python -m mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/

# 索引与项目检查
python scripts/generate_py_file_index.py
python scripts/check_task_completion.py
python scripts/check_doc_sync.py

# CLI 示例
python -m app.cli.main analyze --asset 600000.SH
python -m app.cli.main scenario --topic "人工智能产业发展"
python -m app.cli.main ingest file --file report.pdf
python -m app.cli.main report --template asset_analysis --asset 600519.SH --output report.md
python -m app.cli.main crawl scheduler-start
python -m app.cli.main knowledge start
```

## Claude-specific workflow

- 应用代码变更后，在可行时使用 Playwright MCP 对本地应用做 live browser 验证；视觉或交互变更需要截图时，以截图作为证据。
- .claude/ is ignored local context and optional. 仅在它存在时读取；它的缺失不得阻塞正常仓库工作或构成前置条件。
- Claude subagents 仅用于独立的仓库探索或验证；范围狭窄的编辑由主会话完成。
