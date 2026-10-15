# Research Workbench Development Map

Claw执行流定位为`ui/claw-flow.mjs`、`disclosures.mjs`、`uploads.mjs`及原`core/app/views/shell`；正文搜索为`service.search_sessions`、`main`的严格JSON POST和`client`固定`session.search`映射，UI由`session-search.mjs`串行消费。近处测试为`research_web_claw_flow/send_races/disclosures/uploads/session_search.test.mjs`、`test_session_search.py`与`test_automation_research_task.py`。不新增正文库、调度器或依赖；搜索与长试跑句的权限/失败契约同步UI、API、安全及原生文档，安装CI仍须绑定新候选。

`main.py:local_boundary` 的 `entry_navigation` 仅允许用户触发的根路径 GET 顶层文档导航。
`test_api.py` 的 `clicked_entry` 覆盖本机/私网链接、哈希路由、API/资源/iframe/Origin
拒绝及 Host/HTTPS 保留；权威合同见接口清单、安全清单与安装文档。

Native Tailscale 私网 opt-in 在 `main.py:create_app/local_boundary` 校验精确 HTTPS
origin/Host，`service_manager.py` Doctor 读取运行中 `web_access` 投影。
近处回归为 `test_api.py` 的 tailscale/invalid_private_origin 与 `test_service_manager.py`
的 doctor_web_access。配置步骤、默认回环与多用户边界见安装文档、04-api 和安全清单。

Hot关注位于follows.ts/migration0019；周期计划位于periodic-briefs.ts/migration0020和brief-control的内部租约准入。Host hot_routes/hot_manager与Automation routes管理适配；UI为hot-follows/hot-brief-plans。近处测试覆盖PG最小角色、回放、截止、慢写回滚及Host真实白名单。

schema21的periodic_report_executions保存周期一次性报告原件和回执；periodic-report.ts通过
私有bootstrap的产品Python执行hot_periodic_report.py，复用hot_documents/report_documents，
不启动DSH。periodic handler先保存可复用产物，再在hot.brief的controller队列事务完成。
periodic.report签名读取32KiB块，Manager复验全部hash；GET和UI只下载既存字节。
测试为periodic-report.test.ts、periodic-briefs.integration.ts及test_hot_documents/manager/web。

Hot零重试准备位于launch_runtime.hot_zero_retry，私有同项目启用配置只影响本实例官方route。
正式执行为hot_handoff.execute_hot_handoff/hot_routes execute，复用send及原生marker恢复；
test_hot_execution覆盖丢失/重启/失败真值，test_hot_retry_policy/runtime_launch覆盖配置与overlay。
model-control.ts取消明确未发送reserved，hot_model_controls.py复验knownUnsent回执，真实PG测试
精确清理本次资源，未知或历史资源保留。

`app/research_web/live_acceptance_budget.py` 是实例私有验收账本；入口为 launcher/guard，近处测试为 `test_live_acceptance_budget.py`、`test_runtime_launch.py`、`research_web_guard.test.mjs`。费用、期限、持久扣票或绑定变化须同步预算设计与安全合同。

## FinGPT 深入研究定位

原生计划由 projection.py、runtime/research.cordis.yml 和 guard.mjs 处理；research_evidence.py 管理会话来源与底稿质量投影；resources/research_report.py 管理确定性中文报告。UI 的 research-report.mjs 复用当前研究空间与草稿控制器。近处用例为 test_fingpt_research.py、test_research_report.py 与 research_web_fingpt.test.mjs；改变引用/格式合同须同步 API、文件、UI、安装文档和架构清单。


本文件只回答四个问题：改哪片源码、先读哪份权威文档、跑哪些测试、什么变化需要同步文档。文件和公开符号的机械清单由 [生成索引](generated/py_file_index.md) 负责。

每轮资源收尾由`iteration_resources.py`/`iteration_cache.py`复用`docker_resources.py`及`git_safety.mjs`：任务归属/证据保存、全项目20GiB受管缓存预算、合并后自动清理与修补feature身份认证。权威规则见AGENTS、AGENT_WORKFLOW和Docker手册；近处测试为`test_iteration_resources.py`、`test_docker_resources.py`、`iteration_closeout.test.mjs`及`git_safety.test.mjs`。不新增产品API或调度器，风险为管理平面与安全清理。

## 当前 Research Web

Hot 的阶段一入口位于 `research_workbench_entrypoint/hot.py`（配置、诊断与 Native 生命周期），
`hot_manager.py`（签名进程管理）、`hot_postgres.py`（实例归属与受管 PG）和
`services/hot/`（PostgreSQL、私有签名回环协议与独立 Node 服务）。对应文档为
`services/hot/README.md` 与安装指南 Hot 小节；测试为 `test_hot_entrypoint.py`、`test_hot_manager.py` 及
`services/hot/tests/`。Web 生命周期、Settings、研究交接与结果页已装配；实现入口和
真实链路验收仍分别取证。新增入口属于 dual-runtime 清单；它不创建第二个研究引擎。

