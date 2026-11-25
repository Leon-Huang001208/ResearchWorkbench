# OpenAPI 参数说明：457 个业务用法, 124 个 location/name 组合

宿主 macOS（Mac mini），任务为 API 文档化。承接 2026-11-24 的响应模型批次：
全量手册显示 `parameters_described = 0`，457 个参数用法没有说明，本任务补这一层。

## 做法

新增 `app/research_web/api_parameter_docs.py`：以 `location:name` 为键的词汇表，加上
按路径前缀的语义覆盖。`create_app` 只调用一次 `install_openapi_parameter_docs(app)`，
包装 `app.openapi` 并在返回前补 `description`。

- 只写 OpenAPI：不进入请求解析、校验、序列化或响应路径。
- 已有 `description` 一律保留；包装器可重复调用。
- 前缀覆盖处理同名不同义的参数：`did`（数据集/档案）、`code`（证券/OAuth）、
  `state`（业务状态/OAuth）、`kind`（报告/能力/信号）、`page`、`view`、`start`、`end` 等。
- 当前覆盖 457 个业务参数用法、124 个 location/name 组合；静态资源路径不列入 API Manual。

## 为什么不批量猜响应 schema

剩余 453 个操作的返回多来自 `await service.x()` 或既有序列化函数，真实结构在 service
层；本批仍保持 `未记载`。参数说明可以逐项对应现有签名与枚举，因此先做完这一层。

## 验证

- `test_api_parameter_docs.py` 覆盖业务参数、死条目、前缀匹配、已有说明保留、幂等，
  以及补说明前后的字段约束、真实 HTTP 请求和响应一致性：6 passed。
- `test_api.py` 全模块在本地 300 秒上限结束，未取得通过结果；改为验证与本次接线相关的
  OpenAPI/requestBody、字段校验和同源边界用例：2 passed。
- `pytest tests/research_web/test_workbench_operations.py tests/research_web/test_documentation.py`：
  36 passed。
- `node --test tests/javascript/actions_quota_governance.test.mjs`：38 passed。
- 与架构生成物合同合并执行：200 passed。
- `ruff check` 通过；新文件的 `ruff format --check` 通过，`main.py` 原有格式差异保持。

只读 Python 评审核对源码 `75131f724fc4f767ce76c408ba1ef8af59683b6d`，无 P1/P2 问题。
评审另将禁用包装的完整 schema 与剥除新增说明后的 schema 比较，完全一致；重点核对
`before` 运行 ID、带时区 `as_of`、分页起点、CN/US/HK 事件市场与 OAuth 参数语义。
架构首页/Atlas 的源码阅读链接同步固定到该真实提交，包含新增词汇表与回归测试。

## CI 范围

全量 Web 合同仍在 45 分钟作业上限被取消（不是用例失败）。`api_doc_only` 增加
`api_parameter_docs.py` 作为触发核心；`main.py` 只有在同一差异命中该模块时才允许，
并执行 `test_api.py` 中的 schema/字段校验与同源边界合同。混合或未知文件仍回退完整路径。

## 未做

- 未改其余 453 个操作的响应 schema：需要逐条读 service 实现，不能从同类接口推断。
- 未改操作级 `summary`/`description`：本批只补参数；操作说明另批处理。

<!-- architecture-review {"group":"research-api","structure":"unchanged","reason":"只在 create_app 上补充仅写 OpenAPI 的参数说明，路由、请求解析、响应与运行拓扑不变；04-api.md 已同步。","diagrams":[]} -->
<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"复用既有 Checks scope selector 扩展 api_doc_only，执行主应用相关 schema、字段校验和同源合同；不新增 job、runner、依赖、权限、dispatch 或时限。","diagrams":[]} -->
