# Research Workbench × LSH 详细蓝图追踪契约

## 1. 目的

本契约是详细产品蓝图、API Atlas、架构图和产品原型之间的稳定追踪标准。任何功能都必须能够回答：它为什么存在、出现在哪个页面、调用哪个接口、由哪个服务负责、读写哪些数据、产生哪些事件，以及异常时进入什么状态。

三个 JSON Catalog 是机器可校验的唯一追踪源：

- `capabilities.json`：产品能力与页面。
- `api-atlas.json`：HTTP/SSE 接口契约。
- `traceability.json`：Service、数据 Owner、领域事件与跨层映射。

## 2. 稳定编号

| 对象 | 格式 | 示例 |
|---|---|---|
| 能力 | `CAP-<DOMAIN>-NNN` | `CAP-FIN-001` |
| 页面 | `PAGE-PNN` | `PAGE-P04` |
| API | `API-<DOMAIN>-NNN` | `API-RES-001` |
| 服务 | `SVC-<DOMAIN>-NNN` | `SVC-RES-001` |
| 数据 Owner | `DATA-<DOMAIN>-NNN` | `DATA-AST-001` |
| 事件 | `EVT-<DOMAIN>-NNN` | `EVT-ALT-001` |

编号一经进入已发布 Catalog 不得复用。重命名保留编号；删除对象保留记录并以能力决策或接口状态说明替代路径。

## 3. 必填字段

### Capability

`id`、`domain`、`name`、`decision`、`description`、`page_ids`。

`decision` 只允许：

- `retain`：保留原能力与产品职责。
- `merge`：合并到共享内核，原入口不得继续维护平行实现。
- `remove`：删除重复能力，追踪项必须声明 `replacement_capability_ids`。
- `add`：合并平台新增能力。

### Page

`id`、`route`、`name`、`domain`、`states`。所有页面必须声明 `default`、`loading`、`empty`、`partial`、`error`、`permission_denied`。事实页面额外声明 `stale`、`unavailable`、`quarantined`；Claw 页面额外声明 `blocked_runtime`。

### Interface

`id`、`method`、`path`、`request_model`、`response_model`、`response_kind`、`success_statuses`、`errors`、`idempotency`、`service_id`、`read_data_owner_ids`、`write_data_owner_ids`、`event_ids`、`security`、`fact_envelope_fields`。

所有写接口必须声明幂等语义。事实响应必须按固定顺序返回：

```text
as_of, observed_at, available_at, source_refs, freshness_status, quality_flags
```

`freshness_status` 只允许 `fresh`、`stale`、`unavailable`、`quarantined`。缺失事实使用明确缺失语义，不得用零值或模型猜测补齐。

### Trace

`capability_id`、`page_ids`、`api_ids`、`service_ids`、`data_owner_ids`、`event_ids`、`local_interaction`。

活跃能力必须映射至少一个页面或明确为本地交互，并映射至少一个 API 或明确为本地交互。`remove` 能力不再映射页面/API，但必须声明非空 `replacement_capability_ids`。

## 4. 数据与安全边界

- 事实区、研究区、个人观察区分别由对应数据 Owner 管理。
- 模块只通过 Service/Contract 通信，不得绕过 Owner 直接访问其他模块数据表。
- 模型和 Runtime 不得写事实区。
- DSH Runtime 不持有数据库权限。
- Skill 只允许声明式提示词、I/O Schema、平台内置工具、附件、受控网页域名和注册白名单 MCP。

## 5. 变更规则

1. 先更新 Catalog 和测试，再更新图、页面和实现。
2. Additive API 直接增加稳定编号，不创建全量 `/api/v2`。
3. 旧接口删除前必须有替代映射、兼容窗口、等价验证和回退说明。
4. 生成器只校验和投影 Catalog，不得静默修复输入。