归档核心为 `services/hot/src/archive.ts`，受控命令为 `scripts/archive.ts`；对应真实测试
`archive.integration.ts`、`managed-archive.integration.ts`。Native CLI 经 HotManager 管理
私有归档、恢复目标和未知结果日志。hot_joint_archive.py 追加选定会话快照的签名联合恢复，
不恢复 Native 执行历史。新 inventory 直接哈希 PostgreSQL JSONB 文本，旧未标记编码要求
从原库重备份；研究 ZIP 的 payload（含 metadata）及实际 ZIP 各受 64 MiB 上限约束。
Hot 持久采集位于 `services/hot/src/collection.ts`，共享源目录为
`app/research_web/datahub/hot_public_sources.json`。migration 5 的原文/inbox/水位提交、
分批解析、限定来源调度、重领与取消由 `collection.integration.ts` 验证；
`scripts/collection-proof.ts` 对四个官方来源做真实双轮后台验证。
来源控制在 `src/source-control.ts`、migration 6、`rwb hot source-configure`；配置版本、
不可变审计、签名权限、重复请求、取消窗口与暂停 inbox 恢复由 source-control/source-cancel
及真实 service integration 测试负责。
模型累计预算核心为 `services/hot/src/model-budget.ts` 与 migration 7，测试为
`model-budget.integration.ts`。migration17 / `research-model.ts` 在相同 owner 事务中预留
研究预算和不可变 call/attempt 映射，已存结果终态/跨日复用。实际 DSH 流经
runtime/hot-model.mjs 的私有预算桥发送；内核测试和真实研究回执分别认证。
模型接入契约为 `services/hot/src/dsh-text.ts`，使用固定 DSH prepared-call API，
对应 `dsh-text.test.ts` / `dsh-receipt.test.ts`；正常 worker 经 native-model.ts 装配。
固定 Native 验收入口为 `scripts/model-live-proof.ts`，其 `src/native-dsh.mjs` 复用固定
DSH 服务与现有 Keychain bridge；版本来自共用 runtime 合同，新官方路由为
`llm-deepseek-api-key`，真实目录/零重试prepared-call见 `native-dsh.integration.ts`。
migration 9 做每日准入/跨日重验，credential-safety
测试覆盖转义后的秘密反射。Hot 处理与正式研究共用授权 scope，装配入口见后文。
事件与频道持久层为 `services/hot/src/events.ts` 与 migration 10，测试为
`events.integration.ts`。共享身份、不可变材料关联、直接后续图、第三频道配置、
合并/拆分/重新归属/标题/频道人工纠错、历史投影和人工判断继承在此验证。
模型评分须绑定已有回执；正向测试为 synthetic，不等于真实归组/规则质量验收。
普通 worker、签名产品 RPC、Web 页面和正式研究使用此持久层。
材料归组工作流为 `services/hot/src/processing.ts` / `dsh-grouping.ts` 与 migration 11；
采集 parse 事务注册不可变版本的处理项，可选模型能力接入同一 worker 的 `hot.process`。
`processing.integration.ts` / `dsh-grouping.test.ts` 验证冻结输入、跨语言候选、回执复用、
迟到/拒绝/预算终态和精确版本投影。`model-live-proof.ts group` 沿用固定验收 scope，
不增加新额度。Native bootstrap、领域规则和产品读取入口见以下各项。
领域规则为 `services/hot/src/channel-rules.ts`、migration 12 与 `channels.example.json`；
同一 worker heartbeat 有界轮询并持久保存评分依据、覆盖状态、独立运营主体和时点。
`channel-rules.test.ts` / `.integration.ts` 覆盖旧文/未知时间不增热、官方低热度重要政策、
来源变更/旧历史及人工评分优先。真实样本入口 `scripts/channel-live-proof.ts` 不调用模型；
公开频道配置、读写 RPC/CLI/UI 和研究交接均复用此领域合同。
内部签名事件/频道 RPC 在 `services/hot/src/projections.ts`、`channel-control.ts` 与
`service.ts`，migration 13 保存频道条件配置审计。`event-rpc.integration.ts` 通过真实
service/PG/scoped roles 验证历史投影、固定 cutoff 分页、字面筛选、继承评分、权限和UUID重放。
这些读取不调度或调用模型；Python CLI/Host/UI、关注与研究交接使用此签名接口。
Native CLI projections/control 在 `hot.py` / `hot_manager.py`，新命令为 channels/events/event/
channel-configure/event-correct；Python stdlib 测试验证参数映射、读写key分离、回执/输入门
与outcome_unknown UUID保留。event-rpc integration 中真实 Python dispatch/owned Node/PG
往返隔离凭据backend和解释器选择，并验证父进程消失后的独立回收；不是系统Keychain证明。
Web Host/UI、正式模型激活与研究快照交接由下列模块连接。
Hot Host为 `app/research_web/hot_service.py` / `hot_routes.py`，前端为 `ui/hot-workspace.mjs`；
main挂载惰性有界桥，core/app/shell/settings保留既有路由并新增工作区/设置。对应std测试
`test_hot_web.py`与`research_web_hot.test.mjs`验证关闭竞态、超时容量、明确动作、UUID重试、
安全文本/链接及跨页材料选择/cutoff。实际浏览器未配置旅程使用离线研究runtime fixture，
不等于真实事件/研究或干净安装。Hot图与API清单为同一文档事实源。

