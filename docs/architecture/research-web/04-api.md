# Research Web 接口清单

Goldar V1 增加 `/api/research/frameworks` 目录、版本化快照和页面会话接口。解释与深度验证均要求客户端提交当前 `snapshot_revision`；版本漂移返回 409，避免跨快照混合结论。详细字段与模式边界见 [研究框架](08-research-frameworks.md)。

能力工作区 v0 没有新增后端 API。`#/skills` 以 `kind=skill|tool|workflow|data` 作为四个主分区，
`view=library|mine|plans|connections|market` 只表示类型内二级视图；这些都是纯前端路由参数，继续读取
本页已有的 capabilities、tools、data catalog、data connections 与 report-workflows 接口。
旧 kind 深链保持兼容，无 kind 的 plans/connections 分别归一到 Workflow/Tool；`market` 只在 Tool
分区有效。Phase 2A 已增加功能开关保护的只读 MCP Registry API；Phase 2B 增加安装预览、
不可变安装记录、健康探测、Runtime 启停、OAuth、会话授权、资源/提示读取、高风险审批及 DSH
私有工具代理。Phase 2C 增加通用 Automation、运行查询/重试、报告日程显式迁移与投递渠道接口。

本轮跨平台修复不新增或修改 HTTP 路由。Windows 上的 Runtime 认证读取、DataHub 快照接口和会话文件下载在进入既有响应契约前执行规范路径、重解析点、普通文件及打开前后身份校验；失败继续返回既有安全错误，不暴露本机路径或文件内容。waterfall/cancel 的空或非字符串标识在协议边界统一返回 `protocol_error`。
MCP staging、安装 payload、清单与确认令牌目录的 Windows mode 修正发生在服务装配和安装预览
边界，不改变请求或响应 schema；目录类型、符号链接和重解析点仍关闭失败，POSIX 私有权限检查
保持不变。

路由由源码声明、架构清单与 OpenAPI 双向核对；唯一操作数由生成检查更新，不以手写计数替代。`report_workflow_routes.py` 提供具体报告 Workflow 的资源、版本、Provider 探测、运行、重试、交付和日程接口；`mcp_registry/routes.py` 提供只读目录、同步与外部 Publisher 交接；`mcp_runtime/routes.py` 提供功能开关保护的安装、运行、授权和 Host 代理契约；`automation/routes.py` 提供任务、Run、迁移和渠道契约；`operations.py` 只聚合真实运行证据。目录与消息使用当前原生能力版本契约；API 不是旧 `/api/research-runs`。

