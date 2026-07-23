# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

AlphaFoundry 是一个本地优先、企业级的买方投研情报系统，核心定位是 **AI 驱动的事件型量化（Event-driven Quant）**：AI 负责发现事件和产业链传播路径，Timing Engine 判断市场是否认可该逻辑，Signal Lab 负责统计验证和回测。

本文件是 Claude 的最高优先级入口，必须保持简短。详细的执行规则在 `.claude/rules/` 中。

---

## 开发命令

**Python 解释器**：`C:\Users\H01402\AppData\Local\anaconda3\envs\alphafoundry\python.exe`（`conda activate alphafoundry`）

CLI 入口通过 `af` 命令暴露（`pyproject.toml` 注册为 `app.cli.main:main`）。

```bash
# 启动 API 服务（开发模式，自动重载）
uvicorn app.api.main:app --reload
# 访问: http://127.0.0.1:8000 | Swagger: /docs | 健康: /health

# 数据库初始化
python scripts/bootstrap_db.py

# 运行全部测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_<module>.py -v

# 运行单个测试函数
python -m pytest tests/test_<module>.py::test_<name> -v

# 代码格式化检查（必须全部通过才能标记任务完成）
ruff check .
black . --check
isort . --check-only

# 类型检查
mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/

# 生成 py 文件索引（docs/generated/py_file_index.md）
python scripts/generate_py_file_index.py

# 完成检查脚本
python scripts/check_task_completion.py
python scripts/check_doc_sync.py

# CLI 使用示例
af analyze --asset 600000.SH
af scenario --topic "人工智能产业发展"
af ingest --file report.pdf
af report --asset 600519.SH --type full
af crawl scheduler-start
af knowledge start
```

---

## 架构速览

模块化单体，PostgreSQL + pgvector 作为唯一事实源，各层之间通过 `core/contracts/`（Pydantic v2）交换数据。

```text
外部数据 → data_layer (adapters/crawlers/normalizers)
         → ingestion_queue (PostgreSQL) → knowledge_worker (KnowledgePipeline)
         → knowledge_layer (实体解析 → 断言 → Event DB → 向量检索)
         → reasoning (证据链 → 情景 → 推理追踪)
         → cognitive_agents (Blackboard: Bull/Bear/Skeptic/Fundamental/Macro…)
         → timing_engine (Regime/Flow/Theme/Sentiment/Crowding)
         → signal_lab (特征 → 标签 → 评分 → Event Study 回测)
         → memory_learning (Episode/Failure/Strategy Memory)
         → reporting (占位符 → Evidence 检索 → ModelGateway → Word/Markdown)
         → app (CLI: Click | API: FastAPI | Web: 工作台)
                         ↕
               storage (PostgreSQL + Alembic 迁移)
```

**关键架构约定**：

- 添加新数据源：在 `data_sources/` 新建 `.py` 文件并调用 `register(SourceSpec(...))`，`ConnectorRegistry` 自动发现
- 所有模型调用必须经过 `core/model_gateway/`，不得在业务代码中直接调用模型 API
- Agent 不直接互聊，所有观点写入 `CognitiveBlackboard`（`AgentView` schema）
- 未通过 Signal Lab 验证的信号只能停留 `research_only`，不能升级为交易候选
- `core/connectors/base.py` 定义 Connector 生命周期：`discover → fetch → save_raw → parse → normalize → validate → persist`

---

## 0. 强制规则加载

在执行任何任务前，Claude 必须阅读：

1. `CLAUDE.md`
2. `.claude/rules/00-core-rules.md`
3. `.claude/rules/01-task-workflow.md`

然后，根据任务类型，Claude 必须阅读：

- 代码变更 → `.claude/rules/02-test-policy.md`
- 文档变更 → `.claude/rules/03-doc-sync-policy.md`
- Git / 分支 / 提交 / PR 工作 → `.claude/rules/04-git-workflow.md`
- 阻塞任务 → `.claude/rules/05-blocking-policy.md`
- 最终响应 → `.claude/rules/06-final-response.md`

对于代码变更，Claude 还必须阅读：

- `docs/ARCHITECTURE.md`
- `docs/DEVELOPMENT_MAP.md`
- 相关的 `docs/modules/*.md`

## 0.1 项目实践规则（在相关任务时必须查看）

在处理特定类型的任务时，Claude 还必须阅读 `.claude/rules/project-practices/` 中的这些规则：