原生计划：`runtime/research.cordis.yml` / `runtime/guard.mjs` 仅装配固定 Todo 与精确授权；
`projection.py` 恢复同会话回合/写入版本，`ui/views.mjs` / `shell.mjs` 在研究空间呈现。
合同见 `architecture/research-web/02-research-runtime.md`、`04-api.md` 和 `research-web-ui.md`；
验证为 `test_protocol.py`、`test_event_recovery.py`、`test_runtime_launch.py`、
`research_web_guard.test.mjs`、`research_web_ui.test.mjs`。原生插件集成证据独立于模型 live、
浏览器、干净安装和 macOS CI；文件交付与 Todo 完成分别判定。

`app/research_web/portfolio_decisions/` 与 `ui/etf-paper.mjs` 提供工程ETF模拟。
权威合同为 `architecture/research-web/03-data-files.md`，API为 `04-api.md`；
测试为 `test_etf_decisions.py`、`test_etf_decision_routes.py`、`research_web_etf_paper.test.mjs`。
时间因果、资金事务、恢复、数据准入或执行假设变化须同步合同与测试，不认证真实收益。


`rwb-docker`、`docker/manage.py`、`docker/Dockerfile.control`、`docker/Dockerfile.dev`
及 `docker/buildkitd.toml` 是 Mac mini 管理平面与开发基座，权威说明为
`docs/research-web-docker.md`，近处测试为 `tests/research_web/test_docker_manager.py`。
生命周期/配额/镜像/挂载变化须同步该手册；真实镜像、实例健康与开发重建另保留本次证据。

异根 Native 私有 pair 认证共享 `web_bootstrap.py` 的现有 bounded reader；OS 用户标准根
发现、调用内根/父/record FD 与真实 lease 复查由 Docker 和 Native manager 同路径消费。
`test_docker_runtime.py` 覆盖重复 start、restart 预拒绝、stop/start、正常 Native bridge、
安装 preflight 拒绝及 root/record/process/lease/scope/controller 变化；其他近处 catalog
以临时 locator 隔离真实用户记录。fixture 不证明物理 Docker 或安装后 Native 切换。

| 双运行时源码区域 | 职责 | 权威文档 | 主要测试 | 文档更新触发 |
| --- | --- | --- | --- | --- |
| `runtimes/research_web.json`、`app/research_web/runtime_contract.py` | Native/Docker 共用 Python、Node、CJPY、DSH、pnpm 事实 | `research-web-installation.md`、`architecture/research-web/01-system.md` | `test_runtime_contract.py`、`docker_runtime_contract.test.mjs` | 固定版本、闭包或镜像事实变化 |
| `research_workbench_entrypoint/runtime_mode.py`、`bootstrap.py`、`docker_runtime.py` | 无 `.venv` 的模式路由、安全切换、Compose 归属 | `research-web-installation.md`、`architecture/research-web/02-research-runtime.md` | `test_runtime_mode.py`、`test_docker_runtime.py` | mode schema、CLI、归属或错误码变化 |
| `research_workbench_entrypoint/docker_resources.py` | 精确资源预览/清理、卷归档恢复、测试任务收尾 | `research-web-installation.md`、`architecture/research-web/02-research-runtime.md` | `test_docker_resources.py`；Mac Docker Desktop 真实资源验证 | 命名、保留、删除授权、引用或备份合同变化 |
| `app/research_web/process_spec.py`、`runtime_state.py`、`staged_runtime.py`、`launch_runtime.py`、`service_manager.py` | 共用进程规范，分离认证状态和镜像内已验证 DSH 资产 | `architecture/research-web/01-system.md`、`02-research-runtime.md` | `test_service_manager.py`、`test_runtime_launch.py`、`test_staged_runtime.py` | 生命周期、挂载或 DSH 资产合同变化 |
| `app/research_web/credential_backend.py`、连接/MCP/Automation 调用点 | Native 系统 keyring 与 Docker 私有文件凭据后端的明确选择 | `architecture/research-web/03-data-files.md`、`05-security-validation.md` | `test_credential_backend.py`、相关连接/MCP/Automation 测试 | 凭据存储、ACL 或跨模式边界变化 |
| `Dockerfile`、`compose.yaml`、`.dockerignore`、`docker/` | 非 root 单容器镜像、DSH/Web 监督、认证健康检查 | `research-web-installation.md`、`architecture/research-web/01-system.md` | `test_docker_packaging.py`、`test_container_supervisor.py`、`docker_runtime_contract.test.mjs` | 基础镜像、构建、挂载、端口或健康变化 |