| Method | 路径 | 源码 |
|---|---|---|
| GET | `/api/research/mcp/registries` | `app/research_web/mcp_registry/routes.py` |
| POST | `/api/research/mcp/registries` | `app/research_web/mcp_registry/routes.py` |
| GET | `/api/research/mcp/registries/{registry_id}` | `app/research_web/mcp_registry/routes.py` |
| PATCH | `/api/research/mcp/registries/{registry_id}` | `app/research_web/mcp_registry/routes.py` |
| DELETE | `/api/research/mcp/registries/{registry_id}` | `app/research_web/mcp_registry/routes.py` |
| POST | `/api/research/mcp/registries/{registry_id}/sync` | `app/research_web/mcp_registry/routes.py` |
| GET | `/api/research/mcp/servers` | `app/research_web/mcp_registry/routes.py` |
| GET | `/api/research/mcp/servers/{registry_id}/{server_name:path}/versions/{version}` | `app/research_web/mcp_registry/routes.py` |
| POST | `/api/research/mcp/publisher/preview` | `app/research_web/mcp_registry/routes.py` |
| POST | `/api/research/mcp/publisher/validate` | `app/research_web/mcp_registry/routes.py` |
| GET / POST | `/api/research/mcp/installations` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/installations/preview` | `app/research_web/mcp_runtime/routes.py` |
| GET / PATCH / DELETE | `/api/research/mcp/installations/{installation_id}` | `app/research_web/mcp_runtime/routes.py` |
| GET | `/api/research/mcp/installations/{installation_id}/status` | `app/research_web/mcp_runtime/routes.py` |
| GET | `/api/research/mcp/installations/{installation_id}/capabilities` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/installations/{installation_id}/probe` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/installations/{installation_id}/enable` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/installations/{installation_id}/disable` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/installations/{installation_id}/update` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/installations/{installation_id}/oauth/start` | `app/research_web/mcp_runtime/routes.py` |
| GET | `/api/research/mcp/oauth/callback` | `app/research_web/mcp_runtime/routes.py` |
| GET | `/api/research/mcp/approvals` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/approvals/{approval_id}/approve` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/mcp/approvals/{approval_id}/deny` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/sessions/{session_id}/mcp-authorizations` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/sessions/{session_id}/mcp/resources/read` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/sessions/{session_id}/mcp/prompts/get` | `app/research_web/mcp_runtime/routes.py` |
| POST | `/api/research/internal/mcp/tools/call` | `app/research_web/mcp_runtime/routes.py` |
| GET | `/api/research/automations` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automations` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automations/migrations/report-schedules/preview` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automations/migrations/report-schedules/apply` | `app/research_web/automation/routes.py` |
| GET | `/api/research/automations/{automation_id}` | `app/research_web/automation/routes.py` |
| PATCH | `/api/research/automations/{automation_id}` | `app/research_web/automation/routes.py` |
| DELETE | `/api/research/automations/{automation_id}` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automations/{automation_id}/enable` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automations/{automation_id}/disable` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automations/{automation_id}/run` | `app/research_web/automation/routes.py` |
| GET | `/api/research/automation-runs` | `app/research_web/automation/routes.py` |
| POST | `/api/research/automation-runs/{run_id}/retry` | `app/research_web/automation/routes.py` |
| GET | `/api/research/delivery-channels` | `app/research_web/automation/routes.py` |
| PUT | `/api/research/delivery-channels` | `app/research_web/automation/routes.py` |
| GET | `/api/research/runtime` | `app/research_web/main.py` |
| GET | `/api/research/runtime/tabbit` | `app/research_web/main.py` |
| PUT | `/api/research/runtime/tabbit` | `app/research_web/main.py` |
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
| POST | `/api/research/sessions/{sid}/tabbit-access` | `app/research_web/main.py` |
| GET | `/api/research/sessions/{sid}/tabbit-tabs` | `app/research_web/main.py` |
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
| POST | `/api/research/local-integrations/verifications` | `app/research_web/local_integrations/routes.py` |
| GET | `/api/research/local-integrations/verifications/{verification_id}` | `app/research_web/local_integrations/routes.py` |
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
- Tabbit `web_fetch` 接管依赖浏览器自动化；多实例必须选择 16 位实例 ID。会话授权后才可读取候选，消息最多引用 8 个不重复且同实例的标签页，并要求 `tabbit_live_confirmed=true`。发送前重新验证可用性；claim、提取、释放或 token 生成任一步失败均不提交消息。
- Tabbit 配置 JSON 固定使用 UTF-8；Windows 原子替换只在临时文件句柄关闭后执行。清理异常不得覆盖原始保存错误，接口继续返回既有稳定错误契约。
- 会话、附件、文件、数据集必须属于产品索引中的当前会话；模型参数不能选择任意宿主路径。
- `GET /sessions` 默认只返回正常会话，`view=deleted|all` 显式读取墓碑；软删除写入 30 天可恢复窗口，恢复不触碰 DSH。永久删除和到期清理先调用 DSH `session.delete(cascade=true)`，确认根 ID 位于 `deletedSessionIds` 后才清理本产品目录与索引；运行中或删除已开始的会话拒绝恢复。服务启动与每 6 小时的在线保留期任务都会重试过期墓碑。
- `GET /data/catalog` 与详情接口只读取静态目录；`POST /data/sources/{id}/probes` 才检测一个指定来源，使用 `Idempotency-Key` 去重。探测结果只返回安全化错误码和耗时，不返回凭据或上游正文。
- `GET /data/connections` 汇总 22 个来源的配置、检测、适配和可调用状态；通用 configuration 接口只回传非秘密字段与 `secret_configured`。旧环境迁移必须先预览、再携带明确来源与二次确认执行，任一步失败均补偿恢复配置、凭据和 `.env`。
- `GET /local-integrations` 返回本机集成的安全四维状态；`POST /local-integrations/probes` 要求 `Idempotency-Key` 并返回 202 与独立任务 ID，查询接口只返回安全化状态或错误。服务端只允许一个真实探测执行，使用固定字段与安全操作路由白名单，并对无副作用检测设置时限；超时结果不会落盘。v0 探测不启动软件，不返回命中路径、注册表值、命令参数或环境变量。
- `POST /local-integrations/verifications` 仅接受 Excel、Word、PowerPoint 与 Wind Excel 白名单目标并要求 `Idempotency-Key`；查询接口返回安全化进度与结果。Office 验证只操作服务生成的临时文件；Wind 只在独占空白工作簿执行最小厂商公式并把二维码安全验证映射为待授权。PowerPoint 不要求 `python-pptx`；进程及超时清理由服务端绑定本轮真实所有权，既有用户 Excel 不得成为清理目标。
- 本机验证结果只有在上下文指纹一致且尚未到达 TTL 截止时才参与 `callable` 投影；TTL 为 `0` 时立即失效。
- 研究取数只使用 `internal/data/business-query`，接受稳定业务能力、白名单来源 ID 和能力限定参数；旧产品前缀工具及其平行查询接口已经移除。浏览器不能直接调用 internal 入口。
- 研究台查询和交接均使用 `Idempotency-Key` 并经过串行准入。交接在创建目标会话前验证请求中的数据集归属，并限制页面上下文为 64 KiB；查询受理或 DSH 回合结束均不等于报告交付完成。
- 报告 Workflow API 管理具体报告版本包；运行只允许已启用且有当前版本的项目。`report-projects` 是迁移期后端兼容接口，没有独立产品导航或第二执行引擎，新页面只使用 `report-workflows`。
- operations 接口只返回安全化聚合。`summary` 是页面首选的一次性聚合，同一请求对每个会话的 DSH 历史只读取一次；服务进程状态还会核对状态指纹、项目/数据根与实际 PID 命令签名。分项接口保留给精确读取和测试。没有 usage 或价格时返回未知/未配置，不伪造零和费用。
- 结构错误返回明确 4xx；DSH 协议/连接故障不回退演示。服务端日志不输出密钥。
- MCP Registry 路由在 `RESEARCH_MCP_REGISTRY_ENABLED` 关闭时返回 404。同步固定官方 `/v0.1` 与不透明游标，失败只返回带 `stale` 的最后成功缓存；身份三元组不跨 Registry 合并。认证 Registry 必须使用 HTTPS，无认证 HTTP 仅限精确 loopback，OAuth 端点始终使用 HTTPS。服务器 API 返回有界 Unicode plain text；包记录分别返回 `package_type_supported` 与 `immutable_reference`，不返回 `supported/installable` 或 Stage 2A 可安装承诺。Publisher 两个接口只返回规范 JSON、摘要、完整 argv 和 `executed:false`，从不启动 CLI。
- MCP Runtime 路由在 `RESEARCH_MCP_RUNTIME_ENABLED` 关闭时返回 404。安装必须先生成绑定完整摘要的短期确认令牌；本地目标只接受固定版本、逐制品哈希、直接 argv、最小环境和安全解包，远程目标只接受 HTTPS 或显式 loopback。安装、探测、启用与授权分离；每次调用重核安装版本、工具名、schema 哈希、风险分级和会话快照。无人值守只允许任务显式锁定且标记为可无人值守的只读工具；高风险调用必须完成一次性人工审批。内部工具代理只接受私有 loopback 控制密钥，不向浏览器公开。
- Automation 路由在 `RESEARCH_AUTOMATIONS_ENABLED` 关闭时返回 404。任务保存服务端解析的目标版本与内容 SHA；启动只补最近一次遗漏，重叠、版本漂移和中断均写入独立 Run。研究失败不自动重试，投递失败按固定退避独立重试且不改研究状态。渠道秘密只进入系统凭据库；报告日程迁移必须显式预览、逐项选择并原子应用。
- SSE 为 `snapshot`、`runtime_error` 和心跳；重连通过原生日志恢复。取消和审批复用真实原生 RPC。
- 输出格式和独立交付状态见 [数据与文件](03-data-files.md)。文件下载与 HTML 预览不是任意静态仓库服务。

本清单与 `architecture-map.json` 同步维护。检查接口路径存在不能替代请求/响应契约测试。

Windows 专项作业实际启动 `127.0.0.1:8088`，读取 `/local-integrations` 并完成一次幂等探测轮询。该验证覆盖服务初始化与接口生命周期，不新增 API，也不将未安装厂商软件的 runner 投影为可调用。服务启动使用与生产相同的私有目录校验和 DSH 认证控制文件读取器；CI 占位元数据不表示 DSH 或厂商服务在线。

Phase 2A/2B/2C 路由现在在未设置环境变量时默认启用；显式 `RESEARCH_MCP_REGISTRY_ENABLED=0`、`RESEARCH_MCP_RUNTIME_ENABLED=0` 或 `RESEARCH_AUTOMATIONS_ENABLED=0` 时，既有 404/禁用契约保持不变。接口路径和 schema 未变化。

2026-09-11 的格式基线维护未新增或修改任何 HTTP 路由、请求字段、响应字段或错误码。