- 写 Python 代码时 → `001-code-quality.md` (代码格式化/质量规范)
- 写测试时 → `002-testing.md` (测试规范)
- 加日志时 → `003-logging.md` (日志规范)
- 数据库迁移时 → `004-database-migrations.md` (数据库迁移规范)
- 修改 Pydantic 契约时 → `005-pydantic-contracts.md` (Pydantic 契约规范)
- CLI 开发时 → `006-cli-development.md` (CLI 开发规范)
- 更新文档时 → `007-auto-update-docs.md` (文档更新规范)
- Signal Lab 开发时 → `008-signal-lab.md` (Signal Lab 开发规范)

---

## 1. 项目子系统

AlphaFoundry 不是简单的前端/后端项目，它包含以下子系统：

- `app/` - API、CLI、Web 工作台
- `core/` - 契约、接口、服务、模型网关、配置
- `data_layer/` - 适配器、爬虫、解析器、规范化器、仓储
- `knowledge_layer/` - 实体解析、断言、事件、检索
- `reasoning/` - 证据、情景、怀疑论检查、追踪
- `cognitive_agents/` - 认知代理和黑板
- `timing_engine/` - 市场择时模型
- `signal_lab/` - 特征、标签、评分、回测
- `memory_learning/` - 结果记忆、失败记忆、学习日志
- `reporting/` - 报告生成和投影
- `storage/` - 数据库模式和迁移
- `ingestion/` - 结构化摄入模块
- `cron_jobs/` - 定时自动化
- `scripts/` - 操作脚本
- `tests/` - 测试套件
- `.ai/` - 任务状态、进度、报告

---

## 2. 不可协商规则

1. 除非实现、测试、文档和验证都完成，否则不要标记任务为"完成"
2. 如果任何 `.py` 源文件变更，必须添加或更新测试，除非在测试报告中明确说明理由
3. 如果任何源文件变更，必须更新相关文档
4. 除非命令确实运行过，否则不要声称测试通过了
5. 如果任何必需的检查失败，任务就是阻塞的，不是完成的
6. 不要伪造成功
7. 不要从任务文件中删除任务
8. 除非用户明确要求，否则不要执行破坏性操作
9. 每个会话只专注于一个任务
10. 所有完成的工作都必须在 `.ai/reports/` 中留下可审计的证据

## 2.1 运行环境

- Python 命令默认使用 alphafoundry conda 环境的解释器：`C:\Users\H01402\AppData\Local\anaconda3\envs\alphafoundry\python.exe`（激活方式：`conda activate alphafoundry`）
- 不要使用或安装系统 Python（`C:\Python314`）或 base 环境的包，除非用户明确要求

---

## 3. 必需的完成检查

在标记任何任务为"完成"前，Claude 必须运行：

```bash
ruff check .
black . --check
isort . --check-only
mypy core/ data_layer/ knowledge_layer/ reasoning/ reporting/ signal_lab/ app/
python -m pytest tests/ -v
python scripts/generate_py_file_index.py
python scripts/check_task_completion.py
python scripts/check_doc_sync.py
```

**所有代码变更后（无论是否涉及 UI）**，Claude 必须使用 Playwright MCP 打开本地 AlphaFoundry（`http://127.0.0.1:8765`），验证应用是否正常运行、变更已同步生效，并截图留证。

如果任何命令失败，不要标记任务为完成。遵循 `.claude/rules/05-blocking-policy.md`。

---

## 4. 文档检查

如果源代码变更，Claude 必须更新相关文档。

可能的文档目标：

- `docs/modules/*.md`
- `docs/FILE_GUIDE.md`
- `docs/ARCHITECTURE.md`
- `docs/REFERENCE.md`
- `docs/DATA_SOURCES.md`
- `docs/DATA_STORAGE.md`
- `docs/backup_restore.md`
- `docs/CHANGELOG.md`
- `docs/generated/py_file_index.md`

具体需要哪些文档由以下决定：

- `docs/DEVELOPMENT_MAP.md`
- `.claude/rules/03-doc-sync-policy.md`
- `scripts/check_doc_sync.py`

---

## 5. 任务状态位置

任务文件：

```text
.ai/tasks/task_<task_id>.json
```

进度文件：

```text
.ai/progress/progress_<task_id>.md
.ai/progress/progress.md
```

报告：

```text
.ai/reports/test_report_<task_id>.md
```

任务仅在以下情况下才算完成：

- 实现完成
- 测试已添加或有理由说明
- 文档已同步
- 所有必需的检查通过
- 测试报告存在
- 任务状态已更新
- 进度已更新

---

## 6. 最终响应要求

每个最终响应必须遵循 `.claude/rules/06-final-response.md`。

必需的最少字段：

```text
Task ID:
Affected subsystem:
Changed source files:
Changed tests:
Changed docs:
Commands run:
Test result:
Doc sync result:
Status:
Remaining risks:
```