以下原有表继续映射产品模块；上表只添加部署与运行边界，不创建第二套 Web/DSH 引擎。

端点基础 helper 为 `research_workbench_entrypoint/runtime_endpoints.py`，成对内部 origin
事务为 `app/research_web/control_origin.py`；对应 `test_runtime_endpoints.py` 与
`test_control_origin.py`。前者保存私有端点 CAS 快照并生成回环候选，后者保留控制 token、只重绑
既有 URL；二者由公开启动器消费，只有真实健康后发布端点。`EndpointStore.restore` 用本次发布
快照 CAS 恢复旧端口并生成新 revision，避免恢复旧 CAS 代际。复用 `runtime_mode.py` 的私有读写/锁，修改该边界须保留
`test_runtime_mode.py`、`test_runtime_auth.py`、`test_datahub.py`、`test_mcp_authorization.py`
负面测试；接口合同见运行时与安全模块文档。

Docker fresh-root 事务只在 `docker_runtime.py` 与 `setup_web.py` 内借外层真实 lease 保留父/根 FD 和调用内观察。`test_setup_web.py` 覆盖 owned-classification fixture 的真实 Native 子进程桥、真实临时监听身份、no-start 无产品根、后续真实 mkdir、晚期发布/恢复拒绝与 controller/lease 替换；既有 container/bind-race 测试明确使用已存在的受管数据根。Native/auth、通用 guard、依赖与验证策略不变。

生命周期集成由 service_manager、bootstrap、docker_runtime、setup_web、web_bootstrap
共同覆盖；`lifecycle_lock.py` 改用 stdlib logging，`assert_held` 验证本进程实际持有的锁对象，
用于安装候选内部调用而不增加 skip-lock 开关。`docker/supervisor.py` 的 prepare-only 入口
只用原 creator 补齐缺失控制文件；controller 通过无发布端口/无凭据挂载的固定镜像临时 guest
执行，精确核对一次性归属并确认清理。新增用例在原有 service_manager/runtime_endpoints/
runtime_mode/docker_runtime/setup_web/cli_lazy/web_bootstrap/container_supervisor 测试模块内。

Docker bind 根与私有叶布局由 Dockerfile/Compose 配置、entrypoint 父目录检查、supervisor
严格创建与 healthcheck 只读消费共同维护；测试闭包为 `test_container_supervisor.py`、
`test_credential_backend.py`、`test_runtime_launch.py`、`test_docker_packaging.py` 与
`docker_runtime_contract.test.mjs`。不得通过放宽 owner、mode 或 no-follow 来适配 bind 映射。
固定凭据与产品日志 bind 缺失叶的两阶段首建在supervisor内实现；其确定性测试模拟root→当前UID/GID并覆盖
foreign owner/group、mode/inode变化、alias/替换与自定义路径不豁免，原validator不修改。
Docker `/state` 为私有 tmpfs，状态叶不采用 bind 映射例外或写初始化；宿主 state/logs 在受管
生命周期私有创建后单独绑定。controller 测试覆盖必需 tmpfs、实际 RW、严格选项语义及
旧 host runtime 原样保留；CI 直接 Compose fixture 同步准备 logs，平台门范围不扩展。
同一 Engine HostConfig.Tmpfs 投影由正常与临时 control-preparer inspect 共用；后者仍只挂载
唯一产品 data bind 与原四个私有 tmpfs，测试同时覆盖省略重复 Mounts、严格选项与未知替换不清理。

`test_docker_runtime.py` 还覆盖Compose创建后返回非零/超时的恢复：本次launch标签识别、
精确容器清理、未知实例保留、既有停止容器保护，以及离线repair失败后旧接受image重建。

| 源码区域 | 职责 | 权威文档 | 主要测试 | 文档更新触发 |
| --- | --- | --- | --- | --- |
| `app/research_web/main.py`、`service.py`、`client.py` | HTTP/SSE、会话和 DSH 投影；按运行模式注入凭据后端 | `architecture/research-web/01-system.md`、`02-research-runtime.md`、`04-api.md` | `tests/research_web/test_api.py`、`test_protocol.py` | 路由、状态、恢复或认证变化 |

