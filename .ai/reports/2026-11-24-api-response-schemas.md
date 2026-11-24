# 接口响应结构：只写文档，不改运行时

宿主 macOS（Mac mini），任务为 API 文档化。承接同一任务的 A 阶段：全量手册生成后，
缺口清单显示 **460 个操作中 0 个声明 2xx 响应 schema**，本任务补这一层。

## 选择的做法与实测依据

FastAPI 有两条看似等价的路：

| 做法 | 运行时影响 | OpenAPI |
| --- | --- | --- |
| `response_model=X` | **校验并过滤**响应，未声明字段被丢弃 | 生成 schema |
| `responses={200: {"model": X}}` | 无（原样返回） | 生成 schema |

实测（FastAPI 0.141.1 / pydantic 2.13.5）：处理器返回
`{"id": "x", "extra": "KEPT?", "n": 3}` 时，`response_model` 输出只剩 `{"id": "x"}`，
而 `responses={200: {"model": X}}` 完整保留三个键，同时 OpenAPI 仍生成 `$ref`。

因此统一采用后者。另实测：注册后再改 `route.responses` **无效**（OpenAPI 已缓存），
必须在装饰器上声明。

## 覆盖范围

| 接口 | 成功码 | 模型 |
| --- | --- | --- |
| `POST /data/queries` | 202 | `DeskQueryRecord` |
| `GET /data/queries` | 200 | `DeskQueryList` |
| `GET /data/queries/{query_id}` | 200 | `DeskQueryRecord` |
| `POST /data/queries/{query_id}/cancel` | 200 | `DeskQueryRecord` |
| `POST /assets/observations` | 202 | `AssetObservation` |
| `GET /assets/observations` | 200 | `AssetObservationList` |
| `GET /assets/observations/{observation_id}` | 200 | `AssetObservation` |

共 7 条。响应 schema 计数从 **0 → 7**；其余 453 条继续标 `未记载`，不用同类推断。

字段来源均为真实序列化函数：`workbench._public_query` 的 11 字段白名单、
`asset_workspace.public_observation` 的投影（明确移除 `request`、`refresh_keys`、
`history_generation`）。

错误响应按真实处理器核对：查询详情与观察详情返回 `StoreError` /
`AssetWorkspaceError` 的默认 **400**，取消查询显式 **404**，创建查询 **409/422**，
创建观察 **400/422**；创建观察当前没有 503 分支，未写入 schema。

## 运行时不变证据

- `pytest tests/research_web/test_workbench_operations.py`：9 passed（含新增回归）。
- `pytest tests/research_web/test_asset_loading.py tests/research_web/test_asset_directory.py`：40 passed。
- 新增
  `test_desk_query_response_models_document_shape_without_filtering_runtime`
  同时断言：OpenAPI 出现 `$ref`、模型 `extra="allow"`、实际响应仍为 `{"items"}`。
- `ruff check` / `ruff format --check` 通过。

## 手册侧连带修复

生成器原先对**所有**模型都写 `extra=forbid`，会把响应模型描述错。现按 schema 的
`additionalProperties` 判定：`False` 写 `forbid`，`True`/对象写「允许额外字段，
下列字段是已知子集」。已核对 `DeskQueryRecord`/`AssetObservation` 为 `True`，
`DeskQuery`/`BusinessQuery` 为 `False`。

## 未做

- 未给其余 453 条接口补 schema：多数处理器返回 `await service.x()`，真实结构在 service 层，
  需逐条读实现，不能批量推断。
- 未补参数 `description`（457 个参数仍为空）。

## 项目门禁

`app/research_web/` 改动触发 README 复核回执门禁；本次结论为 `unchanged`：
只补接口文档模型并写入 `04-api.md`，README 的入口、运行命令和部署边界未变。

全量 Web 合同在 45 分钟作业上限被取消（不是用例失败），因此沿已有窄范围模式新增
`api_doc_only`：以 `schemas_responses.py` 为触发核心，只跑 workbench 操作、
asset loading／directory 与文档路由，以及对应的 JS 合同；混合或未知文件仍回退全量。
范围选择、真实分支和允许清单由 `tests/javascript/actions_quota_governance.test.mjs` 覆盖。

<!-- architecture-review {"group":"verification-workflow","structure":"unchanged","reason":"在既有 Checks scope selector 增加 api_doc_only 收窄，不新增 job、runner、依赖、权限、平台 dispatch 或时限；验证流程与平台职责不变。","diagrams":[]} -->
- 未部署；本任务只改变源码与生成物。

<!-- architecture-review {"group":"workbench","structure":"unchanged","reason":"响应模型只登记 OpenAPI 结构，路由、服务与数据流未变，不新增节点或接口。","diagrams":[]} -->
