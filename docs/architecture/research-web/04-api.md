# Research Web 接口清单

路由由源码声明、架构清单与重启后的 8088 OpenAPI 双向核对：当前有 125 个唯一 HTTP 操作、127 项源码声明（包括根页）。其中报告运行详情与取消各保留一条兼容声明，因此声明数不能当作唯一接口数。`report_workflow_routes.py` 提供具体报告 Workflow 的资源、版本、Provider 探测、运行、重试、交付和日程接口；`operations.py` 只聚合真实运行证据。目录与消息使用当前原生能力版本契约；API 不是旧 `/api/research-runs`。

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
| DELETE | `/api/research/sessions/{sid}` | `app/research_web/main.py` |
| POST | `/api/research/sessions/{sid}/restore` | `app/research_web/main.py` |
| DELETE | `/api/research/sessions/{sid}/permanent` | `app/research_web/main.py` |
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
| GET | `/api/research/assets/observations` | `app/research_web/asset_routes.py` |
| POST | `/api/research/assets/observations` | `app/research_web/asset_routes.py` |
| GET | `/api/research/assets/observations/{observation_id}` | `app/research_web/asset_routes.py` |
| GET | `/api/research/watchlists` | `app/research_web/asset_routes.py` |
| POST | `/api/research/watchlists` | `app/research_web/asset_routes.py` |
| POST | `/api/research/watchlists/{watchlist_id}/items` | `app/research_web/asset_routes.py` |
| GET | `/api/research/asset-notes` | `app/research_web/asset_routes.py` |
| POST | `/api/research/asset-notes` | `app/research_web/asset_routes.py` |
| PATCH | `/api/research/asset-notes/{note_id}` | `app/research_web/asset_routes.py` |
| GET | `/api/research/asset-alerts` | `app/research_web/asset_routes.py` |
| POST | `/api/research/asset-alerts` | `app/research_web/asset_routes.py` |
| PATCH | `/api/research/asset-alerts/{alert_id}` | `app/research_web/asset_routes.py` |
| GET | `/api/research/asset-notifications` | `app/research_web/asset_routes.py` |
| GET | `/api/research/operations/summary` | `app/research_web/operations.py` |
| GET | `/api/research/operations/usage` | `app/research_web/operations.py` |
| GET | `/api/research/operations/tools` | `app/research_web/operations.py` |
| GET | `/api/research/operations/datahub` | `app/research_web/operations.py` |
| GET | `/api/research/operations/services` | `app/research_web/operations.py` |
| GET | `/api/research/operations/storage` | `app/research_web/operations.py` |
| GET | `/api/research/local-integrations` | `app/research_web/local_integrations/routes.py` |
| POST | `/api/research/local-integrations/probes` | `app/research_web/local_integrations/routes.py` |
| GET | `/api/research/local-integrations/probes/{probe_id}` | `app/research_web/local_integrations/routes.py` |
| GET | `/api/research/data/catalog` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/data/capabilities/{capability_id}` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/data/sources/{source_id}` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/data/connections` | `app/research_web/datahub/routes.py` |
| GET | `/api/research/data/connections/migration-preview` | `app/research_web/datahub/routes.py` |
| POST | `/api/research/data/connections/migrations` | `app/research_web/datahub/routes.py` |
| GET / PUT / DELETE | `/api/research/data/sources/{source_id}/configuration` | `app/research_web/datahub/routes.py` |
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
| GET | `/api/research/report-workflows` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/providers` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/providers/{provider_id}/probe` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/migrations` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/{workflow_id}` | `app/research_web/report_workflow_routes.py` |
| PATCH | `/api/research/report-workflows/{workflow_id}/draft` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/copy` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/resources` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/{workflow_id}/versions` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/versions` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/versions/{version}/publish` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/versions/{version}/rollback` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/versions/{version}/preflight` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/{workflow_id}/versions/{version}/resources` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/{workflow_id}/versions/{version}/resources/{resource_path:path}` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/disable` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/{workflow_id}/runs` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-workflows/{workflow_id}/runs` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-workflows/{workflow_id}/schedule` | `app/research_web/report_workflow_routes.py` |
| PUT | `/api/research/report-workflows/{workflow_id}/schedule` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-runs/{run_id}` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-runs/{run_id}/cancel` | `app/research_web/report_workflow_routes.py` |
| POST | `/api/research/report-runs/{run_id}/retry` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-runs/{run_id}/refresh-manifests` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-runs/{run_id}/delivery` | `app/research_web/report_workflow_routes.py` |
| GET | `/api/research/report-projects` | `app/research_web/report_routes.py` |
| POST | `/api/research/report-projects` | `app/research_web/report_routes.py` |
| GET | `/api/research/report-projects/{project_id}` | `app/research_web/report_routes.py` |
| PATCH | `/api/research/report-projects/{project_id}` | `app/research_web/report_routes.py` |
| POST | `/api/research/report-projects/{project_id}/files` | `app/research_web/report_routes.py` |
| GET | `/api/research/report-projects/{project_id}/versions` | `app/research_web/report_routes.py` |
| POST | `/api/research/report-projects/{project_id}/versions` | `app/research_web/report_routes.py` |
| POST | `/api/research/report-projects/{project_id}/rollback` | `app/research_web/report_routes.py` |
| GET | `/api/research/report-projects/{project_id}/runs` | `app/research_web/report_routes.py` |
| POST | `/api/research/report-projects/{project_id}/runs` | `app/research_web/report_routes.py` |
| GET | `/api/research/report-projects/{project_id}/schedule` | `app/research_web/report_routes.py` |
| PUT | `/api/research/report-projects/{project_id}/schedule` | `app/research_web/report_routes.py` |
| GET | `/api/research/report-projects/{project_id}/artifacts` | `app/research_web/report_routes.py` |
| GET | `/api/research/report-projects/{project_id}/artifacts/{artifact_id}` | `app/research_web/report_routes.py` |
| GET | `/api/research/documentation/{name}` | `app/research_web/documentation.py` |