| `model_credentials.py`、`runtime/model-credentials.mjs`、`launch_runtime.py` | Native Keychain 与显式 Docker 加密模型文件的私有桥接、owned overlay；Host record 保留原实现 | `architecture/research-web/05-security-validation.md`、`02-research-runtime.md`、`research-web-installation.md` | `test_model_credentials.py`、`test_runtime_launch.py`、`research_web_model_credentials.test.mjs`；真实 Keychain/固定 DSH 仅显式 opt-in 合成验收，真实模型另验 | 后端、命名空间、凭据回退、记录委托或受管解释器变化 |
| `rwb`、`rwb.cmd`、`research_workbench_entrypoint/web_*.py`、`app/research_web/service_manager.py`、`service_diagnostics.py`、`lifecycle_lock.py` | 环境后备诊断、服务事实、排他锁、启动恢复与 Web ready | `research-web-installation.md`、`architecture/research-web/01-system.md`、`02-research-runtime.md`、`05-security-validation.md` | `test_web_contract.py`、`test_web_bootstrap.py`、`test_service_manager.py`、`test_cli_lazy.py` | 公开 CLI、PID/端口归属、健康、错误码、恢复或浏览器时机变化 |
| `app/research_web/ui/`、`app/research_web/asset_workspace.py`、`app/research_web/asset_routes.py` | 当前产品原生 UI 与 Asset Workbench backend | `research-web-ui.md`、`research-web-appearance.md` | 验证策略 focused closure：`ui/asset-workspace.mjs` → `tests/javascript/research_web_workbench.test.mjs`；`asset_workspace.py` / `asset_routes.py` → `tests/javascript/research_web_workbench.test.mjs` + `tests/research_web/test_asset_workspace.py`，并累积架构与 Project Constraints 检查；其他 UI 运行相关测试和 E2E | 导航、DOM、可访问性、交互或 Asset Workbench API 合同变化 |
| `app/research_web/datahub/` | 目录、Provider、Broker、快照 | `research-web-datahub.md`、`architecture/research-web/03-data-files.md` | `providers_akshare.py` → `tests/research_web/test_datahub_catalog.py` + `tests/research_web/test_datahub.py`；其他已登记 DataHub 测试 | 能力、来源、字段、路由或快照合同变化 |
| `app/research_web/integrations/` | 五阶段集成状态和探测编排 | `architecture/research-web/09-integration-coordinator.md` | `tests/research_web/test_integration*.py` | 状态、归因、授权或探测变化 |
| `app/research_web/frameworks/`、`ui/frameworks*` | Gold／Dollar 专用框架 | `architecture/research-web/08-research-frameworks.md` | `test_frameworks*.py`、`research_web_frameworks*.test.mjs` | 方法版本、快照、评分、renderer 或会话绑定变化 |
| `app/research_web/capabilities/`、`skills/` | Skill、Method、Tool、Workflow | `research-web-capabilities.md`、`architecture/research-web/07-capabilities.md` | `test_capabilities*.py`、能力 UI 测试 | 目录、包版本、资源、权限或发现变化 |
| `mcp_registry/`、`mcp_runtime/` | MCP 目录、安装、Host 和授权 | `research-web-capabilities.md`、Research Web 架构模块文档 | `test_mcp_*.py`、marketplace 测试 | Registry、安装、OAuth、策略或调用边界变化 |
| `automation/` | 定时任务、Run 和投递 | Research Web 架构模块文档 | `test_automation*.py`、计划 UI 测试 | 调度、重叠、恢复、投递或秘密边界变化 |
| `report_workflows/` | 报告模板、底稿、运行和交付 | `architecture/research-web/03-data-files.md`、`04-api.md` | `test_report_workflow*.py` | 模板、资源、运行、Excel 或交付变化 |
| `documentation.py`、`build_research_web_api_atlas.mjs`、文档检查脚本 | 安全只读文档入口和离线门禁 | `research-web-documentation.md`、`architecture/research-web/06-documentation-contract.md` | 文档治理、架构和路由测试 | 文档 schema、索引、图文或检查策略变化 |

`architecture/research-web/architecture-map.json` 是 Research Web 架构 source/document/test/diagram inventory 的机器真源；`.agents/verification-policy.json` 是 changed-file → impact → validation route 的唯一机器真源。图册首页与 API Atlas 同时从该清单生成；`--check` 只读检查集合和完整内容，不写工作区。`reading.modules` 复用 `groups`，只为研究框架与集成协调器补充集中阅读定位。两者互补且不互相推导：新增 Research Web 源文件仍须进入架构清单，而本表的测试闭包说明不能替代 verification policy。

Docker CI 由 Linux 真机在指定提交完成本机验收后，通过 `.github/workflows/research-web-docker.yml` 的 `workflow_dispatch` 和必填 `expected_sha` 发起；Mac PR/push 不自动触发，checkout 与 dispatch SHA 不一致时失败关闭。本机 Docker 构建、Native/macOS 安装门及真实 Windows 回执必须分别记录，源码测试不替代平台生命周期。仅 docs 变化按 changed set 的规划器结果验收，不能因旧任务已验收而虚写回执。

