# Research Web 接口清单

路由由 `main.py`、`workbench.py`、`operations.py`、`datahub/routes.py`、`capabilities/routes.py`、`documentation.py` 核对，共 60 项声明（包括根页）。目录与消息使用当前原生能力版本契约；API 不是旧 `/api/research-runs`。

| Method | 路径 | 源码 |
|---|---|---|
| GET | `/api/research/runtime` | `app/research_web/main.py` |
| GET | `/api/research/models` | `app/research_web/main.py` |
| PUT | `/api/research/runtime/model` | `app/research_web/main.py` |
| GET | `/api/research/workspaces` | `app/research_web/main.py` |
| GET | `/api/research/sessions` | `app/research_web/main.py` |
| POST | `/api/research/sessions` | `app/research_web/main.py` |
| GET | `/api/research/sessions/{sid}` | `app/research_web/main.py` |
| PATCH | `/api/research/sessions/{sid}` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/messages` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/cancel` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/approvals/{aid}` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/questions/{qid}` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/upgrade` | `app/research_web/main.py` |
| GET | `/api/research/sessions/{sid}/events` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/uploads` | `app/research_web/main.py` |
| GET | `/api/research/sessions/{sid}/files` | `app/research_web/main.py` |
| GET | `/api/research/sessions/{sid}/files/{fid}/{action}` | `app/research_web/main.py` |
| GET | `/api/research/skills` | `app/research_web/main.py` |
| GET | `/` | `app/research_web/main.py` |
| POST | `/api/research/data/queries` | `app/research_web/workbench.py` |
| GET | `/api/research/data/queries` | `app/research_web/workbench.py` |
| GET | `/api/research/data/queries/{query_id}` | `app/research_web/workbench.py` |
| POST | `/api/research/handoffs` | `app/research_web/workbench.py` |
| GET | `/api/research/artifacts` | `app/research_web/workbench.py` |
| GET | `/api/research/operations/summary` | `app/research_web/operations.py` |
| GET | `/api/research/operations/usage` | `app/research_web/operations.py` |
| GET | `/api/research/operations/tools` | `app/research_web/operations.py` |
| GET | `/api/research/operations/datahub` | `app/research_web/operations.py` |
| GET | `/api/research/operations/services` | `app/research_web/operations.py` |
| GET | `/api/research/operations/storage` | `app/research_web/operations.py` |
| GET | `/api/research/data/catalog` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/data/capabilities/{capability_id}` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/data/sources/{source_id}` | `app/research_web/datahub/routes.py` |
| POST | `/api/research/data/sources/{source_id}/probes` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/data/probes/{probe_id}` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/sessions/{sid}/datasets` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/sessions/{sid}/datasets/{did}` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/sessions/{sid}/datasets/{did}/rows` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/sessions/{sid}/datasets/{did}/files/{name}` | `app/research_web/datahub/routes.py` |
| POST | `/api/research/internal/data/business-query` | `app/research_web/datahub/routes.py` |
| POST | `/api/research/internal/data/cancel` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/capabilities` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/tools` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/workflows` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/import` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/creation-sessions` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/from-artifact` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/capabilities/{cid}` | `app/research_web/capabilities/routes.py` |
| PATCH | `/api/research/capabilities/{cid}/draft` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/{cid}/copy` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/{cid}/check` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/{cid}/publish` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/{cid}/disable` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/{cid}/enable` | `app/research_web/capabilities/routes.py` |
| POST | `/api/research/capabilities/{cid}/rollback` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/capabilities/{cid}/versions` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/capabilities/{cid}/versions/{version}/export` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/capabilities/{cid}/versions/{version}` | `app/research_web/capabilities/routes.py` |
| GET | `/api/research/documentation/{name}` | `app/research_web/documentation.py` |

## 约束与错误

- 消息提交使用 `Idempotency-Key`；受理返回 202，不是执行或交付成功。受理未知时不自动重试。
- 会话、附件、文件、数据集必须属于产品索引中的当前会话；模型参数不能选择任意宿主路径。
- `GET /data/catalog` 与详情接口只读取静态目录；`POST /data/sources/{id}/probes` 才检测一个指定来源，使用 `Idempotency-Key` 去重。探测结果只返回安全化错误码和耗时，不返回凭据或上游正文。
- 研究取数只使用 `internal/data/business-query`，接受稳定业务能力、白名单来源 ID 和能力限定参数；旧产品前缀工具及其平行查询接口已经移除。浏览器不能直接调用 internal 入口。
- 研究台查询和交接均使用 `Idempotency-Key` 并经过串行准入。交接在创建目标会话前验证请求中的数据集归属，并限制页面上下文为 64 KiB；查询受理或 DSH 回合结束均不等于报告交付完成。
- operations 接口只返回安全化聚合。`summary` 是页面首选的一次性聚合，同一请求对每个会话的 DSH 历史只读取一次；分项接口保留给精确读取和测试。没有 usage 或价格时返回未知/未配置，不伪造零和费用。
- 结构错误返回明确 4xx；DSH 协议/连接故障不回退演示。服务端日志不输出密钥。
- SSE 为 `snapshot`、`runtime_error` 和心跳；重连通过原生日志恢复。取消和审批复用真实原生 RPC。
- 输出格式和独立交付状态见 [数据与文件](03-data-files.md)。文件下载与 HTML 预览不是任意静态仓库服务。

本清单与 `architecture-map.json` 同步维护。检查接口路径存在不能替代请求/响应契约测试。