## 约束与错误

- 消息提交使用 `Idempotency-Key`；受理返回 202，不是执行或交付成功。受理未知时不自动重试。
- 会话、附件、文件、数据集必须属于产品索引中的当前会话；模型参数不能选择任意宿主路径。
- `GET /sessions` 默认只返回正常会话，`view=deleted|all` 显式读取墓碑；软删除写入 30 天可恢复窗口，恢复不触碰 DSH。永久删除和到期清理先调用 DSH `session.delete(cascade=true)`，确认根 ID 位于 `deletedSessionIds` 后才清理本产品目录与索引；运行中或删除已开始的会话拒绝恢复。服务启动与每 6 小时的在线保留期任务都会重试过期墓碑。
- `GET /data/catalog` 与详情接口只读取静态目录；`POST /data/sources/{id}/probes` 才检测一个指定来源，使用 `Idempotency-Key` 去重。探测结果只返回安全化错误码和耗时，不返回凭据或上游正文。
- `GET /data/connections` 汇总 22 个来源的配置、检测、适配和可调用状态；通用 configuration 接口只回传非秘密字段与 `secret_configured`。旧环境迁移必须先预览、再携带明确来源与二次确认执行，任一步失败均补偿恢复配置、凭据和 `.env`。
- `GET /local-integrations` 返回本机集成的安全四维状态；`POST /local-integrations/probes` 要求 `Idempotency-Key` 并返回 202 与独立任务 ID，查询接口只返回安全化状态或错误。服务端只允许一个真实探测执行，使用固定字段与安全操作路由白名单，并对无副作用检测设置时限；超时结果不会落盘。v0 探测不启动软件，不返回命中路径、注册表值、命令参数或环境变量。
- 研究取数只使用 `internal/data/business-query`，接受稳定业务能力、白名单来源 ID 和能力限定参数；旧产品前缀工具及其平行查询接口已经移除。浏览器不能直接调用 internal 入口。
- 研究台查询和交接均使用 `Idempotency-Key` 并经过串行准入。交接在创建目标会话前验证请求中的数据集归属，并限制页面上下文为 64 KiB；查询受理或 DSH 回合结束均不等于报告交付完成。
- 报告 Workflow API 管理具体报告版本包；运行只允许已启用且有当前版本的项目。`report-projects` 是迁移期后端兼容接口，没有独立产品导航或第二执行引擎，新页面只使用 `report-workflows`。
- operations 接口只返回安全化聚合。`summary` 是页面首选的一次性聚合，同一请求对每个会话的 DSH 历史只读取一次；服务进程状态还会核对状态指纹、项目/数据根与实际 PID 命令签名。分项接口保留给精确读取和测试。没有 usage 或价格时返回未知/未配置，不伪造零和费用。
- 结构错误返回明确 4xx；DSH 协议/连接故障不回退演示。服务端日志不输出密钥。
- SSE 为 `snapshot`、`runtime_error` 和心跳；重连通过原生日志恢复。取消和审批复用真实原生 RPC。
- 输出格式和独立交付状态见 [数据与文件](03-data-files.md)。文件下载与 HTML 预览不是任意静态仓库服务。

本清单与 `architecture-map.json` 同步维护。检查接口路径存在不能替代请求/响应契约测试。

Windows 专项作业实际启动 `127.0.0.1:8088`，读取 `/local-integrations` 并完成一次幂等探测轮询。该验证覆盖服务初始化与接口生命周期，不新增 API，也不将未安装厂商软件的 runner 投影为可调用。服务启动使用与生产相同的私有目录校验和 DSH 认证控制文件读取器；CI 占位元数据不表示 DSH 或厂商服务在线。