Docker 启动/安装修复的目标闭包还覆盖 `test_setup_web.py` 的候选失败与摘要恢复、
`test_cli_lazy.py` 的 Native `status --json` 安全投影。`test_docker_runtime.py` 检查延迟健康、
失败回滚归属、不可变镜像选择及 Doctor 的 `dsh` 公共字段；`test_runtime_contract.py` 成对检查
无关祖先目录活动和合同父目录瞬时 alias。API 与本机集成测试使用每例独立的内存 keyring，
不读取宿主凭据；生产凭据错误仍失败关闭。

本地集成回归另覆盖 `test_web_bootstrap.py` 的工作树环境归属、`test_runtime_mode.py` 的
坏 Native 环境与 PID 重用拒绝，以及 `test_container_supervisor.py` 的完整页面探测总时限。
容器 supervisor 的 Web 预算回归在原测试模块使用真实 loopback HTTP/认证和确定性耗时钟，
覆盖三项 GET 完整就绪、剩余期限裁剪、各页面错误与精确子进程清理；不替代镜像真机验收。
Docker 控制测试使用临时端口，真实端口冲突断言继续执行，不要求停止开发者正在运行的服务。

上述 DataHub 专项映射仅登记策略中明确允许的路径。未登记 DataHub 路径继续 fallback / fail closed，不能仅凭目录位置推断为低风险。`asset_workspace.py` / `asset_routes.py` → `research_web_workbench.test.mjs` + `test_asset_workspace.py` 只说明验证策略的 focused closure，不表示本次修改了 `architecture-map.json` 或从架构 inventory 推导了验收路由。

## 兼容平台

下列代码仍受维护，但不是当前 Research Web 的默认依赖：

| 源码区域 | 权威参考 | 更新触发 |
| --- | --- | --- |
| `app/api/`、`app/cli/commands/`、`app/web/` | `docs/modules/app_*.md`、`REFERENCE.md` | 兼容路由、命令或旧 UI 合同变化 |
| `core/`、`services/` | `docs/modules/core_*.md`、`docs/modules/services.md` | 领域契约、服务边界或模型网关变化 |
| `connectors/`、`data_layer/`、`ingestion/`、`cron_jobs/` | `DATA_SOURCES.md`、对应 `docs/modules/` | Connector 生命周期、来源或持久化变化 |
| `storage/`、`data_layer/repositories/` | `DATA_STORAGE.md`、仓储模块文档 | schema、迁移、Repository 或事务变化 |
| `knowledge_layer/`、`reasoning/`、`cognitive_agents/` | 对应 `docs/modules/` | 提取、证据、推理或旧 Agent 合同变化 |
| `signal_lab/`、`timing_engine/`、`memory_learning/`、`reporting/` | 对应 `docs/modules/` | 计算、回测、记忆或报告投影变化 |
| `src-tauri/`、`desktop/`、`scripts/desktop/` | `desktop_packaging.md` | 任何桌面运行、安装、更新或平台行为变化 |

兼容模块文档不应把自身描述成 Research Web 现役入口。文件增删或公开符号变化时更新生成索引；纯内部行为变化不需要制造索引 diff。

## 规则与交付

