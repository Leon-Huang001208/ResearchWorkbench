# Ruff、Black、isort 格式基线修复记录

## 范围

- 修复上一轮本机集成交付暴露的 4 个相关文件，不扩展为全仓历史格式化。
- 仅调整导入布局、长表达式排版，并使用 Python 3.11 已原生支持的 `datetime.fromisoformat(...Z)` 等价写法移除过时抑制。
- 报告 Workflow 测试中的同模块导入由 Ruff 与 isort 9 给出相反布局；保留 Ruff 的规范分组，并以单行 `isort: skip` 将例外限制在该导入，不放宽全局配置。

## RED 证据

- `ruff check`：`app/research_web/local_integrations/__init__.py` 报 `I001`。
- `black --check`：`app/research_web/local_integrations/manager.py` 与 `data_layer/adapters/wind/client.py` 需要重排。
- `isort --check-only`：`tests/research_web/test_report_workflows.py` 导入顺序失败。
- 全仓 Black 另有 165 个历史文件需要格式化，Ruff 还包含大量非格式规则债务；它们不属于本次“少量格式漂移”修复，没有混入本提交。

## GREEN 证据

- 上述 4 个文件的 Ruff、Black、isort 定向门禁全部通过。
- `mypy --follow-imports=silent` 覆盖 3 个源文件：通过。
- 本机集成、Wind 适配器与报告 Workflow 回归：`211 passed, 1 skipped`。
- Research Web 架构门禁通过后记录最终结果；`git diff --check` 与项目约束在交付前复跑。

## 文档同步说明

- Research Web 架构文档与复核记录已同步注明此次变更不改变 API、状态、运行时或安全拓扑。
- Wind 数据源、文件指南、模块文档和更新日志已同步注明行为不变。
- 桌面打包文档明确记录 Wind 客户端只发生语义不变的排版调整，不据此扩大桌面或 Windows 验收声明。
- `docs/generated/py_file_index.md` 已使用仓库生成器从当前源码树重建，补齐当前主线尚未投影的导入、函数与方法条目；不手工编辑生成内容。