- `AGENTS.md`：共享工程规则真身；`CLAUDE.md` 只保留 Claude 专属差异。
- `docs/AGENT_WORKFLOW.md`：选择本地快环、worktree 或后台／远程执行。
- `.agents/project-constraints.json`：架构、平台和文档治理门禁配置。
- `.agents/verification-policy.json`：改动路径到 Component × Risk(L0-L4) × Platform、local/CI/real-machine lane 和 merge/release gate 的唯一机器真源。
- `scripts/plan_verification.mjs`：受管共享内核的只读薄入口，保留 changed-files 模式；显式 `--base --task-context` 输出 Git 绑定 plan v4，保留完整 changed set 和总门，按实际宿主落实 RWB 功能开发/macOS 与平台适配职责，不执行计划中的命令。
- `scripts/validate_verification_receipt.mjs`：受管共享内核的只读薄入口，receipt v3 分别推导 `hostAcceptance`、完整 `platformHandoffs` 与 `aggregateAcceptance`，同时保留总 `mergeReady`/`releaseReady`。CI 的实际 runner/checkout 和真机平台独立核对，不能用单宿主证据证明所有原生平台；继续只读兼容历史 plan v2/receipt v1、plan v3/receipt v2。
- `scripts/summarize_verification_delivery.mjs`：只读复核 plan v4 / receipt v3 后输出任务/平台验收及交付 metadata。候选必须一致，未知 metadata 拒绝；metadata 不能改写机械结果，PR/合并/实例及图形身份只是记录，不由摘要认证实际交付。
- `tests/javascript/verification_policy.test.mjs`、`verification_receipt.test.mjs`、`verification_platform_task_entry.test.mjs`：规划、升级、平台、状态、安全与证据合同；新薄入口 fixture 只证明参数/职责路由，受管内核集成和真实平台证据分别验收。
- `scripts/git_safety.mjs`、`tests/javascript/git_safety.test.mjs`：RWB macOS 受管 Git 入口、共用目录锁、仓库本地维护配置、可恢复备份与清理保留合同；临时仓库恢复测试不代表其他宿主启用。操作和限制见 `docs/AGENT_WORKFLOW.md`，不修改共享框架安装副本或产品运行时。
- `tests/javascript/verification_delivery_summary.test.mjs`：正式受管 validator 的交付摘要合同，使用临时 Git 与明确 synthetic 证据；覆盖候选、未知 metadata、路径及旧/未绑定回执拒绝，不证明原生或远端验收。
- `tests/javascript/repository_cross_platform_contract.test.mjs`：Git 换行、vendor 字节稳定和本机状态忽略合同。
- `.agents/runtime/leon-engineering/manifest.json`：共享验收内核固定版本、source commit、协议和受管文件哈希；不拥有项目策略。
- `.agents/skills/incremental-validation/`：Codex/Claude 共用的项目增量验收流程；只引用策略和脚本，不复制路由表。
- `docs/actions-budget.md`：GitHub Actions 免费额度、冻结状态、平台路由与保留策略。
- `.ai/reports/`：每个实现任务的真实证据及 `architecture-review` 标记。
- 源码结构或导入发生变化时运行 `python scripts/generate_py_file_index.py --check`；需要更新时先生成再复核。
- `Research Web Tabbit Verify` 当前仅手动触发；Tabbit 契约变化或平台支持声明必须显式运行双平台工作流，自动 Project Constraints 继续检查其触发器契约。
- 普通 Research Web 改动由 Ubuntu `Research Web Checks` 承担；Bootstrap 和 Desktop Verify 必须依路径命中，不能由 docs-only 提交触发。Windows Verify 由 policy changed-set 条件选择，但只能从 Windows 真机以 exact SHA `workflow_dispatch`，不能由 Mac PR/push 自动触发。

## 最小验证

双运行时 Python 质量检查限定于当前 changed set。格式化先核对非导入 AST 与导入集合；
内部端口 TypedDict、已验证记录的类型说明和显式 `check=False` 不改变参数省略、拒绝或返回码合同。
Ruff/Black/isort 与 mypy 使用的实际版本、参数和同版本基线必须记录，历史 PASS 不替代当前诊断。

```bash
node scripts/plan_verification.mjs --project . --changed-file <path>
node scripts/plan_verification.mjs --project . --base <base-sha> --task-context <project-relative-json>
node scripts/validate_verification_receipt.mjs --project . --plan <plan-json> --receipt <receipt-json>
node scripts/summarize_verification_delivery.mjs --project . --plan <project-relative-plan-json> --receipt <project-relative-receipt-json> --delivery <project-relative-delivery-json>
node scripts/check_documentation_governance.mjs --project .
python scripts/generate_py_file_index.py --check
node scripts/check_research_architecture.mjs --project . --base <base>
python scripts/check_doc_sync.py --project . --base <base>
node .agents/project-constraints.mjs --project . --changed-file <path>
```

先对完整 changed set 重复传入 `--changed-file`，再按 `validationsByLevel` 从 L0 执行到 `requiredLevel`；多文件取最高风险并合并去重。局部失败或非预期行为必须带 signal 重新规划。receipt 保存摘要、组件、平台、local/CI/real-machine 实际状态、`mergeReady`、`releaseReady`、未覆盖风险和升级判断，并通过 validator 才能交接。选中 gate 未运行时记录 `NOT_RUN` 或 `MANUAL_REQUIRED`，绝不写成 `PASS`。Project Constraints 保持独立的架构/平台/文档门，不复制策略内容。

平台任务由 Git 绑定模式自动发现完整变更；task 固定候选/base、目标与本宿主范围，并只能补选已登记的 `supplementalGateIds`。本宿主 PASS 不提升其他平台状态，也不推导总体验收 READY；说明源码、图源/生成物、候选、CI 实际 checkout 与报告所属提交分开记录。受管内核只由正式 source→preview/apply/verify 更新，不手工维护副本或 manifest。

已知组件可以在策略中映射不同等级的候选验证：低等级只选择局部项，耦合或 signal 升级后才纳入依赖/smoke/full 项。未登记测试仍按 `unknown_path` 升级 L4/`full-delivery`，不得仅凭位于 `tests/` 目录推断低风险。

Docker staging 的包发布载荷与过滤合同归 docker/stage_dsh.py、test_staged_runtime.py；改目录筛选须同时验证真实 Node 导入及容器 DSH 健康，不能仅靠镜像构建或资产哈希。

Hot 正常 Native 模型装配：services/hot/src/native-model.ts 由 service.ts owner 建立后加载，读取已有预算和当日定价并复用 native-dsh.mjs。默认停用、缺凭据/权限、跨日 guard 及跨价格缓存兼容分别在 native-model.test.ts、dsh-cache-compat.test.ts 与 model-budget.integration.ts 验证；实际 readiness/cache 脚本为 native-model-readiness-proof.ts。

研究共享预算私有接口为 `services/hot/src/research-model-rpc.ts`，service注册五项签名控制操作；
DSH流消费者为 `app/research_web/runtime/hot-model.mjs` / `hot-model-stream.mjs`，由launch_runtime
overlay装配；private hot-model HTTP路由经HotWebService/HotManager转入签名RPC。完整请求
冻结/预算、一次prepared发送、回执先存后输出和取消反例见research_web_hot_model_stream.test.mjs，
签名大帧/归属见test_hot_model_bridge.py；真实SDK离线SSE见native-research-stream.integration.mjs。
`model-budget.ts` 的事务内dispatch helper与run/价目校验共享owner fence。标准流usage由服务计算
费用并保存完整回放；transport只为回执/缓存开放有界大帧。测试为research-model-rpc/transport
单元及research-evidence真实PG/RPC。正式研究执行复用hot_handoff与已有DSH send。

Hot 模型管理由 hot_model_controls.py / scripts/model-control.ts 连接 model-control.ts；0014-model-controls.sql 添加不可变审计和状态保护。model-control.integration.ts 覆盖普通角色拒绝、活动归属拒绝迁移、迟到回执和真实三条 CLI；test_hot_model_controls.py 覆盖 pre-key、UUID、记录失败与冷库恢复。

Hot 用户定价：hot_pricing.py 经 check-pricing.ts/ pricing.ts 校验并保存私有日期记录；native-model.ts 在 run/reserve/dispatch 验证日期与指纹。pricing.test.ts/test_hot_pricing.py 覆盖新模拟日期、变化阻断、私有文件、真实CLI及fsync故障。

browser-dataset-proof.ts 是有界真实事件读取验收准备/恢复脚本：固定原授权schema/ledger、验证probe与identity、临时暂停来源并新建隔离控制角色；不调用模型，恢复时保留原quota。Web浏览器读取截图和失败/独立清理证据在任务报告。

Hot简报冻结核心为 `services/hot/src/briefs.ts`，验收为 `briefs.test.ts` 和
`briefs.integration.ts`；同一只读事务冻结全部关联版本、频道配置、原判断与覆盖依据，
校验规范JSON哈希并导出安全Markdown。该内核只负责冻结；持久记录、公开入口、
DOCX、原文副本和调度映射由下列适配负责。合同见 `services/hot/README.md` 简报小节。

持久简报为 `services/hot/src/brief-control.ts` / migration15，service签名接口brief.create/get/list；controller条件版本发布与UUID重放，读取复验冻结哈希。`event-rpc.integration.ts`真实Node/PG验证旧版保持、重启重放、权限与不可变性。公开Host/UI/CLI、DOCX及调度研究映射复用固定版本。

Hot简报Host为hot_routes/hot_service与HotManager，网页core/hot-workspace新增briefs视图和详情显式生成；brief.export按32KiB UTF8分块，Host固定版本并校验完整哈希。相关test_hot_manager/test_hot_web、research_web_hot与event-rpc integration覆盖只读权限、未知UUID、晚到预览和真实HTTP→Node/PG。浏览器/MD-DOCX真实验收另存任务报告。

早期浏览器简报验收使用原hot_acceptance_model schema15，保存真实AI/宏观两份version1简报并从浏览器下载；browser-dataset-proof.ts使用独立proofId写一次基线，恢复失败也独立禁用已绑定临时角色，失败/权限清理状态分开记录。当前schema20，真实Keychain/DSH报告及联合恢复的后续证据不由该旧证明替代。

Hot token限额修订为migration18/model-control.ts `amend-tokens`及Native
`model-amend-tokens`，仅停机migration-owner增加已有scope的两个token列并保留原费用审计。
冻结Hot快照的脚本准入在Snapshots.admit_hot_script与ResearchService.native_admission；
既有capability准入后验证本会话Hot归属和所有原件哈希，仅返回该dataset只读目录。
初期研究曾因预留上限无报告；后续已生成并核验真实报告，执行最终因预算终止。
hot_results分别显示执行failed与交付completed；读资料的Seatbelt验收不等于报告完成。

Hot研究结果读取/原回合核对为hot_results.py与hot_routes，测试test_hot_results/test_delivery及research_web_hot；Delivery.refresh新增可选不可变key，旧调用默认保持。结果按Delivery原合同完整流式SHA核验，100文件/每文件16MiB，超限明确不可核验，不以展示截断写入failed。
